# AI 模块单元测试计划

## Context

上轮实现了 DiskScanner AI 辅助文件分析功能，所有文件语法检查通过。现需补充完整单元测试覆盖四个核心 AI 模块，迭代修复至全部通过。

## Task 1: 创建 `test/test_ai_modules.py`

一个测试文件，约 100+ 用例，覆盖 ai/ 下四个模块 + worker 基础测试。

### 1.1 ai/config.py — AIConfig (~25 用例)
- **TestAIConfigInit**: 默认值 (base_url="", api_key="", model="gpt-4o-mini", cache_enabled=True, auto_analyze=True, max_concurrent=3)
- **TestAIConfigSingleton**: instance() 同一对象, reset() 后新对象
- **TestAIConfigLoad**: 文件不存在→默认值, 有效JSON→正确加载, 损坏JSON→静默默认, 部分字段→缺失用默认, 无ai节→全部默认, Unicode值
- **TestAIConfigSave**: 自动创建目录, JSON内容正确, save→load roundtrip, Unicode
- **TestAIConfigIsConfigured**: 空key=False, 空白key=False, 有效key=True
- **TestAIConfigDirs**: get_cache_dir/get_log_dir 自动创建

### 1.2 ai/cache.py — AICache (~30 用例)
- **TestAICacheMakeKey**: 32位hex, 确定性, 顺序无关(parts.sort), 不同items不同key, 空列表
- **TestAICacheGet**: 内存命中, 磁盘命中+回填内存, 未命中None, cache_enabled=False不读磁盘, 损坏磁盘JSON→None
- **TestAICachePut**: 写内存+磁盘, cache_enabled=False不写磁盘, 带page_idx, 更新path_index, 空items/result不报错
- **TestAICacheGetPage**: 命中/未命中, 多页面独立
- **TestAICacheGetItemResult**: 已知路径→结果, 未知→None
- **TestAICacheClear**: 清内存+磁盘+page_keys, 保留非.json文件, cache_enabled=False不报错
- **TestAICacheHasPage**: True/False/clear后False
- **TestAICacheThreadSafety**: 10线程并发put

### 1.3 ai/client.py — AIClient (~35 用例)
- **TestAIExceptions**: 层级 AINotConfiguredError/AINetworkError/AITimeoutError → AIError → Exception
- **TestPydanticModels**: Deletability枚举值, FileAnalysis必填验证, AnalysisResponse创建+model_dump+model_validate
- **TestAIClientEnsureClient**: 无key→AINotConfiguredError, 有效key→创建client, 复用client, 自定义base_url, 无base_url
- **TestAIClientAnalyzeBatch**: structured成功, 降级json_object(3种触发: not_supported/response_format/invalid), 非降级异常直接抛
- **TestAIClientCallStructured**: 成功, parsed=None→AIError, APIConnection→AINetworkError, APITimeout→AITimeoutError, Auth→AIError, RateLimit→AIError, StatusError(400)原样抛, StatusError(500)→AINetworkError
- **TestAIClientCallJsonObject**: 成功, 空内容→AIError, 无效JSON→AIError, 各异常转换
- **TestAIClientClose**: close后None, 无client时close不报错

### 1.4 ai/prompts.py (~15 用例)
- **TestSystemPrompt**: 非空, 含DiskScanner, 含safe/caution/unsafe, 含JSON
- **TestFormatItemsForPrompt**: [FILE]单文件, [DIR]单目录, 混合, 编号递增, 日期YYYY-MM-DD, zero/None modified→N/A, 空列表→空串
- **TestBuildUserPrompt**: 含scan_path, 含时间戳, 仅文件→"N个文件", 仅目录→"N个目录", 混合→"N个文件和目录"

### 1.5 ai/worker.py (~3 用例, PyQt5不可用时跳过)
- **TestAIWorkerBasic**: 初始化参数, cancel设置标志

## Task 2: 运行测试并迭代修复

```
python -m pytest test/test_ai_modules.py -v
```
如有失败→修复源码或测试→重跑→直至全部通过。

## Mocking 策略

| 依赖 | 策略 |
|------|------|
| FileNode/DirNode | dataclass Mock + monkeypatch sys.modules['disk_scanner'] |
| openai/httpx | fake module 注入 sys.modules (异常类+OpenAI类+httpx.Timeout) |
| APPDATA | monkeypatch.setenv → tmp_path |
| AIConfig 单例 | autouse fixture 每次 reset() |
| PyQt5 | pytest.importorskip 跳过 |

## 关键文件
- **新建**: `test/test_ai_modules.py`
- **可能修改**: `ai/config.py`, `ai/cache.py`, `ai/client.py`, `ai/prompts.py` (修复bug)

## Verification
```bash
python -m pytest test/test_ai_modules.py -v
# 迭代修复直至全部 PASS
```
