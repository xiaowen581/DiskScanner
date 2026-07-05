#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiskScanner Web GUI (web_ui.py) 单元测试
覆盖: HTTP API 路由、扫描、导出、浏览、状态查询
运行: python3 -m unittest test_gui_api.py -v
"""

import os
import sys
import json
import csv
import io
import tempfile
import shutil
import threading
import time
import unittest
from http.client import HTTPConnection
from urllib.parse import urlencode

# 指向父目录以导入被测模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disk_scanner import Scanner, ScanResult, FileNode, DirNode

# 导入 gui 模块
import web_ui as gui_module
from web_ui import APIHandler, AppState, STATE

# 检测端口可用性
def find_free_port():
    import socket
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class TestGUIAPIServer(unittest.TestCase):
    """通过真实 HTTP 请求测试 Web API"""

    @classmethod
    def setUpClass(cls):
        """启动 HTTP 服务器和创建临时目录"""
        cls.tmpdir = tempfile.mkdtemp(prefix="gui_api_test_")
        # 创建测试文件
        for i in range(10):
            with open(os.path.join(cls.tmpdir, f"file_{i}.txt"), 'wb') as f:
                f.write(b'\x00' * (100 * (i + 1)))
        sub = os.path.join(cls.tmpdir, "subdir")
        os.makedirs(sub)
        for i in range(3):
            with open(os.path.join(sub, f"sub_{i}.py"), 'wb') as f:
                f.write(b'\x00' * 50)

        cls.port = find_free_port()
        from http.server import HTTPServer
        cls.server = HTTPServer(('127.0.0.1', cls.port), APIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)  # 等待服务器启动

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        """每个测试前重置状态"""
        STATE.result = None
        STATE.scan_path = ""
        STATE.scanning = False

    def _get(self, path):
        conn = HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('GET', path)
        resp = conn.getresponse()
        body = resp.read().decode('utf-8')
        try:
            data = json.loads(body)
        except Exception:
            data = body
        conn.close()
        return resp.status, data

    def _post(self, path, data=None):
        body = json.dumps(data or {}).encode('utf-8')
        conn = HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('POST', path, body=body,
                     headers={'Content-Type': 'application/json'})
        resp = conn.getresponse()
        rbody = resp.read().decode('utf-8')
        try:
            rdata = json.loads(rbody)
        except Exception:
            rdata = rbody
        conn.close()
        return resp.status, rdata

    # ── 状态 API ──

    def test_status_initial(self):
        status, data = self._get('/api/status')
        self.assertEqual(status, 200)
        self.assertFalse(data['scanning'])
        self.assertFalse(data['has_result'])

    # ── 扫描 API ──

    def test_scan_valid_path(self):
        status, data = self._post('/api/scan', {'path': self.tmpdir})
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'started')

        # 等待扫描完成
        for _ in range(20):
            time.sleep(0.3)
            _, sdata = self._get('/api/status')
            if not sdata['scanning'] and sdata['has_result']:
                break

        self.assertFalse(STATE.scanning)
        self.assertIsNotNone(STATE.result)
        self.assertEqual(STATE.result.total_files, 13)  # 10 + 3

    def test_scan_empty_path(self):
        status, data = self._post('/api/scan', {'path': ''})
        self.assertEqual(status, 400)
        self.assertIn('error', data)

    def test_scan_nonexistent_path(self):
        status, data = self._post('/api/scan', {'path': '/nonexistent/path/xyz'})
        self.assertEqual(status, 404)

    def test_scan_file_path(self):
        filepath = os.path.join(self.tmpdir, "file_0.txt")
        status, data = self._post('/api/scan', {'path': filepath})
        self.assertEqual(status, 400)

    # ── 结果 API ──

    def test_result_no_scan(self):
        status, data = self._get('/api/result')
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'no_result')

    def test_result_after_scan(self):
        # 先扫描
        self._post('/api/scan', {'path': self.tmpdir})
        for _ in range(20):
            time.sleep(0.3)
            if STATE.result:
                break

        status, data = self._get('/api/result?view=files')
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'ready')
        self.assertIn('summary', data)
        self.assertIn('items', data)
        self.assertIn('pagination', data)
        self.assertGreater(len(data['items']), 0)

    def test_result_dirs_view(self):
        self._post('/api/scan', {'path': self.tmpdir})
        for _ in range(20):
            time.sleep(0.3)
            if STATE.result:
                break

        status, data = self._get('/api/result?view=dirs')
        self.assertEqual(status, 200)
        self.assertEqual(data['view'], 'dirs')
        for item in data['items']:
            self.assertEqual(item['type'], 'dir')

    def test_result_files_view(self):
        self._post('/api/scan', {'path': self.tmpdir})
        for _ in range(20):
            time.sleep(0.3)
            if STATE.result:
                break

        status, data = self._get('/api/result?view=files&sort=size&order=desc')
        self.assertEqual(status, 200)
        # 验证按大小降序排列
        sizes = [item['size'] for item in data['items']]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_result_pagination(self):
        self._post('/api/scan', {'path': self.tmpdir})
        for _ in range(20):
            time.sleep(0.3)
            if STATE.result:
                break

        status, data = self._get('/api/result?view=files&page=1&page_size=5')
        self.assertEqual(status, 200)
        self.assertLessEqual(len(data['items']), 5)
        self.assertIn('total_pages', data['pagination'])

    def test_result_top_n(self):
        self._post('/api/scan', {'path': self.tmpdir})
        for _ in range(20):
            time.sleep(0.3)
            if STATE.result:
                break

        status, data = self._get('/api/result?view=files&top=3')
        self.assertEqual(status, 200)
        self.assertLessEqual(len(data['items']), 3)

    # ── 浏览 API ──

    def test_browse_default(self):
        status, data = self._get('/api/browse')
        self.assertEqual(status, 200)
        self.assertIn('items', data)
        self.assertIn('current', data)

    def test_browse_path(self):
        status, data = self._get(f'/api/browse?path={self.tmpdir}')
        self.assertEqual(status, 200)
        self.assertEqual(data['current'], os.path.abspath(self.tmpdir))
        self.assertGreater(len(data['items']), 0)

    def test_browse_nonexistent(self):
        status, data = self._get('/api/browse?path=/nonexistent/path')
        self.assertEqual(status, 404)

    # ── 根目录 API ──

    def test_roots(self):
        status, data = self._get('/api/roots')
        self.assertEqual(status, 200)
        self.assertIn('roots', data)
        self.assertGreater(len(data['roots']), 0)

    # ── 导出 API ──

    def test_export_csv(self):
        # 先扫描
        self._post('/api/scan', {'path': self.tmpdir})
        for _ in range(20):
            time.sleep(0.3)
            if STATE.result:
                break

        conn = HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('GET', '/api/export?format=csv')
        resp = conn.getresponse()
        body = resp.read()
        conn.close()

        self.assertEqual(resp.status, 200)
        ct = resp.getheader('Content-Type')
        self.assertIn('csv', ct)

        text = body.decode('utf-8-sig')
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        # 表头 + 数据行
        self.assertGreater(len(rows), 1)
        self.assertTrue(len(rows[0][0]) > 0)

    def test_export_json(self):
        self._post('/api/scan', {'path': self.tmpdir})
        for _ in range(20):
            time.sleep(0.3)
            if STATE.result:
                break

        conn = HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('GET', '/api/export?format=json')
        resp = conn.getresponse()
        body = resp.read()
        conn.close()

        self.assertEqual(resp.status, 200)
        data = json.loads(body.decode('utf-8'))
        self.assertIn('summary', data)
        self.assertIn('files', data)
        self.assertIn('directories', data)

    def test_export_no_result(self):
        status, data = self._get('/api/export?format=csv')
        self.assertEqual(status, 400)
        self.assertIn('error', data)

    # ── 子节点 API ──

    def test_children(self):
        self._post('/api/scan', {'path': self.tmpdir})
        for _ in range(20):
            time.sleep(0.3)
            if STATE.result:
                break

        abs_tmp = os.path.abspath(self.tmpdir)
        status, data = self._get(f'/api/children?path={abs_tmp}')
        self.assertEqual(status, 200)
        self.assertIn('items', data)

    def test_children_no_result(self):
        status, data = self._get(f'/api/children?path={self.tmpdir}')
        self.assertEqual(status, 200)
        self.assertEqual(data['items'], [])

    def test_children_invalid_path(self):
        status, data = self._get('/api/children?path=/nonexistent')
        self.assertEqual(status, 200)
        self.assertEqual(data['items'], [])

    # ── 404 ──

    def test_404_get(self):
        status, data = self._get('/api/nonexistent')
        self.assertEqual(status, 404)

    def test_404_post(self):
        status, data = self._post('/api/nonexistent')
        self.assertEqual(status, 404)

    # ── 带过滤的扫描 ──

    def test_scan_with_min_size(self):
        self._post('/api/scan', {'path': self.tmpdir, 'min_size': '500'})
        for _ in range(20):
            time.sleep(0.3)
            if STATE.result:
                break

        self.assertIsNotNone(STATE.result)
        # 所有文件应 >= 500 bytes
        for f in STATE.result.all_files:
            self.assertGreaterEqual(f.size, 500)

    def test_scan_with_extensions(self):
        self._post('/api/scan', {'path': self.tmpdir, 'extensions': '.py'})
        for _ in range(20):
            time.sleep(0.3)
            if STATE.result:
                break

        self.assertIsNotNone(STATE.result)
        for f in STATE.result.all_files:
            self.assertEqual(f.extension, '.py')


class TestFmtTimeHelper(unittest.TestCase):
    """测试 gui._fmt_time 辅助函数"""

    def test_zero(self):
        self.assertEqual(gui_module._fmt_time(0), 'N/A')

    def test_none(self):
        self.assertEqual(gui_module._fmt_time(None), 'N/A')

    def test_valid(self):
        result = gui_module._fmt_time(1704067200.0)
        self.assertRegex(result, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}')


if __name__ == '__main__':
    unittest.main()
