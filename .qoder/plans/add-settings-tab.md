# 添加 Settings 标签页 + AI 手动触发

## Context

当前 AI 设置通过 Scanner 工具栏的 "AI" 按钮弹出模态对话框 (`AISettingsDialog`) 来配置。用户希望：
1. 将 AI 设置移入一个新的 "Settings" 标签页（内嵌在主 TabWidget 中，而非弹窗）
2. 保留 AI 按钮，功能改为**手动触发 AI 分析**

## 修改文件清单

| 文件 | 操作 |
|---|---|
| `ui/settings_frame.py` | **新建** - Settings 标签页 Widget |
| `pyqt_gui.py` | **修改** - 添加第三个 Settings 标签页 |
| `ui/scanner_frame.py` | **修改** - AI 按钮改为手动触发分析 |

---

## Task 1: 新建 `ui/settings_frame.py`

创建 `SettingsFrame(QWidget)` 类，包含以下区域：

### AI 配置区
复用 `AISettingsDialog` 中的字段布局，但作为内嵌 Widget 而非弹窗：
- **API Base URL** - QLineEdit
- **API Key** - QLineEdit (Password 模式)
- **Model** - QLineEdit
- **Auto-analyze after scan** - QCheckBox
- **Enable disk cache** - QCheckBox
- **Enable replay** - QCheckBox
- **Enable thinking mode** - QCheckBox
- **Max concurrent pages** - QSpinBox (1-10)
- **Save 按钮** - 调用 `AIConfig.save()` 保存配置

### 关键设计
- 直接从 `AIConfig.instance()` 读取/写入配置（单例模式，无需信号传递）
- 使用现有主题系统 (`C`, `make_font`, `RoundButton` 等) 保持风格一致
- Save 按钮保存后在状态区显示 "Settings saved" 提示

---

## Task 2: 修改 `pyqt_gui.py`

在 `DiskScannerApp.__init__` 中：

```python
from ui.settings_frame import SettingsFrame
# ... 在 Docker tab 之后添加:
self.settings_frame = SettingsFrame(self.notebook)
self.notebook.addTab(self.settings_frame, "  Settings  ")
```

---

## Task 3: 修改 `ui/scanner_frame.py`

### 3a. AI 按钮功能变更
将 `_build_toolbar` 中的 AI 按钮回调从 `_open_ai_settings` 改为 `_manual_ai_analyze`：

```python
self._ai_btn = RoundButton(None, "AI", self._manual_ai_analyze, ...)
```

### 3b. 新增 `_manual_ai_analyze` 方法

```python
def _manual_ai_analyze(self):
    """手动触发 AI 分析当前页"""
    if not self._ai_config.is_configured:
        QMessageBox.warning(self, "AI Not Configured",
            "Please configure AI settings first.\nGo to Settings tab.")
        return
    if not self.result or self._total_items == 0:
        QMessageBox.information(self, "No Data", "Please scan first.")
        return
    self._ai_analyzing = False  # 重置标志允许重新触发
    self._trigger_ai_analysis()
```

### 3c. 保留 `_open_ai_settings` 方法
保留但不再从按钮调用（兼容测试或其他引用）。

---

## Task 4: 验证

1. 启动 `python pyqt_gui.py` 确认三个标签页正常显示
2. Settings 标签页中修改配置并保存，确认 `settings.json` 更新
3. Scanner 标签页中点击 AI 按钮，确认触发手动分析（而非弹出设置对话框）
4. 未配置 API Key 时点击 AI 按钮，确认显示提示去 Settings 配置
