#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docker_frame.py — Docker 父标签页 (PyQt5 版本)
包含子 QTabWidget，下分 Images / Containers / Volumes 三个子标签页
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from ui.theme import C
from ui.docker_images import DockerImagesFrame
from ui.docker_containers import DockerContainersFrame
from ui.docker_volumes import DockerVolumesFrame


class DockerFrame(QWidget):
    """Docker 管理父标签页 — 内含子 QTabWidget (Images / Containers / Volumes)"""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.root = app

        self._loaded = {"images": False, "containers": False, "volumes": False}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 子 QTabWidget
        self.notebook = QTabWidget()
        self.notebook.setObjectName("dockerTabs")
        layout.addWidget(self.notebook)

        # Sub-tab 1: Images
        self.images_frame = DockerImagesFrame(self.notebook, self.app)
        self.notebook.addTab(self.images_frame, "  Images  ")

        # Sub-tab 2: Containers
        self.containers_frame = DockerContainersFrame(self.notebook, self.app)
        self.notebook.addTab(self.containers_frame, "  Containers  ")

        # Sub-tab 3: Volumes
        self.volumes_frame = DockerVolumesFrame(self.notebook, self.app)
        self.notebook.addTab(self.volumes_frame, "  Volumes  ")

        # Lazy-load sub-tabs
        self.notebook.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, idx):
        """首次切换到子标签页时自动加载数据"""
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
