#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DiskScanner GUI 单元测试
覆盖: 分页逻辑、视图切换、排序重置、大数据量渲染性能
运行: python3 -m unittest test_gui_pagination.py -v
"""

import os
import sys
import time
import unittest
import tempfile
import shutil
from pathlib import Path

# 指向父目录以导入被测模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disk_scanner import FileNode, DirNode, ScanResult, Scanner

# 测试模式：自动跳过对话框，不弹窗
import tkinter_gui as _tkmod
_tkmod._DIALOG_AUTO_DISMISS = True

# tkinter 测试需要显示服务器，在无头环境中跳过
import tkinter
try:
    _test_root = tkinter.Tk()
    _test_root.withdraw()
    _test_root.destroy()
    _HAS_DISPLAY = True
except Exception:
    _HAS_DISPLAY = False


@unittest.skipUnless(_HAS_DISPLAY, "No display available")
class TestGUIPagination(unittest.TestCase):
    """测试 GUI 分页机制"""

    @classmethod
    def setUpClass(cls):
        """创建临时目录和大量文件用于测试"""
        cls.tmpdir = tempfile.mkdtemp(prefix="gui_test_")
        # 创建 500 个文件（超过 page_size=200）
        for i in range(500):
            Path(cls.tmpdir, f"file_{i:04d}.txt").write_text("x" * (i + 1))
        # 创建 10 个子目录
        for i in range(10):
            d = Path(cls.tmpdir, f"subdir_{i:02d}")
            d.mkdir()
            for j in range(5):
                (d / f"sub_{j}.dat").write_text("y" * 100)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        from tkinter_gui import ScannerApp
        self.app = ScannerApp()
        # 执行扫描，获取真实数据
        scanner = Scanner()
        self.app.result = scanner.scan(self.tmpdir)
        self.app._render()

    def tearDown(self):
        self.app.root.destroy()

    def test_initial_page_is_zero(self):
        """初始页码应为 0"""
        self.assertEqual(self.app._page, 0)

    def test_page_size_is_200(self):
        """默认每页 200 条"""
        self.assertEqual(self.app._page_size, 200)

    def test_treeview_limited_to_page_size(self):
        """Treeview 中的行数不应超过 page_size"""
        children = self.app.tree.get_children()
        self.assertLessEqual(len(children), self.app._page_size)

    def test_total_items_matches_data(self):
        """_total_items 应等于排序后的总条目数"""
        # dirs 视图
        self.app._switch("dirs")
        self.assertGreater(self.app._total_items, 0)
        # files 视图
        self.app._switch("files")
        self.assertGreater(self.app._total_items, 0)
        # files 应该有 500 + 50 = 550 个
        self.assertEqual(self.app._total_items, 550)

    def test_pagination_math(self):
        """550 个文件，每页 200，应有 3 页"""
        self.app._switch("files")
        max_page = (self.app._total_items - 1) // self.app._page_size
        self.assertEqual(max_page, 2)  # 页码 0, 1, 2

    def test_next_page(self):
        """点击下一页，页码递增"""
        self.app._switch("files")
        self.assertEqual(self.app._page, 0)
        self.app._next_page()
        self.assertEqual(self.app._page, 1)
        self.app._next_page()
        self.assertEqual(self.app._page, 2)
        # 最后一页，不再递增
        self.app._next_page()
        self.assertEqual(self.app._page, 2)

    def test_prev_page(self):
        """点击上一页，页码递减"""
        self.app._switch("files")
        self.app._page = 2
        self.app._prev_page()
        self.assertEqual(self.app._page, 1)
        self.app._prev_page()
        self.assertEqual(self.app._page, 0)
        # 第一页，不再递减
        self.app._prev_page()
        self.assertEqual(self.app._page, 0)

    def test_last_page_has_remainder(self):
        """最后一页应显示余数条数据"""
        self.app._switch("files")
        # 跳到最后一页
        max_page = (self.app._total_items - 1) // self.app._page_size
        self.app._page = max_page
        self.app._render()
        children = self.app.tree.get_children()
        expected = self.app._total_items % self.app._page_size
        if expected == 0:
            expected = self.app._page_size
        self.assertEqual(len(children), expected)

    def test_switch_resets_page(self):
        """切换视图时页码归零"""
        self.app._switch("files")
        self.app._next_page()
        self.assertGreater(self.app._page, 0)
        self.app._switch("dirs")
        self.assertEqual(self.app._page, 0)

    def test_sort_resets_page(self):
        """切换排序时页码归零"""
        self.app._switch("files")
        self.app._page = 2
        self.app._sort_by("name")
        self.assertEqual(self.app._page, 0)

    def test_page_label_updates(self):
        """分页标签应显示 当前页/总页数"""
        self.app._switch("files")
        text = self.app._page_label.cget("text")
        self.assertIn("/", text)
        self.assertIn("1", text)


@unittest.skipUnless(_HAS_DISPLAY, "No display available")
class TestGUIRenderPerformance(unittest.TestCase):
    """测试大数据量下渲染不会卡死"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="gui_perf_")
        # 创建 1000 个文件
        for i in range(1000):
            Path(cls.tmpdir, f"big_{i:04d}.log").write_text("z" * 50)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        from tkinter_gui import ScannerApp
        self.app = ScannerApp()
        scanner = Scanner()
        self.app.result = scanner.scan(self.tmpdir)

    def tearDown(self):
        self.app.root.destroy()

    def test_render_files_completes_quickly(self):
        """切换到 FILES 视图应在 2 秒内完成（1000 条数据）"""
        start = time.time()
        self.app._switch("files")
        elapsed = time.time() - start
        self.assertLess(elapsed, 2.0,
                        f"渲染 1000 条文件耗时 {elapsed:.2f}s，超过 2s 阈值")

    def test_render_dirs_completes_quickly(self):
        """切换到 DIRS 视图应在 2 秒内完成"""
        start = time.time()
        self.app._switch("dirs")
        elapsed = time.time() - start
        self.assertLess(elapsed, 2.0,
                        f"渲染目录耗时 {elapsed:.2f}s，超过 2s 阈值")

    def test_treeview_never_exceeds_page_size(self):
        """无论如何操作，Treeview 行数 <= page_size"""
        self.app._switch("files")
        for _ in range(5):
            self.app._next_page()
        children = self.app.tree.get_children()
        self.assertLessEqual(len(children), self.app._page_size)

    def test_pagination_through_all_pages(self):
        """遍历所有页面，每页都有数据且不超过 page_size"""
        self.app._switch("files")
        max_page = (self.app._total_items - 1) // self.app._page_size
        total_shown = 0
        for p in range(max_page + 1):
            self.app._page = p
            self.app._render()
            children = self.app.tree.get_children()
            self.assertGreater(len(children), 0, f"第 {p} 页没有数据")
            self.assertLessEqual(len(children), self.app._page_size)
            total_shown += len(children)
        self.assertEqual(total_shown, self.app._total_items)


