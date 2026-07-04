#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docker_base.py — Docker tab 基类 (PyQt5 版本)
提供 QTableWidget + checkbox 通用逻辑
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QApplication,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from ui.theme import (
    C, F_SMALL, F_TINY, F_BTN, make_font,
    RoundButton, ConfirmDialog, InfoDialog,
)


class DockerTabBase(QWidget):
    """Base class for Docker management tabs."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.root = app  # 主窗口
        self._checked = set()
        self.item_map = {}
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(6)

        tb = QHBoxLayout()
        self._build_toolbar(tb)
        outer.addLayout(tb)

        # Table
        self.tree = QTableWidget()
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.verticalHeader().setVisible(False)
        self.tree.setShowGrid(True)
        self.tree.setSortingEnabled(False)

        self.tree.cellClicked.connect(self._on_click)

        outer.addWidget(self.tree, stretch=1)

        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setFont(make_font(F_TINY))
        self.status_label.setStyleSheet(f"color: {C['text3']};")
        outer.addWidget(self.status_label)

    def _build_toolbar(self, layout):
        """Override in subclass."""
        pass

    def load(self):
        """Override in subclass to load data."""
        pass

    def _on_click(self, row, col):
        if col == 0:
            iid = str(row)
            self._toggle_check(iid)

    def _toggle_check(self, iid):
        if iid in self._checked:
            self._checked.discard(iid)
        else:
            self._checked.add(iid)
        checked = iid in self._checked
        ck = "[x]" if checked else "[ ]"
        row = int(iid)

        item = self.tree.item(row, 0)
        if item:
            item.setText(ck)

        # Update row background
        base = 'odd' if row % 2 else 'even'
        if checked:
            bg = QColor(C["checked_odd"] if base == 'odd' else C["checked_even"])
        else:
            bg = QColor(C["tree_row1"] if base == 'odd' else C["tree_row2"])
        for c in range(self.tree.columnCount()):
            ci = self.tree.item(row, c)
            if ci:
                ci.setBackground(bg)

        self._update_check_count()

    def _update_check_count(self):
        """Override in subclass."""
        pass

    def _check_all(self):
        for i in range(self.tree.rowCount()):
            iid = str(i)
            if iid not in self._checked:
                self._toggle_check(iid)
        self._update_check_count()

    def _clear_checks(self):
        self._checked.clear()
        self._reload_rows()

    def _make_btn(self, parent, text, cmd, **kw):
        btn = RoundButton(parent, text, cmd,
                           bg=kw.pop('bg', C["btn_bg"]),
                           fg=kw.pop('fg', C["text"]),
                           hover_bg=kw.pop('hover_bg', C["btn_hover"]),
                           padx=kw.pop('padx', 10))
        return btn

    def _setup_columns(self, cols, widths, alignments=None, headings=None):
        self.tree.setColumnCount(len(cols))
        alignments = alignments or {}
        headings = headings or {}
        labels = [headings.get(c, c) for c in cols]
        self.tree.setHorizontalHeaderLabels(labels)
        for i, c in enumerate(cols):
            self.tree.setColumnWidth(i, widths.get(c, 120))
        self._cols = cols

    def _clear_tree(self):
        self.tree.setRowCount(0)
        self.item_map.clear()
        self._checked.clear()

    def _insert_row(self, iid, values, idx):
        row = int(iid)
        base = 'odd' if idx % 2 else 'even'
        bg = QColor(C["tree_row1"] if base == 'odd' else C["tree_row2"])

        for j, val in enumerate(values):
            item = QTableWidgetItem(str(val))
            item.setBackground(bg)
            if j == 0:
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.tree.setItem(row, j, item)

    def _show_result(self, title, results):
        ok = sum(1 for r in results if r.success)
        fail = len(results) - ok
        msg = f"Success: {ok}, Failed: {fail}"
        if fail:
            err_details = "\n".join(
                r.message for r in results if not r.success
            )[:500]
            InfoDialog(self.root, title, msg + "\n\n" + err_details,
                       msg_color=C["orange"])
        else:
            InfoDialog(self.root, title, msg,
                       msg_color=C["green"])
