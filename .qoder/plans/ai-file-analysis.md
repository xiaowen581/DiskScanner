# AI 辅助文件分析功能

## Context

DiskScanner 是一个磁盘空间分析工具（PyQt5 + Rust），用户扫描目录后看到大量文件/文件夹列表，但无法快速判断哪些可以安全删除。本功能通过接入 OpenAI API，自动分析当前页面显示的文件/目录，给出作用描述和删除建议，以悬浮提示方式展示。

## 新增文件结构

```
ai/                              # AI 模块
├── __init__.py                  # 导出公共 API
├── config.py                    # 配置管理 (settings.json 读写)
├── client.py                    # OpenAI API 封装 (Structured Outputs)
├── cache.py                     # 内存+磁盘缓存
├── worker.py                    # AIWorker (QThread, 最多3页并发)
└── prompts.py                   # Prompt 模板

ui/ai_settings_dialog.py         # AI 设置对话框
ui/ai_tooltip_widget.py          # 自定义 AI 分析浮窗
```

## 修改现有文件

| 文件 | 修改 |
|------|------|
| `requirements.txt` | 添加 `openai>=1.30.0`, `pydantic>=2.0.0` |
| `ui/scanner_frame.py` | 集成AI: 自动触发分析、hover浮窗、toolbar加AI按钮、缓存管理 |
| `pyqt_gui.py` | 启动时初始化 AIConfig |

---

## Task 1: 配置管理模块 `ai/config.py`

- **AIConfig 单例** — 管理 `base_url`, `api_key`, `model`, `auto_analyze`, `max_concurrent`
- 路径: `%APPDATA%\DiskScanner\config\settings.json`
- `load()` / `save()` / `is_configured` 属性
- 目录自动创建 (`os.makedirs(exist_ok=True)`)

## Task 2: Prompt 模板 `ai/prompts.py`

- **System Prompt**: 文件分析助手角色定义，删除建议规则 (safe/caution/unsafe)
- **User Prompt**: 扫描路径 + 文件列表 (路径/大小/日期/类型)，要求JSON返回

## Task 3: AI 客户端 `ai/client.py`

- **Pydantic Schema**: `FileAnalysis(path, description, deletability, reason)` + `AnalysisResponse(items)`
- **AIClient.analyze_batch(items, scan_path)**: 使用 `client.beta.chat.completions.parse()` Structured Outputs
- 回退: Structured Outputs 不可用时降级为 `json_object` 模式
- 异常类: `AINotConfiguredError`, `AINetworkError`, `AITimeoutError`
- 超时30s, temperature=0.1

## Task 4: 缓存模块 `ai/cache.py`

- **AICache**: 内存 dict + 可选磁盘缓存 (`%APPDATA%\DiskScanner\cache\`)
- 缓存键: 页面条目 (path+size+modified) 的 MD5
- `get()` / `put()` / `clear()` / `get_item_result(path)`
- 线程安全: `threading.Lock`
- 清理时机: 每次新 scan 完成时 `clear()`

## Task 5: AIWorker `ai/worker.py`

- **QThread**, 接收 `pages: {page_idx: [nodes]}`, 用 `ThreadPoolExecutor(max_workers=3)` 并发
- 信号: `page_finished(int, object)`, `page_error(int, str)`, `all_finished()`
- `cancel()` 方法支持取消

## Task 6: AI 设置对话框 `ui/ai_settings_dialog.py`

- 输入项: API Base URL, API Key (密码模式), Model
- 开关: Auto-analyze, Cache enabled
- 风格与现有 ConfirmDialog/InfoDialog 一致

## Task 7: AI 浮窗 `ui/ai_tooltip_widget.py`

- **AIAnalysisPopover(QWidget)**: `Qt.ToolTip | Qt.FramelessWindowHint`
- 内容: 文件名 + 作用描述 + 删除建议(safe=绿/caution=橙/unsafe=红) + 理由
- 宽360px, 圆角8px, 使用主题C字典颜色
- `show_for_item(node, analysis, pos)` / `show_loading(node, pos)`

## Task 8: 集成到 ScannerFrame

### 8a. toolbar 添加 AI 按钮
- `_build_toolbar()` 中 Export 按钮后加 "AI" 按钮 (紫色)，点击打开设置对话框

### 8b. 自动触发分析
- `_on_scan_finished()`: 清理缓存 → 触发首页分析
- `_render()` 末尾: `QTimer.singleShot(200, _trigger_ai_analysis)` 检查当前页是否已缓存
- `_trigger_ai_analysis()`: 收集当前页+邻近页(最多3页)，启动 AIWorker

### 8c. Hover 浮窗
- `eventFilter` 监听 `tree.viewport()` 的 MouseMove/Leave
- 500ms 延迟定时器，命中缓存则显示浮窗，否则显示"分析中..."

### 8d. 信号槽
- `_on_ai_page_finished()`: 存缓存，当前页则刷新指示
- `_on_ai_page_error()`: 状态栏提示
- `_on_ai_all_finished()`: 状态栏更新

### 8e. 表格指示标记
- Path 列 item 的 tooltip 追加 AI 分析摘要（如有缓存）

## Task 9: 依赖和初始化

- `requirements.txt` 添加 `openai>=1.30.0`, `pydantic>=2.0.0`
- `pyqt_gui.py` 中 `AIConfig.instance().load()`
- `ai/__init__.py` 导出 AIConfig, AIClient, AICache, AIWorker

---

## AI 提示词

**System**:
```
你是 DiskScanner 的文件分析助手。用户会提供磁盘扫描结果中的文件/目录列表，包含完整路径、最后修改日期、文件大小和类型。

你的任务：
1. 为每个条目提供简短的作用描述（中文，最多20个字符）
2. 判断该条目是否可以安全直接删除

删除建议规则：
- "safe": 临时文件、缓存、日志、缩略图缓存、安装包残留等
- "caution": 用户文档、下载文件、媒体文件等（取决于用户需求）
- "unsafe": 系统文件、配置文件、注册表、程序文件、驱动等

始终以 JSON 格式返回结果。
```

**User** (示例):
```
扫描目录: C:\Users\xxx\Downloads
分析时间: 2026-07-06 12:00:00

以下是该目录下的 3 个文件：

1. [FILE] C:\Users\xxx\Downloads\setup.exe | 修改: 2026-06-15 | 150.00 MB | .exe
2. [FILE] C:\Users\xxx\Downloads\report.pdf | 修改: 2026-07-01 | 2.30 MB | .pdf
3. [FILE] C:\Users\xxx\Downloads\cache.tmp | 修改: 2026-05-10 | 50.00 KB | .tmp
```

## 错误处理

| 场景 | 处理 |
|------|------|
| API Key 未配置 | 状态栏提示 + 点击 AI 按钮打开设置 |
| 网络/超时错误 | page_error 信号, 状态栏显示 |
| 认证失败(401) | 弹窗提示 + 自动打开设置 |
| 限流(429) | 弹窗建议等待 |
| Structured Outputs 不支持 | 回退 json_object 模式 |
| 切换扫描 | cancel() + clear cache |

## 验证方式

1. 安装依赖: `pip install openai pydantic`
2. 启动应用: `python pyqt_gui.py`
3. 点击 AI 按钮，配置 API Key / base_url / model
4. 扫描一个目录，观察:
   - 状态栏显示 AI 分析进度
   - 鼠标悬停文件行，浮窗显示分析结果
   - 翻页后自动分析新页
   - 重新扫描后缓存清理
5. 错误场景: 不配置 API Key 扫描，验证提示信息
