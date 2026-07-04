#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_theme_dark.py — Linux 深色主题 (GitHub Dark / VS Code 风格)
"""

import platform
import subprocess
from tkinter import ttk


# ── 字体检测 (Linux) ──

def detect_font_linux():
    """使用 fc-list 检测 Linux 中文字体"""
    try:
        r = subprocess.run(['fc-list', ':lang=zh', 'family'],
                           capture_output=True, text=True, timeout=3)
        for name in ("Noto Sans CJK SC", "WenQuanYi Micro Hei", "Microsoft YaHei"):
            if name in r.stdout:
                return name
    except Exception:
        pass
    return "sans-serif"

_CN = detect_font_linux()


# ── 调色板 — 现代深色 ──

C = {
    "bg":         "#0d1117",
    "surface":    "#161b22",
    "surface2":   "#1c2128",
    "border":     "#30363d",
    "border2":    "#21262d",
    "input_bg":   "#0d1117",
    "text":       "#e6edf3",
    "text2":      "#8b949e",
    "text3":      "#484f58",
    "accent":     "#58a6ff",
    "green":      "#3fb950",
    "red":        "#f85149",
    "orange":     "#d29922",
    "purple":     "#bc8cff",
    "cyan":       "#79c0ff",
    "tree_bg":    "#0d1117",
    "tree_row1":  "#0d1117",
    "tree_row2":  "#161b22",
    "tree_head":  "#161b22",
    "tree_sel":   "#1f6feb33",
    "btn_bg":     "#21262d",
    "btn_hover":  "#30363d",
    # 勾选行高亮色
    "checked_odd":  "#1a2a40",
    "checked_even": "#162538",
}


# ── 字体常量 ──

F_TITLE = (_CN, 16, "bold")
F_SUB   = (_CN, 10)
F_BODY  = (_CN, 10)
F_SMALL = (_CN, 9)
F_TINY  = (_CN, 8)
F_BIG   = (_CN, 20, "bold")
F_STAT  = (_CN, 13, "bold")
F_MONO  = ("Consolas", 10) if platform.system() == "Windows" else ("Monospace", 10)
F_BTN   = (_CN, 9, "bold")


# ══════════════════════════════════════════════════════════
#  ttk 样式初始化
# ══════════════════════════════════════════════════════════

def setup_styles(style):
    """配置所有 ttk 样式（深色版）"""
    s = style
    c = C

    # Scanner Treeview
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

    # Docker Treeview
    s.configure('Docker.Treeview',
                 background=c["tree_bg"], foreground=c["text"],
                 fieldbackground=c["tree_bg"], font=F_BODY,
                 rowheight=28, borderwidth=0)
    s.configure('Docker.Treeview.Heading',
                 background=c["tree_head"], foreground=c["text2"],
                 font=F_BTN, relief='flat', padding=(8, 5))
    s.map('Docker.Treeview',
          background=[('selected', c["tree_sel"])],
          foreground=[('selected', c["accent"])])

    # Progressbar
    s.configure('Scan.Horizontal.TProgressbar',
                 troughcolor=c["surface"], background=c["accent"],
                 borderwidth=0, thickness=4)

    # Separator
    s.configure('Dark.TSeparator', background=c["border"])

    # Notebook (主标签页)
    s.configure('Dark.TNotebook', background=c["bg"], borderwidth=0)
    s.configure('Dark.TNotebook.Tab',
                 background=c["surface"], foreground=c["text2"],
                 padding=[16, 8], font=F_BTN)
    s.map('Dark.TNotebook.Tab',
          background=[('selected', c["bg"])],
          foreground=[('selected', c["accent"])])

    # Sub-Notebook (Docker 子标签页)
    s.configure('Sub.TNotebook', background=c["bg"], borderwidth=0)
    s.configure('Sub.TNotebook.Tab',
                 background=c["surface2"], foreground=c["text2"],
                 padding=[12, 6], font=F_SMALL)
    s.map('Sub.TNotebook.Tab',
          background=[('selected', c["bg"])],
          foreground=[('selected', c["cyan"])])
