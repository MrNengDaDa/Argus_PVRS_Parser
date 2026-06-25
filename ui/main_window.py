#!/usr/bin/env python3
"""PVRS Editor — 主窗口（带工具栏和状态栏）。"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QSplitter, QToolBar, QAction,
    QFileDialog, QMessageBox, QLabel, QWidget,
    QVBoxLayout, QHBoxLayout, QStyle,
)
from PyQt5.QtCore import Qt

from ui.container_list import ContainerListWidget
from ui.detail_panel import DetailPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PVRS Editor")
        self._editor = None
        self._filepath = None

        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()

    # ---- 工具栏（保存 / 撤销）----

    def _setup_toolbar(self):
        tb = QToolBar("工具栏")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._act_open = QAction(
            self.style().standardIcon(QStyle.SP_DialogOpenButton),
            "打开", self)
        self._act_open.triggered.connect(self._on_open)
        tb.addAction(self._act_open)

        self._act_save = QAction(
            self.style().standardIcon(QStyle.SP_DialogSaveButton),
            "保存", self)
        self._act_save.setShortcut("Ctrl+S")
        self._act_save.triggered.connect(self._on_save)
        tb.addAction(self._act_save)

        self._act_undo = QAction(
            self.style().standardIcon(QStyle.SP_DialogResetButton),
            "撤销全部", self)
        self._act_undo.triggered.connect(self._on_undo)
        tb.addAction(self._act_undo)

        tb.addSeparator()

        self._act_reload = QAction(
            self.style().standardIcon(QStyle.SP_BrowserReload),
            "刷新", self)
        self._act_reload.triggered.connect(self._on_reload)
        tb.addAction(self._act_reload)

    # ---- 主布局 ----

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        self._container_list = ContainerListWidget()
        self._container_list.container_selected.connect(self._on_container_selected)
        splitter.addWidget(self._container_list)

        self._detail_panel = DetailPanel()
        self._detail_panel.element_modified.connect(self._on_element_modified)
        self._detail_panel.save_requested.connect(self._on_save)
        self._detail_panel.undo_requested.connect(self._on_undo)
        self._detail_panel.staged.connect(self._on_staged)
        splitter.addWidget(self._detail_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

    # ---- 状态栏 ----

    def _setup_statusbar(self):
        self._status_path = QLabel("  未打开文件")
        self._status_errors = QLabel("")
        self._status_changes = QLabel("")
        self.statusBar().addWidget(self._status_path, 1)
        self.statusBar().addPermanentWidget(self._status_errors)
        self.statusBar().addPermanentWidget(self._status_changes)

    # ---- 事件处理 ----

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开 PVRS 文件", "",
            "PVRS 文件 (*.pvrs *.drc *.lvs);;所有文件 (*)")
        if not path:
            return
        self._load_file(path)

    def _load_file(self, filepath):
        try:
            from full_token_editor import TokenEditor
            self._editor = TokenEditor(filepath)
        except Exception as e:
            QMessageBox.critical(self, "解析错误", f"无法解析文件:\n{e}")
            return

        self._filepath = filepath
        self._container_list.populate(self._editor)
        self._detail_panel.clear()
        self._update_statusbar()

    def _on_container_selected(self, name):
        if not self._editor:
            return
        self._detail_panel.show_container(self._editor, name)

    def _on_element_modified(self):
        self._container_list.refresh_modification_markers(self._editor)
        self._update_statusbar()

    def _on_save(self):
        if not self._editor:
            QMessageBox.warning(self, "提示", "请先打开文件。")
            return
        if not self._editor.pending_tokens():
            QMessageBox.information(self, "提示", "没有需要保存的修改。")
            return

        reply = QMessageBox.question(
            self, "确认保存",
            f"共 {len(self._editor.pending_tokens())} 项修改，确认保存？",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        result = self._editor.save()
        if result['ok']:
            QMessageBox.information(self, "保存", "保存成功。")
            # 重新加载文件以获取保存后的干净状态
            from full_token_editor import TokenEditor
            self._editor = TokenEditor(self._filepath)
            self._container_list.populate(self._editor)
            # 恢复当前选中的容器
            name = self._container_list.current_name()
            if name and name in self._editor.container_names:
                self._detail_panel.show_container(self._editor, name)
            else:
                self._detail_panel.clear()
        else:
            QMessageBox.critical(
                self, "保存失败",
                f"语法错误:\n{chr(10).join(f'[{l}:{c}] {m}' for l,c,m in result['errors'][:5])}")
        self._update_statusbar()

    def _on_staged(self):
        """暂存后刷新详情面板（保持当前容器选中）。"""
        if not self._editor:
            return
        name = self._container_list.current_name()
        if name:
            self._detail_panel.show_container(self._editor, name)
        self._container_list.refresh_modification_markers(self._editor)
        self._update_statusbar()

    def _on_undo(self):
        if not self._editor:
            return
        self._editor.clear_changes()
        name = self._container_list.current_name()
        if name:
            self._detail_panel.show_container(self._editor, name)
        self._container_list.refresh_modification_markers(self._editor)
        self._update_statusbar()

    def _on_reload(self):
        """刷新当前容器视图。"""
        if not self._editor:
            return
        name = self._container_list.current_name()
        if name:
            self._detail_panel.show_container(self._editor, name)
        self._update_statusbar()

    def _update_statusbar(self):
        if not self._editor:
            self._status_path.setText("  未打开文件")
            self._status_errors.setText("")
            self._status_changes.setText("")
            return

        self._status_path.setText(f"  {self._filepath or ''}")

        n_err = len(self._editor.parse_errors)
        if n_err:
            self._status_errors.setText(f"  ⚠ 语法错误: {n_err}  ")
            self._status_errors.setStyleSheet("color: red;")
        else:
            self._status_errors.setText("  语法: OK  ")
            self._status_errors.setStyleSheet("color: green;")

        n_ch = len(self._editor.pending_tokens())
        self._status_changes.setText(f"  修改: {n_ch} 项  ")
