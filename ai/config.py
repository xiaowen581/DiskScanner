#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai/config.py — AI 配置管理模块
管理 OpenAI API 的 base_url、api_key、model 等全局设置
配置文件路径: ``%APPDATA%\\DiskScanner\\config\\settings.json``
"""

import os
import json
from typing import Optional


# ── 路径常量 ──

def _get_app_data_dir() -> str:
    """获取应用数据目录"""
    base = os.environ.get('APPDATA', os.path.expanduser('~'))
    return os.path.join(base, 'DiskScanner')


APP_DATA_DIR = _get_app_data_dir()
CONFIG_DIR = os.path.join(APP_DATA_DIR, 'config')
SETTINGS_FILE = os.path.join(CONFIG_DIR, 'settings.json')
CACHE_DIR = os.path.join(APP_DATA_DIR, 'cache')
LOG_DIR = os.path.join(APP_DATA_DIR, 'logs')


class AIConfig:
    """AI 配置管理器 (单例模式)"""

    _instance: Optional['AIConfig'] = None

    def __init__(self):
        self.base_url: str = ""
        self.api_key: str = ""
        self.model: str = "gpt-4o-mini"
        self.cache_enabled: bool = True
        self.auto_analyze: bool = True
        self.max_concurrent: int = 3
        self._config_path: str = SETTINGS_FILE
        self._cache_dir: str = CACHE_DIR
        self._log_dir: str = LOG_DIR

    @classmethod
    def instance(cls) -> 'AIConfig':
        """获取单例，首次调用时自动创建"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """重置单例 (仅用于测试)"""
        cls._instance = None

    def load(self) -> None:
        """从 settings.json 加载配置，文件不存在则使用默认值"""
        if not os.path.exists(self._config_path):
            return
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            ai = data.get('ai', {})
            self.base_url = ai.get('base_url', '')
            self.api_key = ai.get('api_key', '')
            self.model = ai.get('model', 'gpt-4o-mini')
            self.cache_enabled = ai.get('cache_enabled', True)
            self.auto_analyze = ai.get('auto_analyze', True)
            self.max_concurrent = ai.get('max_concurrent', 3)
        except (json.JSONDecodeError, OSError):
            pass  # 配置文件损坏时保持默认值

    def save(self) -> None:
        """保存当前配置到 settings.json，自动创建目录"""
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        data = {
            'ai': {
                'base_url': self.base_url,
                'api_key': self.api_key,
                'model': self.model,
                'cache_enabled': self.cache_enabled,
                'auto_analyze': self.auto_analyze,
                'max_concurrent': self.max_concurrent,
            }
        }
        with open(self._config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @property
    def is_configured(self) -> bool:
        """API Key 是否已配置"""
        return bool(self.api_key and self.api_key.strip())

    def get_cache_dir(self) -> str:
        """返回缓存目录，不存在则创建"""
        os.makedirs(self._cache_dir, exist_ok=True)
        return self._cache_dir

    def get_log_dir(self) -> str:
        """返回日志目录，不存在则创建"""
        os.makedirs(self._log_dir, exist_ok=True)
        return self._log_dir
