#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiskScanner 单元测试
覆盖: 数据模型、格式化工具、排序引擎、扫描引擎、导出功能
运行: python3 -m pytest test_disk_scanner.py -v
  或: python3 -m unittest test_disk_scanner.py -v
"""

import os
import sys
import json
import csv
import tempfile
import shutil
import time
import unittest
from pathlib import Path

# 确保能导入被测模块（指向父目录）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disk_scanner import (
    FileNode, DirNode, ScanResult,
    format_size, format_time, parse_size_filter, truncate, pad,
    Scanner, sort_nodes, SORT_MODES, SORT_MODE_KEYS,
    export_csv, export_json,
    apply_filters, build_parser, C,
    get_terminal_width, get_terminal_height,
)


# ════════════════════════════════════════════════════
#  测试工具函数: format_size
# ════════════════════════════════════════════════════

class TestFormatSize(unittest.TestCase):
    """测试 format_size() 字节格式化"""

    def test_bytes(self):
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(1), "1 B")
        self.assertEqual(format_size(512), "512 B")
        self.assertEqual(format_size(1023), "1023 B")

    def test_kilobytes(self):
        self.assertEqual(format_size(1024), "1.00 KB")
        self.assertEqual(format_size(1536), "1.50 KB")
        self.assertEqual(format_size(10240), "10.00 KB")

    def test_megabytes(self):
        self.assertEqual(format_size(1024 ** 2), "1.00 MB")
        self.assertEqual(format_size(int(5.5 * 1024 ** 2)), "5.50 MB")

    def test_gigabytes(self):
        self.assertEqual(format_size(1024 ** 3), "1.00 GB")
        self.assertEqual(format_size(int(28.5 * 1024 ** 3)), "28.50 GB")

    def test_terabytes(self):
        self.assertEqual(format_size(1024 ** 4), "1.00 TB")
        self.assertEqual(format_size(int(2.5 * 1024 ** 4)), "2.50 TB")

    def test_negative(self):
        self.assertEqual(format_size(-1), "0 B")
        self.assertEqual(format_size(-1024), "0 B")

    def test_large_value(self):
        """测试非常大的值"""
        result = format_size(10 * 1024 ** 4)
        self.assertIn("TB", result)
        self.assertTrue(result.startswith("10.00"))


# ════════════════════════════════════════════════════
#  测试工具函数: format_time
# ════════════════════════════════════════════════════

class TestFormatTime(unittest.TestCase):
    """测试 format_time() 时间格式化"""

    def test_zero(self):
        self.assertEqual(format_time(0), "N/A")

    def test_valid_timestamp(self):
        """用已知时间戳验证格式"""
        # 2024-01-01 00:00:00 UTC
        result = format_time(1704067200.0)
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
        self.assertIn("2024", result)

    def test_invalid(self):
        """传入非法值应返回 N/A"""
        self.assertEqual(format_time(None), "N/A")
        self.assertEqual(format_time("abc"), "N/A")


# ════════════════════════════════════════════════════
#  测试工具函数: parse_size_filter
# ════════════════════════════════════════════════════

class TestParseSizeFilter(unittest.TestCase):
    """测试 parse_size_filter() 大小解析"""

    def test_empty(self):
        self.assertEqual(parse_size_filter(""), 0)
        self.assertEqual(parse_size_filter(None), 0)

    def test_plain_bytes(self):
        self.assertEqual(parse_size_filter("1024"), 1024)
        self.assertEqual(parse_size_filter("0"), 0)

    def test_kb(self):
        self.assertEqual(parse_size_filter("1KB"), 1024)
        self.assertEqual(parse_size_filter("10kb"), 10240)

    def test_mb(self):
        self.assertEqual(parse_size_filter("1MB"), 1024 ** 2)
        self.assertEqual(parse_size_filter("100MB"), 100 * 1024 ** 2)

    def test_gb(self):
        self.assertEqual(parse_size_filter("1GB"), 1024 ** 3)
        self.assertEqual(parse_size_filter("2.5GB"), int(2.5 * 1024 ** 3))

    def test_tb(self):
        self.assertEqual(parse_size_filter("1TB"), 1024 ** 4)

    def test_b_suffix(self):
        self.assertEqual(parse_size_filter("500B"), 500)

    def test_with_spaces(self):
        self.assertEqual(parse_size_filter("  100MB  "), 100 * 1024 ** 2)

    def test_float_value(self):
        self.assertEqual(parse_size_filter("1.5GB"), int(1.5 * 1024 ** 3))

    def test_invalid_string(self):
        self.assertEqual(parse_size_filter("abc"), 0)
        self.assertEqual(parse_size_filter("xyzGB"), 0)


# ════════════════════════════════════════════════════
#  测试工具函数: truncate / pad
# ════════════════════════════════════════════════════

class TestTruncate(unittest.TestCase):

    def test_short_string(self):
        self.assertEqual(truncate("hello", 10), "hello")

    def test_exact_length(self):
        self.assertEqual(truncate("hello", 5), "hello")

    def test_long_string(self):
        self.assertEqual(truncate("hello world", 8), "hello...")
        self.assertEqual(len(truncate("hello world", 8)), 8)

    def test_very_short_limit(self):
        result = truncate("abcdefgh", 4)
        self.assertEqual(result, "a...")


class TestPad(unittest.TestCase):

    def test_left_align(self):
        result = pad("hi", 6, "left")
        self.assertEqual(result, "hi    ")
        self.assertEqual(len(result), 6)

    def test_right_align(self):
        result = pad("hi", 6, "right")
        self.assertEqual(result, "    hi")
        self.assertEqual(len(result), 6)

    def test_center_align(self):
        result = pad("hi", 6, "center")
        self.assertEqual(len(result), 6)
        self.assertTrue(result.startswith(" "))
        self.assertTrue(result.endswith(" "))

    def test_no_padding_needed(self):
        result = pad("hello", 3, "left")
        self.assertEqual(result, "hello")


# ════════════════════════════════════════════════════
#  测试数据模型
# ════════════════════════════════════════════════════

class TestDataModels(unittest.TestCase):
    """测试 FileNode / DirNode / ScanResult 数据模型"""

    def test_file_node(self):
        f = FileNode(
            name="test.py", path="/tmp/test.py",
            size=1024, modified=time.time(),
            extension=".py", parent_path="/tmp"
        )
        self.assertEqual(f.name, "test.py")
        self.assertEqual(f.size, 1024)
        self.assertEqual(f.extension, ".py")
        self.assertEqual(f.parent_path, "/tmp")

    def test_file_node_defaults(self):
        f = FileNode(name="a.txt", path="/a.txt", size=0,
                     modified=0.0, extension=".txt")
        self.assertEqual(f.parent_path, "")

    def test_dir_node(self):
        d = DirNode(name="docs", path="/home/docs", size=2048,
                    file_count=5, dir_count=2)
        self.assertEqual(d.name, "docs")
        self.assertEqual(d.size, 2048)
        self.assertEqual(d.file_count, 5)
        self.assertEqual(d.dir_count, 2)
        self.assertEqual(d.children, [])

    def test_dir_node_defaults(self):
        d = DirNode(name="root", path="/")
        self.assertEqual(d.size, 0)
        self.assertEqual(d.file_count, 0)
        self.assertEqual(d.dir_count, 0)
        self.assertEqual(d.children, [])
        self.assertEqual(d.parent_path, "")
        self.assertEqual(d.modified, 0.0)

    def test_scan_result(self):
        r = ScanResult()
        self.assertIsNone(r.root)
        self.assertEqual(r.total_size, 0)
        self.assertEqual(r.total_files, 0)
        self.assertEqual(r.total_dirs, 0)
        self.assertEqual(r.all_files, [])
        self.assertEqual(r.all_dirs, [])
        self.assertEqual(r.skipped_count, 0)

    def test_scan_result_with_data(self):
        root = DirNode(name="root", path="/root", size=1024)
        r = ScanResult(root=root, total_size=1024, total_files=3,
                       total_dirs=1, scan_duration=0.5)
        self.assertEqual(r.root.name, "root")
        self.assertEqual(r.total_size, 1024)
        self.assertEqual(r.scan_duration, 0.5)


# ════════════════════════════════════════════════════
#  测试排序引擎: sort_nodes
# ════════════════════════════════════════════════════

class TestSortNodes(unittest.TestCase):
    """测试 sort_nodes() 排序功能"""

    def setUp(self):
        self.files = [
            FileNode("small.txt", "/small.txt", 100, 1000.0, ".txt"),
            FileNode("big.mp4", "/big.mp4", 5000, 2000.0, ".mp4"),
            FileNode("mid.py", "/mid.py", 1000, 3000.0, ".py"),
        ]

    def test_size_desc(self):
        result = sort_nodes(self.files, "size-desc")
        sizes = [n.size for n in result]
        self.assertEqual(sizes, [5000, 1000, 100])

    def test_size_asc(self):
        result = sort_nodes(self.files, "size-asc")
        sizes = [n.size for n in result]
        self.assertEqual(sizes, [100, 1000, 5000])

    def test_name_sort(self):
        result = sort_nodes(self.files, "name")
        names = [n.name for n in result]
        self.assertEqual(names, ["big.mp4", "mid.py", "small.txt"])

    def test_modified_sort(self):
        result = sort_nodes(self.files, "modified")
        times = [n.modified for n in result]
        self.assertEqual(times, [3000.0, 2000.0, 1000.0])

    def test_invalid_mode_fallback(self):
        """无效排序模式应回退到 size-desc"""
        result = sort_nodes(self.files, "invalid_mode")
        sizes = [n.size for n in result]
        self.assertEqual(sizes, [5000, 1000, 100])

    def test_empty_list(self):
        self.assertEqual(sort_nodes([], "size-desc"), [])

    def test_single_item(self):
        result = sort_nodes([self.files[0]], "size-desc")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "small.txt")

    def test_sort_dirs(self):
        """排序也适用于 DirNode"""
        dirs = [
            DirNode("a", "/a", size=500),
            DirNode("b", "/b", size=2000),
            DirNode("c", "/c", size=100),
        ]
        result = sort_nodes(dirs, "size-desc")
        sizes = [d.size for d in result]
        self.assertEqual(sizes, [2000, 500, 100])

    def test_sort_stability(self):
        """相同大小的节点应保持原顺序（Python sorted 稳定排序）"""
        files = [
            FileNode("a.txt", "/a.txt", 100, 1000.0, ".txt"),
            FileNode("b.txt", "/b.txt", 100, 2000.0, ".txt"),
        ]
        result = sort_nodes(files, "size-desc")
        # 大小相同，应保持原顺序
        self.assertEqual(result[0].name, "a.txt")
        self.assertEqual(result[1].name, "b.txt")

    def test_sort_mode_keys_exist(self):
        self.assertIn("size-desc", SORT_MODE_KEYS)
        self.assertIn("size-asc", SORT_MODE_KEYS)
        self.assertIn("name", SORT_MODE_KEYS)
        self.assertIn("modified", SORT_MODE_KEYS)


# ════════════════════════════════════════════════════
#  测试扫描引擎: Scanner
# ════════════════════════════════════════════════════

class TestScanner(unittest.TestCase):
    """测试 Scanner 核心扫描功能（使用临时目录）"""

    def setUp(self):
        """创建测试用的临时目录结构"""
        self.tmpdir = tempfile.mkdtemp(prefix="diskscanner_test_")

        # 创建文件
        self._create_file("file1.txt", 1000)
        self._create_file("file2.py", 2000)

        # 创建子目录 + 文件
        subdir = os.path.join(self.tmpdir, "subdir")
        os.makedirs(subdir)
        self._create_file(os.path.join("subdir", "file3.mp4"), 5000)

        # 创建空子目录
        emptydir = os.path.join(self.tmpdir, "empty")
        os.makedirs(emptydir)

        # 创建深层嵌套
        deep = os.path.join(self.tmpdir, "a", "b", "c")
        os.makedirs(deep)
        self._create_file(os.path.join("a", "b", "c", "deep.txt"), 300)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_file(self, rel_path, size_bytes):
        path = os.path.join(self.tmpdir, rel_path) if not os.path.isabs(rel_path) else rel_path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(b'\x00' * size_bytes)

    # ── 基本扫描 ──

    def test_scan_basic(self):
        scanner = Scanner()
        result = scanner.scan(self.tmpdir)

        self.assertIsNotNone(result.root)
        self.assertEqual(result.root.path, os.path.abspath(self.tmpdir))
        self.assertEqual(result.total_files, 4)    # file1, file2, file3, deep
        self.assertGreaterEqual(result.total_dirs, 4)  # root, subdir, empty, a, a/b, a/b/c
        self.assertEqual(result.skipped_count, 0)
        self.assertGreater(result.scan_duration, 0)

    def test_scan_total_size(self):
        scanner = Scanner()
        result = scanner.scan(self.tmpdir)
        # 1000 + 2000 + 5000 + 300 = 8300
        self.assertEqual(result.total_size, 8300)

    def test_scan_all_files(self):
        scanner = Scanner()
        result = scanner.scan(self.tmpdir)
        names = sorted(f.name for f in result.all_files)
        self.assertEqual(names, ["deep.txt", "file1.txt", "file2.py", "file3.mp4"])

    def test_scan_all_dirs(self):
        scanner = Scanner()
        result = scanner.scan(self.tmpdir)
        dir_names = [d.name for d in result.all_dirs]
        # 根目录 + subdir + empty + a + b + c = 6
        self.assertGreaterEqual(len(dir_names), 4)

    def test_scan_file_extensions(self):
        scanner = Scanner()
        result = scanner.scan(self.tmpdir)
        exts = sorted(f.extension for f in result.all_files)
        self.assertIn(".txt", exts)
        self.assertIn(".py", exts)
        self.assertIn(".mp4", exts)

    def test_scan_file_parent_paths(self):
        scanner = Scanner()
        result = scanner.scan(self.tmpdir)
        abs_tmp = os.path.abspath(self.tmpdir)
        for f in result.all_files:
            self.assertTrue(f.parent_path.startswith(abs_tmp))

    def test_scan_dir_size_accumulation(self):
        """子目录大小应包含其所有子文件的大小"""
        scanner = Scanner()
        result = scanner.scan(self.tmpdir)

        # 找到 subdir
        subdir = next((d for d in result.all_dirs if d.name == "subdir"), None)
        self.assertIsNotNone(subdir)
        self.assertEqual(subdir.size, 5000)
        self.assertEqual(subdir.file_count, 1)

        # 找到 deep 的父链
        c_dir = next((d for d in result.all_dirs if d.name == "c"), None)
        self.assertIsNotNone(c_dir)
        self.assertEqual(c_dir.size, 300)

    def test_scan_empty_directory(self):
        """空目录应扫描成功，size = 0"""
        empty = os.path.join(self.tmpdir, "empty")
        scanner = Scanner()
        result = scanner.scan(empty)
        self.assertEqual(result.total_files, 0)
        self.assertEqual(result.total_size, 0)
        self.assertGreaterEqual(result.total_dirs, 1)

    def test_scan_deep_nesting(self):
        """深层嵌套目录应正确统计"""
        deep_path = os.path.join(self.tmpdir, "a", "b", "c")
        scanner = Scanner()
        result = scanner.scan(self.tmpdir)
        deep_file = next((f for f in result.all_files if f.name == "deep.txt"), None)
        self.assertIsNotNone(deep_file)
        self.assertEqual(deep_file.size, 300)
        self.assertEqual(deep_file.parent_path, os.path.abspath(deep_path))

    # ── 错误处理 ──

    def test_scan_nonexistent_path(self):
        scanner = Scanner()
        with self.assertRaises(FileNotFoundError):
            scanner.scan("/nonexistent/path/that/does/not/exist")

    def test_scan_file_as_path(self):
        """传入文件路径应抛出 ValueError"""
        file_path = os.path.join(self.tmpdir, "file1.txt")
        scanner = Scanner()
        with self.assertRaises(ValueError):
            scanner.scan(file_path)

    # ── 重复扫描 ──

    def test_scan_reuse(self):
        """同一 Scanner 实例可重复扫描，旧数据应被清除"""
        scanner = Scanner()
        r1 = scanner.scan(self.tmpdir)
        r2 = scanner.scan(self.tmpdir)
        self.assertEqual(r1.total_files, r2.total_files)
        self.assertEqual(r1.total_size, r2.total_size)

    # ── progress_info ──

    def test_progress_info(self):
        scanner = Scanner()
        scanner.scan(self.tmpdir)
        count, path = scanner.progress_info
        self.assertEqual(count, 4)
        self.assertTrue(len(path) > 0)


# ════════════════════════════════════════════════════
#  测试扫描引擎: Scanner 进阶
# ════════════════════════════════════════════════════

class TestScannerAdvanced(unittest.TestCase):
    """Scanner 进阶测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="diskscanner_adv_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_scan_empty_root(self):
        """空根目录"""
        scanner = Scanner()
        result = scanner.scan(self.tmpdir)
        self.assertEqual(result.total_files, 0)
        self.assertEqual(result.total_size, 0)

    def test_scan_many_files(self):
        """较多文件的性能测试"""
        for i in range(200):
            path = os.path.join(self.tmpdir, f"file_{i:04d}.dat")
            with open(path, 'wb') as f:
                f.write(b'\x00' * (100 + i))

        scanner = Scanner()
        start = time.time()
        result = scanner.scan(self.tmpdir)
        elapsed = time.time() - start

        self.assertEqual(result.total_files, 200)
        # 200 个文件应在 2 秒内完成
        self.assertLess(elapsed, 2.0)

    def test_scan_subdirectory_sizes(self):
        """多层子目录大小累加正确"""
        # 创建 sub1/sub2/file.bin
        sub2 = os.path.join(self.tmpdir, "sub1", "sub2")
        os.makedirs(sub2)
        with open(os.path.join(sub2, "file.bin"), 'wb') as f:
            f.write(b'\x00' * 10000)

        scanner = Scanner()
        result = scanner.scan(self.tmpdir)

        sub1 = next((d for d in result.all_dirs if d.name == "sub1"), None)
        self.assertIsNotNone(sub1)
        self.assertEqual(sub1.size, 10000)

        sub2_node = next((d for d in result.all_dirs if d.name == "sub2"), None)
        self.assertIsNotNone(sub2_node)
        self.assertEqual(sub2_node.size, 10000)

    def test_scan_mixed_extensions(self):
        """混合扩展名扫描"""
        for ext in ['.txt', '.py', '.js', '.mp4', '']:
            path = os.path.join(self.tmpdir, f"test{ext}")
            with open(path, 'wb') as f:
                f.write(b'\x00' * 500)

        scanner = Scanner()
        result = scanner.scan(self.tmpdir)

        exts = [f.extension for f in result.all_files]
        self.assertIn(".txt", exts)
        self.assertIn(".py", exts)
        self.assertIn(".js", exts)
        self.assertIn(".mp4", exts)
        self.assertIn("", exts)  # 无扩展名

    def test_dir_file_and_subdir_count(self):
        """验证 dir_count 和 file_count"""
        # root: 2 files, 1 subdir
        with open(os.path.join(self.tmpdir, "a.txt"), 'wb') as f:
            f.write(b'\x00' * 100)
        with open(os.path.join(self.tmpdir, "b.txt"), 'wb') as f:
            f.write(b'\x00' * 200)
        os.makedirs(os.path.join(self.tmpdir, "sub"))
        with open(os.path.join(self.tmpdir, "sub", "c.txt"), 'wb') as f:
            f.write(b'\x00' * 300)

        scanner = Scanner()
        result = scanner.scan(self.tmpdir)

        root = result.root
        self.assertEqual(root.file_count, 2)   # a.txt, b.txt
        self.assertEqual(root.dir_count, 1)    # sub


