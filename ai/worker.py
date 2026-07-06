#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai/worker.py — AI 分析后台线程
使用 ThreadPoolExecutor 实现最多 max_concurrent 页并发请求
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt5.QtCore import QThread, pyqtSignal

from ai.config import AIConfig
from ai.client import AIClient
from ai.cache import AICache

logger = logging.getLogger(__name__)


class AIWorker(QThread):
    """AI 分析后台线程"""

    page_finished = pyqtSignal(int, object)   # (page_index, result_dict)
    page_error = pyqtSignal(int, str)         # (page_index, error_message)
    all_finished = pyqtSignal()

    def __init__(self, pages: dict, scan_path: str, config: AIConfig, cache: AICache):
        """
        Args:
            pages: {page_index: [node_list]} 待分析的页面数据
            scan_path: 扫描根路径
            config: AIConfig 实例
            cache: AICache 实例
        """
        super().__init__()
        self._pages = pages
        self._scan_path = scan_path
        self._config = config
        self._cache = cache
        self._cancelled = False

    def run(self):
        """执行 AI 分析"""
        client = AIClient(self._config)
        max_workers = min(self._config.max_concurrent, len(self._pages))

        try:
            with ThreadPoolExecutor(max_workers=max(max_workers, 1)) as executor:
                futures = {}
                for page_idx, items in self._pages.items():
                    if self._cancelled:
                        break
                    # 检查缓存
                    if self._cache.has_page(page_idx):
                        continue
                    future = executor.submit(
                        self._analyze_page, client, page_idx, items
                    )
                    futures[future] = (page_idx, items)

                for future in as_completed(futures):
                    if self._cancelled:
                        break
                    page_idx, items = futures[future]
                    try:
                        result = future.result()
                        # 存入缓存
                        self._cache.put(items, result, page_idx)
                        self.page_finished.emit(page_idx, result)
                    except Exception as e:
                        logger.error(f"AI 分析页面 {page_idx} 失败: {e}")
                        self.page_error.emit(page_idx, str(e))
        except Exception as e:
            logger.error(f"AI Worker 异常: {e}")
        finally:
            client.close()
            self.all_finished.emit()

    def _analyze_page(self, client: AIClient, page_idx: int, items: list) -> dict:
        """单页分析 (在线程池工作线程中执行)"""
        if self._cancelled:
            raise RuntimeError("已取消")
        return client.analyze_batch(items, self._scan_path)

    def cancel(self):
        """取消未完成的请求"""
        self._cancelled = True
