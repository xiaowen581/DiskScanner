#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scanner_frame.py — File Scanner 标签页 (PyQt5 版本)
包含扫描、排序、过滤、删除、导出等全部功能
"""

import os
import sys
import shutil
import json
import csv

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QFrame, QMenu, QAction, QFileDialog, QMessageBox,
    QSizePolicy, QAbstractItemView, QApplication,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont

_script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _script_dir)

from disk_scanner import (
    Scanner, ScanResult, FileNode, DirNode,
    format_size, parse_size_filter, sort_nodes,
)
from ui.theme import (
    C, F_TITLE, F_BODY, F_SMALL, F_TINY, F_BIG, F_MONO, F_BTN,
    RoundButton, StatCard, ConfirmDialog, InfoDialog, fmt_time, make_font,
)


class ScanWorker(QThread):
    """后台扫描线程"""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, path, follow_symlinks=False):
        super().__init__()
        self.path = path
        self.follow_symlinks = follow_symlinks

    def run(self):
        try:
            scanner = Scanner(follow_symlinks=self.follow_symlinks)
            result = scanner.scan(self.path)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ScannerFrame(QWidget):
    """磁盘扫描器标签页"""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.root = app  # app 是主窗口

        # 状态
        self.result = None
        self.scan_path = ""
        self.view_mode = "dirs"
        self.sort_col = "size"
        self.sort_reverse = True
        self.item_map = {}
        self._scanning = False
        self._scan_result = None
        self._scan_error = None
        self._scan_worker = None
        self._page = 0
        self._page_size = 200
        self._sorted_items = []
        self._total_items = 0
        self._checked_paths = set()
        self._current_row = None

        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(8)

        self._build_header(outer)
        self._build_controls(outer)
        self._build_stats(outer)
        self._build_toolbar(outer)
        self._build_tree(outer)
        self._build_detail(outer)
        self._build_statusbar(outer)

    def _build_header(self, layout):
        hdr = QWidget()
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(0, 0, 0, 0)

        left = QWidget()
        left_layout = QHBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("DiskScanner")
        title.setFont(make_font(F_TITLE))
        title.setStyleSheet(f"color: {C['accent']};")
        left_layout.addWidget(title)
        ver = QLabel(" v1.0 ")
        ver.setFont(make_font(F_TINY))
        ver.setStyleSheet(f"color: {C['text2']}; background-color: {C['surface']}; border-radius: 4px; padding: 2px 6px;")
        left_layout.addWidget(ver)
        left_layout.addStretch()
        hdr_layout.addWidget(left, stretch=1)

        self._new_scan_btn = RoundButton(hdr, "New Scan", self._reset_scan,
                                          bg=C["btn_bg"], fg=C["text"])
        hdr_layout.addWidget(self._new_scan_btn)
        layout.addWidget(hdr)

    def _build_controls(self, layout):
        card = QFrame()
        card.setStyleSheet(f"background-color: {C['surface']}; border-radius: 8px;")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(8)

        # Row 1: Path
        r1 = QHBoxLayout()
        path_lbl = QLabel("PATH")
        path_lbl.setFont(make_font(F_TINY))
        path_lbl.setStyleSheet(f"color: {C['text2']};")
        r1.addWidget(path_lbl)

        self.path_entry = QLineEdit(os.path.expanduser("~"))
        self.path_entry.setFont(make_font(F_MONO))
        self.path_entry.returnPressed.connect(self._start_scan)
        r1.addWidget(self.path_entry, stretch=1)

        self._browse_btn = RoundButton(card, "Browse", self._browse,
                                        bg=C["btn_bg"], fg=C["text"])
        r1.addWidget(self._browse_btn)

        self._scan_btn = RoundButton(card, "START SCAN", self._start_scan,
                                      bg=C["accent"], fg="#ffffff",
                                      hover_bg="#79c0ff")
        r1.addWidget(self._scan_btn)
        card_layout.addLayout(r1)

        # Row 2: Filters
        r2 = QHBoxLayout()
        min_lbl = QLabel("MIN SIZE")
        min_lbl.setFont(make_font(F_TINY))
        min_lbl.setStyleSheet(f"color: {C['text3']};")
        r2.addWidget(min_lbl)
        self.min_size_var = QLineEdit()
        self.min_size_var.setFont(make_font(F_SMALL))
        self.min_size_var.setFixedWidth(80)
        r2.addWidget(self.min_size_var)

        r2.addSpacing(16)
        ext_lbl = QLabel("EXT FILTER")
        ext_lbl.setFont(make_font(F_TINY))
        ext_lbl.setStyleSheet(f"color: {C['text3']};")
        r2.addWidget(ext_lbl)
        self.ext_var = QLineEdit()
        self.ext_var.setFont(make_font(F_SMALL))
        self.ext_var.setFixedWidth(120)
        r2.addWidget(self.ext_var)

        r2.addSpacing(16)
        self.follow_sym = QCheckBox("Follow symlinks")
        self.follow_sym.setFont(make_font(F_SMALL))
        r2.addWidget(self.follow_sym)
        r2.addStretch()
        card_layout.addLayout(r2)

        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(4)
        self.progress.setVisible(False)
        card_layout.addWidget(self.progress)

        layout.addWidget(card)

    def _build_stats(self, layout):
        row = QHBoxLayout()
        row.setSpacing(6)
        self.sc_size  = StatCard(None, "TOTAL SIZE", C["green"])
        row.addWidget(self.sc_size)
        self.sc_files = StatCard(None, "FILES", C["text"])
        row.addWidget(self.sc_files)
        self.sc_dirs  = StatCard(None, "DIRS", C["orange"])
        row.addWidget(self.sc_dirs)
        self.sc_time  = StatCard(None, "DURATION", C["purple"])
        row.addWidget(self.sc_time)
        self.sc_skip  = StatCard(None, "SKIPPED", C["orange"])
        row.addWidget(self.sc_skip)
        layout.addLayout(row)

    def _build_toolbar(self, layout):
        tb = QHBoxLayout()
        tb.setSpacing(2)

        self.view_dirs_btn = RoundButton(None, "DIRS", lambda: self._switch("dirs"),
                                          bg=C["accent"], fg="#ffffff",
                                          hover_bg=C["accent"], padx=12)
        tb.addWidget(self.view_dirs_btn)
        self.view_files_btn = RoundButton(None, "FILES", lambda: self._switch("files"),
                                           bg=C["btn_bg"], fg=C["text"],
                                           hover_bg=C["btn_hover"], padx=12)
        tb.addWidget(self.view_files_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(f"color: {C['border']};")
        sep.setFixedWidth(1)
        tb.addWidget(sep)
        tb.addSpacing(6)

        self._check_all_btn = RoundButton(None, "CHECK PAGE", self._check_all_on_page,
                                            bg=C["btn_bg"], fg=C["text"], padx=8)
        tb.addWidget(self._check_all_btn)
        self._del_btn = RoundButton(None, "DELETE", self._delete_checked,
                                     bg="#da3633", fg="#ffffff", hover_bg="#f85149", padx=10)
        tb.addWidget(self._del_btn)
        self._clear_btn = RoundButton(None, "CLEAR", self._clear_all_checks,
                                       bg=C["btn_bg"], fg=C["text"], padx=8)
        tb.addWidget(self._clear_btn)
        tb.addWidget(RoundButton(None, "CSV", lambda: self._export("csv"),
                                  bg=C["btn_bg"], fg=C["text"], padx=10))
        tb.addWidget(RoundButton(None, "JSON", lambda: self._export("json"),
                                  bg=C["btn_bg"], fg=C["text"], padx=10))

        tb.addStretch()

        # Page nav
        pg = QHBoxLayout()
        pg.setSpacing(2)
        self._prev_btn = RoundButton(None, "<", self._prev_page,
                                      bg=C["btn_bg"], fg=C["text"], padx=8, pady=2)
        pg.addWidget(self._prev_btn)
        self._page_label = QLabel("")
        self._page_label.setFont(make_font(F_SMALL))
        self._page_label.setStyleSheet(f"color: {C['text2']};")
        pg.addWidget(self._page_label)
        self._next_btn = RoundButton(None, ">", self._next_page,
                                      bg=C["btn_bg"], fg=C["text"], padx=8, pady=2)
        pg.addWidget(self._next_btn)
        tb.addLayout(pg)

        self.tree_title = QLabel("")
        self.tree_title.setFont(make_font(F_SMALL))
        self.tree_title.setStyleSheet(f"color: {C['text2']};")
        tb.addWidget(self.tree_title)

        layout.addLayout(tb)

    def _build_tree(self, layout):
        wrap = QFrame()
        wrap.setStyleSheet(f"border: 1px solid {C['border']};")
        wrap_layout = QVBoxLayout(wrap)
        wrap_layout.setContentsMargins(1, 1, 1, 1)

        self.tree = QTableWidget()
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.verticalHeader().setVisible(False)
        self.tree.setShowGrid(True)
        self.tree.setSortingEnabled(False)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_rightclick)
        self.tree.itemSelectionChanged.connect(self._on_select)
        self.tree.cellDoubleClicked.connect(self._on_dblclick)
        self.tree.horizontalHeader().sectionClicked.connect(self._on_header_clicked)

        wrap_layout.addWidget(self.tree)
        layout.addWidget(wrap, stretch=1)

    def _build_detail(self, layout):
        det = QFrame()
        det.setStyleSheet(f"background-color: {C['surface']}; border-radius: 6px;")
        det_layout = QHBoxLayout(det)
        det_layout.setContentsMargins(14, 8, 14, 8)

        self.detail_label = QLabel("Select an item to see details   |   Double-click to drill down   |   Right-click for more")
        self.detail_label.setFont(make_font(F_SMALL))
        self.detail_label.setStyleSheet(f"color: {C['text2']};")
        det_layout.addWidget(self.detail_label, stretch=1)

        self.del_cmd_label = QLabel("")
        self.del_cmd_label.setFont(make_font(F_MONO))
        self.del_cmd_label.setStyleSheet(f"color: {C['red']};")
        det_layout.addWidget(self.del_cmd_label)
        layout.addWidget(det)

    def _build_statusbar(self, layout):
        self.status_label = QLabel("Ready")
        self.status_label.setFont(make_font(F_TINY))
        self.status_label.setStyleSheet(f"color: {C['text3']};")
        layout.addWidget(self.status_label)

    # ══════════════════════════════════════════════════════
    #  扫描逻辑
    # ══════════════════════════════════════════════════════

    def _reset_scan(self):
        self.result = None
        self._checked_paths.clear()
        self._clear_tree()
        for sc in (self.sc_size, self.sc_files, self.sc_dirs, self.sc_time, self.sc_skip):
            sc.set_value("--")
        self.status_label.setText("Ready")
        self.tree_title.setText("")
        self.detail_label.setText("Select an item to see details   |   Double-click to drill down   |   Right-click for more")
        self.del_cmd_label.setText("")

    def _browse(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select directory",
            self.path_entry.text() or os.path.expanduser("~"))
        if path:
            self.path_entry.setText(path)

    def _start_scan(self):
        if self._scanning:
            return
        path = self.path_entry.text().strip()
        if not path:
            QMessageBox.critical(self, "Error", "Please enter a path")
            return
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(abs_path):
            QMessageBox.critical(self, "Error", f"Path not found:\n{abs_path}")
            return
        if not os.path.isdir(abs_path):
            QMessageBox.critical(self, "Error", f"Not a directory:\n{abs_path}")
            return

        self._scanning = True
        self._scan_result = None
        self._scan_error = None
        self.scan_path = abs_path
        self.status_label.setText(f"Scanning {abs_path} ...")
        self.progress.setVisible(True)
        self._clear_tree()

        self._scan_worker = ScanWorker(abs_path, self.follow_sym.isChecked())
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_finished(self, result):
        self.progress.setVisible(False)
        self._scanning = False
        self._scan_worker = None

        self._scan_result = result
        self.result = result
        r = result
        skip_txt = f"  |  Skipped {r.skipped_count}" if r.skipped_count else ""
        self.status_label.setText(
            f"Done: {r.total_files:,} files, {r.total_dirs:,} dirs, "
            f"{r.scan_duration:.2f}s{skip_txt}")
        self._update_stats(r)
        self._render()

    def _on_scan_error(self, error_msg):
        self.progress.setVisible(False)
        self._scanning = False
        self._scan_worker = None
        QMessageBox.critical(self, "Scan Error", error_msg)
        self.status_label.setText("Scan failed")

    def _update_stats(self, r):
        self.sc_size.set_value(format_size(r.total_size))
        self.sc_files.set_value(f"{r.total_files:,}")
        self.sc_dirs.set_value(f"{r.total_dirs:,}")
        self.sc_time.set_value(f"{r.scan_duration:.2f}s")
        self.sc_skip.set_value(str(r.skipped_count) if r.skipped_count else "0")

    def _render(self):
        if not self.result:
            return
        r = self.result

        files = list(r.all_files)
        ms = parse_size_filter(self.min_size_var.text().strip())
        ext_str = self.ext_var.text().strip()
        exts = []
        if ext_str:
            exts = [e.strip().lower() if e.strip().startswith('.')
                    else f'.{e.strip().lower()}' for e in ext_str.split(',') if e.strip()]
        if ms > 0:
            files = [f for f in files if f.size >= ms]
        if exts:
            files = [f for f in files if f.extension in exts]

        dirs = r.all_dirs
        if ms > 0 or exts:
            dp = set(f.parent_path for f in files)
            dirs = [d for d in dirs if d.path in dp or d.path == r.root.path]

        sort_mode = self._sort_mode_key()
        all_items = sort_nodes(dirs if self.view_mode == "dirs" else files, sort_mode)
        self._sorted_items = all_items
        self._total_items = len(all_items)

        max_page = max(0, (self._total_items - 1) // self._page_size)
        if self._page > max_page:
            self._page = max_page
        if self._page < 0:
            self._page = 0

        start = self._page * self._page_size
        end = start + self._page_size
        items = all_items[start:end]
        self.item_map = {}

        is_dirs = self.view_mode == "dirs"
        if is_dirs:
            cols = ["check", "path", "size", "files", "subdirs", "pct", "modified"]
            widths = [36, 500, 110, 80, 80, 70, 150]
            header_labels = [
                "",
                f"Path",
                f"Size{self._arrow('size')}",
                f"Files{self._arrow('files')}",
                f"SubDirs{self._arrow('subdirs')}",
                "%",
                f"Modified{self._arrow('modified')}",
            ]
        else:
            cols = ["check", "path", "size", "ext", "pct", "modified"]
            widths = [36, 540, 110, 80, 70, 150]
            header_labels = [
                "",
                f"Path",
                f"Size{self._arrow('size')}",
                f"Type{self._arrow('ext')}",
                "%",
                f"Modified{self._arrow('modified')}",
            ]

        self.tree.setColumnCount(len(cols))
        self.tree.setHorizontalHeaderLabels(header_labels)
        for i, w in enumerate(widths):
            self.tree.setColumnWidth(i, w)
        self.tree.setRowCount(len(items))
        self._cols = cols

        total = max(r.total_size, 1)
        for i, node in enumerate(items):
            iid = str(i)
            self.item_map[iid] = node
            pct = f"{node.size / total * 100:.1f}%"
            checked = node.path in self._checked_paths
            ck = "[x]" if checked else "[ ]"

            if is_dirs:
                vals = [ck, node.path, format_size(node.size), str(node.file_count),
                        str(node.dir_count), pct, fmt_time(node.modified)]
            else:
                vals = [ck, node.path, format_size(node.size), node.extension or "-",
                        pct, fmt_time(node.modified)]

            # Determine row background
            base = 'odd' if i % 2 else 'even'
            if checked:
                bg = QColor(C["checked_odd"] if base == 'odd' else C["checked_even"])
            else:
                bg = QColor(C["tree_row1"] if base == 'odd' else C["tree_row2"])

            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setBackground(bg)
                if j == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                elif j in (2, 3, 4, 5) and not is_dirs or j in (2, 3, 4, 5, 6) and is_dirs:
                    if j >= 2:
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tree.setItem(i, j, item)

        vlabel = "Directories" if self.view_mode == "dirs" else "Files"
        checked_count = len(self._checked_paths)
        if checked_count > 0:
            self.tree_title.setText(
                f"{vlabel} ({self._total_items:,})  |  Checked: {checked_count}")
        else:
            self.tree_title.setText(f"{vlabel} ({self._total_items:,})")

        if self._total_items == 0:
            self._page_label.setText("")
        else:
            self._page_label.setText(f"{self._page + 1}/{max_page + 1}")

    def _arrow(self, col):
        """返回排序箭头指示符"""
        if col != self.sort_col:
            return ""
        return "\u25bc" if self.sort_reverse else "\u25b2"

    # ── 分页导航 ──

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._render()

    def _next_page(self):
        max_page = max(0, (self._total_items - 1) // self._page_size)
        if self._page < max_page:
            self._page += 1
            self._render()

    # ── 排序 ──

    def _sort_mode_key(self):
        if self.sort_col == "size":
            return "size-desc" if self.sort_reverse else "size-asc"
        elif self.sort_col in ("name", "path"):
            return "name"
        elif self.sort_col == "modified":
            return "modified"
        return "size-desc"

    def _sort_by(self, col):
        if col == self.sort_col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_col = col
            self.sort_reverse = True
        self._page = 0
        self._render()

    def _on_header_clicked(self, logical_index):
        if not hasattr(self, '_cols'):
            return
        if logical_index < len(self._cols):
            col_name = self._cols[logical_index]
            sortable = {"path", "size", "files", "subdirs", "ext", "modified", "name"}
            if col_name in sortable:
                self._sort_by(col_name)

    # ── 视图切换 ──

    def _switch(self, mode):
        self.view_mode = mode
        self._page = 0
        if mode == "dirs":
            self.view_dirs_btn.config(bg=C["accent"], fg="#ffffff")
            self.view_files_btn.config(bg=C["btn_bg"], fg=C["text"])
        else:
            self.view_dirs_btn.config(bg=C["btn_bg"], fg=C["text"])
            self.view_files_btn.config(bg=C["accent"], fg="#ffffff")
        self._render()

    # ── 事件处理 ──

    def _on_select(self):
        row = self.tree.currentRow()
        if row < 0:
            return
        iid = str(row)
        node = self.item_map.get(iid)
        if not node:
            return
        if isinstance(node, DirNode):
            cmd = f'rm -rf "{node.path}"'
            info = (f"[DIR] {node.path}   {format_size(node.size)}"
                    f"   Files: {node.file_count}  SubDirs: {node.dir_count}")
        else:
            cmd = f'rm "{node.path}"'
            info = f"[FILE] {node.path}   {format_size(node.size)}   {node.extension or '?'}"
        self.detail_label.setText(info)
        self.del_cmd_label.setText(f"$ {cmd}")

    def _on_dblclick(self, row, col):
        iid = str(row)
        node = self.item_map.get(iid)
        if not node:
            return
        if os.path.isdir(node.path):
            self.path_entry.setText(node.path)
            QMessageBox.information(self, "Info", f"Scan path set to:\n{node.path}")
        else:
            self.path_entry.setText(os.path.dirname(node.path))

    def _on_rightclick(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        row = item.row()
        iid = str(row)
        self._current_row = iid
        node = self.item_map.get(iid)
        if not node:
            return

        m = QMenu(self)
        if node.path in self._checked_paths:
            m.addAction("Uncheck", lambda: self._toggle_check(iid))
        else:
            m.addAction("Check", lambda: self._toggle_check(iid))

        m.addAction("Check all on page", self._check_all_on_page)
        m.addAction("Uncheck all on page", self._uncheck_all_on_page)
        m.addSeparator()
        m.addAction("Copy path", self._ctx_copy_path)
        m.addAction("Copy parent dir", self._ctx_copy_dir)
        m.addSeparator()
        m.addAction("Scan this dir", lambda: self._ctx_scan(iid))

        m.exec_(self.tree.viewport().mapToGlobal(pos))

    def _ctx_copy_path(self):
        row = self._current_row
        if row is not None:
            node = self.item_map.get(str(row))
            if node:
                QApplication.clipboard().setText(node.path)
                self.status_label.setText(f"Copied: {node.path}")

    def _ctx_copy_dir(self):
        row = self._current_row
        if row is not None:
            node = self.item_map.get(str(row))
            if node:
                d = node.path if isinstance(node, DirNode) else os.path.dirname(node.path)
                QApplication.clipboard().setText(d)
                self.status_label.setText(f"Copied: {d}")

    def _ctx_scan(self, iid):
        node = self.item_map.get(str(iid))
        if node:
            d = node.path if isinstance(node, DirNode) else os.path.dirname(node.path)
            self.path_entry.setText(d)
            self._start_scan()

    # ── 勾选操作 ──

    def _toggle_check(self, iid):
        node = self.item_map.get(iid)
        if not node:
            return
        if node.path in self._checked_paths:
            self._checked_paths.discard(node.path)
        else:
            self._checked_paths.add(node.path)
        self._update_row_check(iid, node.path)
        self._update_check_count()

    def _update_row_check(self, iid, path):
        row = int(iid)
        checked = path in self._checked_paths
        ck = "[x]" if checked else "[ ]"

        # Update checkbox text
        item = self.tree.item(row, 0)
        if item:
            item.setText(ck)

        # Update row background
        base = 'odd' if row % 2 else 'even'
        if checked:
            bg = QColor(C["checked_odd"] if base == 'odd' else C["checked_even"])
        else:
            bg = QColor(C["tree_row1"] if base == 'odd' else C["tree_row2"])
        for col in range(self.tree.columnCount()):
            item = self.tree.item(row, col)
            if item:
                item.setBackground(bg)

    def _update_check_count(self):
        count = len(self._checked_paths)
        vlabel = "Directories" if self.view_mode == "dirs" else "Files"
        if count > 0:
            self.tree_title.setText(
                f"{vlabel} ({self._total_items:,})  |  Checked: {count}")
        else:
            self.tree_title.setText(f"{vlabel} ({self._total_items:,})")

    def _check_all_on_page(self):
        for i in range(self.tree.rowCount()):
            iid = str(i)
            node = self.item_map.get(iid)
            if node:
                self._checked_paths.add(node.path)
                self._update_row_check(iid, node.path)
        self._update_check_count()

    def _uncheck_all_on_page(self):
        for i in range(self.tree.rowCount()):
            iid = str(i)
            node = self.item_map.get(iid)
            if node:
                self._checked_paths.discard(node.path)
                self._update_row_check(iid, node.path)
        self._update_check_count()

    def _clear_all_checks(self):
        self._checked_paths.clear()
        self._render()

    # ── 删除 ──

    def _delete_checked(self):
        if not self._checked_paths:
            InfoDialog(self.root, "Info",
                       "No items checking.\nClick the checkbox column to select items.")
            return

        nodes = []
        all_nodes = list(self.result.all_dirs) + list(self.result.all_files) if self.result else []
        for n in all_nodes:
            if n.path in self._checked_paths:
                nodes.append(n)

        if not nodes:
            self._checked_paths.clear()
            return

        count = len(nodes)
        total_size = sum(n.size for n in nodes)
        dir_count = sum(1 for n in nodes if isinstance(n, DirNode))
        file_count = count - dir_count

        summary = (f"{count} items: {file_count} files, {dir_count} dirs, "
                   f"total {format_size(total_size)}")

        items = []
        for n in nodes:
            lbl = "DIR" if isinstance(n, DirNode) else "FILE"
            items.append((lbl, (n.path, format_size(n.size))))

        dlg = ConfirmDialog(self.root, "Confirm Delete", summary, items,
                             confirm_text=f"Delete {count}")
        if not dlg.result:
            return

        self._batch_delete_nodes(nodes)

    def _batch_delete_nodes(self, nodes):
        if not nodes:
            return

        safe_nodes = []
        blocked = []
        scan_root = os.path.realpath(self.scan_path) if self.scan_path else ""

        for node in nodes:
            target = os.path.realpath(node.path)
            if not scan_root:
                blocked.append((node.path, "No scan path set"))
            elif target == scan_root:
                blocked.append((node.path, "Cannot delete scan root itself"))
            elif not target.startswith(scan_root + os.sep) and target != scan_root:
                blocked.append((node.path, f"Outside scan path: {scan_root}"))
            else:
                safe_nodes.append(node)

        if blocked:
            blocked_msg = "\n".join(f"  {p}: {r}" for p, r in blocked[:10])
            if len(blocked) > 10:
                blocked_msg += f"\n  ... and {len(blocked) - 10} more"
            InfoDialog(self.root, "Security Check Failed",
                       f"{len(blocked)} item(s) blocked for safety:\n\n{blocked_msg}",
                       msg_color=C["red"])
            if not safe_nodes:
                return

        total = len(safe_nodes)
        deleted = 0
        errors = []

        self._del_btn.config(state='disabled')

        for i, node in enumerate(safe_nodes):
            try:
                if isinstance(node, DirNode):
                    shutil.rmtree(node.path, ignore_errors=False)
                else:
                    os.remove(node.path)
                deleted += 1
                self._checked_paths.discard(node.path)
            except Exception as e:
                errors.append(f"{node.path}: {e}")

            if (i + 1) % 50 == 0:
                self.status_label.setText(f"Deleting... {i + 1}/{total}")
                QApplication.processEvents()

        self._del_btn.config(state='normal')

        blocked_count = len(blocked)
        summary_parts = [f"Deleted: {deleted}/{total}"]
        if errors:
            summary_parts.append(f"Failed: {len(errors)}")
        if blocked_count:
            summary_parts.append(f"Blocked: {blocked_count}")

        if errors:
            err_detail = "\n".join(errors[:15])
            InfoDialog(self.root, "Partial Failure",
                       ", ".join(summary_parts) + "\n\n" + err_detail,
                       msg_color=C["orange"])
        else:
            InfoDialog(self.root, "Done", ", ".join(summary_parts),
                       msg_color=C["green"])

        self.status_label.setText(
            f"Deleted {deleted}/{total}" +
            (f", failed {len(errors)}" if errors else "") +
            (f", blocked {blocked_count}" if blocked_count else ""))
        self._page = 0
        self._render()

    # ── 导出 ──

    def _export(self, fmt):
        if not self.result:
            QMessageBox.warning(self, "Warning", "Please scan first")
            return
        r = self.result
        ext = "json" if fmt == "json" else "csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export", f"disk_scan.{ext}",
            "CSV (*.csv);;JSON (*.json)")
        if not path:
            return
        try:
            if fmt == "json":
                def to_dict(n):
                    b = {"name": n.name, "path": n.path, "size": n.size,
                         "size_human": format_size(n.size), "modified": fmt_time(n.modified)}
                    if isinstance(n, FileNode):
                        b["type"] = "file"; b["extension"] = n.extension
                    else:
                        b["type"] = "directory"
                        b["file_count"] = n.file_count; b["dir_count"] = n.dir_count
                    return b
                data = {
                    "summary": {"total_size": r.total_size,
                                 "total_size_human": format_size(r.total_size),
                                 "total_files": r.total_files, "total_dirs": r.total_dirs},
                    "directories": [to_dict(d) for d in sort_nodes(r.all_dirs, "size-desc")],
                    "files": [to_dict(f) for f in sort_nodes(r.all_files, "size-desc")],
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["Type", "Name", "Path", "Size(bytes)", "Size", "Modified"])
                    for n in sort_nodes(r.all_dirs, "size-desc"):
                        w.writerow(["Dir", n.name, n.path, n.size, format_size(n.size), fmt_time(n.modified)])
                    for n in sort_nodes(r.all_files, "size-desc"):
                        w.writerow(["File", n.name, n.path, n.size, format_size(n.size), fmt_time(n.modified)])
            QMessageBox.information(self, "Export OK", f"Saved to:\n{path}")
            self.status_label.setText(f"Exported: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _clear_tree(self):
        self.tree.setRowCount(0)
        self.item_map.clear()
        self._checked_paths.clear()

