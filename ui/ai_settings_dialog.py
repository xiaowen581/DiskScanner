#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/ai_settings_dialog.py — AI 分析设置对话框
提供 base_url、api_key、model 等配置界面
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QCheckBox, QSpinBox, QFrame,
)
from PyQt5.QtCore import Qt

from ai.config import AIConfig


class AISettingsDialog:
    """AI 分析设置对话框"""

    def __init__(self, parent, config: AIConfig = None):
        self._config = config or AIConfig.instance()
        self.result = False
        self._build_and_show(parent)

    def _build_and_show(self, parent):
        from ui._base import RoundButton, _DIALOG_AUTO_DISMISS
        if _DIALOG_AUTO_DISMISS:
            self.result = True
            self.win = None
            return

        from ui.theme import C, make_font, F_BTN, F_SMALL, F_BODY, F_TINY

        dlg = QDialog(parent)
        dlg.setWindowTitle("AI Analysis Settings")
        dlg.resize(520, 420)
        dlg.setMinimumSize(480, 380)
        self.win = dlg

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ──
        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {C['surface']}; padding: 16px;")
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setSpacing(4)

        title_lbl = QLabel("AI Analysis Settings")
        title_lbl.setStyleSheet(f"color: {C['accent']}; font-size: 14pt; font-weight: bold;")
        hdr_layout.addWidget(title_lbl)

        desc_lbl = QLabel("Configure OpenAI API settings for file analysis")
        desc_lbl.setStyleSheet(f"color: {C['text2']}; font-size: 9pt;")
        hdr_layout.addWidget(desc_lbl)

        layout.addWidget(hdr)

        # ── Content ──
        content = QFrame()
        content.setStyleSheet(f"background-color: {C['bg']};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 16)
        content_layout.setSpacing(14)

        # API Base URL
        url_row = self._create_field(
            content, "API Base URL",
            "Leave empty for default OpenAI endpoint",
            self._config.base_url
        )
        self._url_entry = url_row[1]
        content_layout.addWidget(url_row[0])

        # API Key
        key_row = self._create_field(
            content, "API Key",
            "sk-... or your custom API key",
            self._config.api_key,
            echo_mode=QLineEdit.Password
        )
        self._key_entry = key_row[1]
        content_layout.addWidget(key_row[0])

        # Model
        model_row = self._create_field(
            content, "Model",
            "e.g. gpt-4o-mini, gpt-4o",
            self._config.model
        )
        self._model_entry = model_row[1]
        content_layout.addWidget(model_row[0])

        # Options
        options_frame = QFrame()
        options_frame.setStyleSheet("background: transparent;")
        options_layout = QVBoxLayout(options_frame)
        options_layout.setContentsMargins(0, 8, 0, 0)
        options_layout.setSpacing(8)

        self._auto_cb = QCheckBox("Auto-analyze after scan")
        self._auto_cb.setChecked(self._config.auto_analyze)
        self._auto_cb.setFont(make_font(F_SMALL))
        options_layout.addWidget(self._auto_cb)

        self._cache_cb = QCheckBox("Enable disk cache")
        self._cache_cb.setChecked(self._config.cache_enabled)
        self._cache_cb.setFont(make_font(F_SMALL))
        options_layout.addWidget(self._cache_cb)

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
        content_layout.addStretch()
        layout.addWidget(content, stretch=1)

        # ── Button bar ──
        btn_bar = QFrame()
        btn_bar.setStyleSheet(f"background-color: {C['surface']}; padding: 14px;")
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.addStretch()

        cancel_btn = RoundButton(btn_bar, "Cancel", lambda: dlg.reject(),
                                  bg=C["btn_bg"], fg=C["text"])
        btn_layout.addWidget(cancel_btn)

        save_btn = RoundButton(btn_bar, "Save", lambda: self._save(dlg),
                                bg=C["accent"], fg="#ffffff", hover_bg="#79c0ff")
        btn_layout.addWidget(save_btn)

        layout.addWidget(btn_bar)

        dlg.setStyleSheet(f"QDialog {{ background-color: {C['bg']}; }}")
        self.result = (dlg.exec_() == QDialog.Accepted)

    def _save(self, dlg):
        """保存配置"""
        self._config.base_url = self._url_entry.text().strip()
        self._config.api_key = self._key_entry.text().strip()
        self._config.model = self._model_entry.text().strip() or "gpt-4o-mini"
        self._config.auto_analyze = self._auto_cb.isChecked()
        self._config.cache_enabled = self._cache_cb.isChecked()
        self._config.max_concurrent = self._conc_spin.value()
        self._config.save()
        dlg.accept()

    @staticmethod
    def _create_field(parent, label_text, placeholder, value="",
                      echo_mode=QLineEdit.Normal):
        """创建标签 + 输入框行"""
        from ui.theme import C, make_font, F_TINY, F_MONO

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

        return frame, entry
