#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiskScanner — 原生桌面 GUI（tkinter）
支持扫描、排序、过滤、删除文件/文件夹、导出
纯 Python 标准库，无需任何第三方依赖

启动方式: python3 tkinter_gui.py
"""

import os
import sys
import shutil
import platform
import threading
import json
import csv
from datetime import datetime
import tkinter.font as tkfont
from tkinter import (
    Tk, ttk, Frame, Label, Entry, Button, StringVar,
    BooleanVar, Checkbutton, Menu, Canvas, Scrollbar, Toplevel,
    filedialog, messagebox, HORIZONTAL, VERTICAL, BOTH, LEFT,
    RIGHT, TOP, BOTTOM, X, Y, END, W, E, N, S, FLAT, RIDGE, GROOVE,
)

_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)
from disk_scanner import (
    Scanner, ScanResult, FileNode, DirNode,
    format_size, parse_size_filter, sort_nodes,
)

# ══════════════════════════════════════════════════════════
#  设计系统 — 颜色 / 字体 / 尺寸
# ══════════════════════════════════════════════════════════

# 检测中文字体
def _detect_font():
    try:
        import subprocess
        r = subprocess.run(['fc-list', ':lang=zh', 'family'],
                           capture_output=True, text=True, timeout=3)
        for name in ("Noto Sans CJK SC", "WenQuanYi Micro Hei", "Microsoft YaHei"):
            if name in r.stdout:
                return name
    except Exception:
        pass
    return "sans-serif"

_CN = _detect_font()

# 调色板 — 现代深色 (参考 GitHub Dark / VS Code)
C = {
    "bg":         "#0d1117",     # 主背景 (近黑)
    "surface":    "#161b22",     # 卡片/面板背景
    "surface2":   "#1c2128",     # 次级面板
    "border":     "#30363d",     # 边框/分割线
    "border2":    "#21262d",     # 浅边框
    "input_bg":   "#0d1117",     # 输入框背景
    "text":       "#e6edf3",     # 主文字
    "text2":      "#8b949e",     # 次要文字
    "text3":      "#484f58",     # 弱化文字
    "accent":     "#58a6ff",     # 主强调 (蓝)
    "green":      "#3fb950",     # 成功/大小
    "red":        "#f85149",     # 危险/删除
    "orange":     "#d29922",     # 警告
    "purple":     "#bc8cff",     # 修饰
    "cyan":       "#79c0ff",     # 辅助蓝
    "tree_bg":    "#0d1117",     # 表格背景
    "tree_row1":  "#0d1117",     # 偶数行
    "tree_row2":  "#161b22",     # 奇数行
    "tree_head":  "#161b22",     # 表头
    "tree_sel":   "#1f6feb33",   # 选中行
    "btn_bg":     "#21262d",     # 普通按钮
    "btn_hover":  "#30363d",     # 按钮悬停
}

# 字体
F_TITLE   = (_CN, 16, "bold")
F_SUB     = (_CN, 10)
F_BODY    = (_CN, 10)
F_SMALL   = (_CN, 9)
F_TINY    = (_CN, 8)
F_BIG     = (_CN, 20, "bold")
F_STAT    = (_CN, 13, "bold")
F_MONO    = ("Consolas", 10) if platform.system() == "Windows" else ("Monospace", 10)
F_BTN     = (_CN, 9, "bold")


# ══════════════════════════════════════════════════════════
#  自定义按钮 (Canvas 实现圆角 + 悬停效果)
# ══════════════════════════════════════════════════════════

class RoundButton(Canvas):
    """带圆角和悬停效果的按钮"""
    def __init__(self, parent, text, command, bg=None, fg=None,
                 hover_bg=None, radius=6, padx=14, pady=5, font=F_BTN, **kw):
        self._bg = bg or C["btn_bg"]
        self._fg = fg or C["text"]
        self._hover = hover_bg or C["btn_hover"]
        self._cmd = command
        self._radius = radius
        self._text = text
        self._font = font

        # 使用 tkinter.font 测量文字
        try:
            tf = tkfont.Font(font=font)
            tw = tf.measure(text)
            th = tf.metrics("linespace")
        except Exception:
            tw = len(text) * 8
            th = 14

        w = int(tw + padx * 2)
        h = int(th + pady * 2)
        self._bw, self._bh = w, h

        super().__init__(parent, width=w, height=h,
                         bg=parent.cget("bg"), highlightthickness=0, **kw)
        self._draw(self._bg)
        self.bind("<Enter>", lambda e: self._draw(self._hover))
        self.bind("<Leave>", lambda e: self._draw(self._bg))
        self.bind("<Button-1>", lambda e: self._cmd())

    def _draw(self, fill):
        self.delete("all")
        r, w, h = self._radius, self._bw, self._bh
        # 圆角矩形
        self.create_arc(0, 0, 2*r, 2*r, start=90, extent=90, fill=fill, outline="")
        self.create_arc(w-2*r, 0, w, 2*r, start=0, extent=90, fill=fill, outline="")
        self.create_arc(0, h-2*r, 2*r, h, start=180, extent=90, fill=fill, outline="")
        self.create_arc(w-2*r, h-2*r, w, h, start=270, extent=90, fill=fill, outline="")
        self.create_rectangle(r, 0, w-r, h, fill=fill, outline="")
        self.create_rectangle(0, r, w, h-r, fill=fill, outline="")
        # 文字
        self.create_text(w//2, h//2, text=self._text, fill=self._fg, font=self._font)

    def config(self, bg=None, fg=None, **kw):
        if bg:
            self._bg = bg
            self._draw(self._bg)
        if fg:
            self._fg = fg
            self._draw(self._bg)


# ══════════════════════════════════════════════════════════
#  统计卡片
# ══════════════════════════════════════════════════════════

class StatCard(Frame):
    """一个统计指标卡片"""
    def __init__(self, parent, label, color=C["text"], **kw):
        super().__init__(parent, bg=C["surface"], **kw)
        self._val = Label(self, text="--", bg=C["surface"], fg=color,
                          font=F_BIG, anchor=W)
        self._val.pack(anchor=W, padx=14, pady=(10, 0))
        self._lbl = Label(self, text=label, bg=C["surface"], fg=C["text2"],
                          font=F_SMALL, anchor=W)
        self._lbl.pack(anchor=W, padx=14, pady=(0, 10))

    def set_value(self, val):
        self._val.config(text=val)


# ══════════════════════════════════════════════════════════
#  自定义确认对话框 — 暗色主题
# ══════════════════════════════════════════════════════════

# 测试模式：设为 True 时对话框自动跳过，不弹窗
_DIALOG_AUTO_DISMISS = False


class ConfirmDialog:
    """暗色主题的确认对话框，替代丑陋的 messagebox"""

    def __init__(self, parent, title, summary, items, confirm_text="Delete",
                 confirm_bg="#da3633", confirm_hover="#f85149"):
        """
        parent: 父窗口
        title: 对话框标题
        summary: 顶部摘要文本
        items: 列表 [(label, detail), ...] 显示在滚动区域
        confirm_text: 确认按钮文本
        confirm_bg: 确认按钮背景色
        """
        # 测试模式：跳过弹窗，直接返回确认
        if _DIALOG_AUTO_DISMISS:
            self.result = True
            self.win = None
            return

        self.result = False
        self.win = Toplevel(parent)
        self.win.title(title)
        self.win.geometry("700x520")
        self.win.minsize(500, 380)
        self.win.configure(bg=C["bg"])
        self.win.transient(parent)
        try:
            self.win.grab_set()
        except Exception:
            pass

        # ── 标题栏 ──
        hdr = Frame(self.win, bg=C["surface"], padx=20, pady=14)
        hdr.pack(fill=X)
        Label(hdr, text=title, bg=C["surface"], fg=C["red"],
              font=(_CN, 14, "bold")).pack(anchor=W)
        Label(hdr, text=summary, bg=C["surface"], fg=C["text2"],
              font=F_SMALL, justify=LEFT, wraplength=640).pack(anchor=W, pady=(6, 0))

        # ── 文件列表 ──
        list_frame = Frame(self.win, bg=C["bg"], padx=16, pady=8)
        list_frame.pack(fill=BOTH, expand=True)

        # 表头
        cols = ("type", "path", "size")
        tree = ttk.Treeview(list_frame, columns=cols, show='headings',
                             style='Scan.Treeview')
        tree.heading("type", text="Type")
        tree.heading("path", text="Path")
        tree.heading("size", text="Size")
        tree.column("type", width=60, anchor='center', minwidth=50)
        tree.column("path", width=440, minwidth=200)
        tree.column("size", width=100, anchor=E, minwidth=70)

        ysb = Scrollbar(list_frame, orient=VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=ysb.set)
        tree.pack(side=LEFT, fill=BOTH, expand=True)
        ysb.pack(side=RIGHT, fill=Y)

        for i, (lbl, detail) in enumerate(items):
            tag = 'odd' if i % 2 else 'even'
            tree.insert('', END, values=(lbl, detail[0], detail[1]), tags=(tag,))
        tree.tag_configure('odd', background=C["tree_row1"])
        tree.tag_configure('even', background=C["tree_row2"])

        # ── 按钮栏 ──
        btn_bar = Frame(self.win, bg=C["surface"], padx=20, pady=14)
        btn_bar.pack(fill=X, side=BOTTOM)

        Label(btn_bar, text="This cannot be undone!",
              bg=C["surface"], fg=C["text3"], font=F_SMALL).pack(side=LEFT)

        cancel_btn = RoundButton(btn_bar, text="Cancel",
                                  command=self._on_cancel,
                                  bg=C["btn_bg"], fg=C["text"])
        cancel_btn.pack(side=RIGHT, padx=(8, 0))

        confirm_btn = RoundButton(btn_bar, text=confirm_text,
                                   command=self._on_confirm,
                                   bg=confirm_bg, fg="#ffffff",
                                   hover_bg=confirm_hover)
        confirm_btn.pack(side=RIGHT)

        # 居中显示
        self.win.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        x = px + (pw - 700) // 2
        y = py + (ph - 520) // 2
        self.win.geometry(f"+{x}+{y}")

        # 绑定 ESC 关闭
        self.win.bind('<Escape>', lambda e: self._on_cancel())

        # 阻塞等待结果（headless 环境跳过等待）
        try:
            self.win.wait_window()
        except Exception:
            self.result = False

    def _on_confirm(self):
        self.result = True
        self.win.destroy()

    def _on_cancel(self):
        self.result = False
        self.win.destroy()


class InfoDialog:
    """暗色主题信息对话框"""

    def __init__(self, parent, title, message, msg_color=None):
        # 测试模式：跳过弹窗
        if _DIALOG_AUTO_DISMISS:
            self.win = None
            return

        self.win = Toplevel(parent)
        self.win.title(title)
        self.win.geometry("480x200")
        self.win.configure(bg=C["bg"])
        self.win.transient(parent)
        try:
            self.win.grab_set()
        except Exception:
            pass

        body = Frame(self.win, bg=C["bg"], padx=24, pady=20)
        body.pack(fill=BOTH, expand=True)

        Label(body, text=title, bg=C["bg"],
              fg=msg_color or C["accent"],
              font=(_CN, 13, "bold")).pack(anchor=W)
        Label(body, text=message, bg=C["bg"], fg=C["text"],
              font=F_BODY, justify=LEFT, wraplength=420).pack(anchor=W, pady=(10, 0))

        btn_bar = Frame(self.win, bg=C["surface"], padx=20, pady=12)
        btn_bar.pack(fill=X, side=BOTTOM)
        ok_btn = RoundButton(btn_bar, text="OK", command=self._close,
                              bg=C["accent"], fg="#ffffff", hover_bg="#79c0ff")
        ok_btn.pack(side=RIGHT)

        self.win.update_idletasks()
        px = parent.winfo_x()
        py = parent.winfo_y()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw - 480) // 2
        y = py + (ph - 200) // 2
        self.win.geometry(f"+{x}+{y}")
        self.win.bind('<Escape>', lambda e: self._close())
        self.win.bind('<Return>', lambda e: self._close())
        try:
            self.win.wait_window()
        except Exception:
            pass

    def _close(self):
        self.win.destroy()


# ══════════════════════════════════════════════════════════
#  主应用
# ══════════════════════════════════════════════════════════

class ScannerApp:
    def __init__(self):
        self.root = Tk()
        self.root.title("DiskScanner")
        self.root.geometry("1320x860")
        self.root.minsize(960, 640)
        self.root.configure(bg=C["bg"])

        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except Exception:
            pass
        self._setup_styles()

        # 状态
        self.result = None
        self.scan_path = ""
        self.view_mode = "dirs"
        self.sort_col = "size"
        self.sort_reverse = True
        self.item_map = {}
        self._scanning = False
        self._scan_result = None
        self._scan_error = None
        self._scan_thread = None
        # 分页
        self._page = 0
        self._page_size = 200
        self._sorted_items = []
        self._total_items = 0
        # 勾选状态（跨页持久化，按 path 跟踪）
        self._checked_paths = set()

        self._build_ui()

    # ── 样式 ──

    def _setup_styles(self):
        s = self.style
        c = C
        # Treeview
        s.configure('Scan.Treeview',
                     background=c["tree_bg"], foreground=c["text"],
                     fieldbackground=c["tree_bg"], font=F_BODY,
                     rowheight=28, borderwidth=0)
        s.configure('Scan.Treeview.Heading',
                     background=c["tree_head"], foreground=c["text2"],
                     font=F_BTN, relief='flat', padding=(8, 5))
        s.map('Scan.Treeview',
              background=[('selected', c["tree_sel"])],
              foreground=[('selected', c["accent"])])
        # Progressbar
        s.configure('Scan.Horizontal.TProgressbar',
                     troughcolor=c["surface"], background=c["accent"],
                     borderwidth=0, thickness=4)
        # Separator
        s.configure('Dark.TSeparator', background=c["border"])

    # ── 构建界面 ──

    def _build_ui(self):
        # 外层容器，统一边距
        outer = Frame(self.root, bg=C["bg"])
        outer.pack(fill=BOTH, expand=True, padx=16, pady=12)

        self._build_header(outer)
        self._build_controls(outer)
        self._build_stats(outer)
        self._build_toolbar(outer)
        self._build_tree(outer)
        self._build_detail(outer)
        self._build_statusbar(outer)
        self._build_context_menu()

    def _build_header(self, parent):
        hdr = Frame(parent, bg=C["bg"])
        hdr.pack(fill=X, pady=(0, 10))

        # 左侧标题
        left = Frame(hdr, bg=C["bg"])
        left.pack(side=LEFT)
        Label(left, text="DiskScanner", bg=C["bg"], fg=C["accent"],
              font=F_TITLE).pack(side=LEFT)
        v = Label(left, text=" v1.0 ", bg=C["surface"], fg=C["text2"],
                  font=F_TINY, padx=6, pady=2)
        v.pack(side=LEFT, padx=(10, 0))

        # 右侧新扫描按钮
        self._new_scan_btn = RoundButton(hdr, text="New Scan",
                                          command=self._reset_scan,
                                          bg=C["btn_bg"], fg=C["text"])
        self._new_scan_btn.pack(side=RIGHT)

    def _build_controls(self, parent):
        card = Frame(parent, bg=C["surface"], padx=16, pady=12)
        card.pack(fill=X, pady=(0, 10))

        # 第一行: 路径 + 按钮
        r1 = Frame(card, bg=C["surface"])
        r1.pack(fill=X, pady=(0, 8))

        Label(r1, text="PATH", bg=C["surface"], fg=C["text2"],
              font=F_TINY).pack(side=LEFT, padx=(0, 8))

        self.path_var = StringVar(value=os.path.expanduser("~"))
        self.path_entry = Entry(r1, textvariable=self.path_var, font=F_MONO,
                                 bg=C["input_bg"], fg=C["text"],
                                 insertbackground=C["accent"], relief=FLAT, bd=6,
                                 highlightthickness=1, highlightcolor=C["accent"],
                                 highlightbackground=C["border"])
        self.path_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        self.path_entry.bind('<Return>', lambda e: self._start_scan())

        self._browse_btn = RoundButton(r1, text="Browse", command=self._browse,
                                        bg=C["btn_bg"], fg=C["text"])
        self._browse_btn.pack(side=LEFT, padx=(0, 8))

        self._scan_btn = RoundButton(r1, text="START SCAN", command=self._start_scan,
                                      bg=C["accent"], fg="#ffffff",
                                      hover_bg="#79c0ff")
        self._scan_btn.pack(side=LEFT)

        # 第二行: 过滤
        r2 = Frame(card, bg=C["surface"])
        r2.pack(fill=X)

        Label(r2, text="MIN SIZE", bg=C["surface"], fg=C["text3"],
              font=F_TINY).pack(side=LEFT)
        self.min_size_var = StringVar()
        Entry(r2, textvariable=self.min_size_var, font=F_SMALL, width=10,
              bg=C["input_bg"], fg=C["text"], insertbackground=C["accent"],
              relief=FLAT, bd=4, highlightthickness=1,
              highlightcolor=C["accent"], highlightbackground=C["border"]).pack(side=LEFT, padx=(6, 16))

        Label(r2, text="EXT FILTER", bg=C["surface"], fg=C["text3"],
              font=F_TINY).pack(side=LEFT)
        self.ext_var = StringVar()
        Entry(r2, textvariable=self.ext_var, font=F_SMALL, width=14,
              bg=C["input_bg"], fg=C["text"], insertbackground=C["accent"],
              relief=FLAT, bd=4, highlightthickness=1,
              highlightcolor=C["accent"], highlightbackground=C["border"]).pack(side=LEFT, padx=(6, 16))

        self.follow_sym = BooleanVar(value=False)
        Checkbutton(r2, text="Follow symlinks", variable=self.follow_sym,
                     bg=C["surface"], fg=C["text3"], selectcolor=C["input_bg"],
                     activebackground=C["surface"], activeforeground=C["text2"],
                     font=F_SMALL).pack(side=LEFT)

        # 进度条
        self.progress = ttk.Progressbar(card, mode='indeterminate',
                                         style='Scan.Horizontal.TProgressbar')
        self.progress.pack(fill=X, pady=(8, 0))

    def _build_stats(self, parent):
        row = Frame(parent, bg=C["bg"])
        row.pack(fill=X, pady=(0, 10))

        self.sc_size  = StatCard(row, "TOTAL SIZE", C["green"])
        self.sc_size.pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        self.sc_files = StatCard(row, "FILES", C["text"])
        self.sc_files.pack(side=LEFT, fill=X, expand=True, padx=(3, 3))
        self.sc_dirs  = StatCard(row, "DIRS", C["orange"])
        self.sc_dirs.pack(side=LEFT, fill=X, expand=True, padx=(3, 3))
        self.sc_time  = StatCard(row, "DURATION", C["purple"])
        self.sc_time.pack(side=LEFT, fill=X, expand=True, padx=(3, 3))
        self.sc_skip  = StatCard(row, "SKIPPED", C["orange"])
        self.sc_skip.pack(side=LEFT, fill=X, expand=True, padx=(3, 0))

    def _build_toolbar(self, parent):
        tb = Frame(parent, bg=C["bg"])
        tb.pack(fill=X, pady=(0, 6))

        # 视图切换
        self.view_dirs_btn = RoundButton(tb, text="DIRS", command=lambda: self._switch("dirs"),
                                          bg=C["accent"], fg="#ffffff",
                                          hover_bg=C["accent"], padx=12)
        self.view_dirs_btn.pack(side=LEFT, padx=(0, 2))
        self.view_files_btn = RoundButton(tb, text="FILES", command=lambda: self._switch("files"),
                                           bg=C["btn_bg"], fg=C["text"],
                                           hover_bg=C["btn_hover"], padx=12)
        self.view_files_btn.pack(side=LEFT, padx=(0, 8))

        # 分隔线
        Frame(tb, bg=C["border"], width=1).pack(side=LEFT, fill=Y, padx=8)

        # 操作按钮
        self._check_all_btn = RoundButton(tb, text="CHECK PAGE", command=self._check_all_on_page,
                                            bg=C["btn_bg"], fg=C["text"], padx=8)
        self._check_all_btn.pack(side=LEFT, padx=(0, 2))
        self._del_btn = RoundButton(tb, text="DELETE", command=self._delete_checked,
                                     bg="#da3633", fg="#ffffff", hover_bg="#f85149", padx=10)
        self._del_btn.pack(side=LEFT, padx=(0, 2))
        self._clear_btn = RoundButton(tb, text="CLEAR", command=self._clear_all_checks,
                                       bg=C["btn_bg"], fg=C["text"], padx=8)
        self._clear_btn.pack(side=LEFT, padx=(0, 4))
        RoundButton(tb, text="CSV", command=lambda: self._export("csv"),
                     bg=C["btn_bg"], fg=C["text"], padx=10).pack(side=LEFT, padx=2)
        RoundButton(tb, text="JSON", command=lambda: self._export("json"),
                     bg=C["btn_bg"], fg=C["text"], padx=10).pack(side=LEFT, padx=2)

        # 右侧计数 + 分页
        self.tree_title = Label(tb, text="", bg=C["bg"], fg=C["text2"], font=F_SMALL)
        self.tree_title.pack(side=RIGHT)

        # 分页控件
        pg = Frame(tb, bg=C["bg"])
        pg.pack(side=RIGHT, padx=(8, 4))
        self._prev_btn = RoundButton(pg, text="<", command=self._prev_page,
                                      bg=C["btn_bg"], fg=C["text"], padx=8, pady=2)
        self._prev_btn.pack(side=LEFT, padx=1)
        self._page_label = Label(pg, text="", bg=C["bg"], fg=C["text2"], font=F_SMALL)
        self._page_label.pack(side=LEFT, padx=6)
        self._next_btn = RoundButton(pg, text=">", command=self._next_page,
                                      bg=C["btn_bg"], fg=C["text"], padx=8, pady=2)
        self._next_btn.pack(side=LEFT, padx=1)

    def _build_tree(self, parent):
        wrap = Frame(parent, bg=C["border"], bd=1, relief=FLAT)
        wrap.pack(fill=BOTH, expand=True, pady=(0, 6))

        inner = Frame(wrap, bg=C["tree_bg"], padx=1, pady=1)
        inner.pack(fill=BOTH, expand=True)

        ysb = Scrollbar(inner, orient=VERTICAL)
        xsb = Scrollbar(inner, orient=HORIZONTAL)
        self.tree = ttk.Treeview(inner, style='Scan.Treeview',
                                  yscrollcommand=ysb.set, xscrollcommand=xsb.set,
                                  selectmode='extended', show='headings')
        ysb.config(command=self.tree.yview)
        xsb.config(command=self.tree.xview)
        self.tree.grid(row=0, column=0, sticky='nsew')
        ysb.grid(row=0, column=1, sticky='ns')
        xsb.grid(row=1, column=0, sticky='ew')
        inner.grid_rowconfigure(0, weight=1)
        inner.grid_columnconfigure(0, weight=1)

        self.tree.bind('<Button-1>', self._on_click)
        self.tree.bind('<Double-1>', self._on_dblclick)
        self.tree.bind('<Button-3>', self._on_rightclick)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

    def _build_detail(self, parent):
        det = Frame(parent, bg=C["surface"], padx=14, pady=8)
        det.pack(fill=X, pady=(0, 4))

        self.detail_var = StringVar(value="Select an item to see details   |   Double-click to drill down   |   Right-click for more")
        Label(det, textvariable=self.detail_var, bg=C["surface"], fg=C["text2"],
              font=F_SMALL, anchor=W).pack(side=LEFT, fill=X, expand=True)
        self.del_cmd_var = StringVar()
        Label(det, textvariable=self.del_cmd_var, bg=C["surface"], fg=C["red"],
              font=F_MONO, anchor=E).pack(side=RIGHT)

    def _build_statusbar(self, parent):
        sf = Frame(parent, bg=C["bg"])
        sf.pack(fill=X)
        self.status_var = StringVar(value="Ready")
        Label(sf, textvariable=self.status_var, bg=C["bg"], fg=C["text3"],
              font=F_TINY, anchor=W).pack(side=LEFT)

    def _build_context_menu(self):
        self.ctx_menu = Menu(self.root, tearoff=0,
                              bg=C["surface"], fg=C["text"],
                              activebackground=C["accent"],
                              activeforeground="#ffffff",
                              font=F_SMALL, borderwidth=1,
                              relief=FLAT)

    # ══════════════════════════════════════════════════════
    #  扫描逻辑
    # ══════════════════════════════════════════════════════

    def _reset_scan(self):
        self.result = None
        self._checked_paths.clear()
        self._clear_tree()
        for sc in (self.sc_size, self.sc_files, self.sc_dirs, self.sc_time, self.sc_skip):
            sc.set_value("--")
        self.status_var.set("Ready")
        self.tree_title.config(text="")
        self.detail_var.set("Select an item to see details   |   Double-click to drill down   |   Right-click for more")
        self.del_cmd_var.set("")

    def _browse(self):
        path = filedialog.askdirectory(title="Select directory",
                                        initialdir=self.path_var.get() or "/")
        if path:
            self.path_var.set(path)

    def _start_scan(self):
        if self._scanning:
            return
        path = self.path_var.get().strip()
        if not path:
            messagebox.showerror("Error", "Please enter a path")
            return
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(abs_path):
            messagebox.showerror("Error", f"Path not found:\n{abs_path}")
            return
        if not os.path.isdir(abs_path):
            messagebox.showerror("Error", f"Not a directory:\n{abs_path}")
            return

        self._scanning = True
        self._scan_result = None
        self._scan_error = None
        self.scan_path = abs_path
        self.status_var.set(f"Scanning {abs_path} ...")
        self.progress.start(12)
        self._clear_tree()

        def do_scan():
            try:
                scanner = Scanner(follow_symlinks=self.follow_sym.get())
                self._scan_result = scanner.scan(abs_path)
            except Exception as e:
                self._scan_error = str(e)

        self._scan_thread = threading.Thread(target=do_scan, daemon=True)
        self._scan_thread.start()
        self.root.after(300, self._check_scan_done)

    def _check_scan_done(self):
        if self._scan_thread and self._scan_thread.is_alive():
            self.root.after(300, self._check_scan_done)
            return
        self.progress.stop()
        self._scanning = False

        if self._scan_error:
            messagebox.showerror("Scan Error", self._scan_error)
            self.status_var.set("Scan failed")
            return

        r = self._scan_result
        self.result = r
        skip_txt = f"  |  Skipped {r.skipped_count}" if r.skipped_count else ""
        self.status_var.set(
            f"Done: {r.total_files:,} files, {r.total_dirs:,} dirs, "
            f"{r.scan_duration:.2f}s{skip_txt}")
        self._update_stats(r)
        self._render()

    # ══════════════════════════════════════════════════════
    #  渲染
    # ══════════════════════════════════════════════════════

    def _update_stats(self, r):
        self.sc_size.set_value(format_size(r.total_size))
        self.sc_files.set_value(f"{r.total_files:,}")
        self.sc_dirs.set_value(f"{r.total_dirs:,}")
        self.sc_time.set_value(f"{r.scan_duration:.2f}s")
        self.sc_skip.set_value(str(r.skipped_count) if r.skipped_count else "0")

    def _render(self):
        if not self.result:
            return
        r = self.result

        # 过滤
        files = list(r.all_files)
        ms = parse_size_filter(self.min_size_var.get().strip())
        ext_str = self.ext_var.get().strip()
        exts = []
        if ext_str:
            exts = [e.strip().lower() if e.strip().startswith('.')
                    else f'.{e.strip().lower()}' for e in ext_str.split(',') if e.strip()]
        if ms > 0:
            files = [f for f in files if f.size >= ms]
        if exts:
            files = [f for f in files if f.extension in exts]

        dirs = r.all_dirs
        if ms > 0 or exts:
            dp = set(f.parent_path for f in files)
            dirs = [d for d in dirs if d.path in dp or d.path == r.root.path]

        sort_mode = self._sort_mode_key()
        all_items = sort_nodes(dirs if self.view_mode == "dirs" else files, sort_mode)
        self._sorted_items = all_items
        self._total_items = len(all_items)

        # 分页边界检查
        max_page = max(0, (self._total_items - 1) // self._page_size)
        if self._page > max_page:
            self._page = max_page
        if self._page < 0:
            self._page = 0

        # 只取当前页的数据
        start = self._page * self._page_size
        end = start + self._page_size
        items = all_items[start:end]
        self.item_map = {}

        for c in self.tree.get_children():
            self.tree.delete(c)

        is_dirs = self.view_mode == "dirs"

        if is_dirs:
            cols = ("check", "path", "size", "files", "subdirs", "pct", "modified")
            self.tree.config(columns=cols)
            self.tree.heading("check", text="")
            self.tree.heading("path", text=f"Path{self._arrow('path')}",
                              command=lambda: self._sort_by("path"))
            self.tree.heading("size", text=f"Size{self._arrow('size')}",
                              command=lambda: self._sort_by("size"))
            self.tree.heading("files", text=f"Files{self._arrow('files')}",
                              command=lambda: self._sort_by("files"))
            self.tree.heading("subdirs", text=f"SubDirs{self._arrow('subdirs')}",
                              command=lambda: self._sort_by("subdirs"))
            self.tree.heading("pct", text=f"%{self._arrow('pct')}",
                              command=lambda: self._sort_by("pct"))
            self.tree.heading("modified", text=f"Modified{self._arrow('modified')}",
                              command=lambda: self._sort_by("modified"))
            self.tree.column("check", width=36, anchor='center', minwidth=30, stretch=False)
            self.tree.column("path", width=500, minwidth=200)
            self.tree.column("size", width=110, anchor=E, minwidth=80)
            self.tree.column("files", width=80, anchor=E, minwidth=60)
            self.tree.column("subdirs", width=80, anchor=E, minwidth=60)
            self.tree.column("pct", width=70, anchor=E, minwidth=50)
            self.tree.column("modified", width=150, minwidth=100)
        else:
            cols = ("check", "path", "size", "ext", "pct", "modified")
            self.tree.config(columns=cols)
            self.tree.heading("check", text="")
            self.tree.heading("path", text=f"Path{self._arrow('path')}",
                              command=lambda: self._sort_by("path"))
            self.tree.heading("size", text=f"Size{self._arrow('size')}",
                              command=lambda: self._sort_by("size"))
            self.tree.heading("ext", text=f"Type{self._arrow('ext')}",
                              command=lambda: self._sort_by("ext"))
            self.tree.heading("pct", text=f"%{self._arrow('pct')}",
                              command=lambda: self._sort_by("pct"))
            self.tree.heading("modified", text=f"Modified{self._arrow('modified')}",
                              command=lambda: self._sort_by("modified"))
            self.tree.column("check", width=36, anchor='center', minwidth=30, stretch=False)
            self.tree.column("path", width=540, minwidth=200)
            self.tree.column("size", width=110, anchor=E, minwidth=80)
            self.tree.column("ext", width=80, minwidth=50)
            self.tree.column("pct", width=70, anchor=E, minwidth=50)
            self.tree.column("modified", width=150, minwidth=100)

        total = max(r.total_size, 1)
        for i, node in enumerate(items):
            iid = str(i)
            self.item_map[iid] = node
            pct = f"{node.size / total * 100:.1f}%"
            checked = node.path in self._checked_paths
            ck = "[x]" if checked else "[ ]"
            base_tag = 'odd' if i % 2 else 'even'
            tag = f'{base_tag}_checked' if checked else base_tag
            if is_dirs:
                vals = (ck, node.path, format_size(node.size), node.file_count,
                        node.dir_count, pct, _fmt_time(node.modified))
            else:
                vals = (ck, node.path, format_size(node.size), node.extension or "-",
                        pct, _fmt_time(node.modified))
            self.tree.insert('', END, iid=iid, values=vals, tags=(tag,))

        self.tree.tag_configure('odd', background=C["tree_row1"])
        self.tree.tag_configure('even', background=C["tree_row2"])
        self.tree.tag_configure('odd_checked', background="#1a2a40")
        self.tree.tag_configure('even_checked', background="#162538")

        vlabel = "Directories" if self.view_mode == "dirs" else "Files"
        checked_count = len(self._checked_paths)
        if checked_count > 0:
            self.tree_title.config(
                text=f"{vlabel} ({self._total_items:,})  |  Checked: {checked_count}")
        else:
            self.tree_title.config(text=f"{vlabel} ({self._total_items:,})")

        # 更新分页标签
        max_page = max(0, (self._total_items - 1) // self._page_size)
        if self._total_items == 0:
            self._page_label.config(text="")
        else:
            self._page_label.config(text=f"{self._page + 1}/{max_page + 1}")

    # ── 分页导航 ──

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._render()

    def _next_page(self):
        max_page = max(0, (self._total_items - 1) // self._page_size)
        if self._page < max_page:
            self._page += 1
            self._render()

    # ── 排序 ──

    def _sort_mode_key(self):
        """将当前排序列 + 方向映射为 sort_nodes 的 mode"""
        col = self.sort_col
        rev = self.sort_reverse
        mapping = {
            "size":    ("size-desc", "size-asc"),
            "name":    ("name-desc", "name"),
            "path":    ("path-desc", "path"),
            "modified": ("modified", "modified-asc"),
            "ext":     ("ext-desc", "ext"),
            "files":   ("files-desc", "files-asc"),
            "subdirs": ("subdirs-desc", "subdirs-asc"),
            "pct":     ("size-desc", "size-asc"),  # % 与 size 等价
        }
        if col in mapping:
            return mapping[col][0] if rev else mapping[col][1]
        return "size-desc"

    def _arrow(self, col):
        """生成排序箭头指示符"""
        if self.sort_col != col:
            return ""
        return " \u25bc" if self.sort_reverse else " \u25b2"

    def _sort_by(self, col):
        if col == self.sort_col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_col = col
            self.sort_reverse = True
        self._page = 0
        self._render()

    # ── 视图切换 ──

    def _switch(self, mode):
        self.view_mode = mode
        self._page = 0
        if mode == "dirs":
            self.view_dirs_btn._bg = C["accent"]
            self.view_dirs_btn._fg = "#ffffff"
            self.view_dirs_btn._draw(C["accent"])
            self.view_files_btn._bg = C["btn_bg"]
            self.view_files_btn._fg = C["text"]
            self.view_files_btn._draw(C["btn_bg"])
        else:
            self.view_dirs_btn._bg = C["btn_bg"]
            self.view_dirs_btn._fg = C["text"]
            self.view_dirs_btn._draw(C["btn_bg"])
            self.view_files_btn._bg = C["accent"]
            self.view_files_btn._fg = "#ffffff"
            self.view_files_btn._draw(C["accent"])
        self._render()

    # ══════════════════════════════════════════════════════
    #  事件处理
    # ══════════════════════════════════════════════════════

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        node = self.item_map.get(sel[0])
        if not node:
            return
        if isinstance(node, DirNode):
            cmd = f'rm -rf "{node.path}"'
            info = (f"[DIR] {node.path}   {format_size(node.size)}"
                    f"   Files: {node.file_count}  SubDirs: {node.dir_count}")
        else:
            cmd = f'rm "{node.path}"'
            info = f"[FILE] {node.path}   {format_size(node.size)}   {node.extension or '?'}"
        self.detail_var.set(info)
        self.del_cmd_var.set(f"$ {cmd}")

    def _on_dblclick(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        node = self.item_map.get(sel[0])
        if not node:
            return
        if os.path.isdir(node.path):
            self.path_var.set(node.path)
            messagebox.showinfo("Info", f"Scan path set to:\n{node.path}")
        else:
            self.path_var.set(os.path.dirname(node.path))

    def _on_rightclick(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        self._ctx_sel = sel
        m = self.ctx_menu
        m.delete(0, END)

        # 勾选操作
        iid = sel[0]
        node = self.item_map.get(iid)
        if node:
            if node.path in self._checked_paths:
                m.add_command(label="  Uncheck", command=lambda: self._toggle_check(iid))
            else:
                m.add_command(label="  Check", command=lambda: self._toggle_check(iid))

        m.add_command(label="  Check all on page", command=self._check_all_on_page)
        m.add_command(label="  Uncheck all on page", command=self._uncheck_all_on_page)

        m.add_separator()
        m.add_command(label="  Copy path", command=self._ctx_copy_path)
        m.add_command(label="  Copy parent dir", command=self._ctx_copy_dir)
        m.add_separator()
        m.add_command(label="  Scan this dir", command=lambda: self._ctx_scan(sel))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _ctx_copy_path(self):
        sel = self.tree.selection()
        if sel:
            node = self.item_map.get(sel[0])
            if node:
                self.root.clipboard_clear()
                self.root.clipboard_append(node.path)
                self.status_var.set(f"Copied: {node.path}")

    def _ctx_copy_dir(self):
        sel = self.tree.selection()
        if sel:
            node = self.item_map.get(sel[0])
            if node:
                d = node.path if isinstance(node, DirNode) else os.path.dirname(node.path)
                self.root.clipboard_clear()
                self.root.clipboard_append(d)
                self.status_var.set(f"Copied: {d}")

    def _ctx_scan(self, sel):
        node = self.item_map.get(sel[0])
        if node:
            d = node.path if isinstance(node, DirNode) else os.path.dirname(node.path)
            self.path_var.set(d)
            self._start_scan()

    # ══════════════════════════════════════════════════════
    #  勾选操作
    # ══════════════════════════════════════════════════════

    def _on_click(self, event):
        """处理单击：点击勾选列时切换勾选状态"""
        region = self.tree.identify_region(event.x, event.y)
        if region not in ('cell', 'heading'):
            return
        col = self.tree.identify_column(event.x)
        if col == '#1':  # check column
            iid = self.tree.identify_row(event.y)
            if iid:
                self._toggle_check(iid)
                return "break"  # 阻止默认选择行为

    def _toggle_check(self, iid):
        """切换单个条目的勾选状态"""
        node = self.item_map.get(iid)
        if not node:
            return
        if node.path in self._checked_paths:
            self._checked_paths.discard(node.path)
        else:
            self._checked_paths.add(node.path)
        self._update_row_check(iid, node.path)
        self._update_check_count()

    def _update_row_check(self, iid, path):
        """更新单行的勾选视觉状态"""
        checked = path in self._checked_paths
        ck = "[x]" if checked else "[ ]"
        vals = list(self.tree.item(iid, 'values'))
        vals[0] = ck
        self.tree.item(iid, values=vals)
        # 更新 tag 改变背景色
        old_tags = self.tree.item(iid, 'tags')
        if old_tags:
            base = old_tags[0].replace('_checked', '')
            new_tag = f'{base}_checked' if checked else base
            self.tree.item(iid, tags=(new_tag,))

    def _update_check_count(self):
        """更新工具栏的已勾选计数"""
        count = len(self._checked_paths)
        vlabel = "Directories" if self.view_mode == "dirs" else "Files"
        if count > 0:
            self.tree_title.config(
                text=f"{vlabel} ({self._total_items:,})  |  Checked: {count}")
        else:
            self.tree_title.config(text=f"{vlabel} ({self._total_items:,})")

    def _check_all_on_page(self):
        """勾选当前页所有条目"""
        for iid in self.tree.get_children():
            node = self.item_map.get(iid)
            if node:
                self._checked_paths.add(node.path)
                self._update_row_check(iid, node.path)
        self._update_check_count()

    def _uncheck_all_on_page(self):
        """取消勾选当前页所有条目"""
        for iid in self.tree.get_children():
            node = self.item_map.get(iid)
            if node:
                self._checked_paths.discard(node.path)
                self._update_row_check(iid, node.path)
        self._update_check_count()

    def _clear_all_checks(self):
        """清除所有勾选"""
        self._checked_paths.clear()
        self._render()

    # ══════════════════════════════════════════════════════
    #  删除（基于勾选）
    # ══════════════════════════════════════════════════════

    def _delete_checked(self):
        """删除所有已勾选的条目"""
        if not self._checked_paths:
            InfoDialog(self.root, "Info",
                       "No items checked.\nClick the checkbox column to select items.")
            return

        # 从扫描结果中查找对应的节点
        nodes = []
        all_nodes = list(self.result.all_dirs) + list(self.result.all_files) if self.result else []
        for n in all_nodes:
            if n.path in self._checked_paths:
                nodes.append(n)

        if not nodes:
            self._checked_paths.clear()
            return

        count = len(nodes)
        total_size = sum(n.size for n in nodes)
        dir_count = sum(1 for n in nodes if isinstance(n, DirNode))
        file_count = count - dir_count

        summary = (f"{count} items: {file_count} files, {dir_count} dirs, "
                   f"total {format_size(total_size)}")

        items = []
        for n in nodes:
            lbl = "DIR" if isinstance(n, DirNode) else "FILE"
            items.append((lbl, (n.path, format_size(n.size))))

        dlg = ConfirmDialog(self.root, "Confirm Delete", summary, items,
                             confirm_text=f"Delete {count}")
        if not dlg.result:
            return

        self._batch_delete_nodes(nodes)

    def _batch_delete_nodes(self, nodes):
        """执行批量删除，带进度反馈和安全校验"""
        if not nodes:
            return

        # ═══ 安全校验：路径必须在扫描范围内 ═══
        safe_nodes = []
        blocked = []
        scan_root = os.path.realpath(self.scan_path) if self.scan_path else ""

        for node in nodes:
            target = os.path.realpath(node.path)
            if not scan_root:
                blocked.append((node.path, "No scan path set"))
            elif target == scan_root:
                blocked.append((node.path, "Cannot delete scan root itself"))
            elif not target.startswith(scan_root + os.sep) and target != scan_root:
                blocked.append((node.path, f"Outside scan path: {scan_root}"))
            else:
                safe_nodes.append(node)

        if blocked:
            blocked_msg = "\n".join(f"  {p}: {r}" for p, r in blocked[:10])
            if len(blocked) > 10:
                blocked_msg += f"\n  ... and {len(blocked) - 10} more"
            InfoDialog(self.root, "Security Check Failed",
                       f"{len(blocked)} item(s) blocked for safety:\n\n{blocked_msg}",
                       msg_color=C["red"])
            if not safe_nodes:
                return

        # ═══ 执行删除 ═══
        total = len(safe_nodes)
        deleted = 0
        errors = []

        self._del_btn.config(state='disabled')

        for i, node in enumerate(safe_nodes):
            try:
                if isinstance(node, DirNode):
                    shutil.rmtree(node.path, ignore_errors=False)
                else:
                    os.remove(node.path)
                deleted += 1
                self._checked_paths.discard(node.path)
            except Exception as e:
                errors.append(f"{node.path}: {e}")

            if (i + 1) % 50 == 0:
                self.status_var.set(f"Deleting... {i + 1}/{total}")
                self.root.update_idletasks()

        self._del_btn.config(state='normal')

        # 汇总结果
        blocked_count = len(blocked)
        summary_parts = [f"Deleted: {deleted}/{total}"]
        if errors:
            summary_parts.append(f"Failed: {len(errors)}")
        if blocked_count:
            summary_parts.append(f"Blocked: {blocked_count}")

        if errors:
            err_detail = "\n".join(errors[:15])
            InfoDialog(self.root, "Partial Failure",
                       ", ".join(summary_parts) + "\n\n" + err_detail,
                       msg_color=C["orange"])
        else:
            InfoDialog(self.root, "Done", ", ".join(summary_parts),
                       msg_color=C["green"])

        self.status_var.set(
            f"Deleted {deleted}/{total}" +
            (f", failed {len(errors)}" if errors else "") +
            (f", blocked {blocked_count}" if blocked_count else ""))
        self._page = 0
        self._render()

    # ══════════════════════════════════════════════════════
    #  导出
    # ══════════════════════════════════════════════════════

    def _export(self, fmt):
        if not self.result:
            messagebox.showwarning("Warning", "Please scan first")
            return
        r = self.result
        ext = "json" if fmt == "json" else "csv"
        path = filedialog.asksaveasfilename(
            title="Export", defaultextension=f".{ext}",
            filetypes=[("CSV", "*.csv"), ("JSON", "*.json")],
            initialfile=f"disk_scan.{ext}")
        if not path:
            return
        try:
            if fmt == "json":
                def to_dict(n):
                    b = {"name": n.name, "path": n.path, "size": n.size,
                         "size_human": format_size(n.size), "modified": _fmt_time(n.modified)}
                    if isinstance(n, FileNode):
                        b["type"] = "file"; b["extension"] = n.extension
                    else:
                        b["type"] = "directory"
                        b["file_count"] = n.file_count; b["dir_count"] = n.dir_count
                    return b
                data = {
                    "summary": {"total_size": r.total_size,
                                 "total_size_human": format_size(r.total_size),
                                 "total_files": r.total_files, "total_dirs": r.total_dirs},
                    "directories": [to_dict(d) for d in sort_nodes(r.all_dirs, "size-desc")],
                    "files": [to_dict(f) for f in sort_nodes(r.all_files, "size-desc")],
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["Type", "Name", "Path", "Size(bytes)", "Size", "Modified"])
                    for n in sort_nodes(r.all_dirs, "size-desc"):
                        w.writerow(["Dir", n.name, n.path, n.size, format_size(n.size), _fmt_time(n.modified)])
                    for n in sort_nodes(r.all_files, "size-desc"):
                        w.writerow(["File", n.name, n.path, n.size, format_size(n.size), _fmt_time(n.modified)])
            messagebox.showinfo("Export OK", f"Saved to:\n{path}")
            self.status_var.set(f"Exported: {path}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def _clear_tree(self):
        for c in self.tree.get_children():
            self.tree.delete(c)
        self.item_map.clear()
        self._checked_paths.clear()

    def run(self):
        self.root.mainloop()


# ── 工具函数 ──

def _fmt_time(ts):
    if not ts or ts == 0:
        return "N/A"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "N/A"


def main():
    app = ScannerApp()
    app.run()


if __name__ == '__main__':
    main()



