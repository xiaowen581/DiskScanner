#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docker_containers.py — Docker Containers 子标签页
"""

from tkinter import Label, E, W
from ui.docker_base import DockerTabBase
from ui.theme import C, F_SMALL, ConfirmDialog, InfoDialog
from docker_manager import DockerManager


class DockerContainersFrame(DockerTabBase):

    def _build_toolbar(self, parent):
        self._make_btn(parent, "REFRESH", self.load, padx=8).pack(side="left", padx=(0, 4))
        self._make_btn(parent, "CHECK ALL", self._check_all, padx=8).pack(side="left", padx=(0, 4))
        self._make_btn(parent, "CLEAR", self._clear_checks, padx=8).pack(side="left", padx=(0, 4))
        self._make_btn(parent, "STOP SELECTED", self._stop_selected,
                        bg=C["orange"], fg="#ffffff", hover_bg="#e6b800",
                        padx=12).pack(side="left", padx=(0, 4))
        self._make_btn(parent, "DELETE SELECTED", self._delete_selected,
                        bg="#da3633", fg="#ffffff", hover_bg="#f85149",
                        padx=12).pack(side="left", padx=(0, 4))
        self.count_label = Label(parent, text="", bg=C["bg"], fg=C["text2"], font=F_SMALL)
        self.count_label.pack(side="right")

    def load(self):
        self.status_var.set("Loading containers...")
        self.root.update_idletasks()
        try:
            self.containers = DockerManager.list_containers(all_states=True)
        except Exception as e:
            self.containers = []
            self.status_var.set(f"Error: {e}")
            return
        self._reload_rows()
        self.status_var.set(f"Loaded {len(self.containers)} container(s)")

    def _reload_rows(self):
        self._clear_tree()
        cols = ("check", "name", "image", "id", "state", "status", "ports", "created")
        widths = {"check": 40, "name": 180, "image": 200, "id": 110,
                  "state": 90, "status": 160, "ports": 200, "created": 160}
        anchors = {"check": 'center', "state": 'center', "id": 'center'}
        headings = {"check": "", "name": "Name", "image": "Image", "id": "Container ID",
                    "state": "State", "status": "Status", "ports": "Ports", "created": "Created"}
        self._setup_columns(cols, widths, anchors, headings)

        for i, ctr in enumerate(self.containers):
            iid = str(i)
            self.item_map[iid] = ctr
            ck = "[x]" if iid in self._checked else "[ ]"
            state_display = ctr.state.upper()
            vals = (ck, ctr.name, ctr.image, ctr.id, state_display,
                    ctr.status, ctr.ports, ctr.created_since)
            self._insert_row(iid, vals, i)
        self._update_check_count()

    def _update_check_count(self):
        n = len(self._checked)
        total = len(self.containers)
        self.count_label.config(
            text=f"Containers: {total}  |  Selected: {n}" if n else f"Containers: {total}")

    def _stop_selected(self):
        if not self._checked:
            InfoDialog(self.root, "Info", "No containers selected.")
            return
        ids_to_stop = []
        items = []
        for iid in list(self._checked):
            ctr = self.item_map.get(iid)
            if ctr and ctr.is_running:
                ids_to_stop.append(ctr.id)
                items.append(("CONTAINER", (ctr.name, ctr.state)))
        if not ids_to_stop:
            InfoDialog(self.root, "Info", "No running containers selected.")
            return
        dlg = ConfirmDialog(self.root, "Stop Containers",
                             f"Stop {len(items)} container(s)?", items,
                             confirm_text=f"Stop {len(items)}",
                             confirm_bg=C["orange"], confirm_hover="#e6b800")
        if not dlg.result:
            return
        results = DockerManager.stop_containers(ids_to_stop)
        self._show_result("Stop Containers", results)
        self.load()

    def _delete_selected(self):
        if not self._checked:
            InfoDialog(self.root, "Info", "No containers selected.")
            return
        ids_to_delete = []
        items = []
        for iid in list(self._checked):
            ctr = self.item_map.get(iid)
            if ctr:
                ids_to_delete.append(ctr.id)
                items.append(("CONTAINER", (ctr.name, ctr.state)))
        dlg = ConfirmDialog(self.root, "Delete Containers",
                             f"Delete {len(items)} container(s)?", items,
                             confirm_text=f"Delete {len(items)}")
        if not dlg.result:
            return
        results = DockerManager.remove_containers(ids_to_delete, force=True)
        self._show_result("Delete Containers", results)
        self.load()
