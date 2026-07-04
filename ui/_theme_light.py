#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_theme_light.py — Windows 浅色主题 (Fluent Design / 原生 Windows 风格)
PyQt5 版本 — 仅提供颜色字典和字体常量，QSS 由 theme.py 统一生成
"""

import platform


# ── 字体 (Windows) ──
# Windows 上直接使用 Microsoft YaHei UI，无需 QFontDatabase 检测
# （QFontDatabase 需要 QGuiApplication 先创建，不能在模块导入时调用）
_CN = "Microsoft YaHei UI"


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
