#!/usr/bin/env python3
"""编号表 — 可编辑的 TokenElement 表格。"""

from PyQt5.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QWidget, QVBoxLayout,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor


class LegendTable(QWidget):
    element_modified = pyqtSignal()

    COL_INDEX = 0
    COL_TYPE = 1
    COL_TEXT = 2
    COL_NEW = 3
    COL_LINE = 4

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["编号", "类型", "原文", "新值", "行号"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self._table.cellChanged.connect(self._on_cell_changed)
        self._table.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        self._editor = None
        self._container = None

    def show_legend(self, editor, container_name, legend):
        """从 legend dict 填充表格。"""
        self._editor = editor
        self._container = container_name

        self._table.blockSignals(True)
        self._table.setRowCount(0)

        for idx in sorted(legend):
            type_name, text, modified, line = legend[idx]
            row = self._table.rowCount()
            self._table.insertRow(row)

            # 编号
            item_idx = QTableWidgetItem(str(idx))
            item_idx.setFlags(item_idx.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, self.COL_INDEX, item_idx)

            # 类型
            item_type = QTableWidgetItem(type_name)
            item_type.setFlags(item_type.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, self.COL_TYPE, item_type)

            # 原文
            item_text = QTableWidgetItem(text)
            item_text.setFlags(item_text.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, self.COL_TEXT, item_text)

            # 新值（可编辑）
            new_val = text if not modified else editor.tokens(container_name)[idx - 1].new_text or text
            item_new = QTableWidgetItem(new_val)
            self._table.setItem(row, self.COL_NEW, item_new)

            # 行号
            item_line = QTableWidgetItem(str(line))
            item_line.setFlags(item_line.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, self.COL_LINE, item_line)

            # 修改标记
            if modified:
                for col in range(5):
                    self._table.item(row, col).setBackground(QColor("#FFE0E0"))

        self._table.blockSignals(False)

    def _on_cell_changed(self, row, col):
        if col != self.COL_NEW or not self._editor:
            return
        idx_item = self._table.item(row, self.COL_INDEX)
        new_item = self._table.item(row, self.COL_NEW)
        if not idx_item or not new_item:
            return

        idx = int(idx_item.text())
        old_text = self._table.item(row, self.COL_TEXT).text()
        new_text = new_item.text().strip()

        if new_text == old_text:
            return

        if not new_text:
            return

        ok = self._editor.replace_by_index(self._container, idx, new_text)
        if ok:
            for c in range(5):
                self._table.item(row, c).setBackground(QColor("#FFE0E0"))
            self.element_modified.emit()

    def _on_double_click(self, item):
        """双击原文列 → 批量替换。"""
        if not self._editor or item.column() != self.COL_TEXT:
            return
        old_text = item.text()
        reply = QMessageBox.question(
            self, "批量替换",
            f"将容器 {self._container} 中所有 {old_text!r} 替换为新值？",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        from PyQt5.QtWidgets import QInputDialog
        new_text, ok = QInputDialog.getText(
            self, "输入新值", f"将 {old_text!r} 全部替换为:")
        if not ok or not new_text or new_text == old_text:
            return

        ok = self._editor.replace_by_text(self._container, old_text, new_text)
        if ok:
            legend = self._editor.annotated_legend(self._container)
            self.show_legend(self._editor, self._container, legend)
            self.element_modified.emit()

    def clear(self):
        self._editor = None
        self._container = None
        self._table.setRowCount(0)
