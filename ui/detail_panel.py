#!/usr/bin/env python3
"""详情面板 — 标注视图 / 编号表 / VAR-FUN 引用 三个 Tab。"""

from PyQt5.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import pyqtSignal

from ui.annotated_view import AnnotatedTextView
from ui.legend_table import LegendTable
from ui.var_fun_panel import VarFunPanel


class DetailPanel(QTabWidget):
    element_modified = pyqtSignal()
    save_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    staged = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Tab 1: 标注视图（可双击编辑）
        self._annotated_view = AnnotatedTextView()
        self._annotated_view.element_modified.connect(self.element_modified.emit)
        self._annotated_view.save_requested.connect(self.save_requested.emit)
        self._annotated_view.undo_requested.connect(self.undo_requested.emit)
        self._annotated_view.staged.connect(self.staged.emit)
        self.addTab(self._annotated_view, "标注视图（双击编辑）")

        # Tab 2: 编号表
        self._legend_table = LegendTable()
        self._legend_table.element_modified.connect(self.element_modified.emit)
        self.addTab(self._legend_table, "编号表")

        # Tab 3: VAR/FUN
        self._var_fun_panel = VarFunPanel()
        self.addTab(self._var_fun_panel, "VAR/FUN")

    def show_container(self, editor, name):
        self._editor = editor
        self._container_name = name

        self._annotated_view.show_annotated(editor, name)
        self._legend_table.show_legend(editor, name,
                                       editor.annotated_legend(name))
        self._var_fun_panel.show_refs(editor, name)

    def clear(self):
        self._annotated_view.clear()
        self._legend_table.clear()
        self._var_fun_panel.clear()
