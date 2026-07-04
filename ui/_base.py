#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_base.py — PyQt5 平台无关的公共组件和工具函数
包含 RoundButton、StatCard、ConfirmDialog、InfoDialog、fmt_time
"""

from PyQt5.QtWidgets import (
    QPushButton, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


# ── 测试模式：设为 True 时对话框自动跳过，不弹窗 ──
_DIALOG_AUTO_DISMISS = False


# ── 延迟获取当前主题（避免循环导入） ──

def _get_theme():
    """延迟导入当前活动主题，返回 (C, F_BTN, F_BIG, F_SMALL, F_BODY, F_TINY)"""
    from ui.theme import C, F_BTN, F_BIG, F_SMALL, F_BODY, F_TINY
    return C, F_BTN, F_BIG, F_SMALL, F_BODY, F_TINY


# ══════════════════════════════════════════════════════════
#  自定义按钮 (QPushButton + QSS)
# ══════════════════════════════════════════════════════════

class RoundButton(QPushButton):
    """带圆角和悬停效果的按钮"""
    def __init__(self, parent, text, command, bg=None, fg=None,
                 hover_bg=None, radius=6, padx=14, pady=5, font=None, **kw):
        super().__init__(text, parent)
        C, F_BTN, *_ = _get_theme()
        if font is None:
            font = F_BTN

        self._bg = bg or C["btn_bg"]
        self._fg = fg or C["text"]
        self._hover = hover_bg or C["btn_hover"]
        self._radius = radius
        self._padx = padx
        self._pady = pady

        self.clicked.connect(command)
        self._apply_style()

        from ui.theme import make_font
        self.setFont(make_font(font))

    def _apply_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._bg};
                color: {self._fg};
                border: none;
                border-radius: {self._radius}px;
                padding: {self._pady}px {self._padx}px;
            }}
            QPushButton:hover {{
                background-color: {self._hover};
            }}
            QPushButton:pressed {{
                background-color: {self._hover};
            }}
            QPushButton:disabled {{
                background-color: #44444444;
                color: #88888888;
            }}
        """)

    def config(self, bg=None, fg=None, **kw):
        if bg:
            self._bg = bg
        if fg:
            self._fg = fg
        self._apply_style()
        if 'state' in kw:
            self.setEnabled(kw['state'] != 'disabled')
        if 'text' in kw:
            self.setText(kw['text'])


# ══════════════════════════════════════════════════════════
#  统计卡片
# ══════════════════════════════════════════════════════════

