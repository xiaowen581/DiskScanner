#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docker_volumes.py — Docker Volumes 子标签页
"""

from tkinter import Label, E, W
from ui.docker_base import DockerTabBase
from ui.theme import C, F_SMALL, ConfirmDialog, InfoDialog
from docker_manager import DockerManager


class DockerVolumesFrame(DockerTabBase):

    def _build_toolbar(self, parent):
        self._make_btn(parent, "REFRESH", self.load, padx=8).pack(side="left", padx=(0, 4))
        self._make_btn(parent, "CHECK ALL", self._check_all, padx=8).pack(side="left", padx=(0, 4))
        self._make_btn(parent, "CLEAR", self._clear_checks, padx=8).pack(side="left", padx=(0, 4))
        self._make_btn(parent, "DELETE SELECTED", self._delete_selected,
                        bg="#da3633", fg="#ffffff", hover_bg="#f85149",
                        padx=12).pack(side="left", padx=(0, 4))
        self.count_label = Label(parent, text="", bg=C["bg"], fg=C["text2"], font=F_SMALL)
        self.count_label.pack(side="right")

    def load(self):
        self.status_var.set("Loading volumes...")
        self.root.update_idletasks()
        try:
            self.volumes = DockerManager.list_volumes()
        except Exception as e:
            self.volumes = []
            self.status_var.set(f"Error: {e}")
            return
        self._reload_rows()
        self.status_var.set(f"Loaded {len(self.volumes)} volume(s)")

    def _reload_rows(self):
        self._clear_tree()
        cols = ("check", "name", "driver", "mountpoint", "created")
        widths = {"check": 40, "name": 300, "driver": 100,
                  "mountpoint": 400, "created": 200}
        anchors = {"check": 'center', "driver": 'center'}
        headings = {"check": "", "name": "Volume Name", "driver": "Driver",
                    "mountpoint": "Mountpoint", "created": "Created"}
        self._setup_columns(cols, widths, anchors, headings)

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
        self.count_label.config(
            text=f"Volumes: {total}  |  Selected: {n}" if n else f"Volumes: {total}")

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
