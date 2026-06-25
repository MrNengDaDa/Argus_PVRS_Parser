#!/usr/bin/env python3
"""
标注视图 — 原文中可修改元素直接显示为输入框。

不可编辑文本用灰色 QLabel，可修改元素用 QLineEdit 嵌入原文中。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea,
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, pyqtSignal


class AnnotatedTextView(QWidget):
    """所有可修改 token 直接在原文中以 QLineEdit 呈现，可直接编辑。"""

    element_modified = pyqtSignal()
    save_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    staged = pyqtSignal()

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._flow = QWidget()
        self._flow_layout = QVBoxLayout(self._flow)
        self._flow_layout.setSpacing(0)
        self._flow_layout.setContentsMargins(6, 6, 6, 6)
        scroll.setWidget(self._flow)
        main_layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        for text, slot in [("📋 暂存", self._on_stage),
                           ("💾 保存", lambda: self.save_requested.emit()),
                           ("↩ 撤销全部", lambda: self.undo_requested.emit())]:
            btn = QPushButton(text)
            btn.setStyleSheet("padding: 6px 20px; font-size: 13px;")
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        main_layout.addLayout(btn_row)

        self._editor = None
        self._container = None
        self._edit_widgets = []
        self._legend = {}

    @property
    def _font(self):
        return QFont("Consolas", 11)

    def _text_width(self, text):
        """计算文本在等宽字体下的像素宽度。"""
        from PyQt5.QtGui import QFontMetrics
        fm = QFontMetrics(self._font)
        return fm.horizontalAdvance(text) + 8  # 留 4px 左右padding

    def show_annotated(self, editor, container_name):
        self._editor = editor
        self._container = container_name
        self._edit_widgets = []

        # 清除旧内容（包括 layout row 和 widget）
        while self._flow_layout.count():
            item = self._flow_layout.takeAt(0)
            if item.layout():
                # 清除 HBoxLayout row 中的子 widget
                sub = item.layout()
                while sub.count():
                    sw = sub.takeAt(0)
                    if sw.widget():
                        sw.widget().deleteLater()
            elif item.widget():
                item.widget().deleteLater()

        text, segs = editor.annotated_text(container_name)
        legend = editor.annotated_legend(container_name)

        # 构建 inline 行：每遇到 \n 就换行
        line_widgets = []         # 当前行的 widget 列表
        line_edit_refs = []       # [(idx, QLineEdit), ...]
        current_text = ""         # 当前正在累积的普通文本

        def flush_label():
            nonlocal current_text
            if current_text:
                lbl = QLabel(current_text)
                lbl.setFont(self._font)
                lbl.setStyleSheet("color: #555; padding: 0;")
                lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
                line_widgets.append(lbl)
                current_text = ""

        def flush_line():
            flush_label()
            if line_widgets:
                row = QHBoxLayout()
                row.setSpacing(0)
                row.setContentsMargins(0, 0, 0, 0)
                for w in line_widgets:
                    row.addWidget(w)
                row.addStretch()
                self._flow_layout.addLayout(row)
                line_widgets.clear()

        for seg_text, idx in segs:
            if '\n' in seg_text:
                parts = seg_text.split('\n')
                for i, part in enumerate(parts):
                    if i > 0:
                        flush_line()  # 换行
                    if idx is not False and i == 0:
                        # token 在第一段
                        flush_label()
                        line_widgets.append(self._make_edit(idx, part, legend))
                    elif idx is not False:
                        # token 在后面的段（不太会发生）
                        flush_label()
                        line_widgets.append(self._make_edit(idx, part, legend))
                    else:
                        current_text += part
            elif idx is not False:
                flush_label()
                line_widgets.append(self._make_edit(idx, seg_text, legend))
            else:
                current_text += seg_text

        flush_line()
        self._flow_layout.addStretch()

    def _make_edit(self, idx, text, legend):
        info = legend.get(idx)
        modified = info[2] if info else False
        w = QLineEdit(text)
        w.setFont(self._font)
        # 根据文本内容自动调整宽度
        w.setFixedWidth(self._text_width(text))
        w.setFixedHeight(self._text_width("X") + 6)  # 单行字符高度 + padding
        color = "#CC0000" if modified else "#0066CC"
        bg = "#FFE8E8" if modified else "#FFFFFF"
        w.setStyleSheet(
            f"padding: 0 2px; border: 1px solid {color}; "
            f"background: {bg}; color: {color};")
        w.setToolTip(f"<<{idx}>> [{info[0] if info else '?'}]  ← 原文: {info[1] if info else ''}")
        w.editingFinished.connect(self._make_handler(idx, w))
        return w

    def _on_stage(self):
        """将所有编辑框的当前值同步到 TokenEditor（不写盘）。"""
        if not self._editor or not self._container:
            return
        for idx, widget in self._edit_widgets:
            new_val = widget.text()
            tokens = self._editor.tokens(self._container)
            if idx < 1 or idx > len(tokens):
                continue
            old = tokens[idx - 1].text
            if new_val and new_val != old:
                self._editor.replace_by_index(self._container, idx, new_val)
        self._legend = self._editor.annotated_legend(self._container)
        self.staged.emit()

    def _make_handler(self, idx, widget):
        def handler():
            if not self._editor or not self._container:
                return
            new_val = widget.text()
            tokens = self._editor.tokens(self._container)
            if idx < 1 or idx > len(tokens):
                return
            old = tokens[idx - 1].text
            if not new_val or new_val == old:
                return
            self._editor.replace_by_index(self._container, idx, new_val)
            widget.setStyleSheet(
                widget.styleSheet()
                .replace("#0066CC", "#CC0000")
                .replace("#FFFFFF", "#FFE8E8"))
            self.element_modified.emit()
        return handler

    def clear(self):
        self._editor = None
        self._container = None
        while self._flow_layout.count():
            item = self._flow_layout.takeAt(0)
            if item.layout():
                sub = item.layout()
                while sub.count():
                    sw = sub.takeAt(0)
                    if sw.widget():
                        sw.widget().deleteLater()
            elif item.widget():
                item.widget().deleteLater()
