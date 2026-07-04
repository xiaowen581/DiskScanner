#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
theme.py — 公共设计系统门面 (PyQt5 版本)
自动检测平台，选择对应主题，生成 QSS 样式表，re-export 所有公共 API
"""

import platform as _platform
from PyQt5.QtGui import QFont


# ── 平台自动选择主题 ──

if _platform.system() == "Windows":
    from ui._theme_light import (
        C, F_TITLE, F_SUB, F_BODY, F_SMALL, F_TINY,
        F_BIG, F_STAT, F_MONO, F_BTN,
    )
else:
    from ui._theme_dark import (
        C, F_TITLE, F_SUB, F_BODY, F_SMALL, F_TINY,
        F_BIG, F_STAT, F_MONO, F_BTN,
    )


# ── 字体转换工具 ──

def make_font(font_tuple):
    """将 (family, size, [weight]) 元组转换为 QFont 对象"""
    family = font_tuple[0]
    size = font_tuple[1]
    bold = len(font_tuple) > 2 and "bold" in font_tuple[2:]
    f = QFont(family, size)
    f.setBold(bold)
    return f


# ── QSS 样式表模板 ──

QSS_TEMPLATE = """
/* ── 全局 ── */
QMainWindow, QDialog {
    background-color: %(bg)s;
    color: %(text)s;
}
QWidget {
    color: %(text)s;
}

/* ── 标签页 QTabWidget ── */
QTabWidget::pane {
    border: none;
    background: %(bg)s;
}
QTabBar::tab {
    background: %(surface)s;
    color: %(text2)s;
    padding: 8px 16px;
    border: none;
    min-width: 80px;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 8pt;
}
QTabBar::tab:selected {
    background: %(bg)s;
    color: %(accent)s;
    border-bottom: 2px solid %(accent)s;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background: %(surface2)s;
}

/* Docker 子标签页 (使用 objectName 区分) */
QTabWidget#dockerTabs QTabBar::tab {
    background: %(surface2)s;
    color: %(text2)s;
    padding: 6px 12px;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 10pt;
}
QTabWidget#dockerTabs QTabBar::tab:selected {
    background: %(bg)s;
    color: %(cyan)s;
    border-bottom: 2px solid %(cyan)s;
    font-weight: bold;
}

/* ── 表格 QTableWidget ── */
QTableWidget {
    background-color: %(tree_bg)s;
    alternate-background-color: %(tree_row2)s;
    color: %(text)s;
    gridline-color: %(border)s;
    border: 1px solid %(border)s;
    selection-background-color: %(tree_sel)s;
    selection-color: %(accent)s;
    font-size: 10pt;
}
QTableWidget::item {
    padding: 4px 6px;
    border: none;
}
QTableWidget::item:selected {
    background-color: %(tree_sel)s;
    color: %(accent)s;
}

/* 表头 */
QHeaderView::section {
    background-color: %(tree_head)s;
    color: %(text2)s;
    padding: 5px 8px;
    border: none;
    border-right: 1px solid %(border)s;
    border-bottom: 1px solid %(border)s;
    font-weight: bold;
    font-size: 9pt;
}

/* ── 按钮 QPushButton ── */
QPushButton {
    background-color: %(btn_bg)s;
    color: %(text)s;
    border: none;
    border-radius: 6px;
    padding: 5px 14px;
    font-weight: bold;
    font-size: 9pt;
}
QPushButton:hover {
    background-color: %(btn_hover)s;
}
QPushButton:pressed {
    background-color: %(border)s;
}
QPushButton:disabled {
    background-color: %(surface2)s;
    color: %(text3)s;
}

/* 强调按钮 (objectName=accentBtn) */
QPushButton#accentBtn {
    background-color: %(accent)s;
    color: #ffffff;
}
QPushButton#accentBtn:hover {
    background-color: #79c0ff;
}

/* 危险按钮 (objectName=dangerBtn) */
QPushButton#dangerBtn {
    background-color: #da3633;
    color: #ffffff;
}
QPushButton#dangerBtn:hover {
    background-color: #f85149;
}

/* 警告按钮 (objectName=warnBtn) */
QPushButton#warnBtn {
    background-color: %(orange)s;
    color: #ffffff;
}
QPushButton#warnBtn:hover {
    background-color: #e6b800;
}

/* ── 输入框 QLineEdit ── */
QLineEdit {
    background-color: %(input_bg)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: %(accent)s;
    selection-color: #ffffff;
}
QLineEdit:focus {
    border-color: %(accent)s;
}

/* ── 复选框 QCheckBox ── */
QCheckBox {
    color: %(text3)s;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid %(border)s;
    background: %(input_bg)s;
}
QCheckBox::indicator:checked {
    background: %(accent)s;
    border-color: %(accent)s;
}

/* ── 进度条 QProgressBar ── */
QProgressBar {
    background-color: %(surface)s;
    border: none;
    border-radius: 2px;
    text-align: center;
    color: transparent;
    max-height: 4px;
}
QProgressBar::chunk {
    background-color: %(accent)s;
    border-radius: 2px;
}

/* ── 右键菜单 QMenu ── */
QMenu {
    background-color: %(surface)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    padding: 4px 0px;
}
QMenu::item {
    padding: 6px 24px;
}
QMenu::item:selected {
    background-color: %(accent)s;
    color: white;
}
QMenu::separator {
    height: 1px;
    background: %(border)s;
    margin: 4px 8px;
}

/* ── 滚动条 QScrollBar ── */
QScrollBar:vertical {
    background: %(bg)s;
    width: 10px;
    border: none;
}
QScrollBar::handle:vertical {
    background: %(border)s;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: %(text3)s;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: %(bg)s;
    height: 10px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: %(border)s;
    border-radius: 5px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: %(text3)s;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ── QLabel ── */
QLabel {
    color: %(text)s;
    background: transparent;
}

/* ── 分割线 QFrame[frameShape=4/5] ── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: %(border)s;
}

/* ── 对话框 ── */
QDialog {
    background-color: %(bg)s;
}
"""

# 用当前主题的 C 字典格式化 QSS
QSS = QSS_TEMPLATE % C


# ── 平台无关的公共组件和工具 ──

from ui._base import (
    _DIALOG_AUTO_DISMISS,
    RoundButton,
    StatCard,
    ConfirmDialog,
    InfoDialog,
    fmt_time,
)
