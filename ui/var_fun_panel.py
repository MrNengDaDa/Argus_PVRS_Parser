#!/usr/bin/env python3
"""VAR/FUN 引用面板 — 展示当前容器的变量和函数引用。"""

from PyQt5.QtWidgets import QTextEdit, QVBoxLayout, QLabel, QWidget
from PyQt5.QtGui import QFont


class VarFunPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        lbl = QLabel("当前容器引用的 VAR 和 FUN 定义：")
        lbl.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(lbl)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("Consolas", 10))
        layout.addWidget(self._text)

    def show_refs(self, editor, container_name):
        """展示 VAR 和 FUN 引用信息。"""
        lines = []

        var_refs = editor.var_refs(container_name)
        if var_refs:
            lines.append(f"--- VAR 引用 ({len(var_refs)} 个) ---")
            for name, text in sorted(var_refs.items()):
                lines.append(f"  {name}: {text}")
            lines.append("")

        fun_refs = editor.fun_refs(container_name)
        if fun_refs:
            lines.append(f"--- FUN 引用 ({len(fun_refs)} 个) ---")
            for name, text in sorted(fun_refs.items()):
                lines.append(f"  {name}:")
                for line in text.split('\n'):
                    lines.append(f"    {line}")
            lines.append("")

        if not var_refs and not fun_refs:
            lines.append("（该容器没有引用任何 VAR 或 CALL_FUN）")

        self._text.setPlainText('\n'.join(lines))

    def clear(self):
        self._text.clear()
