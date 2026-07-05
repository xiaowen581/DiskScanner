# DiskScanner Rust 扫描引擎重写方案

## Context

DiskScanner 是一个磁盘空间分析工具，核心扫描引擎 (`disk_scanner.py` 中的 `Scanner` 类) 使用 Python 的 `os.scandir()` + `os.stat()` 递归遍历目录。在大量文件（10万+）场景下性能不佳，因为：
- 每次系统调用都有 Python → C → 内核的跨层开销
- 递归函数调用栈深，GIL 阻止真正并行

目标：用 Rust + PyO3 重写扫描引擎，通过 `jwalk` 实现并行目录遍历，预估 5~20x 性能提升。

## 项目结构

```
DiskScanner-rust/
├── scanner_core/                # 新增 Rust crate
│   ├── Cargo.toml
│   ├── pyproject.toml           # maturin 配置
│   ├── src/
│   │   ├── lib.rs               # PyO3 模块入口 + Python 类型映射
│   │   ├── scanner.rs           # 核心扫描逻辑（jwalk 并行遍历）
│   │   └── models.rs            # Rust 结构体定义
│   └── tests/
│       └── test_scanner.rs      # Rust 侧集成测试
├── test/
│   └── test_rust_scanner.py     # 新增：Rust 模块 Python 集成测试
├── disk_scanner.py              # 修改：优先从 Rust 模块导入
├── requirements.txt             # 修改：添加 maturin 依赖
└── build.py                     # 修改：支持 Rust 扩展构建
```

## Task 1: 环境准备

1. 安装 Rust 工具链（`rustup`）
2. `cargo install maturin`
3. `pip install maturin`

## Task 2: 创建 Rust crate — `scanner_core/`

### 2.1 `scanner_core/Cargo.toml`

```toml
[package]
name = "scanner_core"
version = "0.1.0"
edition = "2021"

[lib]
name = "scanner_core"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }
jwalk = "0.8"          # 并行目录遍历
```

### 2.2 `scanner_core/pyproject.toml`

```toml
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "scanner_core"
version = "0.1.0"
requires-python = ">=3.8"

[tool.maturin]
features = ["pyo3/extension-module"]
```

### 2.3 `scanner_core/src/models.rs` — Rust 数据模型

```rust
pub struct FileEntry {
    pub name: String,
    pub path: String,
    pub size: u64,
    pub modified: f64,
    pub extension: String,
    pub parent_path: String,
}

pub struct DirEntry {
    pub name: String,
    pub path: String,
    pub size: u64,
    pub file_count: u64,
    pub dir_count: u64,
    pub parent_path: String,
    pub modified: f64,
    pub children: Vec<ChildEntry>,  // 子节点（FileEntry 或 DirEntry）
}

pub struct ScanOutput {
    pub all_files: Vec<FileEntry>,
    pub all_dirs: Vec<DirEntry>,
    pub total_size: u64,
    pub total_files: u64,
    pub total_dirs: u64,
    pub skipped_count: u64,
    pub scan_duration: f64,
    pub root_path: String,
    pub root_size: u64,
    pub root_file_count: u64,
    pub root_dir_count: u64,
    pub root_modified: f64,
}
```

### 2.4 `scanner_core/src/scanner.rs` — 核心扫描逻辑

关键设计：
- 使用 `jwalk::WalkDir` 进行并行目录遍历（默认使用 CPU 核心数线程）
- 后序遍历：先收集所有文件信息，再自底向上累加目录大小
- 两遍扫描：第一遍收集所有 entry，第二遍计算目录大小
- 错误处理：权限错误 → skipped_count++，不中断扫描

```rust
pub fn scan_directory(root: &str, follow_symlinks: bool) -> Result<ScanOutput, ScanError> {
    // 1. 验证路径存在且是目录
    // 2. jwalk::WalkDir 并行遍历，收集 (path, metadata) 对
    // 3. 分离文件和目录
    // 4. 自底向上计算每个目录的 size / file_count / dir_count
    // 5. 构建 ScanOutput 返回
}
```

### 2.5 `scanner_core/src/lib.rs` — PyO3 绑定

```rust
#[pymodule]
fn scanner_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyFileNode>()?;
    m.add_class::<PyDirNode>()?;
    m.add_class::<PyScanResult>()?;
    m.add_class::<PyScanner>()?;
    Ok(())
}
```

