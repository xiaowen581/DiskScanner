#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_theme_dark.py — Linux 深色主题 (GitHub Dark / VS Code 风格)
PyQt5 版本 — 仅提供颜色字典和字体常量，QSS 由 theme.py 统一生成
"""

import platform


# ── 字体检测 (Linux) ──

def detect_font_linux():
    """检测 Linux 中文字体"""
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
    "tree_sel":   "#1f6feb",
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
