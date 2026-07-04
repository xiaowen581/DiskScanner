# DiskScanner PyQt5 GUI 需求文档

> 本文档汇总 scanner_frame.py 及相关 UI 组件的交互与设计需求。

---

## 1. 文件路径显示

### 1.1 路径过长省略逻辑
- **终端版**：`disk_scanner.py` 中 `truncate()` 函数截断并加 `...`
- **PyQt5 版**：`QTableWidget` 列宽自适应，`QHeaderView.ResizeToContents` 自动处理
- **Web 版**：CSS `text-overflow: ellipsis` 实现

---

## 2. 第一列勾选交互

### 2.1 显示方式
- 数据行第一列仅显示文本 `[ ]` / `[x]`，不使用 `QCheckBox` 控件覆盖
- 表头第一列放置 `QCheckBox`，用于全选/全取消

### 2.2 列宽
- 第一列固定宽度 **50px**，确保 `[x]` 完整显示不被截断

### 2.3 点击行为
- **单击第一列**：切换该行的勾选状态（标记/取消标记为待删除）
- **表头 checkbox**：全选或全取消当前页

### 2.4 表头 checkbox 定位
- 无数据时隐藏，有数据时显示
- 在第一列中居中显示
- 使用 `QTimer.singleShot(0, _update_header_cb_pos)` 延迟定位，等待布局稳定

---

## 3. 表格列配置

### 3.1 列宽策略

| 列       | 策略               | 宽度  | 说明                          |
|---------|-------------------|-------|------------------------------|
| check   | Fixed             | 50px  | 显示 `[ ]`/`[x]`               |
| path    | Stretch           | 自适应 | 自动填满剩余空间               |
| size    | Fixed             | 110px | 如 `12.34 GB`（2位小数）       |
| files   | Fixed             | 80px  | 文件数                        |
| subdirs | Fixed             | 80px  | 子目录数                      |
| pct     | Fixed             | 70px  | 如 `63%`（去除小数，四舍五入） |
| modified| Fixed             | 150px | 如 `2025-12-01 14:30`（年月日时分）|

### 3.2 列宽手动调整
- size、files、subdirs、pct、modified 列支持表头拖拽调整宽度
- 策略：`QHeaderView.Interactive`

| 字段      | 格式示例              | 说明                              |
|----------|----------------------|-----------------------------------|
| **size** | `12.34 GB`           | 保留2位小数，最多5数字+1小数点+2字母 |
| **%**    | `63%`                | 去除小数，四舍五入，最多3数字+1字符  |
| **modified** | `2025-12-01 14:30` | 年月日时分                        |

### 3.3 点击排序

以下列支持点击表头排序，首次点击降序，再次点击切换为升序：

- **Path**：按路径字母序
- **Size**：按大小（默认降序）
- **Files**：按文件数
- **SubDirs**：按子目录数
- **% (pct)**：按大小占比（等同于按大小排序）
- **Modified**：按修改时间
- **Type (ext)**：按扩展名

排序逻辑见 `_sort_mode_key()` 和 `_sort_by()`。

### 3.4 Path 列省略显示

- 路径过长时使用 `QFontMetrics.elidedText(val, Qt.ElideMiddle, max_width)` 中间省略
- 鼠标悬停时通过 `setToolTip(val)` 显示完整路径
- **主画面**：`_render()` 中设置 Path 列 item 时计算省略
- **ConfirmDialog**：表格填充完成后统一计算省略，tooltip 显示完整路径

---

## 4. 工具栏精简

### 4.1 已移除的重复按钮
- ~~SELECT ALL~~：功能由表头 checkbox 替代
- ~~CLEAR~~：功能由表头 checkbox 替代
- ~~CHECK PAGE~~：功能由表头 checkbox 替代

### 4.2 保留按钮
- **DELETE**：删除已勾选项
- **CSV / JSON**：导出扫描结果

---

## 5. 勾选状态管理

### 5.1 数据存储
- 使用 `set[str]` 类型 `_checked_paths` 存储已勾选路径

### 5.2 状态同步
- 行勾选/取消时更新 `_checked_paths`
- 同步更新行背景色（已勾选高亮）
- 同步更新表头 checkbox 状态（全选判断）

### 5.3 全选/全取消
- 表头 checkbox checked → 全选当前页
- 表头 checkbox unchecked → 全取消当前页
- 通过 `blockSignals` 防止递归

---

## 6. 右键菜单

| 功能           | 说明                           |
|---------------|--------------------------------|
| Check         | 勾选当前行                     |
| Uncheck       | 取消勾选当前行                 |
| Copy path     | 复制完整路径到剪贴板           |
| Copy parent   | 复制父目录路径到剪贴板         |
| Scan this dir | 将当前目录设为扫描目标         |

---

## 7. 对话框设计

### 7.1 Confirm Delete 对话框
- **尺寸**：900×600，最小 700×450
- **表格**：Type（Fixed 70px）、Path（Stretch）、Size（Fixed 130px）
- **Path 列**：省略显示 + tooltip 完整路径（同主画面）
- **底部按钮**：Cancel + Delete（红色）

### 7.2 Done / Partial Failure 对话框 (InfoDialog)
- **尺寸**：600×400，最小 500×350
- **顶部**：图标（✓/⚠）+ 大标题
- **统计卡片**：Deleted / Failed / Blocked，按状态着色（绿/红/橙）
- **错误详情**（Partial Failure）：只读 QTextEdit，Consolas 字体，深色背景
- **底部**：OK 按钮

---

## 8. 分页与渲染

### 8.1 分页参数
- 每页默认 **200** 条
- 底部显示 `当前页 / 总页数`

### 8.2 渲染流程
1. 过滤（大小、扩展名）
2. 排序
3. 分页
4. 设置列宽策略
5. 填充数据行（含 `[ ]`/`[x]` 文本）
6. 更新表头 checkbox 状态与位置

---

## 9. 相关文件

| 文件                    | 职责                             |
|------------------------|----------------------------------|
| `ui/scanner_frame.py`  | PyQt5 GUI 主实现                  |
| `ui/theme.py`          | 颜色、字体、主题组件               |
| `disk_scanner.py`      | 扫描引擎、排序、格式化             |

---

*文档版本: 1.2*
*更新日期: 2026-07-04*
