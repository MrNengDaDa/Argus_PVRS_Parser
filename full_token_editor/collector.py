"""ANTLR Visitor — 收集容器边界和 op_statement 子节点元素。"""

import sys, os
from typing import List, Dict, Any, Optional

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'grammar', 'gen'))

from antlr4.error.ErrorListener import ErrorListener
from grammar.gen.PVRSLexer import PVRSLexer
from grammar.gen.PVRSLexer import PVRSLexer
from grammar.gen.PVRSParser import PVRSParser as _PVRSParser
from grammar.gen.PVRSParserVisitor import PVRSParserVisitor
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
        self.var_map: Dict[str, str] = {}
        self.fun_map: Dict[str, str] = {}

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

        from antlr4.tree.Tree import TerminalNodeImpl
        for op_child in (ctx.children or []):
            if op_child is None:
                continue
            if isinstance(op_child, TerminalNodeImpl):
                continue
            if not hasattr(op_child, 'children') or op_child.children is None:
                continue
            if type(op_child).__name__ == 'Op_statementContext':
                continue
            for gc in op_child.children:
                if gc is None:
                    continue
                if self._is_bracket(gc):
                    continue
                text, cstart, cstop, line = self._node_span(gc)
                if text is None:
                    continue
                self._add_token(container, text,
                    self._context_type_name(gc), cstart, cstop, line)

        self.visitChildren(ctx)
        return None

    def _add_token(self, container, text, type_name, start, stop, line):
        idx = len(self.elements) + 1
        self.elements.append(TokenElement(
            token=None, container=container, idx=idx,
            source=self.source, _text=text, _type=type_name,
            _start=start, _stop=stop, _line=line,
        ))

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

    # ---- 收集 varStmt / defineFun 定义 ----

    def _first_id_text(self, ctx) -> Optional[str]:
        """从 ctx 的直接子节点中提取第一个标识符的文本。
        支持：raw ID token、NameContext（name 规则）、STRING token。"""
        from antlr4.tree.Tree import TerminalNodeImpl
        if not hasattr(ctx, 'children') or not ctx.children:
            return None
        for c in ctx.children:
            if c is None:
                continue
            if isinstance(c, TerminalNodeImpl):
                if c.symbol.type in (PVRSLexer.ID, PVRSLexer.STRING):
                    return c.symbol.text
            elif hasattr(c, 'getText'):
                # NameContext 等规则节点
                txt = c.getText()
                if txt and txt not in ('var', 'define_fun', 'call_fun', '(', ')', '{', '}'):
                    return txt
        return None

    def visitVarStmt(self, ctx):
        """记录 var(NAME ...) 完整文本，key 为变量名。"""
        if ctx.start and ctx.stop:
            key = self._first_id_text(ctx)
            if key and key not in self.var_map:
                self.var_map[key] = self.source[ctx.start.start:ctx.stop.stop + 1]
        self.visitChildren(ctx)
        return None

    def visitDefineFun(self, ctx):
        """记录 define_fun NAME ... { ... } 完整文本，key 为函数名。"""
        if ctx.start and ctx.stop:
            key = self._first_id_text(ctx)
            if key and key not in self.fun_map:
                self.fun_map[key] = self.source[ctx.start.start:ctx.stop.stop + 1]
        self.visitChildren(ctx)
        return None

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


# ============================================================
# 目标收集器（leaf / 指定 context 类型）
# ============================================================

class _TargetedCollector(_ContainerBoundCollector):
    """
    基于 _ContainerBoundCollector，覆盖 visitOp_statement 以支持
    两种自定义收集模式，其余容器逻辑全部复用基类。

    初始化参数
    ----------
    collect_nodes:
        'leaf'             — 所有叶子 TerminalNode
        [Context, ...]     — 只收集匹配的语法节点
    """

    def __init__(self, source: str, collect_nodes):
        super().__init__(source)
        self._collect_nodes = collect_nodes

    def visitDerived_layer_def(self, ctx):
        """不收集 layerRef 元素，仅处理外部 DEF 容器边界并递归子节点。"""
        lr = ctx.layerRef()
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

    def visitOp_statement(self, ctx):
        container = self._container_name(ctx)
        if not container:
            self.visitChildren(ctx)
            return None

        if self._collect_nodes == 'leaf':
            self._walk_leaves(ctx, container)
        else:
            self._walk_targets(ctx, container)

        self.visitChildren(ctx)
        return None

    def _walk_leaves(self, ctx, container):
        """递归到所有 TerminalNode，跳过括号。"""
        from antlr4.tree.Tree import TerminalNodeImpl

        def walk(node):
            if isinstance(node, TerminalNodeImpl):
                if not self._is_bracket(node):
                    t = node.symbol
                    self._add_token(container, t.text or '',
                                    self._context_type_name(node),
                                    t.start, t.stop, t.line)
            elif hasattr(node, 'children') and node.children:
                for c in node.children:
                    if c is not None:
                        walk(c)

        for op_child in (ctx.children or []):
            if op_child is not None:
                walk(op_child)

    def _walk_targets(self, ctx, container):
        """递归到匹配 _collect_nodes 的节点即停止收集。"""
        ctx_targets = tuple(
            t for t in self._collect_nodes if isinstance(t, type))
        token_targets = set(
            t for t in self._collect_nodes if isinstance(t, int))
        from antlr4.tree.Tree import TerminalNodeImpl
        def walk(node):
            if node is None:
                return
            if isinstance(node, TerminalNodeImpl):
                if token_targets and node.symbol.type in token_targets:
                    if not self._is_bracket(node):
                        t = node.symbol
                        self._add_token(container, t.text or '',
                                        self._context_type_name(node),
                                        t.start, t.stop, t.line)
                return
            if ctx_targets and isinstance(node, ctx_targets):
                text, cstart, cstop, line = self._node_span(node)
                if text is not None:
                    self._add_token(container, text,
                                    self._context_type_name(node),
                                    cstart, cstop, line)
                return
            if hasattr(node, 'children') and node.children:
                for c in node.children:
                    walk(c)

        for op_child in (ctx.children or []):
            walk(op_child)
