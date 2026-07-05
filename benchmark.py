#!/usr/bin/env python3
"""benchmark.py — Rust vs Python 扫描引擎性能对比"""
import os
import sys
import time
import tempfile
import statistics
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

# ── Rust 扫描器 ────────────────────────────────────────────
from scanner_core import Scanner as RustScanner, FileNode as RustFileNode, DirNode as RustDirNode

# ── 纯 Python 扫描器 (与 disk_scanner.py fallback 相同逻辑) ──
@dataclass
class PyFileNode:
    name: str
    path: str
    size: int
    modified: float = 0.0
    is_file: bool = True
    parent: Optional[str] = None
    extension: str = ""

@dataclass
class PyDirNode:
    name: str
    path: str
    size: int = 0
    file_count: int = 0
    dir_count: int = 0
    modified: float = 0.0
    is_dir: bool = True
    parent: Optional[str] = None
    children: list = field(default_factory=list)

class PyScanner:
    """纯 Python 目录扫描器 (os.walk 实现)"""
    def __init__(self, follow_symlinks=False):
        self.follow_symlinks = follow_symlinks
        self.all_files: List[PyFileNode] = []
        self.all_dirs: List[PyDirNode] = []
        self.skipped_count = 0

    def scan(self, root_path: str):
        self.all_files.clear()
        self.all_dirs.clear()
        self.skipped_count = 0
        root_path = os.path.abspath(root_path)

        if os.path.isfile(root_path):
            try:
                st = os.stat(root_path)
                self.all_files.append(PyFileNode(
                    name=os.path.basename(root_path),
                    path=root_path,
                    size=st.st_size,
                    modified=st.st_mtime,
                    parent=os.path.dirname(root_path),
                    extension=os.path.splitext(root_path)[1].lower(),
                ))
            except (PermissionError, OSError):
                self.skipped_count += 1
            return self._make_result(root_path)

        dir_map = {}
        for dirpath, dirnames, filenames in os.walk(root_path, followlinks=self.follow_symlinks):
            try:
                dir_st = os.stat(dirpath)
            except (PermissionError, OSError):
                self.skipped_count += 1
                continue

            dn = PyDirNode(
                name=os.path.basename(dirpath) or dirpath,
                path=dirpath,
                modified=dir_st.st_mtime,
                parent=os.path.dirname(dirpath) if dirpath != root_path else None,
            )
            dir_map[dirpath] = dn
            self.all_dirs.append(dn)

            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                try:
                    st = os.stat(fp)
                    ext = os.path.splitext(fn)[1].lower()
                    self.all_files.append(PyFileNode(
                        name=fn, path=fp, size=st.st_size,
                        modified=st.st_mtime, parent=dirpath, extension=ext,
                    ))
                    dn.file_count += 1
                    dn.size += st.st_size
                except (PermissionError, OSError):
                    self.skipped_count += 1
            dn.dir_count = len(dirnames)

        return self._make_result(root_path)

    def _make_result(self, root_path):
        total_size = sum(f.size for f in self.all_files)
        class Result:
            pass
        r = Result()
        r.root = None
        r.total_size = total_size
        r.total_files = len(self.all_files)
        r.total_dirs = len(self.all_dirs)
        r.scan_duration = 0
        r.all_files = list(self.all_files)
        r.all_dirs = list(self.all_dirs)
        r.skipped_count = self.skipped_count
        return r


# ── 工具函数 ────────────────────────────────────────────────
def fmt_time(t):
    if t < 0.001:
        return f"{t*1_000_000:.0f} µs"
    if t < 1:
        return f"{t*1000:.2f} ms"
    return f"{t:.3f} s"

def benchmark(scanner_cls, label, path, runs=5):
    """对指定扫描器执行多次扫描，返回时间列表和最后结果"""
    times = []
    result = None
    for i in range(runs):
        s = scanner_cls()
        start = time.perf_counter()
        result = s.scan(path)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    return times, result


