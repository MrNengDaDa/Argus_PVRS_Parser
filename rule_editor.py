"""
PVRS RULE 块元素编辑器 — 核心库。

基于 ANTLR4 解析树 + 字符偏移量定位 RULE 块内的可修改元素
（layerRef、constraint、expr），支持精确的文本替换，不破坏
周围的格式和缩进。

作为库使用
----------
    from rule_editor import RuleEditor
    editor = RuleEditor("input.pvrs")
    for e in editor.elements_by_rule("ant_met1"):
        print(e)

    editor.add_change(e, "new_value")
    editor.save()  # 回写文件，自动创建 .bak 备份

扩展性
------
添加新的可修改元素类型：在 ELEMENT_TYPE_REGISTRY 字典中增加
一项 _ElementTypeSpec，并在 _RuleElementCollector 中增加对应
的 visitXxx 方法即可。
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable

# ---- ANTLR4 解析器路径设置 ----
_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'grammar', 'gen'))

from antlr4 import InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener
from PVRSLexer import PVRSLexer
from PVRSParser import PVRSParser as _PVRSParser
from PVRSParserVisitor import PVRSParserVisitor


# ============================================================
# Element — 单个可修改元素的描述
# ============================================================

@dataclass
class Element:
    """
    PVRS RULE 块内的一个可修改元素。

    每个 Element 对应 ANTLR 解析树中的一个语法节点（如 layerRef、
    constraint、expr），记录了该节点在源文本中的精确位置。

    属性说明
    --------
    element_type : str   – 元素类型，对应 ELEMENT_TYPE_REGISTRY 中的 key
    rule_name    : str   – 所属 RULE 的名称（已去除引号）
    text         : str   – 原始文本内容
    line         : int   – 源文件行号（从 1 开始）
    char_start   : int   – 在 LF 归一化源文本中的起始字符偏移（含）
    char_stop    : int   – 在 LF 归一化源文本中的结束字符偏移（含）
    context_type : str   – ANTLR 语法上下文类名（调试用）
    _new_text    : str   – 调用 set_new_text() 暂存的替换文本，None 表示未修改
    """
    element_type: str
    rule_name: str
    text: str
    line: int
    char_start: int
    char_stop: int
    context_type: str = ""

    @property
    def new_text(self) -> Optional[str]:
        """暂存的替换文本，未修改时返回 None。"""
        return getattr(self, '_new_text', None)

    @property
    def modified(self) -> bool:
        """是否已有暂存的修改。"""
        return hasattr(self, '_new_text')

    def set_new_text(self, value: str):
        """暂存一个替换值。"""
        self._new_text = value

    def clear_change(self):
        """取消暂存的修改。"""
        if hasattr(self, '_new_text'):
            del self._new_text

    def __repr__(self):
        tag = " *" if self.modified else ""
        return (f"[{self.element_type}{tag}] line {self.line}: "
                f"{self.text!r} ({self.char_start}-{self.char_stop})")


# ============================================================
# 元素类型注册表 — 在此添加新的可收集类型
# ============================================================

class _ElementTypeSpec:
    """
    一种可收集元素类型的描述符。

    属性
    ----
    label        : str   – 显示名称
    visit_method : str   – Visitor 方法名
    filter_fn    : callable  – 可选过滤器，filter_fn(ctx) 返回 False 时跳过
    desc         : str   – 简短描述文本
    """
    def __init__(self, label: str, visit_method: str,
                 filter_fn: Optional[Callable] = None,
                 desc: str = ""):
        self.label = label
        self.visit_method = visit_method
        self.filter_fn = filter_fn
        self.desc = desc


# 注册表：key = 类型标识符（供 API 查询）
# 新增元素类型时在此添加条目，并在 _RuleElementCollector 中实现对应的
# visitXxx 方法。
ELEMENT_TYPE_REGISTRY: Dict[str, _ElementTypeSpec] = {
    'layerRef': _ElementTypeSpec(
        'layerRef', 'visitLayerRef',
        desc='层引用（名称、数字或带引号的字符串）',
    ),
    'constraint': _ElementTypeSpec(
        'constraint', 'visitConstraint',
        desc='带比较运算符的约束表达式',
    ),
    'expr': _ElementTypeSpec(
        'expr', 'visitExpr',
        # 只收集顶层 expr，避免嵌套子表达式重复出现
        filter_fn=lambda ctx: not isinstance(ctx.parentCtx, _PVRSParser.ExprContext),
        desc='顶层算术表达式',
    ),
}


# ============================================================
# ANTLR Visitor — 遍历解析树收集 RULE 内的元素
# ============================================================

class _RuleElementCollector(PVRSParserVisitor):
    """
    遍历 ANTLR 解析树，收集所有 RULE 块内的可修改元素。

    只收集 ELEMENT_TYPE_REGISTRY 中注册的元素类型。
    叶子节点（layerRef）停止向下遍历，非叶子节点（constraint、
    expr）继续递归子节点。
    """

    def __init__(self, source_text: str):
        self.source = source_text                   # LF 归一化后的源文本
        self.elements: List[Element] = []           # 收集到的元素列表
        self._rule_bounds: Dict[str, tuple] = {}    # {name: (start, line, stop)}

    # ---- 辅助方法 ----

    def _parent_name_from_ctx(self, ctx) -> Optional[str]:
        """
        从当前语法节点向上查找所属的容器块，返回容器名称。

        优先级：rule_statement > 顶层 derived_layer_def
        （RULE 内部的赋值语句归属到该 RULE）
        """
        node = ctx
        found_def = None
        while node is not None:
            if isinstance(node, _PVRSParser.Rule_statementContext):
                rn = node.ruleName()
                return rn.getText() if rn else None
            if isinstance(node, _PVRSParser.Derived_layer_defContext):
                if found_def is None:
                    lr = node.layerRef()
                    if lr is not None and lr.start is not None and lr.stop is not None:
                        found_def = self.source[lr.start.start:lr.stop.stop + 1]
            node = node.parentCtx
        return found_def

    def _add_element(self, etype: str, ctx):
        """
        根据语法节点创建一个 Element 并添加到 self.elements。

        跳过缺少位置信息的节点（正常情况不会发生）以及不在任何
        RULE 块或 derived_layer_def 内的节点。
        元素文本通过 ANTLR 提供的字符偏移量直接从 self.source
        中切片获取，确保与原始文本一字不差。
        """
        if ctx.start is None or ctx.stop is None:
            return
        parent_name = self._parent_name_from_ctx(ctx)
        if not parent_name:
            return                 # 不在任何容器内，跳过
        # ANTLR token 的 start/stop 为包含边界：ctx.start.start 到
        # ctx.stop.stop 是闭区间，切片需要 +1
        text = self.source[ctx.start.start:ctx.stop.stop + 1]
        elem = Element(
            element_type=etype,
            rule_name=parent_name,
            text=text,
            line=ctx.start.line,
            char_start=ctx.start.start,
            char_stop=ctx.stop.stop,
            context_type=type(ctx).__name__,
        )
        self.elements.append(elem)

    # ---- visitor 方法 ----
    # 每个方法对应 ELEMENT_TYPE_REGISTRY 中的一种类型。
    # 叶子节点返回 None 停止递归；非叶子节点调用 visitChildren 继续。

    def visitRule_statement(self, ctx):
        """
        RULE 块入口：记录边界用于 rule_text() 方法、
        递归进入 body 收集子元素。
        """
        name = ctx.ruleName().getText() if ctx.ruleName() else ''
        if name and ctx.start is not None and ctx.stop is not None:
            self._rule_bounds[name] = (
                ctx.start.start, ctx.start.line,
                ctx.stop.stop,
                'RULE',
            )
        self.visitChildren(ctx)
        return None

    def _is_inside_rule(self, ctx) -> bool:
        """检查当前节点是否在某个 rule_statement 内部。"""
        node = ctx.parentCtx
        while node is not None:
            if isinstance(node, _PVRSParser.Rule_statementContext):
                return True
            node = node.parentCtx
        return False

    def visitDerived_layer_def(self, ctx):
        """
        赋值语句入口。只有不在任何 RULE 内部的（顶层的）
        derived_layer_def 才单独记录边界、作为独立容器；
        RULE 内部的赋值语句归属到所在的 RULE 即可。
        """
        if not self._is_inside_rule(ctx):
            lr = ctx.layerRef()
            if lr is not None and lr.start is not None and ctx.start is not None and ctx.stop is not None:
                name = self.source[lr.start.start:lr.stop.stop + 1]
                self._rule_bounds[name] = (
                    ctx.start.start, ctx.start.line,
                    ctx.stop.stop,
                    'DEF',
                )
        self.visitChildren(ctx)
        return None

    def visitLayerRef(self, ctx):
        """layerRef 是叶子节点 (ID|INT_LIT|STRING|EDGE)，只收集不递归。"""
        self._add_element('layerRef', ctx)
        return None

    def visitConstraint(self, ctx):
        """constraint 节点本身已收集，子规则（cmpOp + expr）暂不需单独收集。"""
        self._add_element('constraint', ctx)
        return None

    def visitExpr(self, ctx):
        """
        expr 节点本身已收集（仅顶层），子规则（atom、funcName 等）
        暂不需单独收集，故停止递归以减少遍历开销。
        """
        spec = ELEMENT_TYPE_REGISTRY['expr']
        if spec.filter_fn is None or spec.filter_fn(ctx):
            self._add_element('expr', ctx)
        return None

    def visitChildren(self, ctx):
        """通用回退：递归进入所有子节点。"""
        result = super().visitChildren(ctx)
        return result


# ============================================================
# 语法错误收集器
# ============================================================

class _ParseErrorCollector(ErrorListener):
    """
    ANTLR 错误监听器，收集解析过程中的语法错误。

    当文件有语法错误时，解析树可能不可靠，元素位置信息也会
    出错。RuleEditor 在构造后会通过 has_errors 属性告知调用方。
    """
    def __init__(self):
        super().__init__()
        self.errors: list = []         # [(line, col, msg), ...]

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append((line, column, msg))


# ============================================================
# RuleEditor — 主公开 API
# ============================================================

class RuleEditor:
    """
    PVRS RULE 块编辑器。

    解析 PVRS 文件，提取所有 RULE 块内的可修改元素，支持暂存修改
    并通过精确的字符串切片替换回写文件。自动处理 CRLF / LF 换行符
    差异，确保保存后格式不变。

    典型用法
    --------
        editor = RuleEditor("rules.pvrs")
        elem = editor.elements_by_rule("check_m1")[0]
        editor.add_change(elem, "new_value")
        editor.save()          # 覆盖原文件，自动创建 .bak
    """

    def __init__(self, filepath: str):
        """
        初始化编辑器：读取文件、解析语法、收集元素。

        参数
        ----
        filepath : str – PVRS 规则文件路径
        """
        self.filepath = filepath

        # ---- 读取源文件 ----
        # newline='' 防止 Python 自动转换换行符，以便检测 CRLF
        with open(filepath, 'r', encoding='utf-8', errors='replace', newline='') as f:
            raw = f.read()

        self._raw = raw                       # 保留原始字节（用于 .bak 备份）
        self._crlf = '\r\n' in raw            # 是否使用 Windows 换行
        # 内部统一用 LF，确保 ANTLR 的字符偏移与 self.source 一致
        self.source = raw.replace('\r\n', '\n')

        # ---- ANTLR 解析 ----
        # 使用 InputStream(self.source) 而非 FileStream，确保解析器
        # 看到的文本与 self.source 完全相同
        input_stream = InputStream(self.source)
        lexer = PVRSLexer(input_stream)
        stream = CommonTokenStream(lexer)
        parser = _PVRSParser(stream)
        parser.removeErrorListeners()
        error_listener = _ParseErrorCollector()
        parser.addErrorListener(error_listener)
        self._tree = parser.pvrFile()
        self._parse_errors = error_listener.errors

        # ---- 遍历解析树收集元素 ----
        collector = _RuleElementCollector(self.source)
        collector.visit(self._tree)
        self._elements: List[Element] = collector.elements
        self._rule_bounds: Dict[str, tuple] = collector._rule_bounds

        # 暂存的修改列表
        self._changes: List[Element] = []

    # ======== 查询接口 ========

    @property
    def parse_errors(self) -> list:
        """语法错误列表，每项为 (line, col, msg)。"""
        return list(self._parse_errors)

    @property
    def has_errors(self) -> bool:
        """文件是否存在语法错误。有错误时元素位置信息可能不可靠。"""
        return len(self._parse_errors) > 0

    @property
    def elements(self) -> List[Element]:
        """所有收集到的元素列表。"""
        return list(self._elements)

    def elements_by_rule(self, rule_name: str) -> List[Element]:
        """
        获取指定 RULE 内的所有元素。

        参数
        ----
        rule_name : str – RULE 名称（可带或不带引号）
        """
        name = rule_name.strip('"')
        return [e for e in self._elements
                if e.rule_name.strip('"') == name]

    def elements_by_type(self, element_type: str) -> List[Element]:
        """
        获取指定类型的所有元素。

        参数
        ----
        element_type : str – 类型标识符（如 "layerRef"、"constraint"）
        """
        return [e for e in self._elements if e.element_type == element_type]

    def rule_text(self, rule_name: str) -> str:
        """
        返回指定 RULE 的完整原始文本（含 "RULE name { ... }"）。

        通过解析时记录的字符边界直接从 self.source 切片获取，
        精确还原原文内容（不含周围空白）。
        """
        name = rule_name.strip('"')
        bounds = self._rule_bounds.get(name)
        if bounds is None:
            return ''
        start, _line, stop, _kind = bounds
        return self.source[start:stop + 1]

    def annotated_text(self, rule_name: str) -> str:
        """
        返回带有内嵌标注 `<<N:value>>` 的 RULE 原文视图。

        每个可修改元素被 `<<N:` 和 `>>` 包围显示，
        N 为此 RULE 内的全局编号。配合编号说明表使用，
        可直观定位每个元素的位置和类型。

        实现：从右往左依次在元素右侧插入 `>>`、左侧插入 `<<N:`，
        保证前面的插入不影响后面元素的偏移量。
        """
        elems = self.elements_by_rule(rule_name)
        if not elems:
            return self.rule_text(rule_name)

        text = self.rule_text(rule_name)
        bounds = self._rule_bounds.get(rule_name.strip('"'))
        if bounds is None:
            return text
        rule_start = bounds[0]

        # 按 char_start 降序 → 从后往前替换
        for i, e in enumerate(reversed(elems)):
            global_idx = len(elems) - i
            local_start = e.char_start - rule_start
            local_stop = e.char_stop - rule_start
            # 使用有效值（有修改用 new_text，无修改用原始 text）
            effective = e.new_text if e.modified else e.text
            marker = f'<<{global_idx}:{effective}>>'
            text = (text[:local_start] + marker +
                    text[local_stop + 1:])
        return text

    def annotated_legend(self, rule_name: str) -> str:
        """
        返回与 annotated_text 配套的编号说明表。

        格式示例：
            --- 编号说明（10 个）---
            <<1>> layerRef       M1
            <<2>> constraint     < 0.5
             ...
        """
        elems = self.elements_by_rule(rule_name)
        if not elems:
            return ''
        max_type = max(len(e.element_type) for e in elems)
        lines = [f'--- 编号说明（{len(elems)} 个）---']
        for i, e in enumerate(elems, 1):
            marker = ' [已修改]' if e.modified else ''
            lines.append(
                f'  <<{i}>> {e.element_type:<{max_type}}  '
                f'{e.text}{marker}  (第 {e.line} 行)'
            )
        return '\n'.join(lines)

    def rule_names(self) -> List[str]:
        """文件中所有 RULE 名称列表（按出现顺序）。"""
        seen = set()
        result = []
        for e in self._elements:
            if e.rule_name not in seen:
                seen.add(e.rule_name)
                result.append(e.rule_name)
        return result

    def rule_summaries(self) -> List[Dict[str, Any]]:
        """
        每个容器（RULE / 非 RULE 赋值）的摘要信息。

        返回 [{'name': ..., 'line': ..., 'count': ..., 'types': [...], 'kind': ...}, ...]
        kind 为 'RULE' | 'DEF'（derived_layer_def）
        """
        names = self.rule_names()
        result = []
        for name in names:
            elems = self.elements_by_rule(name)
            bounds = self._rule_bounds.get(name)
            kind = bounds[3] if bounds else ''
            result.append({
                'name': name,
                'line': elems[0].line if elems else 0,
                'count': len(elems),
                'types': sorted(set(e.element_type for e in elems)),
                'kind': kind,
            })
        return result

    def type_counts(self, rule_name: str) -> Dict[str, int]:
        """某个 RULE 内各类型元素的个数统计。"""
        counts: Dict[str, int] = {}
        for e in self.elements_by_rule(rule_name):
            counts[e.element_type] = counts.get(e.element_type, 0) + 1
        return counts

    # ======== 修改接口 ========

    def add_change(self, element: Element, new_text: str):
        """
        暂存一个修改。不立即写入文件。

        参数
        ----
        element  : Element – 要修改的元素（必须来自本编辑器）
        new_text : str     – 新文本内容

        异常
        ----
        ValueError – 如果 element 不属于本编辑器
        """
        if element not in self._elements:
            raise ValueError("Element 不属于此编辑器实例")
        if new_text == element.text:
            element.clear_change()
        else:
            element.set_new_text(new_text)
        self._changes = [e for e in self._elements if e.modified]

    def pending_changes(self) -> List[Element]:
        """所有已暂存修改的元素列表。"""
        return list(self._changes)

    def modified_text(self) -> str:
        """
        返回应用所有暂存修改后的完整文本。

        修改从右往左依次应用（按 char_start 降序），确保前面的修改
        不会影响后面元素的字符偏移量。每次替换是简单的三部分拼接：
        text[:char_start] + new_text + text[char_stop+1:]
        """
        if not self._changes:
            return self.source

        text = self.source
        for elem in sorted(self._changes, key=lambda e: -e.char_start):
            text = (text[:elem.char_start] + elem.new_text +
                    text[elem.char_stop + 1:])
        return text

    def clear_changes(self):
        """撤销所有暂存的修改。"""
        for e in self._elements:
            e.clear_change()
        self._changes = []

    # ======== 保存 ========

    def save(self, output_path: Optional[str] = None, backup: bool = True):
        """
        将修改后的文本写入磁盘。

        参数
        ----
        output_path : str – 输出路径。None 或空字符串表示覆盖原文件，
                            否则写入指定路径。
        backup     : bool – True 时创建带时间戳的 .bak 备份。
                            备份文件命名：<原文件名>.<时间戳>.bak
                            仅当覆盖原文件时才创建备份。

        换行符处理
        ----------
        内部统一使用 LF。保存时如果原始文件是 CRLF，自动恢复。
        open 使用 newline='' 防止 Python 做额外的换行符转换。
        """
        from datetime import datetime

        text = self.modified_text()
        if self._crlf:
            text = text.replace('\n', '\r\n')

        # 确定输出路径
        target = output_path or self.filepath

        # 覆盖原文件时创建带时间戳的备份
        if backup and target == self.filepath:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            bak_path = f'{self.filepath}.{ts}.bak'
            with open(bak_path, 'w', encoding='utf-8', newline='') as f:
                f.write(self._raw)

        with open(target, 'w', encoding='utf-8', newline='') as f:
            f.write(text)


# ============================================================
# 便捷函数（供 CLI 使用）
# ============================================================

def get_element_types() -> List[Dict[str, str]]:
    """返回注册表中所有元素类型的列表（供显示用）。"""
    return [
        {'key': k, 'label': v.label, 'desc': v.desc}
        for k, v in ELEMENT_TYPE_REGISTRY.items()
    ]


def iter_elements_by_rule(elements: List[Element],
                           rule_name: str) -> Dict[str, List[Element]]:
    """
    将某个 RULE 内的元素按类型分组。

    返回 {type_key: [Element, ...], ...}
    """
    groups: Dict[str, List[Element]] = {}
    name = rule_name.strip('"')
    for e in elements:
        if e.rule_name.strip('"') == name:
            groups.setdefault(e.element_type, []).append(e)
    return groups