@unittest.skipUnless(_HAS_DISPLAY, "No display available")
class TestGUICheckbox(unittest.TestCase):
    """测试勾选框功能"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="gui_checkbox_")
        for i in range(50):
            Path(cls.tmpdir, f"doc_{i:02d}.txt").write_text("x" * (i + 1))
        for i in range(30):
            Path(cls.tmpdir, f"app_{i:02d}.log").write_text("z" * 100)
        sub = Path(cls.tmpdir, "subdir")
        sub.mkdir()
        for i in range(5):
            (sub / f"sub_{i}.dat").write_text("d" * 200)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        from tkinter_gui import ScannerApp
        self.app = ScannerApp()
        scanner = Scanner()
        self.app.result = scanner.scan(self.tmpdir)
        self.app._switch("files")

    def tearDown(self):
        self.app.root.destroy()

    def test_initial_no_checks(self):
        """初始状态无任何勾选"""
        self.assertEqual(len(self.app._checked_paths), 0)

    def test_toggle_check(self):
        """点击勾选应切换状态"""
        self.app._render()
        iid = self.app.tree.get_children()[0]
        self.app._toggle_check(iid)
        node = self.app.item_map.get(iid)
        self.assertIn(node.path, self.app._checked_paths)
        # 再次点击取消
        self.app._toggle_check(iid)
        self.assertNotIn(node.path, self.app._checked_paths)

    def test_check_all_on_page(self):
        """勾选当前页所有条目"""
        self.app._render()
        self.app._check_all_on_page()
        children = self.app.tree.get_children()
        for iid in children:
            node = self.app.item_map.get(iid)
            self.assertIn(node.path, self.app._checked_paths)

    def test_uncheck_all_on_page(self):
        """取消勾选当前页"""
        self.app._render()
        self.app._check_all_on_page()
        self.assertGreater(len(self.app._checked_paths), 0)
        self.app._uncheck_all_on_page()
        # 当前页的所有条目应被取消
        for iid in self.app.tree.get_children():
            node = self.app.item_map.get(iid)
            self.assertNotIn(node.path, self.app._checked_paths)

    def test_checks_persist_across_pages(self):
        """勾选状态跨页持久化"""
        self.app._render()
        # 第1页勾选前3个
        for iid in self.app.tree.get_children()[:3]:
            self.app._toggle_check(iid)
        checked_count = len(self.app._checked_paths)
        self.assertEqual(checked_count, 3)

        # 翻到第2页
        self.app._next_page()
        # 勾选状态仍然保留
        self.assertEqual(len(self.app._checked_paths), 3)

        # 翻回第1页
        self.app._prev_page()
        self.assertEqual(len(self.app._checked_paths), 3)

    def test_clear_all_checks(self):
        """清除所有勾选"""
        self.app._render()
        self.app._check_all_on_page()
        self.assertGreater(len(self.app._checked_paths), 0)
        self.app._clear_all_checks()
        self.assertEqual(len(self.app._checked_paths), 0)

    def test_check_count_display(self):
        """勾选后工具栏显示计数"""
        self.app._render()
        self.app._check_all_on_page()
        text = self.app.tree_title.cget("text")
        self.assertIn("Checked:", text)

    def test_checkbox_column_exists(self):
        """勾选列应存在"""
        self.app._render()
        cols = self.app.tree.cget('columns')
        self.assertIn('check', cols)

    def test_row_shows_checkbox(self):
        """每行应显示勾选框符号"""
        self.app._render()
        iid = self.app.tree.get_children()[0]
        vals = self.app.tree.item(iid, 'values')
        # 第一列是勾选框
        self.assertIn(vals[0], ('[ ]', '[x]'))

    def test_checked_row_has_highlight(self):
        """勾选的行应有高亮背景"""
        self.app._render()
        iid = self.app.tree.get_children()[0]
        self.app._toggle_check(iid)
        tags = self.app.tree.item(iid, 'tags')
        self.assertTrue(any('_checked' in t for t in tags))


@unittest.skipUnless(_HAS_DISPLAY, "No display available")
class TestGUIBatchDelete(unittest.TestCase):
    """测试批量删除功能"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="gui_batch_del_")
        for i in range(50):
            Path(cls.tmpdir, f"doc_{i:02d}.txt").write_text("x" * (i + 1))
        for i in range(30):
            Path(cls.tmpdir, f"app_{i:02d}.log").write_text("z" * 100)
        for i in range(10):
            Path(cls.tmpdir, f"cache_{i:02d}.tmp").write_text("t" * 1024)
        sub = Path(cls.tmpdir, "subdir")
        sub.mkdir()
        for i in range(5):
            (sub / f"sub_{i}.dat").write_text("d" * 200)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        from tkinter_gui import ScannerApp
        self.app = ScannerApp()
        scanner = Scanner()
        self.app.result = scanner.scan(self.tmpdir)
        self.app._switch("files")

    def tearDown(self):
        self.app.root.destroy()

    def test_batch_delete_nodes_files(self):
        """批量删除文件应成功"""
        tmp = tempfile.mkdtemp(prefix="batch_del_test_")
        try:
            paths = []
            for i in range(10):
                p = Path(tmp, f"del_{i}.txt")
                p.write_text("test")
                paths.append(str(p))

            nodes = [FileNode(name=os.path.basename(p), path=p,
                              size=4, modified=0, parent_path=tmp, extension=".txt")
                     for p in paths]
            # 先添加到勾选列表
            for p in paths:
                self.app._checked_paths.add(p)

            # 设置扫描路径为临时目录（安全校验需要）
            self.app.scan_path = tmp
            self.app._batch_delete_nodes(nodes)

            for p in paths:
                self.assertFalse(os.path.exists(p), f"文件未删除: {p}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_batch_delete_nodes_dirs(self):
        """批量删除目录应成功"""
        tmp = tempfile.mkdtemp(prefix="batch_del_dir_test_")
        try:
            dir_paths = []
            for i in range(5):
                d = Path(tmp, f"dir_{i}")
                d.mkdir()
                (d / "inner.txt").write_text("content")
                dir_paths.append(str(d))

            nodes = [DirNode(name=os.path.basename(d), path=d,
                             size=7, modified=0,
                             file_count=1, dir_count=0)
                     for d in dir_paths]

            self.app.scan_path = tmp
            self.app._batch_delete_nodes(nodes)

            for d in dir_paths:
                self.assertFalse(os.path.exists(d), f"目录未删除: {d}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_batch_delete_handles_permission_error(self):
        """删除权限不足的文件应记录错误但不崩溃"""
        tmp = tempfile.mkdtemp(prefix="batch_del_perm_")
        try:
            p = Path(tmp, "readonly.txt")
            p.write_text("protected")
            os.chmod(str(p), 0o444)

            fake = FileNode(name="fake.txt", path="/nonexistent/fake.txt",
                            size=0, modified=0, parent_path="/nonexistent",
                            extension=".txt")
            real = FileNode(name="readonly.txt", path=str(p),
                            size=9, modified=0, parent_path=tmp,
                            extension=".txt")

            self.app.scan_path = tmp
            self.app._batch_delete_nodes([fake, real])
        finally:
            try:
                os.chmod(str(Path(tmp, "readonly.txt")), 0o644)
            except Exception:
                pass
            shutil.rmtree(tmp, ignore_errors=True)

    def test_batch_delete_empty_list(self):
        """空列表不应报错"""
        self.app._batch_delete_nodes([])

    def test_batch_delete_removes_from_checked(self):
        """批量删除后应从勾选列表中移除"""
        tmp = tempfile.mkdtemp(prefix="batch_del_checked_")
        try:
            paths = []
            for i in range(5):
                p = Path(tmp, f"ck_{i}.txt")
                p.write_text("x")
                paths.append(str(p))
                self.app._checked_paths.add(str(p))

            nodes = [FileNode(name=os.path.basename(p), path=p,
                              size=1, modified=0, parent_path=tmp, extension=".txt")
                     for p in paths]

            self.app.scan_path = tmp
            self.app._batch_delete_nodes(nodes)
            for p in paths:
                self.assertNotIn(str(p), self.app._checked_paths)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_delete_checked_resets_page(self):
        """批量删除后页码应重置为 0"""
        tmp = tempfile.mkdtemp(prefix="batch_del_page_")
        try:
            paths = []
            for i in range(5):
                p = Path(tmp, f"page_{i}.txt")
                p.write_text("x")
                paths.append(str(p))
                self.app._checked_paths.add(str(p))

            nodes = [FileNode(name=os.path.basename(p), path=p,
                              size=1, modified=0, parent_path=tmp, extension=".txt")
                     for p in paths]

            self.app._page = 3
            self.app.scan_path = tmp
            self.app._batch_delete_nodes(nodes)
            self.assertEqual(self.app._page, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_safety_check_blocks_outside_path(self):
        """安全校验应拦截扫描路径外的文件"""
        # 在扫描路径外创建文件
        outside = tempfile.mkdtemp(prefix="outside_scan_")
        try:
            p = Path(outside, "outside.txt")
            p.write_text("danger")
            node = FileNode(name="outside.txt", path=str(p),
                            size=6, modified=0, parent_path=outside,
                            extension=".txt")
            self.app.scan_path = self.tmpdir  # 扫描路径是另一个目录
            self.app._batch_delete_nodes([node])
            # 文件不应被删除
            self.assertTrue(os.path.exists(str(p)), "安全校验失败：路径外的文件被删除了！")
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_safety_check_blocks_scan_root(self):
        """安全校验应拦截删除扫描根目录本身"""
        node = DirNode(name=os.path.basename(self.tmpdir),
                       path=self.tmpdir, size=0, modified=0,
                       file_count=0, dir_count=0)
        self.app.scan_path = self.tmpdir
        self.app._batch_delete_nodes([node])
        # 根目录不应被删除
        self.assertTrue(os.path.exists(self.tmpdir), "安全校验失败：扫描根目录被删除了！")

    def test_safety_check_blocks_no_scan_path(self):
        """无扫描路径时应拦截所有删除"""
        tmp = tempfile.mkdtemp(prefix="no_scan_path_")
        try:
            p = Path(tmp, "test.txt")
            p.write_text("x")
            node = FileNode(name="test.txt", path=str(p),
                            size=1, modified=0, parent_path=tmp,
                            extension=".txt")
            self.app.scan_path = ""  # 无扫描路径
            self.app._batch_delete_nodes([node])
            self.assertTrue(os.path.exists(str(p)), "安全校验失败：无扫描路径时文件被删除了！")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
