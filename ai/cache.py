#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai/cache.py — AI 分析结果缓存管理
支持内存缓存 + 可选磁盘缓存，线程安全
"""

import os
import json
import hashlib
import threading
import logging
from typing import Optional, Dict

from ai.config import AIConfig

logger = logging.getLogger(__name__)


class AICache:
    """AI 分析结果缓存"""

    def __init__(self, config: AIConfig):
        self._config = config
        self._lock = threading.Lock()
        # 内存缓存: {cache_key: {path: FileAnalysis_dict}}
        self._memory: Dict[str, Dict[str, dict]] = {}
        # 路径索引: {path: FileAnalysis_dict} 用于快速按路径查找
        self._path_index: Dict[str, dict] = {}
        # 页面缓存: {page_idx: cache_key}
        self._page_keys: Dict[int, str] = {}

    @staticmethod
    def _make_key(items: list) -> str:
        """
        生成缓存键: 基于文件路径+大小+修改时间的 MD5
        """
        parts = []
        for node in items:
            path = getattr(node, 'path', '')
            size = getattr(node, 'size', 0)
            modified = getattr(node, 'modified', 0)
            parts.append(f"{path}|{size}|{modified}")
        parts.sort()
        raw = "\n".join(parts)
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    def get(self, items: list) -> Optional[Dict[str, dict]]:
        """
        查找缓存 (先查内存，再查磁盘)

        Returns:
            {path: FileAnalysis_dict} 或 None (未命中)
        """
        key = self._make_key(items)

        with self._lock:
            if key in self._memory:
                return self._memory[key]

        # 磁盘缓存
        if self._config.cache_enabled:
            disk_path = self._get_disk_path(key)
            if disk_path and os.path.exists(disk_path):
                try:
                    with open(disk_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # 回填内存缓存
                    with self._lock:
                        self._memory[key] = data
                        for item in data.values():
                            self._path_index[item.get('path', '')] = item
                    return data
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"磁盘缓存读取失败: {e}")

        return None

    def get_page(self, page_idx: int) -> Optional[Dict[str, dict]]:
        """获取指定页面的缓存"""
        with self._lock:
            key = self._page_keys.get(page_idx)
            if key:
                return self._memory.get(key)
        return None

    def put(self, items: list, result: dict, page_idx: Optional[int] = None) -> None:
        """
        写入缓存

        Args:
            items: 原始 FileNode/DirNode 列表
            result: AI 分析结果 dict {"items": [...]}
            page_idx: 页面索引 (可选)
        """
        key = self._make_key(items)

        # 构建 path -> analysis 映射
        path_map: Dict[str, dict] = {}
        for item in result.get('items', []):
            path = item.get('path', '')
            if path:
                path_map[path] = item

        with self._lock:
            self._memory[key] = path_map
            if page_idx is not None:
                self._page_keys[page_idx] = key
            # 更新路径索引
            self._path_index.update(path_map)

        # 磁盘缓存
        if self._config.cache_enabled:
            self._save_to_disk(key, path_map)

    def get_item_result(self, path: str) -> Optional[dict]:
        """按文件路径查找单条分析结果"""
        with self._lock:
            return self._path_index.get(path)

    def clear(self) -> None:
        """清理全部缓存 (内存 + 磁盘)"""
        with self._lock:
            self._memory.clear()
            self._path_index.clear()
            self._page_keys.clear()

        # 清理磁盘缓存
        if self._config.cache_enabled:
            cache_dir = self._config.get_cache_dir()
            try:
                for fname in os.listdir(cache_dir):
                    if fname.endswith('.json'):
                        fpath = os.path.join(cache_dir, fname)
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
            except OSError:
                pass

    def has_page(self, page_idx: int) -> bool:
        """检查指定页面是否已有缓存"""
        with self._lock:
            return page_idx in self._page_keys

    def _get_disk_path(self, key: str) -> Optional[str]:
        """获取磁盘缓存文件路径"""
        try:
            cache_dir = self._config.get_cache_dir()
            return os.path.join(cache_dir, f"{key}.json")
        except OSError:
            return None

    def _save_to_disk(self, key: str, data: dict) -> None:
        """保存到磁盘缓存"""
        disk_path = self._get_disk_path(key)
        if not disk_path:
            return
        try:
            with open(disk_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError as e:
            logger.warning(f"磁盘缓存写入失败: {e}")
