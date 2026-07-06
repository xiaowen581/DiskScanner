#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/ai_tooltip_widget.py — AI 分析结果浮窗
鼠标悬停文件行时显示 AI 分析结果（作用描述 + 删除建议）
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QCursor


class AIAnalysisPopover(QWidget):
    """AI 分析结果浮窗"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)

        self._apply_style()
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # 标题行: 文件名
        self._title_label = QLabel()
        self._title_label.setWordWrap(True)
        layout.addWidget(self._title_label)

        # 分割线
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {self._C['border']};")
        layout.addWidget(sep)

        # 作用描述
        desc_row = QHBoxLayout()
        desc_row.setSpacing(8)
        desc_icon = QLabel("\u2139")  # ℹ
        desc_icon.setFixedWidth(20)
        desc_icon.setAlignment(Qt.AlignTop)
        desc_icon.setStyleSheet(f"color: {self._C['accent']}; font-size: 11pt; font-weight: bold;")
        desc_row.addWidget(desc_icon)

        self._desc_label = QLabel()
        self._desc_label.setWordWrap(True)
        desc_row.addWidget(self._desc_label, stretch=1)
        layout.addLayout(desc_row)

        # 删除建议
        del_row = QHBoxLayout()
        del_row.setSpacing(8)
        self._del_icon = QLabel()
        self._del_icon.setFixedWidth(20)
        self._del_icon.setAlignment(Qt.AlignTop)
        del_row.addWidget(self._del_icon)

        del_text_wrap = QVBoxLayout()
        del_text_wrap.setSpacing(2)
        self._delete_label = QLabel()
        self._delete_label.setWordWrap(True)
        del_text_wrap.addWidget(self._delete_label)
        self._reason_label = QLabel()
        self._reason_label.setWordWrap(True)
        del_text_wrap.addWidget(self._reason_label)
        del_row.addLayout(del_text_wrap, stretch=1)
        layout.addLayout(del_row)

        layout.addStretch()

    def _apply_style(self):
        """应用主题样式"""
        from ui.theme import C, make_font, F_SMALL, F_BODY, F_TINY
        self._C = C
        self._F_SMALL = F_SMALL
        self._F_BODY = F_BODY
        self._F_TINY = F_TINY

        self.setStyleSheet(f"""
            AIAnalysisPopover {{
                background-color: {C['surface']};
                border: 1px solid {C['border']};
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)

    def show_for_item(self, node, analysis: dict, global_pos: QPoint = None):
        """
        显示某个条目的分析结果

        Args:
            node: FileNode 或 DirNode
            analysis: {"description": "...", "deletability": "safe|caution|unsafe", "reason": "..."}
            global_pos: 全局鼠标位置
        """
        from ui.theme import make_font
        from disk_scanner import DirNode, format_size
        import os

        C = self._C

        # 标题
        is_dir = isinstance(node, DirNode)
        type_str = "\U0001F4C1 DIR" if is_dir else "\U0001F4C4 FILE"  # 📁 / 📄
        name = os.path.basename(node.path) or node.path
        self._title_label.setText(f"{type_str}  {name}")
        self._title_label.setStyleSheet(
            f"color: {C['text']}; font-size: 10pt; font-weight: bold;")
        self._title_label.setToolTip(node.path)

        # 作用描述
        desc = analysis.get('description', '暂无分析')
        self._desc_label.setText(desc)
        self._desc_label.setStyleSheet(f"color: {C['text']}; font-size: 9pt;")

        # 删除建议
        deletability = analysis.get('deletability', 'caution')
        reason = analysis.get('reason', '')

        color_map = {
            'safe': (C['green'], "\u2713", "可安全删除"),      # ✓
            'caution': (C['orange'], "\u26A0", "需谨慎判断"),   # ⚠
            'unsafe': (C['red'], "\u2717", "不建议删除"),       # ✗
        }
        color, icon, label = color_map.get(deletability, (C['orange'], "\u26A0", "需谨慎判断"))

        self._del_icon.setText(icon)
        self._del_icon.setStyleSheet(
            f"color: {color}; font-size: 13pt; font-weight: bold;")

        self._delete_label.setText(label)
        self._delete_label.setStyleSheet(
            f"color: {color}; font-size: 9pt; font-weight: bold;")

        self._reason_label.setText(reason)
        self._reason_label.setStyleSheet(
            f"color: {C['text2']}; font-size: 8pt;")

        # 定位
        if global_pos is None:
            global_pos = QCursor.pos()
        screen_geo = self.screen().availableGeometry() if self.screen() else None
        pos = QPoint(global_pos.x() + 15, global_pos.y() + 15)
        if screen_geo:
            # 确保不超出屏幕
            if pos.x() + self.width() > screen_geo.right():
                pos.setX(global_pos.x() - self.width() - 10)
            if pos.y() + self.height() > screen_geo.bottom():
                pos.setY(global_pos.y() - self.height() - 10)
        self.move(pos)
        self.show()

    def show_loading(self, node, global_pos: QPoint = None):
        """显示加载中状态"""
        from ui.theme import make_font
        from disk_scanner import DirNode
        import os

        C = self._C

        is_dir = isinstance(node, DirNode)
        type_str = "\U0001F4C1 DIR" if is_dir else "\U0001F4C4 FILE"
        name = os.path.basename(node.path) or node.path
        self._title_label.setText(f"{type_str}  {name}")
        self._title_label.setStyleSheet(
            f"color: {C['text']}; font-size: 10pt; font-weight: bold;")

        self._desc_label.setText("AI 分析中...")
        self._desc_label.setStyleSheet(
            f"color: {C['text3']}; font-size: 9pt; font-style: italic;")

        self._del_icon.setText("\u23F3")  # ⏳
        self._del_icon.setStyleSheet(
            f"color: {C['text3']}; font-size: 13pt;")
        self._delete_label.setText("等待分析结果")
        self._delete_label.setStyleSheet(
            f"color: {C['text3']}; font-size: 9pt;")
        self._reason_label.setText("")

        if global_pos is None:
            global_pos = QCursor.pos()
        pos = QPoint(global_pos.x() + 15, global_pos.y() + 15)
        self.move(pos)
        self.show()

    def hide_popover(self):
        """隐藏浮窗"""
        self.hide()
