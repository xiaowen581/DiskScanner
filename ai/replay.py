#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai/replay.py — AI 分析结果 Replay 调试系统
将完整的 prompt 和 response 保存到可读 JSON 文件，
支持从文件加载绕过 API 调用，便于调查和修正 AI 推理结果。
"""

import os
import json
import glob
import hashlib
import logging
from datetime import datetime
from typing import Optional, List

from ai.config import AIConfig

logger = logging.getLogger(__name__)

# 每次 API 请求的最大文件数
BATCH_SIZE = 20


class AIReplay:
    """AI 分析 Replay 管理器"""

    def __init__(self, config: AIConfig):
        self._config = config

    @staticmethod
    def _path_hash(scan_path: str) -> str:
        """扫描路径的短 hash"""
        return hashlib.md5(scan_path.encode('utf-8')).hexdigest()[:12]

    @staticmethod
    def _make_filename(scan_path: str, page_idx: int,
                       chunk_idx: int = 0) -> str:
        """
        生成 replay 文件名: {hash}_page{idx}_chunk{c}.json
        """
        path_hash = hashlib.md5(scan_path.encode('utf-8')).hexdigest()[:12]
        return f"{path_hash}_page{page_idx}_chunk{chunk_idx}.json"

    def _get_file_path(self, scan_path: str, page_idx: int,
                       chunk_idx: int = 0) -> str:
        """获取 replay 文件的完整路径"""
        replay_dir = self._config.get_replay_dir()
        filename = self._make_filename(scan_path, page_idx, chunk_idx)
        return os.path.join(replay_dir, filename)

    def _glob_page_files(self, scan_path: str, page_idx: int) -> List[str]:
        """查找某页的所有 chunk replay 文件"""
        replay_dir = self._config.get_replay_dir()
        prefix = f"{self._path_hash(scan_path)}_page{page_idx}_"
        pattern = os.path.join(replay_dir, f"{prefix}*.json")
        return sorted(glob.glob(pattern))

    # ── 加载 ──

    def load(self, scan_path: str, page_idx: int,
             chunk_idx: int = 0) -> Optional[dict]:
        """
        加载单个 chunk 的 replay response

        Returns:
            response dict {"items": [...]} 或 None
        """
        if not self._config.replay_enabled:
            return None

        fpath = self._get_file_path(scan_path, page_idx, chunk_idx)
        return self._load_from_file(fpath)

    def load_page(self, scan_path: str, page_idx: int) -> Optional[dict]:
        """
        加载某页的所有 chunk 并合并为完整 response

        Returns:
            {"items": [...]} 合并结果，或 None (任一 chunk 缺失/出错)
        """
        if not self._config.replay_enabled:
            return None

        files = self._glob_page_files(scan_path, page_idx)
        if not files:
            return None

        all_items = []
        for fpath in files:
            data = self._load_from_file(fpath)
            if data is None:
                return None  # 任一 chunk 缺失或为错误记录
            items = data.get('items', [])
            all_items.extend(items)

        if not all_items:
            return None

        logger.info(
            f"Replay: 从 {len(files)} 个 chunk 加载 page {page_idx} "
            f"({len(all_items)} items)"
        )
        return {"items": all_items}

    def _load_from_file(self, fpath: str) -> Optional[dict]:
        """从单个文件加载 response，跳过错误记录"""
        if not os.path.exists(fpath):
            return None

        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 跳过错误记录
            if data.get('status') == 'error':
                return None
            response = data.get('response')
            if response and 'items' in response:
                return response
            return None
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Replay: 文件读取失败 -> {fpath}: {e}")
            return None

    # ── 保存 ──

    def save(self, scan_path: str, page_idx: int,
             prompt_messages: list, response: dict,
             chunk_idx: int = 0) -> None:
        """
        保存成功的 prompt + response 到 replay 文件

        Args:
            scan_path: 扫描根路径
            page_idx: 页面索引
            prompt_messages: OpenAI messages 列表
            response: AI 分析结果 {"items": [...]}
            chunk_idx: chunk 索引
        """
        if not self._config.replay_enabled:
            return

        record = self._build_base_record(scan_path, page_idx, chunk_idx)
        record["status"] = "success"
        record["prompt"] = self._extract_prompt(prompt_messages)
        record["response"] = response

        self._write_record(scan_path, page_idx, chunk_idx, record)

    def save_error(self, scan_path: str, page_idx: int,
                   prompt_messages: Optional[list],
                   error_type: str, error_message: str,
                   chunk_idx: int = 0) -> None:
        """
        保存失败的请求信息到 replay 文件

        Args:
            scan_path: 扫描根路径
            page_idx: 页面索引
            prompt_messages: 如果已构建则为 list，否则为 None
            error_type: 异常类型名 (如 "AINetworkError")
            error_message: 错误消息
            chunk_idx: chunk 索引
        """
        if not self._config.replay_enabled:
            return

        record = self._build_base_record(scan_path, page_idx, chunk_idx)
        record["status"] = "error"
        record["error"] = {
            "type": error_type,
            "message": error_message,
        }
        if prompt_messages:
            record["prompt"] = self._extract_prompt(prompt_messages)

        self._write_record(scan_path, page_idx, chunk_idx, record)

    # ── 内部方法 ──

    def _build_base_record(self, scan_path: str, page_idx: int,
                           chunk_idx: int) -> dict:
        return {
            "scan_path": scan_path,
            "page_idx": page_idx,
            "chunk_idx": chunk_idx,
            "timestamp": datetime.now().isoformat(timespec='seconds'),
            "model": self._config.model,
        }

    @staticmethod
    def _extract_prompt(prompt_messages: list) -> dict:
        prompt = {}
        for msg in prompt_messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            if role in ('system', 'user'):
                prompt[role] = content
        return prompt

    def _write_record(self, scan_path: str, page_idx: int,
                      chunk_idx: int, record: dict) -> None:
        fpath = self._get_file_path(scan_path, page_idx, chunk_idx)
        try:
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            status = record.get('status', 'unknown')
            logger.info(
                f"Replay: 保存 [{status}] page {page_idx} "
                f"chunk {chunk_idx} -> {fpath}"
            )
        except OSError as e:
            logger.warning(f"Replay: 文件保存失败 -> {fpath}: {e}")
