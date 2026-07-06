#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiskScanner AI 模块单元测试
覆盖: ai/config.py, ai/cache.py, ai/client.py, ai/prompts.py, ai/worker.py
运行: python -m pytest test/test_ai_modules.py -v
"""

import os
import sys
import json
import hashlib
import tempfile
import threading
import types
import unittest
from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# 指向父目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.config import AIConfig, _get_app_data_dir
from ai.cache import AICache
from ai.client import (
    AIClient, AIError, AINotConfiguredError, AINetworkError, AITimeoutError,
    Deletability, FileAnalysis, AnalysisResponse,
)
from ai.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, format_items_for_prompt, build_user_prompt


# ── Mock 数据类 ──

@dataclass
class MockFileNode:
    name: str
    path: str
    size: int
    modified: float
    extension: str
    parent_path: str = ""


@dataclass
class MockDirNode:
    name: str
    path: str
    size: int = 0
    file_count: int = 0
    dir_count: int = 0
    children: list = field(default_factory=list)
    parent_path: str = ""
    modified: float = 0.0


def mock_format_size(size_bytes: int) -> str:
    if size_bytes < 0:
        return "0 B"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB"
    if size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f} MB"
    return f"{size_bytes / (1024 ** 3):.2f} GB"


# ── Fixtures ──

@pytest.fixture(autouse=True)
def reset_ai_config():
    """每个测试前后重置 AIConfig 单例"""
    AIConfig.reset()
    yield
    AIConfig.reset()


@pytest.fixture
def config_tmp(tmp_path):
    """创建指向临时目录的 AIConfig"""
    cfg = AIConfig()
    cfg._config_path = str(tmp_path / "config" / "settings.json")
    cfg._cache_dir = str(tmp_path / "cache")
    cfg._log_dir = str(tmp_path / "logs")
    return cfg


@pytest.fixture
def cache_tmp(tmp_path):
    """创建使用临时目录的 AICache"""
    cfg = AIConfig()
    cfg.cache_enabled = True
    cfg._cache_dir = str(tmp_path / "ai_cache")
    return AICache(cfg)


@pytest.fixture
def cache_no_disk(tmp_path):
    """创建禁用磁盘缓存的 AICache"""
    cfg = AIConfig()
    cfg.cache_enabled = False
    cfg._cache_dir = str(tmp_path / "ai_cache_disabled")
    return AICache(cfg)


@pytest.fixture
def sample_items():
    return [
        MockFileNode(name="test.txt", path="/data/test.txt",
                     size=1024, modified=1704067200.0, extension=".txt"),
        MockFileNode(name="image.png", path="/data/image.png",
                     size=2048, modified=1704153600.0, extension=".png"),
    ]


@pytest.fixture
def sample_result():
    return {
        "items": [
            {"path": "/data/test.txt", "description": "测试文件",
             "deletability": "safe", "reason": "临时测试文件"},
            {"path": "/data/image.png", "description": "图片文件",
             "deletability": "caution", "reason": "用户图片文件"},
        ]
    }


@pytest.fixture
def patch_disk_scanner(monkeypatch):
    """monkeypatch disk_scanner 模块，使 prompts.py 中的动态导入使用 Mock 类"""
    mock_mod = types.ModuleType("disk_scanner")
    mock_mod.FileNode = MockFileNode
    mock_mod.DirNode = MockDirNode
    mock_mod.format_size = mock_format_size
    monkeypatch.setitem(sys.modules, "disk_scanner", mock_mod)
    return mock_mod


def _make_fake_openai():
    """构建 fake openai 模块"""
    fake = types.ModuleType("openai")

    class _APIConnectionError(Exception):
        pass

    class _APITimeoutError(Exception):
        pass

    class _AuthenticationError(Exception):
        pass

    class _RateLimitError(Exception):
        pass

    class _APIStatusError(Exception):
        def __init__(self, message="", status_code=400):
            super().__init__(message)
            self.status_code = status_code

    fake.APIConnectionError = _APIConnectionError
    fake.APITimeoutError = _APITimeoutError
    fake.AuthenticationError = _AuthenticationError
    fake.RateLimitError = _RateLimitError
    fake.APIStatusError = _APIStatusError

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            self.api_key = kwargs.get("api_key", "")
            self.base_url = kwargs.get("base_url", None)
            self.beta = MagicMock()
            self.chat = MagicMock()

    fake.OpenAI = _FakeOpenAI
    return fake


def _make_fake_httpx():
    fake = types.ModuleType("httpx")
    fake.Timeout = lambda *a, **kw: 60.0
    return fake


@pytest.fixture
def mock_openai_httpx(monkeypatch):
    """注入 fake openai + httpx 到 sys.modules"""
    fake_openai = _make_fake_openai()
    fake_httpx = _make_fake_httpx()
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return fake_openai, fake_httpx


# ════════════════════════════════════════════════════════════
# 1. ai/config.py — AIConfig 配置管理
# ════════════════════════════════════════════════════════════

class TestGetAppDataDir:
    def test_returns_appdata_path(self, monkeypatch):
        monkeypatch.setenv("APPDATA", r"C:\Users\Test\AppData\Roaming")
        result = _get_app_data_dir()
        assert result == os.path.join(r"C:\Users\Test\AppData\Roaming", "DiskScanner")

    def test_fallback_to_home(self, monkeypatch):
        monkeypatch.delenv("APPDATA", raising=False)
        result = _get_app_data_dir()
        expected = os.path.join(os.path.expanduser("~"), "DiskScanner")
        assert result == expected


class TestAIConfigInit:
    def test_default_base_url(self):
        cfg = AIConfig()
        assert cfg.base_url == ""

    def test_default_api_key(self):
        cfg = AIConfig()
        assert cfg.api_key == ""

    def test_default_model(self):
        cfg = AIConfig()
        assert cfg.model == "gpt-4o-mini"

    def test_default_cache_enabled(self):
        cfg = AIConfig()
        assert cfg.cache_enabled is True

    def test_default_auto_analyze(self):
        cfg = AIConfig()
        assert cfg.auto_analyze is True

    def test_default_max_concurrent(self):
        cfg = AIConfig()
        assert cfg.max_concurrent == 3


class TestAIConfigSingleton:
    def test_instance_returns_same(self):
        a = AIConfig.instance()
        b = AIConfig.instance()
        assert a is b

    def test_reset_creates_new(self):
        a = AIConfig.instance()
        AIConfig.reset()
        b = AIConfig.instance()
        assert a is not b

    def test_instance_returns_aiconfig(self):
        assert isinstance(AIConfig.instance(), AIConfig)

    def test_multiple_resets(self):
        instances = []
        for _ in range(3):
            AIConfig.reset()
            instances.append(AIConfig.instance())
        for i in range(1, len(instances)):
            assert instances[i] is not instances[i - 1]


class TestAIConfigLoad:
    def test_load_missing_file(self, config_tmp):
        config_tmp.load()
        assert config_tmp.api_key == ""
        assert config_tmp.model == "gpt-4o-mini"

    def test_load_valid_json(self, config_tmp, tmp_path):
        os.makedirs(os.path.dirname(config_tmp._config_path), exist_ok=True)
        data = {"ai": {
            "base_url": "https://api.example.com",
            "api_key": "sk-test123",
            "model": "gpt-4o",
            "cache_enabled": False,
            "auto_analyze": False,
            "max_concurrent": 5,
        }}
        with open(config_tmp._config_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        config_tmp.load()
        assert config_tmp.base_url == "https://api.example.com"
        assert config_tmp.api_key == "sk-test123"
        assert config_tmp.model == "gpt-4o"
        assert config_tmp.cache_enabled is False
        assert config_tmp.auto_analyze is False
        assert config_tmp.max_concurrent == 5

    def test_load_corrupt_json(self, config_tmp):
        os.makedirs(os.path.dirname(config_tmp._config_path), exist_ok=True)
        with open(config_tmp._config_path, "w", encoding="utf-8") as f:
            f.write("{invalid json!!!")
        config_tmp.load()
        assert config_tmp.api_key == ""

    def test_load_partial_config(self, config_tmp):
        os.makedirs(os.path.dirname(config_tmp._config_path), exist_ok=True)
        data = {"ai": {"api_key": "sk-partial"}}
        with open(config_tmp._config_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        config_tmp.load()
        assert config_tmp.api_key == "sk-partial"
        assert config_tmp.model == "gpt-4o-mini"
        assert config_tmp.cache_enabled is True

    def test_load_empty_ai_section(self, config_tmp):
        os.makedirs(os.path.dirname(config_tmp._config_path), exist_ok=True)
        with open(config_tmp._config_path, "w", encoding="utf-8") as f:
            json.dump({"ai": {}}, f)
        config_tmp.load()
        assert config_tmp.api_key == ""
        assert config_tmp.model == "gpt-4o-mini"

    def test_load_no_ai_section(self, config_tmp):
        os.makedirs(os.path.dirname(config_tmp._config_path), exist_ok=True)
        with open(config_tmp._config_path, "w", encoding="utf-8") as f:
            json.dump({"other": "data"}, f)
        config_tmp.load()
        assert config_tmp.api_key == ""

    def test_load_unicode_values(self, config_tmp):
        os.makedirs(os.path.dirname(config_tmp._config_path), exist_ok=True)
        data = {"ai": {"api_key": "sk-中文key-テスト"}}
        with open(config_tmp._config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        config_tmp.load()
        assert config_tmp.api_key == "sk-中文key-テスト"


class TestAIConfigSave:
    def test_save_creates_directory(self, config_tmp):
        assert not os.path.exists(os.path.dirname(config_tmp._config_path))
        config_tmp.save()
        assert os.path.isdir(os.path.dirname(config_tmp._config_path))

    def test_save_writes_json(self, config_tmp):
        config_tmp.api_key = "sk-save"
        config_tmp.model = "gpt-4o"
        config_tmp.save()
        with open(config_tmp._config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["ai"]["api_key"] == "sk-save"
        assert data["ai"]["model"] == "gpt-4o"

    def test_save_roundtrip(self, config_tmp):
        config_tmp.base_url = "https://api.test.com"
        config_tmp.api_key = "sk-round"
        config_tmp.model = "gpt-4o-mini"
        config_tmp.cache_enabled = False
        config_tmp.auto_analyze = False
        config_tmp.max_concurrent = 7
        config_tmp.save()

        cfg2 = AIConfig()
        cfg2._config_path = config_tmp._config_path
        cfg2.load()
        assert cfg2.base_url == "https://api.test.com"
        assert cfg2.api_key == "sk-round"
        assert cfg2.max_concurrent == 7

    def test_save_unicode(self, config_tmp):
        config_tmp.base_url = "https://中文域名.com"
        config_tmp.save()
        cfg2 = AIConfig()
        cfg2._config_path = config_tmp._config_path
        cfg2.load()
        assert cfg2.base_url == "https://中文域名.com"


class TestAIConfigIsConfigured:
    def test_empty_key(self):
        cfg = AIConfig()
        cfg.api_key = ""
        assert cfg.is_configured is False

    def test_whitespace_key(self):
        cfg = AIConfig()
        cfg.api_key = "   "
        assert cfg.is_configured is False

    def test_valid_key(self):
        cfg = AIConfig()
        cfg.api_key = "sk-xxx"
        assert cfg.is_configured is True

    def test_none_key(self):
        cfg = AIConfig()
        cfg.api_key = None
        # bool(None and ...) is False — no AttributeError
        assert cfg.is_configured is False


class TestAIConfigDirs:
    def test_get_cache_dir_creates(self, config_tmp):
        d = config_tmp.get_cache_dir()
        assert os.path.isdir(d)
        assert d == config_tmp._cache_dir

    def test_get_cache_dir_exists(self, config_tmp):
        os.makedirs(config_tmp._cache_dir, exist_ok=True)
        d = config_tmp.get_cache_dir()
        assert os.path.isdir(d)

    def test_get_log_dir_creates(self, config_tmp):
        d = config_tmp.get_log_dir()
        assert os.path.isdir(d)
        assert d == config_tmp._log_dir

    def test_get_log_dir_exists(self, config_tmp):
        os.makedirs(config_tmp._log_dir, exist_ok=True)
        d = config_tmp.get_log_dir()
        assert os.path.isdir(d)


# ════════════════════════════════════════════════════════════
# 2. ai/cache.py — AICache 缓存管理
# ════════════════════════════════════════════════════════════

class TestAICacheMakeKey:
    def test_returns_md5_hex(self, sample_items):
        key = AICache._make_key(sample_items)
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_deterministic(self, sample_items):
        assert AICache._make_key(sample_items) == AICache._make_key(sample_items)

    def test_order_independent(self):
        a = MockFileNode("a", "/a", 100, 1.0, ".txt")
        b = MockFileNode("b", "/b", 200, 2.0, ".py")
        assert AICache._make_key([a, b]) == AICache._make_key([b, a])

    def test_different_items_different_key(self):
        a = [MockFileNode("a", "/a", 100, 1.0, ".txt")]
        b = [MockFileNode("b", "/b", 200, 2.0, ".py")]
        assert AICache._make_key(a) != AICache._make_key(b)

    def test_empty_list(self):
        key = AICache._make_key([])
        expected = hashlib.md5("".encode("utf-8")).hexdigest()
        assert key == expected

    def test_missing_attributes(self):
        """node 缺少 size/modified 时使用 getattr 默认值"""
        class Minimal:
            path = "/x"
        key = AICache._make_key([Minimal()])
        assert len(key) == 32


class TestAICacheGet:
    def test_memory_cache_hit(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result)
        got = cache_tmp.get(sample_items)
        assert got is not None
        assert "/data/test.txt" in got

    def test_cache_miss(self, cache_tmp, sample_items):
        assert cache_tmp.get(sample_items) is None

    def test_disk_cache_hit(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result)
        # 清除内存缓存，保留磁盘缓存
        cache_tmp._memory.clear()
        cache_tmp._path_index.clear()
        got = cache_tmp.get(sample_items)
        assert got is not None
        assert "/data/test.txt" in got

    def test_disk_cache_backfill_memory(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result)
        cache_tmp._memory.clear()
        cache_tmp._path_index.clear()
        cache_tmp.get(sample_items)
        # 内存应该被回填
        key = AICache._make_key(sample_items)
        assert key in cache_tmp._memory

    def test_disk_cache_disabled(self, cache_no_disk, sample_items, sample_result):
        cache_no_disk.put(sample_items, sample_result)
        cache_no_disk._memory.clear()
        # 磁盘缓存禁用，应返回 None
        assert cache_no_disk.get(sample_items) is None

    def test_corrupt_disk_cache(self, cache_tmp, sample_items):
        """磁盘缓存 JSON 损坏时返回 None"""
        cache_tmp.put(sample_items, {"items": [
            {"path": "/data/test.txt", "description": "t",
             "deletability": "safe", "reason": "r"}
        ]})
        cache_tmp._memory.clear()
        cache_tmp._path_index.clear()
        # 破坏磁盘文件
        key = AICache._make_key(sample_items)
        disk_path = cache_tmp._get_disk_path(key)
        with open(disk_path, "w") as f:
            f.write("corrupt json!!!")
        assert cache_tmp.get(sample_items) is None


class TestAICachePut:
    def test_put_memory(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result)
        key = AICache._make_key(sample_items)
        assert key in cache_tmp._memory

    def test_put_disk(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result)
        key = AICache._make_key(sample_items)
        disk_path = cache_tmp._get_disk_path(key)
        assert os.path.exists(disk_path)

    def test_put_disk_disabled(self, cache_no_disk, sample_items, sample_result):
        cache_no_disk.put(sample_items, sample_result)
        key = AICache._make_key(sample_items)
        disk_path = cache_no_disk._get_disk_path(key)
        assert not os.path.exists(disk_path)

    def test_put_with_page_idx(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result, page_idx=2)
        assert cache_tmp.has_page(2)

    def test_put_without_page_idx(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result)
        assert len(cache_tmp._page_keys) == 0

    def test_put_updates_path_index(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result)
        assert "/data/test.txt" in cache_tmp._path_index
        assert "/data/image.png" in cache_tmp._path_index

    def test_put_empty_items(self, cache_tmp):
        cache_tmp.put([], {"items": []})
        # 不应报错

    def test_put_empty_result(self, cache_tmp, sample_items):
        cache_tmp.put(sample_items, {})
        key = AICache._make_key(sample_items)
        assert cache_tmp._memory[key] == {}


class TestAICacheGetPage:
    def test_page_cached(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result, page_idx=0)
        got = cache_tmp.get_page(0)
        assert got is not None

    def test_page_not_cached(self, cache_tmp):
        assert cache_tmp.get_page(99) is None

    def test_multiple_pages(self, cache_tmp):
        items_a = [MockFileNode("a", "/a", 10, 1.0, ".txt")]
        items_b = [MockFileNode("b", "/b", 20, 2.0, ".py")]
        res_a = {"items": [{"path": "/a", "description": "A", "deletability": "safe", "reason": "r"}]}
        res_b = {"items": [{"path": "/b", "description": "B", "deletability": "caution", "reason": "r"}]}
        cache_tmp.put(items_a, res_a, page_idx=0)
        cache_tmp.put(items_b, res_b, page_idx=1)
        assert cache_tmp.get_page(0)["/a"]["description"] == "A"
        assert cache_tmp.get_page(1)["/b"]["description"] == "B"


class TestAICacheGetItemResult:
    def test_existing_path(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result)
        item = cache_tmp.get_item_result("/data/test.txt")
        assert item is not None
        assert item["description"] == "测试文件"

    def test_nonexistent_path(self, cache_tmp):
        assert cache_tmp.get_item_result("/no/such/path") is None


class TestAICacheClear:
    def test_clear_memory(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result, page_idx=0)
        cache_tmp.clear()
        assert len(cache_tmp._memory) == 0

    def test_clear_path_index(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result)
        cache_tmp.clear()
        assert len(cache_tmp._path_index) == 0

    def test_clear_page_keys(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result, page_idx=0)
        cache_tmp.clear()
        assert len(cache_tmp._page_keys) == 0

    def test_clear_disk_files(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result)
        cache_tmp.clear()
        cache_dir = cache_tmp._config.get_cache_dir()
        json_files = [f for f in os.listdir(cache_dir) if f.endswith(".json")]
        assert len(json_files) == 0

    def test_clear_preserves_non_json(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result)
        cache_dir = cache_tmp._config.get_cache_dir()
        # 放一个非 json 文件
        with open(os.path.join(cache_dir, "readme.txt"), "w") as f:
            f.write("keep me")
        cache_tmp.clear()
        assert os.path.exists(os.path.join(cache_dir, "readme.txt"))

    def test_clear_disabled(self, cache_no_disk):
        cache_no_disk.clear()  # 不应报错


class TestAICacheHasPage:
    def test_has_cached_page(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result, page_idx=0)
        assert cache_tmp.has_page(0) is True

    def test_no_cached_page(self, cache_tmp):
        assert cache_tmp.has_page(99) is False

    def test_after_clear(self, cache_tmp, sample_items, sample_result):
        cache_tmp.put(sample_items, sample_result, page_idx=0)
        cache_tmp.clear()
        assert cache_tmp.has_page(0) is False


class TestAICacheThreadSafety:
    def test_concurrent_put(self, cache_tmp):
        """10 线程并发 put 不报错"""
        errors = []

        def worker(idx):
            try:
                items = [MockFileNode(f"f{idx}", f"/f{idx}", idx * 100, float(idx), ".txt")]
                result = {"items": [{"path": f"/f{idx}", "description": f"file {idx}",
                                     "deletability": "safe", "reason": "test"}]}
                cache_tmp.put(items, result, page_idx=idx)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        # 验证所有页面都缓存了
        for i in range(10):
            assert cache_tmp.has_page(i)


# ════════════════════════════════════════════════════════════
# 3. ai/client.py — AIClient API 客户端
# ════════════════════════════════════════════════════════════

class TestAIExceptions:
    def test_hierarchy(self):
        assert issubclass(AINotConfiguredError, AIError)
        assert issubclass(AINetworkError, AIError)
        assert issubclass(AITimeoutError, AIError)

    def test_aierror_is_exception(self):
        assert issubclass(AIError, Exception)

    def test_exception_message(self):
        e = AIError("test msg")
        assert str(e) == "test msg"


class TestPydanticModels:
    def test_deletability_values(self):
        assert Deletability.SAFE.value == "safe"
        assert Deletability.CAUTION.value == "caution"
        assert Deletability.UNSAFE.value == "unsafe"

    def test_file_analysis_creation(self):
        fa = FileAnalysis(path="/a.txt", description="测试", deletability=Deletability.SAFE, reason="临时文件")
        assert fa.path == "/a.txt"
        assert fa.deletability == Deletability.SAFE

    def test_file_analysis_required_fields(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FileAnalysis()  # 缺少必填字段

    def test_analysis_response_creation(self):
        items = [
            FileAnalysis(path="/a", description="d", deletability=Deletability.SAFE, reason="r"),
            FileAnalysis(path="/b", description="d2", deletability=Deletability.UNSAFE, reason="r2"),
        ]
        resp = AnalysisResponse(items=items)
        assert len(resp.items) == 2

    def test_analysis_response_model_dump(self):
        resp = AnalysisResponse(items=[
            FileAnalysis(path="/a", description="d", deletability=Deletability.SAFE, reason="r"),
        ])
        d = resp.model_dump()
        assert "items" in d
        assert d["items"][0]["path"] == "/a"
        assert d["items"][0]["deletability"] == "safe"

    def test_analysis_response_model_validate(self):
        data = {"items": [
            {"path": "/x", "description": "desc", "deletability": "caution", "reason": "why"},
        ]}
        resp = AnalysisResponse.model_validate(data)
        assert resp.items[0].deletability == Deletability.CAUTION


class TestAIClientEnsureClient:
    def test_no_api_key_raises(self):
        cfg = AIConfig()
        cfg.api_key = ""
        client = AIClient(cfg)
        with pytest.raises(AINotConfiguredError):
            client._ensure_client()

    def test_creates_openai_client(self, mock_openai_httpx):
        cfg = AIConfig()
        cfg.api_key = "sk-test"
        client = AIClient(cfg)
        c = client._ensure_client()
        assert c is not None

    def test_reuses_client(self, mock_openai_httpx):
        cfg = AIConfig()
        cfg.api_key = "sk-test"
        client = AIClient(cfg)
        c1 = client._ensure_client()
        c2 = client._ensure_client()
        assert c1 is c2

    def test_custom_base_url(self, mock_openai_httpx):
        fake_openai, _ = mock_openai_httpx
        cfg = AIConfig()
        cfg.api_key = "sk-test"
        cfg.base_url = "https://custom.api.com"
        client = AIClient(cfg)
        c = client._ensure_client()
        assert c.base_url == "https://custom.api.com"

    def test_no_base_url(self, mock_openai_httpx):
        fake_openai, _ = mock_openai_httpx
        cfg = AIConfig()
        cfg.api_key = "sk-test"
        cfg.base_url = ""
        client = AIClient(cfg)
        c = client._ensure_client()
        assert c.base_url is None


class TestAIClientAnalyzeBatch:
    def _make_client(self, mock_openai_httpx, patch_disk_scanner):
        cfg = AIConfig()
        cfg.api_key = "sk-test"
        return AIClient(cfg), cfg

    def test_structured_success(self, mock_openai_httpx, patch_disk_scanner):
        fake_openai, _ = mock_openai_httpx
        client, _ = self._make_client(mock_openai_httpx, patch_disk_scanner)
        client._ensure_client()

        # Mock _call_structured 成功
        resp = AnalysisResponse(items=[
            FileAnalysis(path="/data/test.txt", description="测试", deletability=Deletability.SAFE, reason="临时"),
        ])
        client._client.beta.chat.completions.parse.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(parsed=resp))]
        )

        items = [MockFileNode("test.txt", "/data/test.txt", 1024, 1704067200.0, ".txt")]
        result = client.analyze_batch(items, "/data")
        assert "items" in result
        assert result["items"][0]["path"] == "/data/test.txt"

    def test_fallback_to_json_object(self, mock_openai_httpx, patch_disk_scanner):
        """Structured Outputs 不支持时降级到 json_object"""
        fake_openai, _ = mock_openai_httpx
        client, _ = self._make_client(mock_openai_httpx, patch_disk_scanner)
        client._ensure_client()

        # _call_structured 抛出包含 "not supported" 的异常
        client._client.beta.chat.completions.parse.side_effect = Exception("response_format not supported")

        # Mock _call_json_object 成功
        json_resp = '{"items": [{"path": "/a", "description": "d", "deletability": "safe", "reason": "r"}]}'
        client._client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json_resp))]
        )

        items = [MockFileNode("a", "/a", 10, 1.0, ".txt")]
        result = client.analyze_batch(items, "/")
        assert result["items"][0]["path"] == "/a"

    def test_fallback_response_format(self, mock_openai_httpx, patch_disk_scanner):
        fake_openai, _ = mock_openai_httpx
        client, _ = self._make_client(mock_openai_httpx, patch_disk_scanner)
        client._ensure_client()
        client._client.beta.chat.completions.parse.side_effect = Exception("response_format is invalid")
        json_resp = '{"items": [{"path": "/b", "description": "d", "deletability": "caution", "reason": "r"}]}'
        client._client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json_resp))]
        )
        items = [MockFileNode("b", "/b", 20, 2.0, ".py")]
        result = client.analyze_batch(items, "/")
        assert result["items"][0]["deletability"] == "caution"

    def test_no_fallback_on_other_error(self, mock_openai_httpx, patch_disk_scanner):
        """非降级异常直接抛出"""
        fake_openai, _ = mock_openai_httpx
        client, _ = self._make_client(mock_openai_httpx, patch_disk_scanner)
        client._ensure_client()
        client._client.beta.chat.completions.parse.side_effect = AITimeoutError("请求超时")

        items = [MockFileNode("c", "/c", 30, 3.0, ".js")]
        with pytest.raises(AITimeoutError):
            client.analyze_batch(items, "/")


class TestAIClientCallStructured:
    def _setup(self, mock_openai_httpx):
        fake_openai, _ = mock_openai_httpx
        cfg = AIConfig()
        cfg.api_key = "sk-test"
        client = AIClient(cfg)
        client._ensure_client()
        return client, fake_openai

    def test_success(self, mock_openai_httpx):
        client, fake_openai = self._setup(mock_openai_httpx)
        resp_obj = AnalysisResponse(items=[
            FileAnalysis(path="/a", description="d", deletability=Deletability.SAFE, reason="r"),
        ])
        client._client.beta.chat.completions.parse.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(parsed=resp_obj))]
        )
        result = client._call_structured(client._client, [])
        assert result["items"][0]["path"] == "/a"

    def test_none_parsed(self, mock_openai_httpx):
        client, fake_openai = self._setup(mock_openai_httpx)
        client._client.beta.chat.completions.parse.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(parsed=None))]
        )
        with pytest.raises(AIError, match="AI 返回空结果"):
            client._call_structured(client._client, [])

    def test_connection_error(self, mock_openai_httpx):
        client, fake_openai = self._setup(mock_openai_httpx)
        client._client.beta.chat.completions.parse.side_effect = fake_openai.APIConnectionError("conn fail")
        with pytest.raises(AINetworkError):
            client._call_structured(client._client, [])

    def test_timeout_error(self, mock_openai_httpx):
        client, fake_openai = self._setup(mock_openai_httpx)
        client._client.beta.chat.completions.parse.side_effect = fake_openai.APITimeoutError("timeout")
        with pytest.raises(AITimeoutError):
            client._call_structured(client._client, [])

    def test_auth_error(self, mock_openai_httpx):
        client, fake_openai = self._setup(mock_openai_httpx)
        client._client.beta.chat.completions.parse.side_effect = fake_openai.AuthenticationError("bad key")
        with pytest.raises(AIError, match="认证失败"):
            client._call_structured(client._client, [])

    def test_rate_limit_error(self, mock_openai_httpx):
        client, fake_openai = self._setup(mock_openai_httpx)
        client._client.beta.chat.completions.parse.side_effect = fake_openai.RateLimitError("slow down")
        with pytest.raises(AIError, match="限流"):
            client._call_structured(client._client, [])

    def test_api_status_400_rethrows(self, mock_openai_httpx):
        """400 原样抛出，让上层降级处理"""
        client, fake_openai = self._setup(mock_openai_httpx)
        client._client.beta.chat.completions.parse.side_effect = fake_openai.APIStatusError("bad req", status_code=400)
        with pytest.raises(fake_openai.APIStatusError):
            client._call_structured(client._client, [])

    def test_api_status_500(self, mock_openai_httpx):
        client, fake_openai = self._setup(mock_openai_httpx)
        client._client.beta.chat.completions.parse.side_effect = fake_openai.APIStatusError("server err", status_code=500)
        with pytest.raises(AINetworkError):
            client._call_structured(client._client, [])


class TestAIClientCallJsonObject:
    def _setup(self, mock_openai_httpx):
        fake_openai, _ = mock_openai_httpx
        cfg = AIConfig()
        cfg.api_key = "sk-test"
        client = AIClient(cfg)
        client._ensure_client()
        return client, fake_openai

    def _valid_json(self):
        return json.dumps({"items": [
            {"path": "/a", "description": "d", "deletability": "safe", "reason": "r"}
        ]})

    def test_success(self, mock_openai_httpx):
        client, _ = self._setup(mock_openai_httpx)
        client._client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=self._valid_json()))]
        )
        result = client._call_json_object(client._client, [])
        assert result["items"][0]["path"] == "/a"

    def test_empty_content(self, mock_openai_httpx):
        client, _ = self._setup(mock_openai_httpx)
        client._client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=None))]
        )
        with pytest.raises(AIError, match="空内容"):
            client._call_json_object(client._client, [])

    def test_invalid_json(self, mock_openai_httpx):
        client, _ = self._setup(mock_openai_httpx)
        client._client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not valid json{{{"))]
        )
        with pytest.raises(AIError, match="JSON 解析失败"):
            client._call_json_object(client._client, [])

    def test_connection_error(self, mock_openai_httpx):
        client, fake_openai = self._setup(mock_openai_httpx)
        client._client.chat.completions.create.side_effect = fake_openai.APIConnectionError("fail")
        with pytest.raises(AINetworkError):
            client._call_json_object(client._client, [])

    def test_timeout_error(self, mock_openai_httpx):
        client, fake_openai = self._setup(mock_openai_httpx)
        client._client.chat.completions.create.side_effect = fake_openai.APITimeoutError("t")
        with pytest.raises(AITimeoutError):
            client._call_json_object(client._client, [])

    def test_auth_error(self, mock_openai_httpx):
        client, fake_openai = self._setup(mock_openai_httpx)
        client._client.chat.completions.create.side_effect = fake_openai.AuthenticationError("a")
        with pytest.raises(AIError, match="认证失败"):
            client._call_json_object(client._client, [])

    def test_rate_limit_error(self, mock_openai_httpx):
        client, fake_openai = self._setup(mock_openai_httpx)
        client._client.chat.completions.create.side_effect = fake_openai.RateLimitError("r")
        with pytest.raises(AIError, match="限流"):
            client._call_json_object(client._client, [])


class TestAIClientClose:
    def test_close_resets_client(self, mock_openai_httpx):
        cfg = AIConfig()
        cfg.api_key = "sk-test"
        client = AIClient(cfg)
        client._ensure_client()
        assert client._client is not None
        client.close()
        assert client._client is None

    def test_close_when_no_client(self):
        cfg = AIConfig()
        client = AIClient(cfg)
        client.close()  # 不应报错

    def test_reopen_after_close(self, mock_openai_httpx):
        cfg = AIConfig()
        cfg.api_key = "sk-test"
        client = AIClient(cfg)
        c1 = client._ensure_client()
        client.close()
        c2 = client._ensure_client()
        assert c1 is not c2


# ════════════════════════════════════════════════════════════
# 4. ai/prompts.py — 提示词模板
# ════════════════════════════════════════════════════════════

class TestSystemPrompt:
    def test_not_empty(self):
        assert len(SYSTEM_PROMPT) > 0

    def test_contains_diskscanner(self):
        assert "DiskScanner" in SYSTEM_PROMPT

    def test_contains_deletability_levels(self):
        assert "safe" in SYSTEM_PROMPT
        assert "caution" in SYSTEM_PROMPT
        assert "unsafe" in SYSTEM_PROMPT

    def test_contains_json_requirement(self):
        assert "JSON" in SYSTEM_PROMPT

    def test_contains_path_field(self):
        assert "path" in SYSTEM_PROMPT


class TestFormatItemsForPrompt:
    def test_single_file(self, patch_disk_scanner):
        items = [MockFileNode("test.txt", "/data/test.txt", 1024, 1704067200.0, ".txt")]
        text = format_items_for_prompt(items, "/data")
        assert "[FILE]" in text
        assert "/data/test.txt" in text
        assert ".txt" in text

    def test_single_dir(self, patch_disk_scanner):
        items = [MockDirNode("mydir", "/data/mydir", size=4096, modified=1704067200.0)]
        text = format_items_for_prompt(items, "/data")
        assert "[DIR]" in text
        assert "/data/mydir" in text

    def test_mixed_types(self, patch_disk_scanner):
        items = [
            MockFileNode("f.txt", "/f.txt", 100, 1.0, ".txt"),
            MockDirNode("d", "/d", 200, modified=1.0),
        ]
        text = format_items_for_prompt(items, "/")
        assert "[FILE]" in text
        assert "[DIR]" in text

    def test_numbered_lines(self, patch_disk_scanner):
        items = [
            MockFileNode(f"f{i}.txt", f"/f{i}.txt", i * 10, float(i), ".txt")
            for i in range(1, 4)
        ]
        text = format_items_for_prompt(items, "/")
        assert "1." in text
        assert "2." in text
        assert "3." in text

    def test_modified_date_format(self, patch_disk_scanner):
        items = [MockFileNode("f.txt", "/f.txt", 100, 1704067200.0, ".txt")]
        text = format_items_for_prompt(items, "/")
        # 1704067200 = 2024-01-01 UTC
        assert "2024-01-01" in text or "2023-12-31" in text  # timezone dependent

    def test_zero_modified(self, patch_disk_scanner):
        items = [MockFileNode("f.txt", "/f.txt", 100, 0, ".txt")]
        text = format_items_for_prompt(items, "/")
        assert "N/A" in text

    def test_none_modified(self, patch_disk_scanner):
        class NodeNoMod:
            path = "/x"
            size = 100
            modified = None
            extension = ".txt"
        items = [NodeNoMod()]
        text = format_items_for_prompt(items, "/")
        assert "N/A" in text

    def test_empty_items(self, patch_disk_scanner):
        text = format_items_for_prompt([], "/")
        assert text == ""


class TestBuildUserPrompt:
    def test_contains_scan_path(self, patch_disk_scanner):
        items = [MockFileNode("f.txt", "/data/f.txt", 100, 1.0, ".txt")]
        text = build_user_prompt(items, "/data")
        assert "/data" in text

    def test_contains_timestamp(self, patch_disk_scanner):
        items = [MockFileNode("f.txt", "/f.txt", 100, 1.0, ".txt")]
        text = build_user_prompt(items, "/")
        # Should contain a date pattern like YYYY-MM-DD
        import re
        assert re.search(r"\d{4}-\d{2}-\d{2}", text)

    def test_file_only_type_label(self, patch_disk_scanner):
        items = [MockFileNode("f.txt", "/f.txt", 100, 1.0, ".txt")]
        text = build_user_prompt(items, "/")
        assert "1 个文件" in text

    def test_dir_only_type_label(self, patch_disk_scanner):
        items = [MockDirNode("d", "/d", 200, modified=1.0)]
        text = build_user_prompt(items, "/")
        assert "1 个目录" in text

    def test_mixed_type_label(self, patch_disk_scanner):
        items = [
            MockFileNode("f.txt", "/f.txt", 100, 1.0, ".txt"),
            MockDirNode("d", "/d", 200, modified=1.0),
        ]
        text = build_user_prompt(items, "/")
        assert "2 个文件和目录" in text

    def test_empty_items(self, patch_disk_scanner):
        text = build_user_prompt([], "/")
        assert "0 个文件" in text


# ════════════════════════════════════════════════════════════
# 5. ai/worker.py — AIWorker (PyQt5 不可用时跳过)
# ════════════════════════════════════════════════════════════

class TestAIWorkerBasic:
    def test_import_or_skip(self):
        pytest.importorskip("PyQt5")
        from ai.worker import AIWorker
        assert AIWorker is not None

    def test_cancel_sets_flag(self):
        pytest.importorskip("PyQt5")
        from ai.worker import AIWorker
        cfg = AIConfig()
        cache = AICache(cfg)
        worker = AIWorker(pages={}, scan_path="/", config=cfg, cache=cache)
        assert worker._cancelled is False
        worker.cancel()
        assert worker._cancelled is True

    def test_init_params(self):
        pytest.importorskip("PyQt5")
        from ai.worker import AIWorker
        cfg = AIConfig()
        cache = AICache(cfg)
        pages = {0: [], 1: []}
        worker = AIWorker(pages=pages, scan_path="/data", config=cfg, cache=cache)
        assert worker._pages is pages
        assert worker._scan_path == "/data"
        assert worker._config is cfg
        assert worker._cache is cache


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