# ════════════════════════════════════════════════════
#  测试导出功能: export_csv / export_json
# ════════════════════════════════════════════════════

class TestExport(unittest.TestCase):
    """测试 CSV / JSON 导出"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="diskscanner_export_")
        # 创建测试文件
        with open(os.path.join(self.tmpdir, "a.txt"), 'wb') as f:
            f.write(b'\x00' * 1000)
        subdir = os.path.join(self.tmpdir, "sub")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "b.py"), 'wb') as f:
            f.write(b'\x00' * 2000)

        scanner = Scanner()
        self.result = scanner.scan(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_export_csv(self):
        csv_path = os.path.join(self.tmpdir, "output.csv")
        export_csv(self.result, csv_path)

        self.assertTrue(os.path.exists(csv_path))

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # 表头 + 目录 + 文件
        self.assertEqual(rows[0], ["类型", "名称", "路径", "大小(字节)", "大小(可读)", "修改时间"])
        # 至少包含 2 个目录和 2 个文件的行
        type_col = [row[0] for row in rows[1:]]
        self.assertIn("目录", type_col)
        self.assertIn("文件", type_col)

    def test_export_csv_content(self):
        """验证 CSV 内容完整性"""
        csv_path = os.path.join(self.tmpdir, "output.csv")
        export_csv(self.result, csv_path)

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # 查找 a.txt
        file_rows = [r for r in rows if r[0] == "文件"]
        names = [r[1] for r in file_rows]
        self.assertIn("a.txt", names)
        self.assertIn("b.py", names)

    def test_export_json(self):
        json_path = os.path.join(self.tmpdir, "output.json")
        export_json(self.result, json_path)

        self.assertTrue(os.path.exists(json_path))

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("summary", data)
        self.assertIn("directories", data)
        self.assertIn("files", data)

    def test_export_json_summary(self):
        json_path = os.path.join(self.tmpdir, "output.json")
        export_json(self.result, json_path)

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        summary = data["summary"]
        self.assertEqual(summary["total_size"], 3000)  # 1000 + 2000
        self.assertEqual(summary["total_files"], 2)
        self.assertGreaterEqual(summary["total_dirs"], 1)
        self.assertIn("total_size_human", summary)

    def test_export_json_files(self):
        json_path = os.path.join(self.tmpdir, "output.json")
        export_json(self.result, json_path)

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        file_names = [f["name"] for f in data["files"]]
        self.assertIn("a.txt", file_names)
        self.assertIn("b.py", file_names)

        # 验证文件结构
        for f in data["files"]:
            self.assertEqual(f["type"], "file")
            self.assertIn("extension", f)
            self.assertIn("size", f)
            self.assertIn("size_human", f)

    def test_export_json_dirs(self):
        json_path = os.path.join(self.tmpdir, "output.json")
        export_json(self.result, json_path)

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        dir_names = [d["name"] for d in data["directories"]]
        self.assertIn("sub", dir_names)

        for d in data["directories"]:
            self.assertEqual(d["type"], "directory")
            self.assertIn("file_count", d)
            self.assertIn("dir_count", d)

    def test_export_sorted(self):
        """导出应按大小降序排列"""
        json_path = os.path.join(self.tmpdir, "output.json")
        export_json(self.result, json_path)

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sizes = [f["size"] for f in data["files"]]
        self.assertEqual(sizes, sorted(sizes, reverse=True))


# ════════════════════════════════════════════════════
#  测试扫描 + 过滤集成
# ════════════════════════════════════════════════════

class TestScanAndFilter(unittest.TestCase):
    """测试扫描结果过滤（模拟 CLI --min-size / --ext 逻辑）"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="diskscanner_filter_")
        self._create("small.txt", 100)
        self._create("big.mp4", 5000)
        self._create("mid.py", 1000)
        self._create("doc.pdf", 3000)

        scanner = Scanner()
        self.result = scanner.scan(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create(self, name, size):
        with open(os.path.join(self.tmpdir, name), 'wb') as f:
            f.write(b'\x00' * size)

    def test_filter_by_min_size(self):
        min_size = 2000
        filtered = [f for f in self.result.all_files if f.size >= min_size]
        self.assertEqual(len(filtered), 2)
        names = [f.name for f in filtered]
        self.assertIn("big.mp4", names)
        self.assertIn("doc.pdf", names)

    def test_filter_by_extension(self):
        exts = [".mp4"]
        filtered = [f for f in self.result.all_files if f.extension in exts]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].name, "big.mp4")

    def test_filter_combined(self):
        min_size = 2000
        exts = [".pdf"]
        filtered = [f for f in self.result.all_files
                    if f.size >= min_size and f.extension in exts]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].name, "doc.pdf")

    def test_filter_no_match(self):
        exts = [".xyz"]
        filtered = [f for f in self.result.all_files if f.extension in exts]
        self.assertEqual(len(filtered), 0)

    def test_filter_all_match(self):
        min_size = 1
        filtered = [f for f in self.result.all_files if f.size >= min_size]
        self.assertEqual(len(filtered), 4)

    def test_sort_then_top_n(self):
        sorted_files = sort_nodes(self.result.all_files, "size-desc")
        top2 = sorted_files[:2]
        self.assertEqual(len(top2), 2)
        self.assertEqual(top2[0].size, 5000)
        self.assertEqual(top2[1].size, 3000)


