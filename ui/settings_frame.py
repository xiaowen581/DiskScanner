#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/settings_frame.py — Settings 标签页 (PyQt5 版本)
内嵌 AI 分析配置，替代模态对话框
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QCheckBox, QSpinBox, QFrame, QScrollArea,
)
from PyQt5.QtCore import Qt

from ai.config import AIConfig
from ui.theme import (
    C, F_SMALL, F_TINY, F_MONO, F_BTN,
    RoundButton, make_font,
)


class SettingsFrame(QWidget):
    """Settings 标签页 — 包含 AI 分析配置"""

    def __init__(self, parent, config: AIConfig = None):
        super().__init__(parent)
        self._config = config or AIConfig.instance()
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ──
        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {C['surface']}; padding: 16px;")
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setSpacing(4)

        title_lbl = QLabel("Settings")
        title_lbl.setStyleSheet(f"color: {C['accent']}; font-size: 14pt; font-weight: bold;")
        hdr_layout.addWidget(title_lbl)

        desc_lbl = QLabel("Configure application settings")
        desc_lbl.setStyleSheet(f"color: {C['text2']}; font-size: 9pt;")
        hdr_layout.addWidget(desc_lbl)

        outer.addWidget(hdr)

        # ── Scrollable content ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet(f"background-color: {C['bg']};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 16)
        content_layout.setSpacing(20)

        # ── AI Analysis 区域标题 ──
        section_lbl = QLabel("AI Analysis")
        section_lbl.setStyleSheet(
            f"color: {C['accent']}; font-size: 11pt; font-weight: bold;")
        content_layout.addWidget(section_lbl)

        section_line = QFrame()
        section_line.setFrameShape(QFrame.HLine)
        section_line.setStyleSheet(f"color: {C['border']};")
        section_line.setMaximumHeight(1)
        content_layout.addWidget(section_line)

        # ── API 配置字段 ──
        self._url_entry = self._create_field(
            content_layout, "API Base URL",
            "Leave empty for default OpenAI endpoint",
            self._config.base_url
        )

        self._key_entry = self._create_field(
            content_layout, "API Key",
            "sk-... or your custom API key",
            self._config.api_key,
            echo_mode=QLineEdit.Password
        )

        self._model_entry = self._create_field(
            content_layout, "Model",
            "e.g. gpt-4o-mini, gpt-4o",
            self._config.model
        )

        # ── 选项区 ──
        options_frame = QFrame()
        options_frame.setStyleSheet("background: transparent;")
        options_layout = QVBoxLayout(options_frame)
        options_layout.setContentsMargins(0, 4, 0, 0)
        options_layout.setSpacing(8)

        opt_title = QLabel("Options")
        opt_title.setStyleSheet(
            f"color: {C['text']}; font-size: 10pt; font-weight: bold;")
        options_layout.addWidget(opt_title)

        self._auto_cb = QCheckBox("Auto-analyze after scan")
        self._auto_cb.setChecked(self._config.auto_analyze)
        self._auto_cb.setFont(make_font(F_SMALL))
        options_layout.addWidget(self._auto_cb)

        self._cache_cb = QCheckBox("Enable disk cache")
        self._cache_cb.setChecked(self._config.cache_enabled)
        self._cache_cb.setFont(make_font(F_SMALL))
        options_layout.addWidget(self._cache_cb)

        self._replay_cb = QCheckBox("Enable replay (save/load AI results for debugging)")
        self._replay_cb.setChecked(self._config.replay_enabled)
        self._replay_cb.setFont(make_font(F_SMALL))
        options_layout.addWidget(self._replay_cb)

        self._think_cb = QCheckBox("Enable thinking mode (deepseek-r1 etc.)")
        self._think_cb.setChecked(self._config.think_enabled)
        self._think_cb.setFont(make_font(F_SMALL))
        options_layout.addWidget(self._think_cb)

        # Max concurrent
        conc_row = QHBoxLayout()
        conc_lbl = QLabel("Max concurrent pages:")
        conc_lbl.setFont(make_font(F_SMALL))
        conc_row.addWidget(conc_lbl)
        self._conc_spin = QSpinBox()
        self._conc_spin.setRange(1, 10)
        self._conc_spin.setValue(self._config.max_concurrent)
        self._conc_spin.setFont(make_font(F_SMALL))
        self._conc_spin.setFixedWidth(60)
        conc_row.addWidget(self._conc_spin)
        conc_row.addStretch()
        options_layout.addLayout(conc_row)

        content_layout.addWidget(options_frame)

        # ── Save 按钮行 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._save_btn = RoundButton(
            content, "Save", self._save_settings,
            bg=C["accent"], fg="#ffffff", hover_bg="#79c0ff"
        )
        btn_row.addWidget(self._save_btn)
        content_layout.addLayout(btn_row)

        # ── 状态提示 ──
        self._status_label = QLabel("")
        self._status_label.setFont(make_font(F_SMALL))
        self._status_label.setStyleSheet(f"color: {C['green']};")
        content_layout.addWidget(self._status_label)

        content_layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    def _save_settings(self):
        """保存配置到 settings.json"""
        self._config.base_url = self._url_entry.text().strip()
        self._config.api_key = self._key_entry.text().strip()
        self._config.model = self._model_entry.text().strip() or "gpt-4o-mini"
        self._config.auto_analyze = self._auto_cb.isChecked()
        self._config.cache_enabled = self._cache_cb.isChecked()
        self._config.replay_enabled = self._replay_cb.isChecked()
        self._config.think_enabled = self._think_cb.isChecked()
        self._config.max_concurrent = self._conc_spin.value()
        self._config.save()
        self._status_label.setText("✓ Settings saved")
        # 3 秒后清除提示
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self._status_label.setText(""))

    def reload_settings(self):
        """从 AIConfig 重新加载当前值到界面"""
        self._url_entry.setText(self._config.base_url)
        self._key_entry.setText(self._config.api_key)
        self._model_entry.setText(self._config.model)
        self._auto_cb.setChecked(self._config.auto_analyze)
        self._cache_cb.setChecked(self._config.cache_enabled)
        self._replay_cb.setChecked(self._config.replay_enabled)
        self._think_cb.setChecked(self._config.think_enabled)
        self._conc_spin.setValue(self._config.max_concurrent)

    @staticmethod
    def _create_field(parent_layout, label_text, placeholder, value="",
                      echo_mode=QLineEdit.Normal):
        """创建标签 + 输入框行，添加到 parent_layout，返回 QLineEdit"""
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        row = QVBoxLayout(frame)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        lbl = QLabel(label_text)
        lbl.setFont(make_font(F_TINY))
        lbl.setStyleSheet(f"color: {C['text2']}; font-weight: bold;")
        row.addWidget(lbl)

        entry = QLineEdit(value)
        entry.setFont(make_font(F_MONO))
        entry.setPlaceholderText(placeholder)
        entry.setEchoMode(echo_mode)
        row.addWidget(entry)

        parent_layout.addWidget(frame)
        return entry
