#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai/client.py — OpenAI API 客户端封装
使用 Structured Outputs 获取结构化分析结果，支持降级回退
"""

import logging
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field

from ai.config import AIConfig
from ai.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


# ── 异常类 ──

class AIError(Exception):
    """AI 模块基础异常"""


class AINotConfiguredError(AIError):
    """API Key 未配置"""


class AINetworkError(AIError):
    """网络/API 通信错误"""


class AITimeoutError(AIError):
    """请求超时"""


class AIRequestError(AIError):
    """请求失败，携带 prompt_messages 用于 replay 保存"""
    def __init__(self, original_error, prompt_messages=None):
        super().__init__(str(original_error))
        self.original_error = original_error
        self.prompt_messages = prompt_messages


# ── Structured Outputs Schema ──

class Deletability(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    UNSAFE = "unsafe"


class FileAnalysis(BaseModel):
    path: str = Field(description="文件的完整路径，与输入一致")
    description: str = Field(description="文件/目录作用的简短描述，最多20字")
    deletability: Deletability = Field(description="删除建议等级: safe/caution/unsafe")
    reason: str = Field(description="删除建议的理由，最多30字")


class AnalysisResponse(BaseModel):
    items: List[FileAnalysis] = Field(description="每个文件/目录的分析结果")


# ── 客户端 ──

class AIClient:
    """OpenAI API 客户端封装"""

    def __init__(self, config: AIConfig):
        self._config = config
        self._client = None

    def _ensure_client(self):
        """延迟创建 OpenAI 客户端实例"""
        if not self._config.is_configured:
            raise AINotConfiguredError("API Key 未配置，请在设置中配置 API Key")

        if self._client is None:
            import openai
            import httpx

            kwargs = {
                "api_key": self._config.api_key,
                "timeout": httpx.Timeout(60.0, connect=15.0),
            }
            if self._config.base_url and self._config.base_url.strip():
                kwargs["base_url"] = self._config.base_url.strip()

            self._client = openai.OpenAI(**kwargs)

        return self._client

    def analyze_batch(self, items: list, scan_path: str,
                      return_prompt: bool = False):
        """
        分析一批文件/目录

        Args:
            items: FileNode 或 DirNode 列表 (最多200条)
            scan_path: 扫描根路径
            return_prompt: 为 True 时返回 (messages, result_dict) 元组

        Returns:
            dict: {"items": [...]}
            或 tuple: (messages_list, result_dict) 当 return_prompt=True

        Raises:
            AINotConfiguredError: API Key 未配置
            AINetworkError: 网络/API 错误
            AITimeoutError: 请求超时
        """
        client = self._ensure_client()
        user_prompt = build_user_prompt(items, scan_path)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 尝试 Structured Outputs
        try:
            result = self._call_structured(client, messages)
        except Exception as e:
            err_str = str(e).lower()
            # 如果是不支持 Structured Outputs，降级到 json_object
            if "response_format" in err_str or "not supported" in err_str or "invalid" in err_str:
                logger.info("Structured Outputs 不支持，降级到 json_object 模式")
                try:
                    result = self._call_json_object(client, messages)
                except Exception as inner_e:
                    raise AIRequestError(inner_e, messages) from inner_e
            else:
                raise AIRequestError(e, messages) from e

        if return_prompt:
            return messages, result
        return result

    def _call_kwargs(self) -> dict:
        """构建可选的 extra_body 参数"""
        kw = {}
        if self._config.think_enabled:
            kw["extra_body"] = {"think": True}
        return kw

    def _call_structured(self, client, messages: list) -> dict:
        """使用 Structured Outputs (beta API)"""
        import openai

        try:
            response = client.beta.chat.completions.parse(
                model=self._config.model,
                messages=messages,
                response_format=AnalysisResponse,
                temperature=0.1,
                **self._call_kwargs(),
            )
            parsed = response.choices[0].message.parsed
            if parsed is None:
                raise AIError("AI 返回空结果")
            return parsed.model_dump()
        except openai.APIConnectionError as e:
            raise AINetworkError(f"网络连接失败: {e}") from e
        except openai.APITimeoutError as e:
            raise AITimeoutError(f"请求超时: {e}") from e
        except openai.AuthenticationError as e:
            raise AIError(f"API Key 认证失败: {e}") from e
        except openai.RateLimitError as e:
            raise AIError(f"API 限流，请稍后重试: {e}") from e
        except openai.APIStatusError as e:
            if e.status_code == 400:
                raise  # 让上层降级处理
            raise AINetworkError(f"API 错误 ({e.status_code}): {e}") from e

    def _call_json_object(self, client, messages: list) -> dict:
        """降级: 使用 json_object 响应格式"""
        import openai
        import json

        try:
            response = client.chat.completions.create(
                model=self._config.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
                **self._call_kwargs(),
            )
            content = response.choices[0].message.content
            if not content:
                raise AIError("AI 返回空内容")

            data = json.loads(content)
            # 验证并规范化
            parsed = AnalysisResponse.model_validate(data)
            return parsed.model_dump()
        except openai.APIConnectionError as e:
            raise AINetworkError(f"网络连接失败: {e}") from e
        except openai.APITimeoutError as e:
            raise AITimeoutError(f"请求超时: {e}") from e
        except openai.AuthenticationError as e:
            raise AIError(f"API Key 认证失败: {e}") from e
        except openai.RateLimitError as e:
            raise AIError(f"API 限流，请稍后重试: {e}") from e
        except json.JSONDecodeError as e:
            raise AIError(f"AI 返回的 JSON 解析失败: {e}") from e

    def close(self):
        """关闭客户端连接"""
        self._client = None
