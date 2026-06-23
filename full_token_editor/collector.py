"""ANTLR Visitor — 收集容器边界和 op_statement 子节点元素。"""

import sys, os
from typing import List, Dict, Any, Optional

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'grammar', 'gen'))

from antlr4.error.ErrorListener import ErrorListener
from PVRSLexer import PVRSLexer
from PVRSParser import PVRSParser as _PVRSParser
from PVRSParserVisitor import PVRSParserVisitor
from .elements import TokenElement, _token_type_name


# ============================================================
# 容器边界收集器（Visitor）
# ============================================================

class _ContainerBoundCollector(PVRSParserVisitor):
    """
    收集容器的 token 范围 + op_statement 直接子节点的元素。

    收集粒度：op_statement 的每个子节点（几何操作、dim check 等）
    的直接 children，不再向下递归。例如 geomInteract 的 children：
        ~  geom_interact  (  layer1  layer2  > 0.5  )
    每个 token / rule context 对应一个 Element。
    """

    def __init__(self, source: str):
        self.source = source
        self.containers: List[Dict[str, Any]] = []
        self.elements: List[TokenElement] = []

    # ---- 辅助 ----

    def _container_name(self, ctx) -> Optional[str]:
        """从节点向上找到所属容器名。RULE 优先于 derived_layer_def。"""
        node = ctx
        found_def = None
        while node:
            if isinstance(node, _PVRSParser.Rule_statementContext):
                rn = node.name()
                return rn.getText() if rn else None
            if isinstance(node, _PVRSParser.Derived_layer_defContext):
                if found_def is None:
                    lr = node.layerRef()
                    if lr and lr.start:
                        found_def = self.source[lr.start.start:lr.stop.stop + 1]
            node = node.parentCtx
        return found_def

    def _context_type_name(self, node) -> str:
        from antlr4.Token import CommonToken
        from antlr4.tree.Tree import TerminalNodeImpl
        if isinstance(node, TerminalNodeImpl):
            return _token_type_name(node.symbol.type)
        if isinstance(node, CommonToken):
            return _token_type_name(node.type)
        cls = type(node).__name__
        if cls.endswith('Context'):
            cls = cls[:-7]
        return cls

    # ---- 收集 op_statement 的子节点 ----

    def visitOp_statement(self, ctx):
        container = self._container_name(ctx)
        if not container:
            self.visitChildren(ctx)
            return None

        for op_child in (ctx.children or []):
            if op_child is None:
                continue
            from antlr4.tree.Tree import TerminalNodeImpl
            if isinstance(op_child, TerminalNodeImpl):
                continue
            if not hasattr(op_child, 'children') or op_child.children is None:
                continue
            cls_name = type(op_child).__name__
            if cls_name == 'Op_statementContext':
                continue

            for gc in op_child.children:
                if gc is None:
                    continue
                if self._is_bracket(gc):
                    continue
                text, cstart, cstop, line = self._node_span(gc)
                if text is None:
                    continue
                idx = len(self.elements) + 1
                self.elements.append(TokenElement(
                    token=None, container=container, idx=idx,
                    source=self.source,
                    _text=text, _type=self._context_type_name(gc),
                    _start=cstart, _stop=cstop, _line=line,
                ))

        self.visitChildren(ctx)
        return None

    def _is_bracket(self, node) -> bool:
        from antlr4.Token import CommonToken
        from antlr4.tree.Tree import TerminalNodeImpl
        if isinstance(node, TerminalNodeImpl):
            ttype = node.symbol.type
        elif isinstance(node, CommonToken):
            ttype = node.type
        else:
            return False
        bracket_types = {
            PVRSLexer.LPAREN, PVRSLexer.RPAREN,
            PVRSLexer.LBRACK, PVRSLexer.RBRACK,
        }
        return ttype in bracket_types

    def _node_span(self, node):
        from antlr4.Token import CommonToken
        from antlr4.tree.Tree import TerminalNodeImpl
        if isinstance(node, TerminalNodeImpl):
            sym = node.symbol
            return (sym.text or '', sym.start, sym.stop, sym.line)
        if isinstance(node, CommonToken):
            return (node.text or '', node.start, node.stop, node.line)
        if hasattr(node, 'start') and node.start and node.stop:
            return (self.source[node.start.start:node.stop.stop + 1],
                    node.start.start, node.stop.stop, node.start.line)
        return (None, 0, 0, 0)

    # ---- 记录容器边界 ----

    def visitRule_statement(self, ctx):
        name = ctx.name().getText() if ctx.name() else ''
        if name and ctx.start is not None:
            self.containers.append({
                'name': name, 'kind': 'RULE',
                'char_start': ctx.start.start,
                'char_stop': ctx.stop.stop if ctx.stop else ctx.start.stop,
                'line': ctx.start.line,
            })
        self.visitChildren(ctx)
        return None

    def visitDerived_layer_def(self, ctx):
        lr = ctx.layerRef()

        container = self._container_name(ctx)
        if container and lr and lr.start and lr.stop:
            text = self.source[lr.start.start:lr.stop.stop + 1]
            idx = len(self.elements) + 1
            self.elements.append(TokenElement(
                token=None, container=container, idx=idx,
                source=self.source,
                _text=text, _type='layerRef',
                _start=lr.start.start, _stop=lr.stop.stop,
                _line=lr.start.line,
            ))

        node = ctx.parentCtx
        inside_rule = False
        while node:
            if isinstance(node, _PVRSParser.Rule_statementContext):
                inside_rule = True
                break
            node = node.parentCtx

        if not inside_rule and lr and lr.start and ctx.start:
            name = self.source[lr.start.start:lr.stop.stop + 1]
            self.containers.append({
                'name': name, 'kind': 'DEF',
                'char_start': ctx.start.start,
                'char_stop': ctx.stop.stop if ctx.stop else ctx.start.stop,
                'line': ctx.start.line,
            })
        self.visitChildren(ctx)
        return None


# ============================================================
# 语法错误收集器
# ============================================================

class _ErrorCollector(ErrorListener):
    def __init__(self):
        super().__init__()
        self.errors = []
    def syntaxError(self, r, sym, line, col, msg, e):
        self.errors.append((line, col, msg))
