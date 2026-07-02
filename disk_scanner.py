#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiskScanner — 磁盘空间分析工具 v1.0
递归扫描指定目录，统计文件/文件夹大小，支持排序与导出。
纯 Python 标准库实现，无需安装第三方依赖。
"""

import os
import sys
import argparse
import time
import csv
import json
import signal
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


# ─────────────────────────────────────────────
# 终端颜色 (ANSI)
# ─────────────────────────────────────────────

class C:
    """ANSI 颜色代码"""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    REVERSE = "\033[7m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    BOLD_CYAN  = "\033[1;36m"
    BOLD_GREEN = "\033[1;32m"
    BOLD_RED   = "\033[1;31m"
    BOLD_YELLOW = "\033[1;33m"
    BOLD_WHITE  = "\033[1;37m"

    @staticmethod
    def disable():
        for attr in dir(C):
            if not attr.startswith('_') and attr != 'disable' and isinstance(getattr(C, attr), str):
                setattr(C, attr, '')


# 如果不是 TTY，禁用颜色
if not sys.stdout.isatty():
    C.disable()


# ─────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────

@dataclass
class FileNode:
    name: str
    path: str
    size: int
    modified: float
    extension: str
    parent_path: str = ""


@dataclass
class DirNode:
    name: str
    path: str
    size: int = 0
    file_count: int = 0
    dir_count: int = 0
    children: list = field(default_factory=list)
    parent_path: str = ""
    modified: float = 0.0


@dataclass
class ScanResult:
    root: Optional[DirNode] = None
    total_size: int = 0
    total_files: int = 0
    total_dirs: int = 0
    scan_duration: float = 0.0
    all_files: List[FileNode] = field(default_factory=list)
    all_dirs: List[DirNode] = field(default_factory=list)
    skipped_count: int = 0


# ─────────────────────────────────────────────
# 格式化工具
# ─────────────────────────────────────────────

def format_size(size_bytes: int) -> str:
    """将字节数格式化为人类可读字符串"""
    if size_bytes < 0:
        return "0 B"
    units = [
        (1024 ** 4, "TB"),
        (1024 ** 3, "GB"),
        (1024 ** 2, "MB"),
        (1024,      "KB"),
        (1,         "B"),
    ]
    for threshold, unit in units:
        if size_bytes >= threshold:
            value = size_bytes / threshold
            if threshold == 1:
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
    return "0 B"


def format_time(timestamp: float) -> str:
    if timestamp == 0:
        return "N/A"
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "N/A"


def parse_size_filter(size_str: str) -> int:
    if not size_str:
        return 0
    size_str = size_str.strip().upper()
    multipliers = {"TB": 1024**4, "GB": 1024**3, "MB": 1024**2, "KB": 1024, "B": 1}
    for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if size_str.endswith(suffix):
            num_str = size_str[:-len(suffix)].strip()
            try:
                return int(float(num_str) * mult)
            except ValueError:
                return 0
    try:
        return int(size_str)
    except ValueError:
        return 0


def truncate(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len - 3] + "..."


def pad(s: str, width: int, align: str = "left") -> str:
    """固定宽度填充（考虑 ANSI 转义码不影响显示宽度）"""
    visible_len = len(s)
    # 去除 ANSI 计算可见长度
    import re
    clean = re.sub(r'\033\[[0-9;]*m', '', s)
    visible_len = len(clean)
    padding = max(0, width - visible_len)
    if align == "right":
        return " " * padding + s
    elif align == "center":
        left_pad = padding // 2
        right_pad = padding - left_pad
        return " " * left_pad + s + " " * right_pad
    else:
        return s + " " * padding


def get_terminal_width() -> int:
    try:
        return os.get_terminal_size().columns
    except Exception:
        return 120


def get_terminal_height() -> int:
    try:
        return os.get_terminal_size().lines
    except Exception:
        return 40


# ─────────────────────────────────────────────
# 扫描引擎
# ─────────────────────────────────────────────

class Scanner:
    def __init__(self, follow_symlinks: bool = False):
        self.follow_symlinks = follow_symlinks
        self.all_files: List[FileNode] = []
        self.all_dirs: List[DirNode] = []
        self.skipped_count = 0
        self._file_count = 0
        self._dir_count = 0
        self._current_path = ""

    @property
    def progress_info(self):
        return self._file_count, self._current_path

    def scan(self, root_path: str) -> ScanResult:
        start_time = time.time()
        self.all_files.clear()
        self.all_dirs.clear()
        self.skipped_count = 0
        self._file_count = 0
        self._dir_count = 0

        abs_path = os.path.abspath(root_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"路径不存在: {abs_path}")
        if not os.path.isdir(abs_path):
            raise ValueError(f"指定路径不是目录: {abs_path}")

        root_dir = self._scan_dir(abs_path, parent_path="")
        scan_duration = time.time() - start_time

        return ScanResult(
            root=root_dir,
            total_size=root_dir.size if root_dir else 0,
            total_files=self._file_count,
            total_dirs=self._dir_count,
            scan_duration=scan_duration,
            all_files=list(self.all_files),
            all_dirs=list(self.all_dirs),
            skipped_count=self.skipped_count,
        )

    def _scan_dir(self, dir_path: str, parent_path: str) -> DirNode:
        self._current_path = dir_path
        try:
            stat = os.stat(dir_path, follow_symlinks=self.follow_symlinks)
            modified = stat.st_mtime
        except (OSError, PermissionError):
            modified = 0.0

        dir_node = DirNode(
            name=os.path.basename(dir_path) or dir_path,
            path=dir_path,
            parent_path=parent_path,
            modified=modified,
        )
        self._dir_count += 1
        self.all_dirs.append(dir_node)

        try:
            entries = list(os.scandir(dir_path))
        except (PermissionError, OSError):
            self.skipped_count += 1
            return dir_node

        for entry in entries:
            try:
                if not self.follow_symlinks and entry.is_symlink():
                    continue

                if entry.is_dir(follow_symlinks=False):
                    child_dir = self._scan_dir(entry.path, parent_path=dir_path)
                    dir_node.size += child_dir.size
                    dir_node.dir_count += 1
                    dir_node.children.append(child_dir)

                elif entry.is_file(follow_symlinks=False):
                    try:
                        file_stat = entry.stat(follow_symlinks=False)
                        file_node = FileNode(
                            name=entry.name,
                            path=entry.path,
                            size=file_stat.st_size,
                            modified=file_stat.st_mtime,
                            extension=os.path.splitext(entry.name)[1].lower(),
                            parent_path=dir_path,
                        )
                    except (OSError, PermissionError):
                        self.skipped_count += 1
                        continue

                    dir_node.size += file_node.size
                    dir_node.file_count += 1
                    dir_node.children.append(file_node)
                    self.all_files.append(file_node)
                    self._file_count += 1

            except (PermissionError, OSError):
                self.skipped_count += 1

        return dir_node


# ─────────────────────────────────────────────
# 排序引擎
# ─────────────────────────────────────────────

SORT_MODES = {
    "size-desc": ("大小(降序)", lambda x: x.size, True),
    "size-asc":  ("大小(升序)", lambda x: x.size, False),
    "name":      ("名称",       lambda x: x.name.lower(), False),
    "modified":  ("修改时间",   lambda x: x.modified, True),
}
SORT_MODE_KEYS = list(SORT_MODES.keys())


def sort_nodes(nodes: list, mode: str = "size-desc") -> list:
    if mode not in SORT_MODES:
        mode = "size-desc"
    _, key_fn, reverse = SORT_MODES[mode]
    return sorted(nodes, key=key_fn, reverse=reverse)


# ─────────────────────────────────────────────
# 导出
# ─────────────────────────────────────────────

def export_csv(result: ScanResult, output_path: str):
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["类型", "名称", "路径", "大小(字节)", "大小(可读)", "修改时间"])
        for node in sort_nodes(result.all_dirs, "size-desc"):
            writer.writerow(["目录", node.name, node.path,
                             node.size, format_size(node.size), format_time(node.modified)])
        for node in sort_nodes(result.all_files, "size-desc"):
            writer.writerow(["文件", node.name, node.path,
                             node.size, format_size(node.size), format_time(node.modified)])
    print(f"{C.GREEN}已导出到: {output_path}{C.RESET}")


def export_json(result: ScanResult, output_path: str):
    def node_to_dict(n):
        base = {
            "name": n.name, "path": n.path,
            "size": n.size, "size_human": format_size(n.size),
            "modified": format_time(n.modified),
        }
        if isinstance(n, FileNode):
            base["type"] = "file"
            base["extension"] = n.extension
        else:
            base["type"] = "directory"
            base["file_count"] = n.file_count
            base["dir_count"] = n.dir_count
        return base

    data = {
        "summary": {
            "total_size": result.total_size,
            "total_size_human": format_size(result.total_size),
            "total_files": result.total_files,
            "total_dirs": result.total_dirs,
            "scan_duration_sec": round(result.scan_duration, 2),
        },
        "directories": [node_to_dict(d) for d in sort_nodes(result.all_dirs, "size-desc")],
        "files": [node_to_dict(f) for f in sort_nodes(result.all_files, "size-desc")],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"{C.GREEN}已导出到: {output_path}{C.RESET}")


# ─────────────────────────────────────────────
# 交互式 TUI
# ─────────────────────────────────────────────

def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def move_cursor(row, col):
    sys.stdout.write(f"\033[{row};{col}H")


def hide_cursor():
    sys.stdout.write("\033[25l")
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write("\033[25h")
    sys.stdout.flush()


def get_key() -> str:
    """读取单个按键"""
    try:
        import tty, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A': return 'up'
                    if ch3 == 'B': return 'down'
                    if ch3 == '5':
                        sys.stdin.read(1)
                        return 'pgup'
                    if ch3 == '6':
                        sys.stdin.read(1)
                        return 'pgdn'
                return 'esc'
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        return input().strip()


def draw_line(text: str, width: int, border_color: str = C.CYAN):
    """绘制一条带颜色的分隔线"""
    return f"{border_color}{'─' * width}{C.RESET}"


def draw_box_header(title: str, width: int, border_color: str = C.CYAN):
    top    = f"{border_color}╭{'─' * (width - 2)}╮{C.RESET}"
    title_line = f"{border_color}│{C.RESET} {C.BOLD}{title}{C.RESET}{' ' * max(0, width - len(title) - 4)}{border_color}│{C.RESET}"
    bottom = f"{border_color}╰{'─' * (width - 2)}╯{C.RESET}"
    return f"{top}\n{title_line}\n{bottom}"


def interactive_ui(result: ScanResult, scan_path: str):
    """交互式界面"""
    width = get_terminal_width()
    height = get_terminal_height()

    current_view = "dirs"      # "dirs" or "files"
    sort_mode_idx = 0
    sort_mode = SORT_MODE_KEYS[sort_mode_idx]
    selected_idx = 0
    page_offset = 0
    show_detail = False
    show_help = False

    def get_nodes():
        if current_view == "dirs":
            return sort_nodes(result.all_dirs, sort_mode)
        else:
            return sort_nodes(result.all_files, sort_mode)

    def get_visible():
        return max(10, height - 16)

    def render():
        nonlocal width, height
        width = get_terminal_width()
        height = get_terminal_height()
        nodes = get_nodes()
        visible = get_visible()
        total_size = max(result.total_size, 1)

        lines = []

        # 标题栏
        title = f"{C.BOLD_CYAN}  ◆ DiskScanner v1.0{C.RESET}"
        lines.append(title)

        # 摘要
        summary = (
            f"  {C.BOLD}路径:{C.RESET} {scan_path}    "
            f"{C.BOLD}总大小:{C.RESET} {C.BOLD_GREEN}{format_size(result.total_size)}{C.RESET}    "
            f"{C.BOLD}文件:{C.RESET} {result.total_files:,}    "
            f"{C.BOLD}目录:{C.RESET} {result.total_dirs:,}    "
            f"{C.BOLD}耗时:{C.RESET} {result.scan_duration:.2f}s"
        )
        if result.skipped_count > 0:
            summary += f"    {C.YELLOW}跳过:{result.skipped_count}{C.RESET}"
        lines.append(summary)
        lines.append(draw_line("", width))

        # 表头
        view_label = "目录" if current_view == "dirs" else "文件"
        sort_label = SORT_MODES[sort_mode][0]
        header_title = f" {C.BOLD}{view_label}大小排行{C.RESET}  (排序:{sort_label} | 共{len(nodes):,}条)"
        lines.append(header_title)

        # 列标题
        if current_view == "dirs":
            col_header = (
                f"  {C.BOLD_CYAN}"
                f"{pad('#', 6, 'right')}"
                f"  {pad('路径', 55)}"
                f"  {pad('大小', 14, 'right')}"
                f"  {pad('文件数', 8, 'right')}"
                f"  {pad('子目录', 8, 'right')}"
                f"  {pad('修改时间', 20)}"
                f"  {pad('占比', 8, 'right')}"
                f"{C.RESET}"
            )
        else:
            col_header = (
                f"  {C.BOLD_CYAN}"
                f"{pad('#', 6, 'right')}"
                f"  {pad('路径', 55)}"
                f"  {pad('大小', 14, 'right')}"
                f"  {pad('类型', 8)}"
                f"  {pad('修改时间', 20)}"
                f"  {pad('占比', 8, 'right')}"
                f"{C.RESET}"
            )
        lines.append(col_header)
        lines.append(draw_line("", width, C.DIM))

        # 数据行
        start = page_offset
        end = min(start + visible, len(nodes))
        for i in range(start, end):
            node = nodes[i]
            pct = node.size / total_size * 100
            is_selected = (i == selected_idx)

            if is_selected:
                prefix = f"  {C.REVERSE}"
                suffix = C.RESET
            else:
                prefix = "  "
                suffix = ""

            name_color = C.CYAN if isinstance(node, DirNode) else ""
            size_color = C.GREEN if not is_selected else ""
            dim_color = C.DIM if not is_selected else ""

            if current_view == "dirs":
                row = (
                    f"{prefix}"
                    f"{dim_color}{pad(str(i+1), 6, 'right')}{C.RESET if not is_selected else ''}"
                    f"  {name_color}{pad(truncate(node.path, 55), 55)}{C.RESET if not is_selected else ''}"
                    f"  {size_color}{pad(format_size(node.size), 14, 'right')}{C.RESET if not is_selected else ''}"
                    f"  {pad(str(node.file_count), 8, 'right')}"
                    f"  {pad(str(node.dir_count), 8, 'right')}"
                    f"  {dim_color}{pad(format_time(node.modified), 20)}{C.RESET if not is_selected else ''}"
                    f"  {pad(f'{pct:.1f}%', 8, 'right')}"
                    f"{suffix}"
                )
            else:
                row = (
                    f"{prefix}"
                    f"{dim_color}{pad(str(i+1), 6, 'right')}{C.RESET if not is_selected else ''}"
                    f"  {name_color}{pad(truncate(node.path, 55), 55)}{C.RESET if not is_selected else ''}"
                    f"  {size_color}{pad(format_size(node.size), 14, 'right')}{C.RESET if not is_selected else ''}"
                    f"  {pad(node.extension or '-', 8)}"
                    f"  {dim_color}{pad(format_time(node.modified), 20)}{C.RESET if not is_selected else ''}"
                    f"  {pad(f'{pct:.1f}%', 8, 'right')}"
                    f"{suffix}"
                )
            lines.append(row)

        # 空行填充
        while len(lines) < visible + 7:
            lines.append("")

        # 底部操作栏
        lines.append(draw_line("", width))
        if show_detail:
            # 详情面板
            node = nodes[selected_idx] if selected_idx < len(nodes) else None
            if node:
                lines.append(f"  {C.BOLD_YELLOW}━━━ 详情 ━━━{C.RESET}")
                lines.append(f"  {C.BOLD}路径:{C.RESET} {node.path}")
                lines.append(f"  {C.BOLD}大小:{C.RESET} {C.BOLD_GREEN}{format_size(node.size)}{C.RESET}")
                if isinstance(node, DirNode):
                    lines.append(f"  {C.BOLD}文件数:{C.RESET} {node.file_count:,}    {C.BOLD}子目录数:{C.RESET} {node.dir_count:,}")
                    del_cmd = f'rm -rf "{node.path}"'
                else:
                    lines.append(f"  {C.BOLD}类型:{C.RESET} {node.extension or '未知'}")
                    del_cmd = f'rm "{node.path}"'
                lines.append(f"  {C.BOLD}修改时间:{C.RESET} {format_time(node.modified)}")
                lines.append(f"  {C.BOLD_RED}删除命令:{C.RESET} {C.YELLOW}$ {del_cmd}{C.RESET}")
                lines.append(f"  {C.RED}⚠ 请谨慎操作，删除后不可恢复！{C.RESET}")
        elif show_help:
            lines.append(f"  {C.BOLD_GREEN}━━━ 帮助 ━━━{C.RESET}")
            lines.append(f"  {C.CYAN}↑/↓{C.RESET}       上下移动")
            lines.append(f"  {C.CYAN}PgUp/PgDn{C.RESET} 翻页")
            lines.append(f"  {C.CYAN}g / G{C.RESET}     跳转到顶部/底部")
            lines.append(f"  {C.CYAN}f{C.RESET}         切换 目录/文件 视图")
            lines.append(f"  {C.CYAN}s{C.RESET}         切换排序模式")
            lines.append(f"  {C.CYAN}d{C.RESET}         显示详情与删除命令")
            lines.append(f"  {C.CYAN}e{C.RESET}         导出结果到 CSV")
            lines.append(f"  {C.CYAN}h{C.RESET}         显示/隐藏帮助")
            lines.append(f"  {C.CYAN}q/Esc{C.RESET}    退出程序")
        else:
            lines.append(
                f"  {C.DIM}[↑↓]导航  [f]切换视图  [s]排序  "
                f"[d]详情/删除命令  [e]导出  [h]帮助  [q]退出{C.RESET}"
            )

        # 输出
        clear_screen()
        output = "\n".join(lines[:height])
        sys.stdout.write(output)
        sys.stdout.flush()

    # 主循环
    hide_cursor()
    try:
        render()
        while True:
            key = get_key()
            nodes = get_nodes()
            visible = get_visible()

            if key in ('q', 'esc', '\x03'):
                break
            elif key == 'up':
                show_detail = False
                if selected_idx > 0:
                    selected_idx -= 1
                    if selected_idx < page_offset:
                        page_offset = selected_idx
            elif key == 'down':
                show_detail = False
                if selected_idx < len(nodes) - 1:
                    selected_idx += 1
                    if selected_idx >= page_offset + visible:
                        page_offset = selected_idx - visible + 1
            elif key == 'pgup':
                show_detail = False
                selected_idx = max(0, selected_idx - visible)
                page_offset = max(0, page_offset - visible)
            elif key == 'pgdn':
                show_detail = False
                selected_idx = min(len(nodes) - 1, selected_idx + visible)
                page_offset = min(len(nodes) - 1, page_offset + visible)
            elif key == 'g':
                show_detail = False
                selected_idx = 0
                page_offset = 0
            elif key == 'G':
                show_detail = False
                selected_idx = max(0, len(nodes) - 1)
                page_offset = max(0, selected_idx - visible + 1)
            elif key == 'f':
                show_detail = False
                current_view = "files" if current_view == "dirs" else "dirs"
                selected_idx = 0
                page_offset = 0
            elif key == 's':
                show_detail = False
                sort_mode_idx = (sort_mode_idx + 1) % len(SORT_MODE_KEYS)
                sort_mode = SORT_MODE_KEYS[sort_mode_idx]
                selected_idx = 0
                page_offset = 0
            elif key == 'd':
                show_detail = not show_detail
                show_help = False
            elif key == 'h':
                show_help = not show_help
                show_detail = False
            elif key == 'e':
                export_path = os.path.join(os.getcwd(), f"disk_scan_{int(time.time())}.csv")
                export_csv(result, export_path)
                time.sleep(1.5)
            render()

    except KeyboardInterrupt:
        pass
    finally:
        show_cursor()
        clear_screen()
        print(f"{C.DIM}已退出 DiskScanner。{C.RESET}")


# ─────────────────────────────────────────────
# 非交互模式
# ─────────────────────────────────────────────

def non_interactive_output(result: ScanResult, scan_path: str, top_n: int = 0):
    width = get_terminal_width()
    total_size = max(result.total_size, 1)

    print(f"\n{C.BOLD_CYAN}◆ DiskScanner v1.0{C.RESET}")
    print(f"{C.BOLD}路径:{C.RESET} {scan_path}    "
          f"{C.BOLD}总大小:{C.RESET} {C.BOLD_GREEN}{format_size(result.total_size)}{C.RESET}    "
          f"{C.BOLD}文件:{C.RESET} {result.total_files:,}    "
          f"{C.BOLD}目录:{C.RESET} {result.total_dirs:,}    "
          f"{C.BOLD}耗时:{C.RESET} {result.scan_duration:.2f}s")
    if result.skipped_count > 0:
        print(f"{C.YELLOW}注意: 跳过 {result.skipped_count} 个无权限条目{C.RESET}")
    print(draw_line("", width))

    # 目录表
    dirs = sort_nodes(result.all_dirs, "size-desc")
    if top_n > 0:
        dirs = dirs[:top_n]

    if dirs:
        print(f"\n{C.BOLD}  目录大小排行 ({len(dirs)} 条):{C.RESET}")
        print(f"  {C.BOLD_CYAN}{pad('#', 6, 'right')}  {pad('路径', 55)}  {pad('大小', 14, 'right')}  {pad('文件数', 8, 'right')}  {pad('占比', 8, 'right')}{C.RESET}")
        print(draw_line("", width, C.DIM))
        for i, d in enumerate(dirs):
            pct = d.size / total_size * 100
            print(f"  {C.DIM}{pad(str(i+1), 6, 'right')}{C.RESET}"
                  f"  {C.CYAN}{pad(truncate(d.path, 55), 55)}{C.RESET}"
                  f"  {C.GREEN}{pad(format_size(d.size), 14, 'right')}{C.RESET}"
                  f"  {pad(str(d.file_count), 8, 'right')}"
                  f"  {pad(f'{pct:.1f}%', 8, 'right')}")

    # 文件表
    files = sort_nodes(result.all_files, "size-desc")
    if top_n > 0:
        files = files[:top_n]

    if files:
        print(f"\n{C.BOLD}  文件大小排行 ({len(files)} 条):{C.RESET}")
        print(f"  {C.BOLD_CYAN}{pad('#', 6, 'right')}  {pad('路径', 55)}  {pad('大小', 14, 'right')}  {pad('类型', 8)}  {pad('占比', 8, 'right')}{C.RESET}")
        print(draw_line("", width, C.DIM))
        for i, f in enumerate(files):
            pct = f.size / total_size * 100
            print(f"  {C.DIM}{pad(str(i+1), 6, 'right')}{C.RESET}"
                  f"  {pad(truncate(f.path, 55), 55)}"
                  f"  {C.GREEN}{pad(format_size(f.size), 14, 'right')}{C.RESET}"
                  f"  {C.MAGENTA}{pad(f.extension or '-', 8)}{C.RESET}"
                  f"  {pad(f'{pct:.1f}%', 8, 'right')}")

    print()


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="disk_scanner",
        description="DiskScanner — 磁盘空间分析工具 (纯 Python，无依赖)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python3 disk_scanner.py /home/user              # 交互式扫描\n"
            "  python3 disk_scanner.py . -n 20                 # Top 20\n"
            "  python3 disk_scanner.py /var --min-size 100MB   # 过滤大于100MB\n"
            "  python3 disk_scanner.py /home --ext .mp4,.mkv   # 仅视频文件\n"
            "  python3 disk_scanner.py /home --export report.csv\n"
            "  python3 disk_scanner.py /home --no-interactive  # 直接输出\n"
        ),
    )
    parser.add_argument("path", nargs="?", default=".", help="扫描目标目录 (默认: 当前目录)")
    parser.add_argument("-n", "--top", type=int, default=0, help="仅显示 Top N 条目 (0=全部)")
    parser.add_argument("--min-size", type=str, default="", help="最小文件大小过滤 (如: 100MB, 1GB)")
    parser.add_argument("--ext", type=str, default="", help="扩展名过滤 (逗号分隔, 如: .mp4,.mkv)")
    parser.add_argument("--sort", choices=["size", "name", "modified"], default="size", help="排序字段")
    parser.add_argument("--order", choices=["asc", "desc"], default="desc", help="排序方向")
    parser.add_argument("--export", type=str, default="", help="导出路径 (.csv 或 .json)")
    parser.add_argument("--no-interactive", action="store_true", help="非交互模式")
    parser.add_argument("--follow-symlinks", action="store_true", help="跟踪符号链接")
    return parser


def apply_filters(result: ScanResult, min_size: int, ext_filter: list) -> ScanResult:
    if min_size <= 0 and not ext_filter:
        return result
    filtered_files = result.all_files
    if min_size > 0:
        filtered_files = [f for f in filtered_files if f.size >= min_size]
    if ext_filter:
        filtered_files = [f for f in filtered_files if f.extension in ext_filter]
    filtered_dir_paths = set(f.parent_path for f in filtered_files)
    return ScanResult(
        root=result.root,
        total_size=sum(f.size for f in filtered_files),
        total_files=len(filtered_files),
        total_dirs=len(filtered_dir_paths),
        scan_duration=result.scan_duration,
        all_files=filtered_files,
        all_dirs=[d for d in result.all_dirs if d.path in filtered_dir_paths or d.path == result.root.path],
        skipped_count=result.skipped_count,
    )


def main():
    if hasattr(signal, 'SIGPIPE'):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    parser = build_parser()
    args = parser.parse_args()
    scan_path = os.path.abspath(args.path)

    print(f"{C.CYAN}正在扫描: {scan_path}{C.RESET}")

    scanner = Scanner(follow_symlinks=args.follow_symlinks)
    spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    spinner_idx = 0
    last_progress_time = time.time()

    # 使用简单动画显示扫描进度
    import threading
    stop_event = threading.Event()

    def progress_spinner():
        nonlocal spinner_idx
        while not stop_event.is_set():
            count, current = scanner.progress_info
            line = f"\r{C.CYAN}{spinner_chars[spinner_idx % len(spinner_chars)]}{C.RESET} 已扫描 {count:,} 个文件... {C.DIM}{truncate(current, 50)}{C.RESET}"
            sys.stdout.write(line)
            sys.stdout.flush()
            spinner_idx += 1
            time.sleep(0.1)

    spinner_thread = threading.Thread(target=progress_spinner, daemon=True)
    spinner_thread.start()

    try:
        result = scanner.scan(scan_path)
    except FileNotFoundError as e:
        stop_event.set()
        print(f"\r{C.BOLD_RED}错误:{C.RESET} {e}")
        sys.exit(1)
    except ValueError as e:
        stop_event.set()
        print(f"\r{C.BOLD_RED}错误:{C.RESET} {e}")
        sys.exit(1)

    stop_event.set()
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()

    print(f"{C.GREEN}扫描完成:{C.RESET} {result.total_files:,} 个文件, "
          f"{result.total_dirs:,} 个目录, 耗时 {result.scan_duration:.2f}s")
    if result.skipped_count > 0:
        print(f"{C.YELLOW}注意: 跳过 {result.skipped_count} 个无权限条目{C.RESET}")

    # 过滤
    min_size = parse_size_filter(args.min_size)
    ext_filter = []
    if args.ext:
        ext_filter = [e.strip().lower() if e.strip().startswith('.') else f'.{e.strip().lower()}'
                      for e in args.ext.split(',') if e.strip()]
    result = apply_filters(result, min_size, ext_filter)

    if (min_size > 0 or ext_filter) and result.total_files == 0:
        print(f"{C.YELLOW}过滤后没有匹配的文件。{C.RESET}")
        sys.exit(0)

    # 导出
    if args.export:
        export_path = os.path.abspath(args.export)
        if export_path.endswith('.json'):
            export_json(result, export_path)
        else:
            export_csv(result, export_path)

    # 显示
    if args.no_interactive or not sys.stdin.isatty():
        non_interactive_output(result, scan_path=scan_path, top_n=args.top)
    else:
        interactive_ui(result, scan_path=scan_path)


if __name__ == "__main__":
    main()
