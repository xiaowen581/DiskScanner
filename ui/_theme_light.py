#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_theme_light.py — Windows 浅色主题 (Fluent Design / 原生 Windows 风格)
"""

import platform
from tkinter import ttk

# ── 字体检测 (Windows) ──

def detect_font_windows():
    """Windows 字体检测 — 优先 Microsoft YaHei，回退 Segoe UI"""
    try:
        import tkinter as _tk
        import tkinter.font as tkfont
        # 需要临时创建 Tk 实例才能获取字体列表
        _tmp_root = _tk.Tk()
        _tmp_root.withdraw()
        available = tkfont.families()
        _tmp_root.destroy()
        for name in ("Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Segoe UI"):
            if name in available:
                return name
        # 部分匹配
        for name in ("Microsoft YaHei", "SimHei"):
            if any(name in f for f in available):
                return name
    except Exception:
        pass
    return "Segoe UI"

_CN = detect_font_windows()


# ── 调色板 — Windows 浅色 (Fluent Design) ──

C = {
    "bg":         "#f0f0f0",
    "surface":    "#ffffff",
    "surface2":   "#f5f5f5",
    "border":     "#d0d0d0",
    "border2":    "#e0e0e0",
    "input_bg":   "#ffffff",
    "text":       "#1a1a1a",
    "text2":      "#5a5a5a",
    "text3":      "#999999",
    "accent":     "#0078d4",
    "green":      "#107c10",
    "red":        "#d13438",
    "orange":     "#ca5010",
    "purple":     "#881798",
    "cyan":       "#038387",
    "tree_bg":    "#ffffff",
    "tree_row1":  "#ffffff",
    "tree_row2":  "#f5f5f5",
    "tree_head":  "#e8e8e8",
    "tree_sel":   "#cce8ff",
    "btn_bg":     "#e1e1e1",
    "btn_hover":  "#c8c8c8",
    # 勾选行高亮色（浅色主题适配）
    "checked_odd":  "#e3f2fd",
    "checked_even": "#d6ebfa",
}


# ── 字体常量 ──

F_TITLE = (_CN, 16, "bold")
F_SUB   = (_CN, 10)
F_BODY  = (_CN, 10)
F_SMALL = (_CN, 9)
F_TINY  = (_CN, 8)
F_BIG   = (_CN, 20, "bold")
F_STAT  = (_CN, 13, "bold")
F_MONO  = ("Consolas", 10)
F_BTN   = (_CN, 9, "bold")


# ══════════════════════════════════════════════════════════
#  ttk 样式初始化
# ══════════════════════════════════════════════════════════

def setup_styles(style):
    """配置所有 ttk 样式（浅色版）"""
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