class StatCard(QFrame):
    def __init__(self, parent, label, color=None, **kw):
        super().__init__(parent)
        C, _, F_BIG, F_SMALL, *_ = _get_theme()
        if color is None:
            color = C["text"]

        self.setStyleSheet(
            f"StatCard {{ background-color: {C['surface']}; border-radius: 8px; }}"
            f"QLabel {{ background: transparent; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        self._val = QLabel("--")
        self._val.setStyleSheet(f"color: {color}; font-size: 20pt; font-weight: bold;")
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color: {C['text2']}; font-size: 9pt;")

        layout.addWidget(self._val)
        layout.addWidget(self._lbl)

    def set_value(self, val):
        self._val.setText(str(val))


# ══════════════════════════════════════════════════════════
#  自定义对话框
# ══════════════════════════════════════════════════════════

class ConfirmDialog:
    """确认对话框"""

    def __init__(self, parent, title, summary, items, confirm_text="Delete",
                 confirm_bg="#da3633", confirm_hover="#f85149"):
        if _DIALOG_AUTO_DISMISS:
            self.result = True
            self.win = None
            return

        C, F_BTN, _, F_SMALL, F_BODY, _ = _get_theme()

        dlg = QDialog(parent)
        dlg.setWindowTitle(title)
        dlg.resize(700, 520)
        dlg.setMinimumSize(500, 380)
        self.win = dlg

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {C['surface']}; padding: 14px;")
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setSpacing(6)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {C['red']}; font-size: 14pt; font-weight: bold;")
        summary_lbl = QLabel(summary)
        summary_lbl.setStyleSheet(f"color: {C['text2']}; font-size: 9pt;")
        summary_lbl.setWordWrap(True)
        hdr_layout.addWidget(title_lbl)
        hdr_layout.addWidget(summary_lbl)
        layout.addWidget(hdr)

        # Table
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Type", "Path", "Size"])
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {C['bg']};
                alternate-background-color: {C['tree_row2']};
                color: {C['text']};
                gridline-color: {C['border']};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {C['tree_head']};
                color: {C['text2']};
                padding: 5px 8px;
                border: none;
                border-bottom: 1px solid {C['border']};
            }}
        """)
        table.setRowCount(len(items))
        for i, (lbl, detail) in enumerate(items):
            table.setItem(i, 0, QTableWidgetItem(lbl))
            table.setItem(i, 1, QTableWidgetItem(str(detail[0])))
            table.setItem(i, 2, QTableWidgetItem(str(detail[1])))
        table.setColumnWidth(0, 60)
        table.setColumnWidth(2, 100)

        layout.addWidget(table, stretch=1)

        # Button bar
        btn_bar = QFrame()
        btn_bar.setStyleSheet(f"background-color: {C['surface']}; padding: 14px;")
        btn_layout = QHBoxLayout(btn_bar)
        warn_lbl = QLabel("This cannot be undone!")
        warn_lbl.setStyleSheet(f"color: {C['text3']}; font-size: 9pt;")
        btn_layout.addWidget(warn_lbl)
        btn_layout.addStretch()

        cancel_btn = RoundButton(btn_bar, "Cancel", lambda: dlg.reject(),
                                  bg=C["btn_bg"], fg=C["text"])
        btn_layout.addWidget(cancel_btn)

        confirm_btn = RoundButton(btn_bar, confirm_text, lambda: dlg.accept(),
                                   bg=confirm_bg, fg="#ffffff",
                                   hover_bg=confirm_hover)
        btn_layout.addWidget(confirm_btn)

        layout.addWidget(btn_bar)

        dlg.setStyleSheet(f"QDialog {{ background-color: {C['bg']}; }}")

        self.result = (dlg.exec_() == QDialog.Accepted)


class InfoDialog:
    """信息对话框"""

    def __init__(self, parent, title, message, msg_color=None):
        if _DIALOG_AUTO_DISMISS:
            self.win = None
            return

        C, F_BTN, _, F_SMALL, F_BODY, _ = _get_theme()

        dlg = QDialog(parent)
        dlg.setWindowTitle(title)
        dlg.resize(480, 200)
        dlg.setMinimumSize(350, 150)
        self.win = dlg

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 0)
        layout.setSpacing(10)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {msg_color or C['accent']}; font-size: 13pt; font-weight: bold;")
        msg_lbl = QLabel(message)
        msg_lbl.setStyleSheet(f"color: {C['text']}; font-size: 10pt;")
        msg_lbl.setWordWrap(True)

        layout.addWidget(title_lbl)
        layout.addWidget(msg_lbl)
        layout.addStretch()

        btn_bar = QFrame()
        btn_bar.setStyleSheet(f"background-color: {C['surface']}; padding: 12px;")
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.addStretch()
        ok_btn = RoundButton(btn_bar, "OK", lambda: dlg.accept(),
                              bg=C["accent"], fg="#ffffff", hover_bg="#79c0ff")
        btn_layout.addWidget(ok_btn)
        layout.addWidget(btn_bar)

        dlg.setStyleSheet(f"QDialog {{ background-color: {C['bg']}; }}")

        # 支持 Esc 和 Enter 关闭
        dlg.exec_()


# ══════════════════════════════════════════════════════════
#  时间格式化工具函数
# ══════════════════════════════════════════════════════════

def fmt_time(ts):
    if not ts or ts == 0:
        return "N/A"
    try:
        from datetime import datetime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "N/A"
