#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docker_images.py — Docker Images 子标签页
"""

from tkinter import Label, E, W
from ui.docker_base import DockerTabBase
from ui.theme import C, F_SMALL, ConfirmDialog, InfoDialog
from docker_manager import DockerManager


class DockerImagesFrame(DockerTabBase):

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
        self.status_var.set("Loading images...")
        self.root.update_idletasks()
        try:
            self.images = DockerManager.list_images()
        except Exception as e:
            self.images = []
            self.status_var.set(f"Error: {e}")
            return
        self._reload_rows()
        self.status_var.set(f"Loaded {len(self.images)} image(s)")

    def _reload_rows(self):
        self._clear_tree()
        cols = ("check", "repository", "tag", "id", "size", "created")
        widths = {"check": 40, "repository": 320, "tag": 120,
                  "id": 120, "size": 110, "created": 180}
        anchors = {"check": 'center', "size": E, "id": 'center'}
        headings = {"check": "", "repository": "Repository", "tag": "Tag",
                    "id": "Image ID", "size": "Size", "created": "Created"}
        self._setup_columns(cols, widths, anchors, headings)

        for i, img in enumerate(self.images):
            iid = str(i)
            self.item_map[iid] = img
            ck = "[x]" if iid in self._checked else "[ ]"
            vals = (ck, img.repository, img.tag, img.id,
                    img.size_human, img.created_since)
            self._insert_row(iid, vals, i)
        self._update_check_count()

    def _update_check_count(self):
        n = len(self._checked)
        total = len(self.images)
        self.count_label.config(
            text=f"Images: {total}  |  Selected: {n}" if n else f"Images: {total}")

    def _delete_selected(self):
        if not self._checked:
            InfoDialog(self.root, "Info", "No images selected.")
            return
        items = []
        ids_to_delete = []
        for iid in list(self._checked):
            img = self.item_map.get(iid)
            if img:
                items.append(("IMAGE", (img.full_name, img.size_human)))
                ids_to_delete.append(img.id)
        dlg = ConfirmDialog(self.root, "Delete Images",
                             f"Delete {len(items)} image(s)?", items,
                             confirm_text=f"Delete {len(items)}")
        if not dlg.result:
            return
        results = DockerManager.remove_images(ids_to_delete, force=True)
        self._show_result("Delete Images", results)
        self.load()
