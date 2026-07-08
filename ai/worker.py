#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai/worker.py — AI 分析后台线程
使用 ThreadPoolExecutor 实现并发请求，每批最多 BATCH_SIZE 条
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt5.QtCore import QThread, pyqtSignal

from ai.config import AIConfig
from ai.client import AIClient, AIRequestError
from ai.cache import AICache
from ai.replay import AIReplay, BATCH_SIZE

logger = logging.getLogger(__name__)


class AIWorker(QThread):
    """AI 分析后台线程"""

    page_finished = pyqtSignal(int, object)   # (page_index, result_dict)
    page_error = pyqtSignal(int, str)         # (page_index, error_message)
    all_finished = pyqtSignal()

    def __init__(self, pages: dict, scan_path: str, config: AIConfig,
                 cache: AICache, replay: AIReplay = None):
        """
        Args:
            pages: {page_index: [node_list]} 待分析的页面数据
            scan_path: 扫描根路径
            config: AIConfig 实例
            cache: AICache 实例
            replay: AIReplay 实例 (可选, 默认从 config 创建)
        """
        super().__init__()
        self._pages = pages
        self._scan_path = scan_path
        self._config = config
        self._cache = cache
        self._replay = replay or AIReplay(config)
        self._cancelled = False

    def run(self):
        """执行 AI 分析"""
        client = AIClient(self._config)

        try:
            # ── 阶段 1: 构建所有 chunk 任务 ──
            # chunk_tasks: [(page_idx, chunk_idx, items), ...]
            chunk_tasks = []
            for page_idx, items in self._pages.items():
                if self._cancelled:
                    break
                if self._cache.has_page(page_idx):
                    continue
                # 检查 replay (加载整页所有 chunk)
                replay_result = self._replay.load_page(
                    self._scan_path, page_idx
                )
                if replay_result is not None:
                    self._cache.put(items, replay_result, page_idx)
                    self.page_finished.emit(page_idx, replay_result)
                    continue
                # 拆分为 BATCH_SIZE 个 chunk
                for c, start in enumerate(range(0, len(items), BATCH_SIZE)):
                    chunk_items = items[start:start + BATCH_SIZE]
                    chunk_tasks.append((page_idx, c, chunk_items))

            if self._cancelled or not chunk_tasks:
                return

            max_workers = min(
                self._config.max_concurrent, len(chunk_tasks)
            )

            # ── 阶段 2: 并发执行 ──
            # page_results: {page_idx: {chunk_idx: result_dict}}
            page_results: dict[int, dict[int, dict]] = {}
            page_errors: dict[int, str] = {}

            with ThreadPoolExecutor(max_workers=max(max_workers, 1)) as executor:
                futures = {}
                for page_idx, chunk_idx, items in chunk_tasks:
                    if self._cancelled:
                        break
                    future = executor.submit(
                        self._analyze_chunk, client, page_idx, chunk_idx, items
                    )
                    futures[future] = (page_idx, chunk_idx, items)

                for future in as_completed(futures):
                    if self._cancelled:
                        break
                    page_idx, chunk_idx, items = futures[future]
                    try:
                        messages, result, error = future.result()

                        if error:
                            # 请求失败 — 保存错误记录
                            self._replay.save_error(
                                self._scan_path, page_idx, messages,
                                error["type"], error["message"], chunk_idx
                            )
                            page_errors.setdefault(page_idx, error["message"])
                        else:
                            # 请求成功 — 保存 replay + 收集结果
                            self._replay.save(
                                self._scan_path, page_idx, messages,
                                result, chunk_idx
                            )
                            page_results.setdefault(page_idx, {})[chunk_idx] = result
                    except Exception as e:
                        err_type = type(e).__name__
                        err_msg = str(e)
                        logger.error(
                            f"AI 分析 page {page_idx} chunk {chunk_idx} "
                            f"异常: {e}"
                        )
                        self._replay.save_error(
                            self._scan_path, page_idx, None,
                            err_type, err_msg, chunk_idx
                        )
                        page_errors.setdefault(page_idx, err_msg)

            # ── 阶段 3: 合并 chunk 结果并发信号 ──
            for page_idx, chunks in page_results.items():
                if self._cancelled:
                    break
                merged_items = []
                for c in sorted(chunks.keys()):
                    merged_items.extend(chunks[c].get('items', []))
                result = {"items": merged_items}
                self._cache.put(
                    self._pages[page_idx], result, page_idx
                )
                self.page_finished.emit(page_idx, result)

            for page_idx, err_msg in page_errors.items():
                if page_idx not in page_results:
                    self.page_error.emit(page_idx, err_msg)

        except Exception as e:
            logger.error(f"AI Worker 异常: {e}")
        finally:
            client.close()
            self.all_finished.emit()

    def _analyze_chunk(self, client: AIClient, page_idx: int,
                       chunk_idx: int, items: list):
        """
        单 chunk 分析 (在线程池工作线程中执行)

        Returns:
            (messages, result_dict, error_info_or_None)
        """
        if self._cancelled:
            raise RuntimeError("已取消")
        try:
            messages, result = client.analyze_batch(
                items, self._scan_path, return_prompt=True
            )
            return messages, result, None
        except AIRequestError as e:
            err_type = type(e.original_error).__name__
            err_msg = str(e.original_error)
            logger.warning(
                f"AI chunk 请求失败 (page {page_idx} chunk {chunk_idx}): "
                f"{err_type}: {err_msg}"
            )
            return e.prompt_messages, None, {
                "type": err_type,
                "message": err_msg,
            }
        except Exception as e:
            err_type = type(e).__name__
            err_msg = str(e)
            logger.warning(
                f"AI chunk 请求失败 (page {page_idx} chunk {chunk_idx}): "
                f"{err_type}: {err_msg}"
            )
            return None, None, {
                "type": err_type,
                "message": err_msg,
            }

    def cancel(self):
        """取消未完成的请求"""
        self._cancelled = True