def create_test_tree(base_dir, num_files=5000, depth=4, branching=8):
    """创建深层嵌套测试目录树"""
    import random
    count = 0
    def _fill(d, cur_depth):
        nonlocal count
        if cur_depth >= depth or count >= num_files:
            return
        for i in range(branching):
            if count >= num_files:
                break
            sub = os.path.join(d, f"d{cur_depth}_{i}")
            os.makedirs(sub, exist_ok=True)
            # 每层写几个文件
            for j in range(max(1, branching // 2)):
                if count >= num_files:
                    break
                fp = os.path.join(sub, f"f_{count:06d}.dat")
                with open(fp, "wb") as f:
                    f.write(b"x" * random.randint(64, 4096))
                count += 1
            _fill(sub, cur_depth + 1)
    _fill(base_dir, 0)
    return count


def main():
    print("=" * 70)
    print("  DiskScanner 性能基准测试: Rust (scanner_core) vs Python (os.walk)")
    print("=" * 70)
    print()

    RUNS = 3

    # ── 测试 1: 真实目录 ─────────────────────────────────
    real_paths = [
        ("项目目录", r"C:\Users\psh\Documents\github"),
        ("venv site-packages", r"C:\Users\psh\Documents\github\.venv\Lib\site-packages"),
        ("Python 安装目录", r"C:\Users\psh\AppData\Local\Programs\Python\Python313"),
    ]

    for label, path in real_paths:
        if not os.path.isdir(path):
            print(f"  [跳过] {label}: {path} 不存在")
            continue

        print(f"── 测试: {label} ({path})")
        print()

        rust_times, rust_res = benchmark(RustScanner, "Rust", path, runs=RUNS)
        py_times, py_res = benchmark(PyScanner, "Python", path, runs=RUNS)

        rust_best = min(rust_times)
        rust_avg = statistics.mean(rust_times)
        py_best = min(py_times)
        py_avg = statistics.mean(py_times)

        speedup_best = py_best / rust_best if rust_best > 0 else float('inf')
        speedup_avg = py_avg / rust_avg if rust_avg > 0 else float('inf')

        print(f"   {'指标':<16} {'Rust':>12} {'Python':>12} {'加速比':>10}")
        print(f"   {'─'*16} {'─'*12} {'─'*12} {'─'*10}")
        print(f"   {'最佳时间':<16} {fmt_time(rust_best):>12} {fmt_time(py_best):>12} {speedup_best:>9.2f}x")
        print(f"   {'平均时间':<16} {fmt_time(rust_avg):>12} {fmt_time(py_avg):>12} {speedup_avg:>9.2f}x")
        print(f"   {'文件数':<16} {rust_res.total_files:>12,} {py_res.total_files:>12,}")
        print(f"   {'目录数':<16} {rust_res.total_dirs:>12,} {py_res.total_dirs:>12,}")
        print(f"   {'总大小':<16} {rust_res.total_size:>12,} {py_res.total_size:>12,}")
        print()
        print(f"   Rust 单次时间: {', '.join(fmt_time(t) for t in rust_times)}")
        print(f"   Py   单次时间: {', '.join(fmt_time(t) for t in py_times)}")
        print()

    # ── 测试 2: 合成目录 (大量小文件) ──────────────────────
    print("── 测试: 合成目录 (大量小文件)")
    with tempfile.TemporaryDirectory() as tmpdir:
        n = create_test_tree(tmpdir, num_files=2000, depth=3, branching=6)
        print(f"   创建: {n:,} 文件")
        print()

        rust_times, rust_res = benchmark(RustScanner, "Rust", tmpdir, runs=RUNS)
        py_times, py_res = benchmark(PyScanner, "Python", tmpdir, runs=RUNS)

        rust_best = min(rust_times)
        rust_avg = statistics.mean(rust_times)
        py_best = min(py_times)
        py_avg = statistics.mean(py_times)
        speedup_best = py_best / rust_best if rust_best > 0 else float('inf')
        speedup_avg = py_avg / rust_avg if rust_avg > 0 else float('inf')

        print(f"   {'指标':<16} {'Rust':>12} {'Python':>12} {'加速比':>10}")
        print(f"   {'─'*16} {'─'*12} {'─'*12} {'─'*10}")
        print(f"   {'最佳时间':<16} {fmt_time(rust_best):>12} {fmt_time(py_best):>12} {speedup_best:>9.2f}x")
        print(f"   {'平均时间':<16} {fmt_time(rust_avg):>12} {fmt_time(py_avg):>12} {speedup_avg:>9.2f}x")
        print(f"   {'文件数':<16} {rust_res.total_files:>12,} {py_res.total_files:>12,}")
        print(f"   {'目录数':<16} {rust_res.total_dirs:>12,} {py_res.total_dirs:>12,}")
        print()
        print(f"   Rust 单次时间: {', '.join(fmt_time(t) for t in rust_times)}")
        print(f"   Py   单次时间: {', '.join(fmt_time(t) for t in py_times)}")

    print()
    print("=" * 70)
    print("  基准测试完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
