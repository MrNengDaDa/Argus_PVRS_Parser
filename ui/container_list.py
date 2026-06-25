#!/usr/bin/env python3
"""容器列表面板 — 显示所有 RULE / DEF 容器。"""

from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QLabel, QVBoxLayout, QWidget
from PyQt5.QtCore import pyqtSignal, Qt


class ContainerListWidget(QWidget):
    container_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("容器列表")
        lbl.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(lbl)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_clicked)
        layout.addWidget(self._list)

        self._container_names = []
        self._current_name = None

    def current_name(self):
        return self._current_name

    def populate(self, editor):
        """从 TokenEditor 填充容器列表。"""
        self._list.clear()
        self._container_names = []
        if editor is None:
            return

        for c in editor.containers():
            kind_label = 'RULE' if c['kind'] == 'RULE' else '  DEF'
            text = f"{kind_label}  {c['name']}   ({c['count']} 个元素)"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, c['name'])
            self._list.addItem(item)
            self._container_names.append(c['name'])

    def refresh_modification_markers(self, editor):
        """刷新修改标记。"""
        if editor is None:
            return
        for i in range(self._list.count()):
            item = self._list.item(i)
            name = item.data(Qt.UserRole)
            if not name:
                continue
            tokens = editor.tokens(name)
            modified = any(t.modified for t in tokens)
            kind = 'RULE' if any(
                c['name'] == name and c['kind'] == 'RULE'
                for c in editor.containers()
            ) else '  DEF'
            cnt = len(tokens)
            txt = f"{kind}  {name}   ({cnt} 个元素)"
            if modified:
                txt = f"* {txt}"
            item.setText(txt)

    def _on_clicked(self, item):
        name = item.data(Qt.UserRole)
        if name:
            self._current_name = name
            self.container_selected.emit(name)
