"""TokenEditor — 主编辑器。"""

import re, sys, os
from typing import List, Dict, Any
from datetime import datetime

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'grammar', 'gen'))

from antlr4 import InputStream, CommonTokenStream
from grammar.gen.PVRSLexer import PVRSLexer
from grammar.gen.PVRSParser import PVRSParser as _PVRSParser
from .collector import _ContainerBoundCollector, _TargetedCollector, _ErrorCollector
from .elements import TokenElement


# ============================================================
# TokenEditor
# ============================================================

class TokenEditor:
    """
    基于完整 token 流的 PVRS 元素修改器。

    收集 RULE 和 derived_layer_def 内 op_statement 的直接子节点，
    支持按编号或文本修改，修改后自动生成标注视图。
    """

    def __init__(self, filepath: str, collect_nodes=None):
        """
        collect_nodes:
            None        — op_statement 直接子节点（默认）
            'leaf'      — 所有叶子 token
            [Context, ...] — 收集匹配的语法节点类型列表
        """
        self.filepath = filepath
        self._collect_nodes = collect_nodes
        with open(filepath, 'r', encoding='utf-8', errors='replace', newline='') as f:
            raw = f.read()

        self._crlf = '\r\n' in raw
        self._raw = raw
        self.source = raw.replace('\r\n', '\n')

        # ANTLR 解析
        inp = InputStream(self.source)
        lexer = PVRSLexer(inp)
        self._token_stream = CommonTokenStream(lexer)
        self._token_stream.fill()

        parser = _PVRSParser(self._token_stream)
        parser.removeErrorListeners()
        err = _ErrorCollector()
        parser.addErrorListener(err)
        self._tree = parser.pvrFile()
        self._parse_errors = err.errors

        # 收集
        if collect_nodes is None:
            collector = _ContainerBoundCollector(self.source)
        else:
            collector = _TargetedCollector(self.source, collect_nodes)
        collector.visit(self._tree)
        # debug print removed
        self._containers = collector.containers
        self.var_map: Dict[str, str] = collector.var_map
        self.fun_map: Dict[str, str] = collector.fun_map

        self._tokens: List[TokenElement] = collector.elements
        self._container_tokens: Dict[str, List[TokenElement]] = {}
        self._build_token_index()

    def _build_token_index(self):
        for te in self._tokens:
            name = te.container
            if name not in self._container_tokens:
                self._container_tokens[name] = []
            te2 = te
            te2.index = len(self._container_tokens[name]) + 1
            self._container_tokens[name].append(te2)

    # ---- 属性 ----

    @property
    def parse_errors(self) -> list:
        return list(self._parse_errors)

    @property
    def has_errors(self) -> bool:
        return len(self._parse_errors) > 0

    @property
    def container_names(self) -> List[str]:
        return [c['name'] for c in self._containers]

    def containers(self) -> List[Dict[str, Any]]:
        result = []
        for c in self._containers:
            name = c['name']
            count = len(self._container_tokens.get(name, []))
            types = sorted(set(
                t.type_name for t in self._container_tokens.get(name, [])
            ))
            result.append({
                'name': name, 'kind': c['kind'], 'line': c['line'],
                'count': count, 'types': types,
            })
        return result

    def tokens(self, container: str) -> List[TokenElement]:
        return list(self._container_tokens.get(container, []))

    def all_tokens(self) -> List[TokenElement]:
        return list(self._tokens)

    def container_text(self, container: str) -> str:
        for c in self._containers:
            if c['name'] == container:
                return self.source[c['char_start']:c['char_stop'] + 1]
        return ''

    def var_refs(self, container: str) -> Dict[str, str]:
        """返回该容器内引用的所有 VAR 定义。扫描容器原文匹配 var_map。"""
        result = {}
        text = self.container_text(container)
        for name, full in self.var_map.items():
            if re.search(r'\b' + re.escape(name) + r'\b', text, re.IGNORECASE):
                result[name] = full
        return result

    def fun_refs(self, container: str) -> Dict[str, str]:
        """返回该容器内引用的所有 CALL_FUN 定义。扫描容器原文匹配 fun_map。"""
        result = {}
        text = self.container_text(container)
        for name, full in self.fun_map.items():
            if re.search(r'\b' + re.escape(name) + r'\b', text, re.IGNORECASE):
                result[name] = full
        return result

    # ---- 修改 ----

    def replace_by_text(self, container: str, old_text: str,
                        new_text: str) -> bool:
        ts = self.tokens(container)
        matched = [t for t in ts if t.text == old_text]
        if not matched:
            return False
        for t in matched:
            t._new_text = new_text
        return True

    def replace_by_index(self, container: str, index: int,
                         new_text: str) -> bool:
        ts = self.tokens(container)
        if index < 1 or index > len(ts):
            return False
        ts[index - 1]._new_text = new_text
        return True

    def pending_tokens(self) -> List[TokenElement]:
        return [t for t in self._tokens if t.modified]

    def clear_changes(self):
        for t in self._tokens:
            if t.modified:
                del t._new_text

    # ---- 标注视图 ----

    def annotated_text(self, container: str):
        """
        返回带 <<N:value>> 标注的容器文本，以及结构化的段列表。

        返回
        ----
        (annotated_str, segments)
          annotated_str : str  — 标注后的显示文本
          segments : [[text, index], ...] — 每个段是 [文本, 编号或False]
        """
        ts = self.tokens(container)
        if not ts:
            return (self.container_text(container), [])

        text = self.container_text(container)
        bounds_start = None
        for c in self._containers:
            if c['name'] == container:
                bounds_start = c['char_start']
                break
        if bounds_start is None:
            return (text, [])

        # 用偏移量记录每个 token 的替换信息
        replacements = {}  # {local_start: (local_stop, effective_text, index)}
        for t in ts:
            local_start = t.char_start - bounds_start
            local_stop = t.char_stop - bounds_start
            effective = t.new_text if t.modified else t.text
            replacements[local_start] = (local_stop, effective, t.index)

        # 从左到右构建标注字符串 + 段列表
        annotated_parts = []
        segments = []
        i = 0
        while i < len(text):
            if i in replacements:
                local_stop, effective, idx = replacements[i]
                marker = f'<<{idx}:{effective}>>'
                annotated_parts.append(marker)
                segments.append([effective, idx])
                i = local_stop + 1
            else:
                # 收集连续的非 token 文本
                j = i
                while j < len(text) and j not in replacements:
                    j += 1
                seg = text[i:j]
                annotated_parts.append(seg)
                segments.append([seg, False])
                i = j

        return (''.join(annotated_parts), segments)

    def annotated_legend(self, container: str) -> dict:
        """
        返回标注视图的编号说明表，以 dict 形式。

        返回
        ----
        {index: [type_name, text, modified: bool, line: int], ...}
        其中 index 为标注视图中的 <<N>> 编号。
        """
        ts = self.tokens(container)
        return {
            t.index: [t.type_name, t.text, t.modified, t.line]
            for t in ts
        }

    @staticmethod
    def format_legend(legend: dict) -> str:
        """将 annotated_legend() 返回的 dict 格式化为可读字符串。"""
        if not legend:
            return ''
        max_type = max(len(v[0]) for v in legend.values())
        lines = [f'--- Token 编号说明（{len(legend)} 个）---']
        for idx in sorted(legend):
            type_name, text, modified, line = legend[idx]
            m = ' [已修改]' if modified else ''
            lines.append(
                f'  <<{idx}>> {type_name:<{max_type}}  '
                f'{text!r}{m}  (第 {line} 行)'
            )
        return '\n'.join(lines)

    # ---- 校验保存 ----

    def check(self) -> dict:
        return {
            'ok': not self.has_errors,
            'errors': self.parse_errors,
            'container_count': len(self._containers),
            'token_count': len(self._tokens),
            'containers': self.containers(),
        }

    def save(self, output_path: str = None, backup: bool = True) -> dict:
        text = self.source
        changes = sorted(self.pending_tokens(), key=lambda t: -t.char_start)
        for t in changes:
            text = (text[:t.char_start] + t.new_text +
                    text[t.char_stop + 1:])

        errors = self._validate_text(text)
        if errors:
            return {'ok': False, 'errors': errors}

        if self._crlf:
            text = text.replace('\n', '\r\n')

        target = output_path or self.filepath
        if backup and target == self.filepath:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            bak = f'{self.filepath}.{ts}.bak'
            with open(bak, 'w', encoding='utf-8', newline='') as f:
                f.write(self._raw)

        with open(target, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        return {'ok': True, 'errors': []}

    def _validate_text(self, text: str) -> list:
        stream = InputStream(text)
        lexer = PVRSLexer(stream)
        tstream = CommonTokenStream(lexer)
        tstream.fill()
        parser = _PVRSParser(tstream)
        parser.removeErrorListeners()
        err = _ErrorCollector()
        parser.addErrorListener(err)
        parser.pvrFile()
        return err.errors
