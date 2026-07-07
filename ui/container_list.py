#!/usr/bin/env python3
"""容器列表面板 — 显示所有 RULE / DEF 容器，支持名称过滤。"""

from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QLabel, QVBoxLayout, QWidget, QLineEdit
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

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("输入名称后回车过滤...")
        self._filter_input.setClearButtonEnabled(True)
        self._filter_input.returnPressed.connect(self._on_filter_changed)
        self._filter_input.textChanged.connect(self._on_filter_text_changed)
        layout.addWidget(self._filter_input)

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
        self._filter_input.clear()
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

    def _on_filter_text_changed(self, text):
        """输入框清空时自动恢复全部显示。"""
        if not text.strip():
            self._show_all()

    def _on_filter_changed(self):
        """输入文字后回车确认，过滤列表项。"""
        text = self._filter_input.text().strip()
        if not text:
            self._show_all()
            return
        for i in range(self._list.count()):
            item = self._list.item(i)
            name = item.data(Qt.UserRole) or ''
            item.setHidden(text.lower() not in name.lower())

    def _show_all(self):
        """显示所有列表项。"""
        for i in range(self._list.count()):
            self._list.item(i).setHidden(False)

    def _on_clicked(self, item):
        name = item.data(Qt.UserRole)
        if name:
            self._current_name = name
            self.container_selected.emit(name)
