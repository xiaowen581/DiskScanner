#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
theme.py — 公共设计系统门面
自动检测平台，选择对应主题，re-export 所有公共 API

Linux / macOS → _theme_dark  (深色 GitHub Dark 风格)
Windows       → _theme_light (浅色 Fluent Design 风格)
"""

import platform as _platform

# ── 平台自动选择主题 ──

if _platform.system() == "Windows":
    from ui._theme_light import (
        C, F_TITLE, F_SUB, F_BODY, F_SMALL, F_TINY,
        F_BIG, F_STAT, F_MONO, F_BTN, setup_styles,
    )
else:
    from ui._theme_dark import (
        C, F_TITLE, F_SUB, F_BODY, F_SMALL, F_TINY,
        F_BIG, F_STAT, F_MONO, F_BTN, setup_styles,
    )

# ── 平台无关的公共组件和工具 ──

from ui._base import (
    _DIALOG_AUTO_DISMISS,
    RoundButton,
    StatCard,
    ConfirmDialog,
    InfoDialog,
    fmt_time,
)
