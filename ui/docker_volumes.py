#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docker_volumes.py — Docker Volumes 子标签页 (PyQt5 版本)
"""

from PyQt5.QtWidgets import QLabel, QHBoxLayout, QApplication
from PyQt5.QtCore import Qt
from ui.docker_base import DockerTabBase
from ui.theme import C, F_SMALL, make_font, ConfirmDialog, InfoDialog
from docker_manager import DockerManager


class DockerVolumesFrame(DockerTabBase):

    def _build_toolbar(self, layout):
        btn1 = self._make_btn(None, "REFRESH", self.load, padx=8)
        layout.addWidget(btn1)
        btn2 = self._make_btn(None, "CHECK ALL", self._check_all, padx=8)
        layout.addWidget(btn2)
        btn3 = self._make_btn(None, "CLEAR", self._clear_checks, padx=8)
        layout.addWidget(btn3)
        btn4 = self._make_btn(None, "DELETE SELECTED", self._delete_selected,
                               bg="#da3633", fg="#ffffff", hover_bg="#f85149",
                               padx=12)
        layout.addWidget(btn4)
        layout.addStretch()
        self.count_label = QLabel("")
        self.count_label.setFont(make_font(F_SMALL))
        self.count_label.setStyleSheet(f"color: {C['text2']};")
        layout.addWidget(self.count_label)

    def load(self):
        self.status_label.setText("Loading volumes...")
        QApplication.processEvents()
        try:
            self.volumes = DockerManager.list_volumes()
        except Exception as e:
            self.volumes = []
            self.status_label.setText(f"Error: {e}")
            return
        self._reload_rows()
        self.status_label.setText(f"Loaded {len(self.volumes)} volume(s)")

    def _reload_rows(self):
        self._clear_tree()
        cols = ["check", "name", "driver", "mountpoint", "created"]
        widths = {"check": 40, "name": 300, "driver": 100,
                  "mountpoint": 400, "created": 200}
        alignments = {"check": Qt.AlignCenter, "driver": Qt.AlignCenter}
        headings = {"check": "", "name": "Volume Name", "driver": "Driver",
                    "mountpoint": "Mountpoint", "created": "Created"}
        self._setup_columns(cols, widths, alignments, headings)

        self.tree.setRowCount(len(self.volumes))
        for i, vol in enumerate(self.volumes):
            iid = str(i)
            self.item_map[iid] = vol
            ck = "[x]" if iid in self._checked else "[ ]"
            vals = (ck, vol.name, vol.driver, vol.mountpoint, vol.created)
            self._insert_row(iid, vals, i)
        self._update_check_count()

    def _update_check_count(self):
        n = len(self._checked)
        total = len(self.volumes)
        self.count_label.setText(
            f"Volumes: {total}  |  Selected: {n}" if n else f"Volumes: {total}")

    def _delete_selected(self):
        if not self._checked:
            InfoDialog(self.root, "Info", "No volumes selected.")
            return
        names = []
        items = []
        for iid in list(self._checked):
            vol = self.item_map.get(iid)
            if vol:
                names.append(vol.name)
                items.append(("VOLUME", (vol.name, vol.driver)))
        dlg = ConfirmDialog(self.root, "Delete Volumes",
                             f"Delete {len(items)} volume(s)?", items,
                             confirm_text=f"Delete {len(items)}")
        if not dlg.result:
            return
        results = DockerManager.remove_volumes(names, force=True)
        self._show_result("Delete Volumes", results)
        self.load()
