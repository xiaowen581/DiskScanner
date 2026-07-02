#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docker_frame.py — Docker 父标签页
包含子 Notebook，下分 Images / Containers / Volumes 三个子标签页
"""

from tkinter import ttk, Frame, BOTH
from ui.theme import C, setup_styles
from ui.docker_images import DockerImagesFrame
from ui.docker_containers import DockerContainersFrame
from ui.docker_volumes import DockerVolumesFrame


class DockerFrame(Frame):
    """Docker 管理父标签页 — 内含子 Notebook (Images / Containers / Volumes)"""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.root = app

        self._loaded = {"images": False, "containers": False, "volumes": False}
        self._build()

    def _build(self):
        # 子 Notebook
        self.notebook = ttk.Notebook(self, style='Sub.TNotebook')
        self.notebook.pack(fill=BOTH, expand=True, padx=8, pady=8)

        # Sub-tab 1: Images
        self.images_frame = DockerImagesFrame(self.notebook, self.app)
        self.notebook.add(self.images_frame, text="  Images  ")

        # Sub-tab 2: Containers
        self.containers_frame = DockerContainersFrame(self.notebook, self.app)
        self.notebook.add(self.containers_frame, text="  Containers  ")

        # Sub-tab 3: Volumes
        self.volumes_frame = DockerVolumesFrame(self.notebook, self.app)
        self.notebook.add(self.volumes_frame, text="  Volumes  ")

        # Lazy-load sub-tabs
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)

    def _on_tab_changed(self, event):
        """首次切换到子标签页时自动加载数据"""
        idx = self.notebook.index(self.notebook.select())
        if idx == 0 and not self._loaded["images"]:
            self.images_frame.load()
            self._loaded["images"] = True
        elif idx == 1 and not self._loaded["containers"]:
            self.containers_frame.load()
            self._loaded["containers"] = True
        elif idx == 2 and not self._loaded["volumes"]:
            self.volumes_frame.load()
            self._loaded["volumes"] = True

    def load_first(self):
        """首次进入 Docker 主 tab 时调用，加载第一个子 tab"""
        if not self._loaded["images"]:
            self.images_frame.load()
            self._loaded["images"] = True