PyO3 类型映射：
- `PyFileNode` → Python `FileNode` (name, path, size, modified, extension, parent_path)
- `PyDirNode` → Python `DirNode` (name, path, size, file_count, dir_count, children, parent_path, modified)
- `PyScanResult` → Python `ScanResult` (root, total_size, total_files, total_dirs, scan_duration, all_files, all_dirs, skipped_count)
- `PyScanner` → Python `Scanner` (__init__(follow_symlinks), scan(path), progress_info property)

关键：`PyDirNode.children` 需要是 `Vec<PyObject>`，混合 FileNode 和 DirNode，与现有 Python 代码兼容。

## Task 3: 修改 `disk_scanner.py` — 集成 Rust 模块

在文件顶部添加 Rust 模块导入（带 fallback）：

```python
# 尝试加载 Rust 原生扩展
try:
    from scanner_core import (
        FileNode as _RustFileNode,
        DirNode as _RustDirNode,
        ScanResult as _RustScanResult,
        Scanner as _RustScanner,
    )
    _HAS_RUST = True
except ImportError:
    _HAS_RUST = False

# 使用 Rust 版本（如果可用），否则使用纯 Python 实现
if _HAS_RUST:
    FileNode = _RustFileNode
    DirNode = _RustDirNode
    ScanResult = _RustScanResult
    Scanner = _RustScanner
```

这样所有下游代码（web_ui.py、scanner_frame.py、测试）无需修改即可自动使用 Rust 引擎。

## Task 4: Rust 侧单元测试

`scanner_core/tests/test_scanner.rs`:

- `test_scan_basic` — 基本目录扫描，验证文件数和目录数
- `test_scan_total_size` — 验证总大小正确
- `test_scan_empty_dir` — 空目录
- `test_scan_deep_nesting` — 深层嵌套
- `test_scan_dir_size_accumulation` — 目录大小累加
- `test_scan_file_extensions` — 扩展名提取
- `test_scan_nonexistent_path` — 不存在的路径报错
- `test_scan_file_as_path` — 传入文件路径报错
- `test_scan_symlinks` — 符号链接处理
- `test_scan_permission_denied` — 权限拒绝不中断
- `test_scan_many_files` — 大量文件性能
- `test_scan_reuse` — 重复扫描

## Task 5: Python 集成测试

`test/test_rust_scanner.py`:

- 验证 Rust 模块可导入
- 验证 FileNode/DirNode/ScanResult 数据模型与 Python 版本兼容
- 验证 Scanner.scan() 返回结果与 Python 版本一致
- 验证 progress_info 属性
- 验证错误处理（FileNotFoundError、ValueError）
- 对比测试：同一目录，Rust 和 Python 结果应一致
- 性能测试：Rust 版本应快于 Python 版本

## Task 6: 构建系统更新

### 6.1 更新 `requirements.txt`

添加 `maturin` 依赖。

### 6.2 更新 `build.py`

在 PyInstaller 打包前，先执行 `maturin develop` 构建 Rust 扩展。

### 6.3 添加 `build.bat` 更新

添加 `cargo build --release` 和 `maturin develop` 步骤。

## Task 7: 验证

1. `cargo test` — Rust 侧全部测试通过
2. `maturin develop` — 构建 Python 扩展
3. `python -m pytest test/test_disk_scanner.py -v` — 现有全部测试通过
4. `python -m pytest test/test_rust_scanner.py -v` — 新增 Rust 集成测试通过
5. `python -m pytest test/test_gui_api.py -v` — Web API 测试通过
6. 性能对比：扫描同一目录，Rust vs Python 耗时

## 关键注意事项

1. **children 字段兼容性**：Python 代码中 `DirNode.children` 是 `list`，混合 `FileNode` 和 `DirNode`。Rust 版本必须返回相同的混合列表。
2. **progress_info 属性**：现有代码通过 `scanner.progress_info` 获取 `(file_count, current_path)` 元组。Rust 版本需要支持此属性（可用 `Arc<Mutex<>>` 共享进度状态）。
3. **Windows 路径**：使用 `std::path::Path` 处理，确保 UTF-8 转换正确（Windows 内部用 UTF-16）。
4. **scan_duration**：在 Rust 侧用 `std::time::Instant` 计时。
5. **isinstance 检查**：下游代码大量使用 `isinstance(node, DirNode)` / `isinstance(node, FileNode)`，Rust 版本导出的类型必须支持这些检查。