# ════════════════════════════════════════════════════
#  测试 apply_filters
# ════════════════════════════════════════════════════

class TestApplyFilters(unittest.TestCase):
    """测试 apply_filters() 过滤函数"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="diskscanner_applyfilter_")
        for name, size in [("small.txt", 100), ("big.mp4", 5000),
                           ("mid.py", 1000), ("doc.pdf", 3000)]:
            with open(os.path.join(self.tmpdir, name), 'wb') as f:
                f.write(b'\x00' * size)
        scanner = Scanner()
        self.result = scanner.scan(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_filter_returns_same(self):
        """无过滤条件应返回原结果"""
        filtered = apply_filters(self.result, 0, [])
        self.assertEqual(filtered.total_files, self.result.total_files)
        self.assertEqual(filtered.total_size, self.result.total_size)

    def test_min_size_filter(self):
        """最小文件大小过滤"""
        filtered = apply_filters(self.result, 2000, [])
        self.assertEqual(filtered.total_files, 2)
        names = [f.name for f in filtered.all_files]
        self.assertIn("big.mp4", names)
        self.assertIn("doc.pdf", names)

    def test_ext_filter(self):
        """扩展名过滤"""
        filtered = apply_filters(self.result, 0, [".mp4"])
        self.assertEqual(filtered.total_files, 1)
        self.assertEqual(filtered.all_files[0].name, "big.mp4")

    def test_combined_filter(self):
        """组合过滤"""
        filtered = apply_filters(self.result, 2000, [".pdf"])
        self.assertEqual(filtered.total_files, 1)
        self.assertEqual(filtered.all_files[0].name, "doc.pdf")

    def test_filter_no_match(self):
        """过滤无匹配结果"""
        filtered = apply_filters(self.result, 0, [".xyz"])
        self.assertEqual(filtered.total_files, 0)
        self.assertEqual(filtered.all_files, [])

    def test_filter_preserves_root(self):
        """过滤后 root 应保留"""
        filtered = apply_filters(self.result, 2000, [])
        self.assertEqual(filtered.root, self.result.root)

    def test_filter_preserves_scan_duration(self):
        """过滤后 scan_duration 应保留"""
        filtered = apply_filters(self.result, 2000, [])
        self.assertEqual(filtered.scan_duration, self.result.scan_duration)

    def test_filter_total_size_recalculated(self):
        """过滤后 total_size 应重新计算"""
        filtered = apply_filters(self.result, 2000, [])
        expected = sum(f.size for f in filtered.all_files)
        self.assertEqual(filtered.total_size, expected)

    def test_filter_dirs_limited(self):
        """过滤后 all_dirs 应只包含相关文件所在目录"""
        filtered = apply_filters(self.result, 0, [".mp4"])
        # 至少根目录应在
        self.assertGreaterEqual(len(filtered.all_dirs), 1)


# ════════════════════════════════════════════════════
#  测试 build_parser
# ════════════════════════════════════════════════════

class TestBuildParser(unittest.TestCase):
    """测试 build_parser() 参数解析"""

    def test_parser_creation(self):
        parser = build_parser()
        self.assertIsNotNone(parser)

    def test_default_args(self):
        parser = build_parser()
        args = parser.parse_args([])
        self.assertEqual(args.path, ".")
        self.assertEqual(args.top, 0)
        self.assertEqual(args.min_size, "")
        self.assertEqual(args.ext, "")
        self.assertEqual(args.sort, "size")
        self.assertEqual(args.order, "desc")
        self.assertEqual(args.export, "")
        self.assertFalse(args.no_interactive)
        self.assertFalse(args.follow_symlinks)

    def test_path_argument(self):
        parser = build_parser()
        args = parser.parse_args(["/tmp"])
        self.assertEqual(args.path, "/tmp")

    def test_top_n(self):
        parser = build_parser()
        args = parser.parse_args(["-n", "20"])
        self.assertEqual(args.top, 20)

    def test_min_size(self):
        parser = build_parser()
        args = parser.parse_args(["--min-size", "100MB"])
        self.assertEqual(args.min_size, "100MB")

    def test_ext_filter(self):
        parser = build_parser()
        args = parser.parse_args(["--ext", ".mp4,.mkv"])
        self.assertEqual(args.ext, ".mp4,.mkv")

    def test_sort_and_order(self):
        parser = build_parser()
        args = parser.parse_args(["--sort", "name", "--order", "asc"])
        self.assertEqual(args.sort, "name")
        self.assertEqual(args.order, "asc")

    def test_export(self):
        parser = build_parser()
        args = parser.parse_args(["--export", "report.csv"])
        self.assertEqual(args.export, "report.csv")

    def test_no_interactive(self):
        parser = build_parser()
        args = parser.parse_args(["--no-interactive"])
        self.assertTrue(args.no_interactive)

    def test_follow_symlinks(self):
        parser = build_parser()
        args = parser.parse_args(["--follow-symlinks"])
        self.assertTrue(args.follow_symlinks)

    def test_combined_args(self):
        parser = build_parser()
        args = parser.parse_args(["/home", "-n", "10", "--min-size", "1GB",
                                  "--ext", ".mp4", "--no-interactive"])
        self.assertEqual(args.path, "/home")
        self.assertEqual(args.top, 10)
        self.assertEqual(args.min_size, "1GB")
        self.assertEqual(args.ext, ".mp4")
        self.assertTrue(args.no_interactive)


# ════════════════════════════════════════════════════
#  测试 C 颜色类
# ════════════════════════════════════════════════════

class TestColorClass(unittest.TestCase):
    """测试 ANSI 颜色类 C"""

    def test_color_constants_exist(self):
        """颜色常量应存在"""
        self.assertIsNotNone(C.RESET)
        self.assertIsNotNone(C.BOLD)
        self.assertIsNotNone(C.RED)
        self.assertIsNotNone(C.GREEN)

    def test_disable_clears_colors(self):
        """disable() 应清空所有颜色字符串"""
        # 保存原始值
        originals = {}
        for attr in dir(C):
            if not attr.startswith('_') and attr != 'disable' and isinstance(getattr(C, attr), str):
                originals[attr] = getattr(C, attr)

        C.disable()

        for attr in originals:
            self.assertEqual(getattr(C, attr), '',
                             f"C.{attr} 应为空字符串")

        # 恢复原始值
        for attr, val in originals.items():
            setattr(C, attr, val)


# ════════════════════════════════════════════════════
#  测试终端工具函数
# ════════════════════════════════════════════════════

class TestTerminalUtils(unittest.TestCase):
    """测试终端工具函数"""

    def test_get_terminal_width(self):
        """get_terminal_width 应返回正整数"""
        w = get_terminal_width()
        self.assertIsInstance(w, int)
        self.assertGreater(w, 0)

    def test_get_terminal_height(self):
        """get_terminal_height 应返回正整数"""
        h = get_terminal_height()
        self.assertIsInstance(h, int)
        self.assertGreater(h, 0)


# ════════════════════════════════════════════════════
#  测试排序进阶
# ════════════════════════════════════════════════════

class TestSortNodesAdvanced(unittest.TestCase):
    """测试更多排序模式"""

    def setUp(self):
        self.files = [
            FileNode("alpha.txt", "/z/alpha.txt", 100, 1000.0, ".txt"),
            FileNode("beta.mp4", "/a/beta.mp4", 5000, 3000.0, ".mp4"),
            FileNode("gamma.py", "/m/gamma.py", 1000, 2000.0, ".py"),
        ]

    def test_name_desc(self):
        result = sort_nodes(self.files, "name-desc")
        names = [n.name for n in result]
        self.assertEqual(names, ["gamma.py", "beta.mp4", "alpha.txt"])

    def test_modified_asc(self):
        result = sort_nodes(self.files, "modified-asc")
        times = [n.modified for n in result]
        self.assertEqual(times, [1000.0, 2000.0, 3000.0])

    def test_path_sort(self):
        result = sort_nodes(self.files, "path")
        paths = [n.path for n in result]
        self.assertEqual(paths, ["/a/beta.mp4", "/m/gamma.py", "/z/alpha.txt"])

    def test_path_desc(self):
        result = sort_nodes(self.files, "path-desc")
        paths = [n.path for n in result]
        self.assertEqual(paths, ["/z/alpha.txt", "/m/gamma.py", "/a/beta.mp4"])

    def test_ext_sort(self):
        result = sort_nodes(self.files, "ext")
        exts = [n.extension for n in result]
        self.assertEqual(exts, [".mp4", ".py", ".txt"])

    def test_ext_desc(self):
        result = sort_nodes(self.files, "ext-desc")
        exts = [n.extension for n in result]
        self.assertEqual(exts, [".txt", ".py", ".mp4"])

    def test_files_desc_dirs(self):
        """file_count 排序适用于 DirNode"""
        dirs = [
            DirNode("a", "/a", size=500, file_count=10),
            DirNode("b", "/b", size=2000, file_count=3),
            DirNode("c", "/c", size=100, file_count=7),
        ]
        result = sort_nodes(dirs, "files-desc")
        counts = [d.file_count for d in result]
        self.assertEqual(counts, [10, 7, 3])

    def test_files_asc_dirs(self):
        dirs = [
            DirNode("a", "/a", size=500, file_count=10),
            DirNode("b", "/b", size=2000, file_count=3),
        ]
        result = sort_nodes(dirs, "files-asc")
        counts = [d.file_count for d in result]
        self.assertEqual(counts, [3, 10])

    def test_subdirs_desc(self):
        dirs = [
            DirNode("a", "/a", size=500, dir_count=2),
            DirNode("b", "/b", size=2000, dir_count=5),
        ]
        result = sort_nodes(dirs, "subdirs-desc")
        counts = [d.dir_count for d in result]
        self.assertEqual(counts, [5, 2])

    def test_subdirs_asc(self):
        dirs = [
            DirNode("a", "/a", size=500, dir_count=2),
            DirNode("b", "/b", size=2000, dir_count=5),
        ]
        result = sort_nodes(dirs, "subdirs-asc")
        counts = [d.dir_count for d in result]
        self.assertEqual(counts, [2, 5])


# ════════════════════════════════════════════════════
#  测试 format_size 边界值补充
# ════════════════════════════════════════════════════

class TestFormatSizeEdgeCases(unittest.TestCase):
    """format_size 边界值补充测试"""

    def test_exact_boundary_kb(self):
        self.assertEqual(format_size(1024), "1.00 KB")
        self.assertEqual(format_size(1023), "1023 B")

    def test_exact_boundary_mb(self):
        self.assertEqual(format_size(1024 ** 2), "1.00 MB")
        self.assertEqual(format_size(1024 ** 2 - 1), "1024.00 KB")

    def test_exact_boundary_gb(self):
        self.assertEqual(format_size(1024 ** 3), "1.00 GB")

    def test_exact_boundary_tb(self):
        self.assertEqual(format_size(1024 ** 4), "1.00 TB")


# ════════════════════════════════════════════════════
#  测试 parse_size_filter 补充
# ════════════════════════════════════════════════════

class TestParseSizeFilterEdgeCases(unittest.TestCase):
    """parse_size_filter 边界值补充"""

    def test_zero_bytes(self):
        self.assertEqual(parse_size_filter("0B"), 0)

    def test_large_value(self):
        self.assertEqual(parse_size_filter("10TB"), 10 * 1024 ** 4)

    def test_decimal_bytes(self):
        self.assertEqual(parse_size_filter("1.5KB"), int(1.5 * 1024))

    def test_only_whitespace(self):
        self.assertEqual(parse_size_filter("   "), 0)


# ════════════════════════════════════════════════════
#  运行
# ════════════════════════════════════════════════════

if __name__ == '__main__':
    unittest.main(verbosity=2)
