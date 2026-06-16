"""
基于 ANTLR Token 流的完整 PVRS 元素修改器（包）。

收集 RULE 块和 derived_layer_def 内 op_statement 的直接子节点，
支持对每个语法节点（操作名、层引用、约束、option 组等）进行独立修改。

用法
----
    from full_token_editor import TokenEditor, TokenEditorPlugin

    te = TokenEditor("input.pvrs")
    te.replace_by_text("chk1", "M1", "METAL1")
    te.save()

    # 命令行
    python -m full_token_editor <file> --show chk1
"""

import sys, os
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'grammar', 'gen'))

from .elements import TokenElement, _token_type_name  # noqa: F401
from .core import TokenEditor
from .plugin import TokenEditorPlugin

__all__ = ['TokenElement', 'TokenEditor', 'TokenEditorPlugin']
