#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_base.py — PyQt5 平台无关的公共组件和工具函数
包含 RoundButton、StatCard、ConfirmDialog、InfoDialog、fmt_time
"""

from PyQt5.QtWidgets import (
    QPushButton, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy, QTextEdit,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFontMetrics


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
        dlg.resize(900, 600)
        dlg.setMinimumSize(700, 450)
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
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
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
                padding: 6px 10px;
                border: none;
                border-bottom: 1px solid {C['border']};
                font-weight: bold;
            }}
        """)
        table.setRowCount(len(items))
        path_items = []
        for i, (lbl, detail) in enumerate(items):
            path_text = str(detail[0])
            type_item = QTableWidgetItem(lbl)
            path_item = QTableWidgetItem(path_text)
            path_item.setToolTip(path_text)
            size_item = QTableWidgetItem(str(detail[1]))
            table.setItem(i, 0, type_item)
            table.setItem(i, 1, path_item)
            table.setItem(i, 2, size_item)
            path_items.append((i, path_text, path_item))
        table.setColumnWidth(0, 70)
        table.setColumnWidth(2, 130)

        # Path 列省略显示（需在布局确定后计算）
        table.resizeColumnsToContents()
        fm = QFontMetrics(table.font())
        col_width = table.columnWidth(1)
        for i, path_text, path_item in path_items:
            max_width = max(col_width - 20, 100)
            elided = fm.elidedText(path_text, Qt.ElideMiddle, max_width)
            path_item.setText(elided)

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
    """信息对话框（支持结果统计和错误详情展示）"""

    def __init__(self, parent, title, message, msg_color=None):
        if _DIALOG_AUTO_DISMISS:
            self.win = None
            return

        C, F_BTN, _, F_SMALL, F_BODY, _ = _get_theme()

        dlg = QDialog(parent)
        dlg.setWindowTitle(title)
        dlg.resize(600, 400)
        dlg.setMinimumSize(500, 350)
        self.win = dlg

        # 解析消息
        summary, details = self._parse_message(message)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 内容区域
        content = QFrame()
        content.setStyleSheet(f"background-color: {C['bg']};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 24, 30, 20)
        content_layout.setSpacing(16)

        # 图标 + 标题
        icon_map = {
            "Done": ("\u2713", C["green"]),
            "Partial Failure": ("\u26A0", C["orange"]),
        }
        icon_char, icon_color = icon_map.get(title, ("\u2139", msg_color or C["accent"]))

        title_frame = QFrame()
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(12)

        icon_lbl = QLabel(icon_char)
        icon_lbl.setStyleSheet(
            f"color: {icon_color}; font-size: 28pt; font-weight: bold;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setMinimumWidth(40)

        title_text = QLabel(title)
        title_text.setStyleSheet(
            f"color: {icon_color}; font-size: 16pt; font-weight: bold;")

        title_layout.addWidget(icon_lbl)
        title_layout.addWidget(title_text)
        title_layout.addStretch()
        content_layout.addWidget(title_frame)

        # 统计卡片区域
        if summary:
            cards_frame = QFrame()
            cards_frame.setStyleSheet("background: transparent;")
            cards_layout = QHBoxLayout(cards_frame)
            cards_layout.setContentsMargins(0, 0, 0, 0)
            cards_layout.setSpacing(12)

            for stat in summary:
                card = self._create_stat_card(
                    cards_frame, stat["label"], stat["value"],
                    stat.get("color", C["text"]))
                cards_layout.addWidget(card)

            cards_layout.addStretch()
            content_layout.addWidget(cards_frame)

        # 错误详情
        if details:
            details_label = QLabel("Error Details:")
            details_label.setStyleSheet(
                f"color: {C['text2']}; font-size: 10pt; font-weight: bold;")
            content_layout.addWidget(details_label)

            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText(details)
            text_edit.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {C['surface']};
                    color: {C['text']};
                    border: 1px solid {C['border']};
                    border-radius: 6px;
                    padding: 8px;
                    font-family: Consolas, monospace;
                    font-size: 9pt;
                }}
            """)
            content_layout.addWidget(text_edit, stretch=1)

        content_layout.addStretch()
        layout.addWidget(content, stretch=1)

        # 按钮栏
        btn_bar = QFrame()
        btn_bar.setStyleSheet(
            f"background-color: {C['surface']}; padding: 14px;")
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.addStretch()
        ok_btn = RoundButton(
            btn_bar, "OK", lambda: dlg.accept(),
            bg=C["accent"], fg="#ffffff", hover_bg="#79c0ff")
        btn_layout.addWidget(ok_btn)
        layout.addWidget(btn_bar)

        dlg.setStyleSheet(f"QDialog {{ background-color: {C['bg']}; }}")
        dlg.exec_()

    def _parse_message(self, message):
        """解析 message，返回 (summary_list, details_str)"""
        parts = message.split("\n\n", 1)
        summary_text = parts[0].strip()
        details = parts[1] if len(parts) > 1 else None

        C, _ = _get_theme()[:2] if _get_theme() else ({}, None)

        summary = []
        import re
        for match in re.finditer(r'(\w+):\s*([^\s,]+)', summary_text):
            label, value = match.group(1), match.group(2)
            if "Deleted" in label:
                color = C.get("green", "#107c10")
            elif "Failed" in label:
                color = C.get("red", "#d13438")
            elif "Blocked" in label:
                color = C.get("orange", "#ca5010")
            else:
                color = C.get("text", "#1a1a1a")
            summary.append({"label": label, "value": value, "color": color})

        return summary, details

    def _create_stat_card(self, parent, label, value, color):
        """创建统计卡片"""
        C = _get_theme()[0]
        card = QFrame(parent)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {C['surface']};
                border-radius: 8px;
                border: 1px solid {C['border']};
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(
            f"color: {color}; font-size: 20pt; font-weight: bold;")
        val_lbl.setAlignment(Qt.AlignCenter)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {C['text2']}; font-size: 9pt;")
        lbl.setAlignment(Qt.AlignCenter)

        layout.addWidget(val_lbl)
        layout.addWidget(lbl)
        return card


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
