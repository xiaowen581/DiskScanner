#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai/ — DiskScanner AI 辅助分析模块
提供文件/目录的 AI 分析功能（作用描述 + 删除建议）
"""

from ai.config import AIConfig
from ai.client import AIClient, AIError, AINotConfiguredError, AINetworkError, AITimeoutError
from ai.cache import AICache

try:
    from ai.worker import AIWorker
except ImportError:
    AIWorker = None  # type: ignore

__all__ = [
    'AIConfig',
    'AIClient',
    'AICache',
    'AIWorker',
    'AIError',
    'AINotConfiguredError',
    'AINetworkError',
    'AITimeoutError',
]
