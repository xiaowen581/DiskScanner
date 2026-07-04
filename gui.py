#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiskScanner Web GUI — 基于浏览器的磁盘空间分析界面
使用 Python 标准库，无需任何第三方依赖

启动方式: python3 gui.py [port]
默认端口: 8888
"""

import os
import sys
import json
import time
import csv
import io
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from disk_scanner import (
    Scanner, ScanResult, FileNode, DirNode,
    format_size, parse_size_filter, sort_nodes
)


class AppState:
    result: ScanResult = None
    scan_path: str = ""
    scanning: bool = False


STATE = AppState()


class APIHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode('utf-8'))
        except Exception:
            return {}

    # ── GET 路由 ──────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        if path == '/' or path == '/index.html':
            self._serve_html()
        elif path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
        elif path == '/api/status':
            self._api_status()
        elif path == '/api/result':
            self._api_result(qs)
        elif path == '/api/browse':
            self._api_browse(qs)
        elif path == '/api/roots':
            self._api_roots()
        elif path == '/api/export':
            self._api_export(qs)
        elif path == '/api/children':
            self._api_children(qs)
        else:
            self.send_error(404)

    # ── POST 路由 ─────────────────────────────────────────

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/scan':
            self._api_scan()
        else:
            self.send_error(404)

    # ── API 实现 ──────────────────────────────────────────

    def _serve_html(self):
        html_path = os.path.join(SCRIPT_DIR, 'index.html')
        try:
            with open(html_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_json({'error': 'index.html 文件未找到，请确保 index.html 与 gui.py 在同一目录'}, 404)

    def _api_status(self):
        self.send_json({
            'scanning': STATE.scanning,
            'has_result': STATE.result is not None,
            'scan_path': STATE.scan_path,
        })

    def _api_scan(self):
        if STATE.scanning:
            return self.send_json({'error': '扫描正在进行中，请等待完成'}, 409)

        body = self.read_body()
        scan_path = body.get('path', '').strip()
        if not scan_path:
            return self.send_json({'error': '请输入扫描路径'}, 400)

        abs_path = os.path.abspath(os.path.expanduser(scan_path))
        if not os.path.exists(abs_path):
            return self.send_json({'error': f'路径不存在: {abs_path}'}, 404)
        if not os.path.isdir(abs_path):
            return self.send_json({'error': f'路径不是目录: {abs_path}'}, 400)

        STATE.scanning = True
        STATE.scan_path = abs_path

        def do_scan():
            try:
                scanner = Scanner(follow_symlinks=body.get('follow_symlinks', False))
                result = scanner.scan(abs_path)

                # 应用过滤
                min_size = parse_size_filter(body.get('min_size', ''))
                ext_filter = []
                ext_str = body.get('extensions', '')
                if ext_str:
                    ext_filter = [
                        e.strip().lower() if e.strip().startswith('.') else f'.{e.strip().lower()}'
                        for e in ext_str.split(',') if e.strip()
                    ]

                if min_size > 0 or ext_filter:
                    filtered = result.all_files
                    if min_size > 0:
                        filtered = [f for f in filtered if f.size >= min_size]
                    if ext_filter:
                        filtered = [f for f in filtered if f.extension in ext_filter]
                    dir_paths = set(f.parent_path for f in filtered)
                    result.all_files = filtered
                    result.all_dirs = [
                        d for d in result.all_dirs
                        if d.path in dir_paths or d.path == result.root.path
                    ]
                    result.total_files = len(filtered)
                    result.total_size = sum(f.size for f in filtered)
                    result.total_dirs = len(dir_paths)

                STATE.result = result
            except Exception as e:
                STATE.result = None
                STATE.scan_path = f'错误: {e}'
            finally:
                STATE.scanning = False

        threading.Thread(target=do_scan, daemon=True).start()
        self.send_json({'status': 'started', 'path': abs_path})

    def _api_result(self, qs):
        if STATE.scanning:
            return self.send_json({'status': 'scanning'})
        if not STATE.result:
            return self.send_json({'status': 'no_result'})

        r = STATE.result
        view = qs.get('view', 'dirs')
        sort_key = qs.get('sort', 'size')
        order = qs.get('order', 'desc')
        top_n = int(qs.get('top', 0))
        page = int(qs.get('page', 1))
        page_size = int(qs.get('page_size', 100))

        sort_mode = f"{sort_key}-{'desc' if order == 'desc' else 'asc'}"
        if sort_mode not in ('size-desc', 'size-asc', 'name', 'modified'):
            sort_mode = 'size-desc'

        if view == 'files':
            nodes = sort_nodes(r.all_files, sort_mode)
        else:
            nodes = sort_nodes(r.all_dirs, sort_mode)

        total = len(nodes)
        if top_n > 0:
            nodes = nodes[:top_n]
            total = len(nodes)

        start = (page - 1) * page_size
        end = start + page_size
        page_nodes = nodes[start:end]
        total_size = max(r.total_size, 1)

        items = []
        for n in page_nodes:
            item = {
                'name': n.name,
                'path': n.path,
                'size': n.size,
                'size_human': format_size(n.size),
                'pct': round(n.size / total_size * 100, 1),
                'modified': _fmt_time(n.modified),
            }
            if isinstance(n, FileNode):
                item['type'] = 'file'
                item['extension'] = n.extension
            else:
                item['type'] = 'dir'
                item['file_count'] = n.file_count
                item['dir_count'] = n.dir_count
            items.append(item)

        self.send_json({
            'status': 'ready',
            'summary': {
                'total_size': r.total_size,
                'total_size_human': format_size(r.total_size),
                'total_files': r.total_files,
                'total_dirs': r.total_dirs,
                'scan_duration': round(r.scan_duration, 2),
                'skipped_count': r.skipped_count,
                'scan_path': STATE.scan_path,
            },
            'view': view,
            'items': items,
            'pagination': {
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size,
            }
        })

    def _api_browse(self, qs):
        path = qs.get('path', '')
        if not path:
            path = os.path.expanduser('~')
        path = os.path.abspath(os.path.expanduser(path))

        if not os.path.exists(path):
            return self.send_json({'error': '路径不存在'}, 404)
        if not os.path.isdir(path):
            path = os.path.dirname(path)

        items = []
        # 父目录
        parent = os.path.dirname(path)
        if parent != path:
            items.append({'name': '..', 'path': parent, 'is_dir': True, 'is_parent': True})

        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
            for entry in entries:
                if entry.name.startswith('.'):
                    continue
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    stat = entry.stat(follow_symlinks=False)
                    items.append({
                        'name': entry.name,
                        'path': entry.path,
                        'is_dir': is_dir,
                        'size': stat.st_size if not is_dir else 0,
                        'modified': _fmt_time(stat.st_mtime),
                    })
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass

        self.send_json({
            'current': path,
            'parent': parent if parent != path else None,
            'items': items[:500],
        })

    def _api_roots(self):
        roots = []
        if sys.platform == 'win32':
            for c in 'CDEFGH':
                p = f'{c}:\\'
                if os.path.exists(p):
                    roots.append({'path': p, 'name': f'{c}: 盘'})
        else:
            home = os.path.expanduser('~')
            roots = [
                {'path': home, 'name': '主目录 (~)'},
                {'path': '/', 'name': '根目录 (/)'},
                {'path': '/home', 'name': '/home'},
                {'path': '/tmp', 'name': '/tmp'},
            ]
            roots = [r for r in roots if os.path.exists(r['path'])]
        self.send_json({'roots': roots})

    def _api_export(self, qs):
        if not STATE.result:
            return self.send_json({'error': '没有扫描结果'}, 400)

        fmt = qs.get('format', 'csv')
        r = STATE.result

        if fmt == 'json':
            def to_dict(n):
                base = {
                    'name': n.name, 'path': n.path,
                    'size': n.size, 'size_human': format_size(n.size),
                    'modified': _fmt_time(n.modified),
                }
                if isinstance(n, FileNode):
                    base['type'] = 'file'
                    base['extension'] = n.extension
                else:
                    base['type'] = 'directory'
                    base['file_count'] = n.file_count
                    base['dir_count'] = n.dir_count
                return base

            data = {
                'summary': {
                    'total_size': r.total_size,
                    'total_size_human': format_size(r.total_size),
                    'total_files': r.total_files,
                    'total_dirs': r.total_dirs,
                },
                'directories': [to_dict(d) for d in sort_nodes(r.all_dirs, 'size-desc')],
                'files': [to_dict(f) for f in sort_nodes(r.all_files, 'size-desc')],
            }
            body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="disk_scan.json"')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(['类型', '名称', '路径', '大小(字节)', '大小(可读)', '修改时间'])
            for node in sort_nodes(r.all_dirs, 'size-desc'):
                writer.writerow(['目录', node.name, node.path,
                                 node.size, format_size(node.size), _fmt_time(node.modified)])
            for node in sort_nodes(r.all_files, 'size-desc'):
                writer.writerow(['文件', node.name, node.path,
                                 node.size, format_size(node.size), _fmt_time(node.modified)])
            body = buf.getvalue().encode('utf-8-sig')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="disk_scan.csv"')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)

    def _api_children(self, qs):
        """获取目录的直接子项（用于树形展开）"""
        path = qs.get('path', '')
        if not path or not os.path.isdir(path):
            return self.send_json({'items': []})

        if not STATE.result:
            return self.send_json({'items': []})

        # 在结果中查找该目录的子项
        children = []
        for d in STATE.result.all_dirs:
            if d.parent_path == path:
                children.append({
                    'name': d.name, 'path': d.path, 'type': 'dir',
                    'size': d.size, 'size_human': format_size(d.size),
                })
        for f in STATE.result.all_files:
            if f.parent_path == path:
                children.append({
                    'name': f.name, 'path': f.path, 'type': 'file',
                    'size': f.size, 'size_human': format_size(f.size),
                    'extension': f.extension,
                })

        children.sort(key=lambda x: x['size'], reverse=True)
        self.send_json({'items': children[:200]})


def _fmt_time(ts):
    if not ts or ts == 0:
        return 'N/A'
    try:
        from datetime import datetime
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return 'N/A'


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h'):
        print("Usage: python gui.py [port]")
        print("  port  端口号 (默认: 8888)")
        sys.exit(0)
    try:
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    except ValueError:
        print(f"Error: Invalid port number: {sys.argv[1]}")
        print("Usage: python gui.py [port]")
        sys.exit(1)
    server = HTTPServer(('127.0.0.1', port), APIHandler)
    url = f'http://127.0.0.1:{port}'

    print(f"\n  ◆ DiskScanner Web GUI")
    print(f"  服务已启动: {url}")
    print(f"  按 Ctrl+C 停止服务器\n")

    # 自动打开浏览器
    try:
        webbrowser.open(url)
    except Exception:
        print(f"  请手动打开浏览器访问: {url}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  服务器已停止。")
        server.server_close()


if __name__ == '__main__':
    main()
