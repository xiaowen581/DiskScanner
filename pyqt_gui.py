#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiskScanner — 主入口
pyqt_gui.py — DiskScanner PyQt5 主入口
提供 File Scanner 和 Docker Manager 两大功能标签页
纯 Python 标准库，无需任何第三方依赖

启动方式: python3 tkinter_gui.py
启动方式: python3 pyqt_gui.py
"""

import os
import sys
from tkinter import Tk, ttk
import types as _types

_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)

from ui.theme import C, setup_styles
from ui.scanner_frame import ScannerFrame
from ui.docker_frame import DockerFrame
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt5.QtCore import Qt

from ui.theme import C, QSS, make_font
from ui.scanner_frame import ScannerFrame
from ui.docker_frame import DockerFrame


import ui.theme as _theme
import ui._base as _base
import ui._base as _base














# Re-export fmt_time as _fmt_time for backward compatibility with tests
_fmt_time = _base.fmt_time


class DiskScannerApp:
    """主应用程序 — 包含 File 和 Docker 两大功能标签页"""
    """主应用程序 — 包含 File Scanner 和 Docker Manager 两大标签页"""

    def __init__(self):
        self.root = Tk()
        self.root.title("DiskScanner + Docker Manager")
        self.root.geometry("1320x860")
        self.root.minsize(960, 640)
        self.root.configure(bg=C["bg"])
    def __init__(self, qapp=None):
        self._qapp = qapp or QApplication.instance() or QApplication(sys.argv)

        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except Exception:
            pass
        setup_styles(self.style)
        self.root = QMainWindow()
        self.root.setWindowTitle("DiskScanner + Docker Manager")
        self.root.resize(1320, 860)
        self.root.setMinimumSize(960, 640)

        # 主 Notebook: File / Docker 两大标签页
        self.notebook = ttk.Notebook(self.root, style='Dark.TNotebook')
        self.notebook.pack(fill='both', expand=True, padx=8, pady=8)
        # Apply global QSS
        self._qapp.setStyleSheet(QSS)

        # 主 QTabWidget: File / Docker 两大标签页
        self.notebook = QTabWidget()
        self.root.setCentralWidget(self.notebook)

        # Tab 1: File Scanner
        self.scanner_frame = ScannerFrame(self.notebook, self.root)
        self.notebook.add(self.scanner_frame, text="  File Scanner  ")
        self.notebook.addTab(self.scanner_frame, "  File Scanner  ")

        # Tab 2: Docker Manager
        self.docker_frame = DockerFrame(self.notebook, self.root)
        self.notebook.add(self.docker_frame, text="  Docker Manager  ")
        self.notebook.addTab(self.docker_frame, "  Docker Manager  ")

        # Lazy-load Docker tab on first view
        self._docker_loaded = False
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)
        self.notebook.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, event):
        idx = self.notebook.index(self.notebook.select())
    def _on_tab_changed(self, idx):
        if idx == 1 and not self._docker_loaded:
            self.docker_frame.load_first()
            self._docker_loaded = True

    def run(self):
        self.root.mainloop()
        self.root.show()
        self._qapp.exec_()


# ── 向后兼容：供旧测试使用 ──
# ── 向后兼容：供测试使用 ──

# 需要代理到 ScannerFrame 的属性集合
_SCANNER_ATTRS = frozenset({
    'result', 'scan_path', 'view_mode', 'sort_col', 'sort_reverse',
    'item_map', 'tree', 'tree_title', '_page', '_page_size', '_total_items',
    '_checked_paths', '_page_label', '_scanning', '_scan_result',
})


class ScannerApp:
    """向后兼容包装器 — 将 ScannerFrame 包装为旧的 ScannerApp 接口"""

    def __init__(self):
        self.root = Tk()
        self.root.title("DiskScanner")
        self.root.geometry("1320x860")
        self.root.minsize(960, 640)
        self.root.configure(bg=C["bg"])
    def __init__(self, qapp=None):
        self._qapp = qapp or QApplication.instance() or QApplication(sys.argv)

        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        setup_styles(style)
        self.root = QMainWindow()
        self.root.setWindowTitle("DiskScanner")
        self.root.resize(1320, 860)
        self.root.setMinimumSize(960, 640)

        # Apply global QSS
        self._qapp.setStyleSheet(QSS)

        self._frame = ScannerFrame(self.root, self.root)
        self._frame.pack(fill='both', expand=True)
        self.root.setCentralWidget(self._frame)

    def __getattr__(self, name):
        return getattr(self._frame, name)

    def __setattr__(self, name, value):
        if name in ('root', '_frame'):
        if name in ('root', '_frame', '_qapp'):
            object.__setattr__(self, name, value)
        elif name in _SCANNER_ATTRS:
            setattr(self._frame, name, value)
        else:
            object.__setattr__(self, name, value)


def __getattr__(name):
    """模块级属性代理 — 将 _DIALOG_AUTO_DISMISS 等转发到 ui._base"""
    if name == '_DIALOG_AUTO_DISMISS':
        return _base._DIALOG_AUTO_DISMISS
    raise AttributeError(f"module 'tkinter_gui' has no attribute {name!r}")
# ── 模块级代理：支持 pyqt_gui._DIALOG_AUTO_DISMISS ──

def __getattr__(name):
    """模块级属性代理 — 将 _DIALOG_AUTO_DISMISS 等转发到 ui._base"""
    if name == '_DIALOG_AUTO_DISMISS':
        return _base._DIALOG_AUTO_DISMISS
    raise AttributeError(f"module 'pyqt_gui' has no attribute {name!r}")


def __setattr_module__(name, value):
    pass  # handled by __setattr__ below


# 允许通过 tkinter_gui._DIALOG_AUTO_DISMISS = True 设置
import types as _types
_orig_module = sys.modules[__name__]
_orig_module = sys.modules[__name__]





class _ModuleProxy(_types.ModuleType):
    def __setattr__(self, name, value):
        if name == '_DIALOG_AUTO_DISMISS':
            _base._DIALOG_AUTO_DISMISS = value
        else:
            super().__setattr__(name, value)

    def __getattr__(self, name):
        if name == '_DIALOG_AUTO_DISMISS':
            return _base._DIALOG_AUTO_DISMISS
        raise AttributeError(f"module 'tkinter_gui' has no attribute {name!r}")
    def __getattr__(self, name):
        if name == '_DIALOG_AUTO_DISMISS':
            return _base._DIALOG_AUTO_DISMISS
        raise AttributeError(f"module 'pyqt_gui' has no attribute {name!r}")




_proxy = _ModuleProxy(__name__)
_proxy.__dict__.update(_orig_module.__dict__)
sys.modules[__name__] = _proxy


def main():
    app = DiskScannerApp()
    app.run()


if __name__ == '__main__':
    main()
