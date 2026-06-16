"""
基于 ANTLR Token 流的完整 PVRS 元素修改器。

与 rule_editor.py 只收集特定语法节点（layerRef/constraint/expr）不同，
本模块收集 RULE 块和 derived_layer_def 内的**每一个 token**，
支持修改任意关键字、标识符、标点、运算符等。

架构
----
    ANTLR Lexer → CommonTokenStream (全量 token)
    │
    ├── 找到每个容器（RULE / derived_layer_def）的 token 范围
    ├── 收集范围内的所有 token → TokenElement
    └── TokenEditor 提供查询/修改/保存接口

用法
----
    from full_token_editor import TokenEditor

    te = TokenEditor("input.pvrs")
    tokens = te.tokens("chk1")
    for t in tokens:
        print(t)

    te.replace_by_text("chk1", "M1", "METAL1")
    te.replace_by_index("chk1", 5, "MET99")
    te.save()

    # 命令行
    python full_token_editor.py <file> --show chk1
    python full_token_editor.py <file> --sample
"""

import sys
import os
import re
from typing import Optional, List, Dict, Any

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'grammar', 'gen'))

from antlr4 import FileStream, InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener
from antlr4.Token import CommonToken
from PVRSLexer import PVRSLexer
from PVRSParser import PVRSParser as _PVRSParser
from PVRSParserVisitor import PVRSParserVisitor


# ============================================================
# TokenElement — 单个 token 的描述
# ============================================================

class TokenElement:
    """一个 ANTLR token 元素。"""
    def __init__(self, token: CommonToken, container: str, idx: int,
                 source: str):
        self.text = token.text or ''          # token 原文
        self.type_name = _token_type_name(token.type)  # 类型名（如 ID、MUL）
        self.line = token.line                 # 行号
        self.char_start = token.start          # 源文本起始偏移
        self.char_stop = token.stop            # 源文本结束偏移
        self.container = container             # 所属容器名
        self.index = idx                       # 1 起始的容器内编号

    @property
    def modified(self) -> bool:
        return hasattr(self, '_new_text')

    @property
    def new_text(self) -> Optional[str]:
        return getattr(self, '_new_text', None)

    def __repr__(self):
        t = f'[{self.type_name}]'
        m = ' *' if self.modified else ''
        return (f'<<{self.index}>> {t} {self.text!r}{m}  '
                f'(line {self.line}, {self.char_start}-{self.char_stop})')


# ============================================================
# 容器边界收集器（Visitor）
# ============================================================

class _ContainerBoundCollector(PVRSParserVisitor):
    """
    收集所有容器的 token 范围，同时记录 op_statement 的 char 范围。
    只收集 op_statement 内部的 token，跳过容器声明行和赋值左侧。
    """

    def __init__(self, source: str):
        self.source = source
        self.containers: List[Dict[str, Any]] = []
        self._op_ranges: List[tuple] = []  # [(char_start, char_stop), ...]

    # ---- 记录 op_statement 范围 ----

    def visitOp_statement(self, ctx):
        if ctx.start and ctx.stop:
            self._op_ranges.append((ctx.start.start, ctx.stop.stop))
        self.visitChildren(ctx)
        return None

    # ---- 记录容器边界 ----

    def visitRule_statement(self, ctx):
        name = ctx.ruleName().getText() if ctx.ruleName() else ''
        if name and ctx.start is not None:
            self.containers.append({
                'name': name,
                'kind': 'RULE',
                'token_start': ctx.start.tokenIndex,
                'token_stop': ctx.stop.tokenIndex if ctx.stop else ctx.start.tokenIndex,
                'char_start': ctx.start.start,
                'char_stop': ctx.stop.stop if ctx.stop else ctx.start.stop,
                'line': ctx.start.line,
            })
        self.visitChildren(ctx)
        return None

    def visitDerived_layer_def(self, ctx):
        # 仅收集不在 RULE 内部的 derived_layer_def
        node = ctx.parentCtx
        while node:
            if isinstance(node, _PVRSParser.Rule_statementContext):
                self.visitChildren(ctx)
                return None
            node = node.parentCtx

        lr = ctx.layerRef()
        if lr and lr.start and ctx.start:
            name = self.source[lr.start.start:lr.stop.stop + 1]
            self.containers.append({
                'name': name,
                'kind': 'DEF',
                'token_start': ctx.start.tokenIndex,
                'token_stop': ctx.stop.tokenIndex if ctx.stop else ctx.start.tokenIndex,
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
# Token 类型名映射
# ============================================================

# 从 lexer 词汇表中提取 token 名 → type 编号 的映射
def _build_token_map():
    vocab = PVRSLexer.__dict__
    tmap = {}
    for k, v in vocab.items():
        if isinstance(v, int) and not k.startswith('_'):
            tmap[v] = k
    return tmap

_TOKEN_MAP = _build_token_map()

def _token_type_name(ttype: int) -> str:
    return _TOKEN_MAP.get(ttype, f'UNKNOWN({ttype})')


# ============================================================
# TokenEditor — 主编辑器
# ============================================================

class TokenEditor:
    """
    基于完整 token 流的 PVRS 元素修改器。

    收集 RULE 和 derived_layer_def 内的所有 token，
    支持按编号或文本修改，修改后自动生成标注视图。
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        with open(filepath, 'r', encoding='utf-8', errors='replace', newline='') as f:
            raw = f.read()

        self._crlf = '\r\n' in raw
        self._raw = raw
        self.source = raw.replace('\r\n', '\n')

        # ---- ANTLR 解析 ----
        inp = InputStream(self.source)
        lexer = PVRSLexer(inp)
        self._token_stream = CommonTokenStream(lexer)
        # 先填满 token 流
        self._token_stream.fill()

        parser = _PVRSParser(self._token_stream)
        parser.removeErrorListeners()
        err = _ErrorCollector()
        parser.addErrorListener(err)
        self._tree = parser.pvrFile()
        self._parse_errors = err.errors

        # 收集容器边界 + op_statement 范围
        collector = _ContainerBoundCollector(self.source)
        collector.visit(self._tree)
        self._containers = collector.containers
        self._op_ranges = collector._op_ranges   # op_statement 的 char 范围

        # 为每个容器收集 token
        self._tokens: List[TokenElement] = []
        self._container_tokens: Dict[str, List[TokenElement]] = {}
        self._build_token_index()

    def _build_token_index(self):
        """将 token 流按容器范围分配，仅收集 op_statement 内部的 token。"""
        all_tokens = self._token_stream.tokens

        def _in_op_range(cs: int, ce: int) -> bool:
            """检查 token 的 char 范围是否在任何 op_statement 内。"""
            for s, e in self._op_ranges:
                if s <= cs and ce <= e:
                    return True
            return False

        for c in self._containers:
            name = c['name']
            tstart = c['token_start']
            tstop = c['token_stop']
            container_tokens = []
            for t in all_tokens:
                if t.channel != 0:
                    continue
                if t.type == -1:
                    continue
                if not (tstart <= t.tokenIndex <= tstop):
                    continue
                # 只收集 op_statement 内的 token
                if not _in_op_range(t.start, t.stop):
                    continue
                idx = len(container_tokens) + 1
                te = TokenElement(t, name, idx, self.source)
                container_tokens.append(te)
            self._container_tokens[name] = container_tokens
            self._tokens.extend(container_tokens)

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
        """返回容器摘要列表。"""
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
        """返回指定容器内的所有 token（按索引顺序）。"""
        return list(self._container_tokens.get(container, []))

    def all_tokens(self) -> List[TokenElement]:
        """返回所有容器的所有 token。"""
        return list(self._tokens)

    # ---- 查询 ----

    def container_text(self, container: str) -> str:
        """返回容器原文。"""
        for c in self._containers:
            if c['name'] == container:
                return self.source[c['char_start']:c['char_stop'] + 1]
        return ''

    # ---- 修改 ----

    def replace_by_text(self, container: str, old_text: str,
                        new_text: str) -> bool:
        """
        将指定容器中所有文本匹配的 token 替换。

        返回 True（有修改）或 False（无匹配）。
        """
        ts = self.tokens(container)
        matched = [t for t in ts if t.text == old_text]
        if not matched:
            return False
        for t in matched:
            t._new_text = new_text
        return True

    def replace_by_index(self, container: str, index: int,
                         new_text: str) -> bool:
        """
        按标注视图中的 <<N>> 编号修改单个 token。

        返回 True（成功）或 False（索引越界）。
        """
        ts = self.tokens(container)
        if index < 1 or index > len(ts):
            return False
        ts[index - 1]._new_text = new_text
        return True

    def pending_tokens(self) -> List[TokenElement]:
        """返回所有已修改的 token。"""
        return [t for t in self._tokens if t.modified]

    def clear_changes(self):
        """撤销所有修改。"""
        for t in self._tokens:
            if t.modified:
                del t._new_text

    # ---- 标注视图 ----

    def annotated_text(self, container: str) -> str:
        """返回带 <<N:value>> 标注的容器原文。"""
        ts = self.tokens(container)
        if not ts:
            return self.container_text(container)

        text = self.container_text(container)
        bounds_start = None
        for c in self._containers:
            if c['name'] == container:
                bounds_start = c['char_start']
                break
        if bounds_start is None:
            return text

        # 从右往左替换（避免偏移量错乱）
        for t in reversed(ts):
            local_start = t.char_start - bounds_start
            local_stop = t.char_stop - bounds_start
            effective = t.new_text if t.modified else t.text
            marker = f'<<{t.index}:{effective}>>'
            text = text[:local_start] + marker + text[local_stop + 1:]
        return text

    def annotated_legend(self, container: str) -> str:
        """返回标注视图的编号说明表。"""
        ts = self.tokens(container)
        if not ts:
            return ''
        max_type = max(len(t.type_name) for t in ts)
        lines = [f'--- Token 编号说明（{len(ts)} 个）---']
        for t in ts:
            m = ' [已修改]' if t.modified else ''
            lines.append(
                f'  <<{t.index}>> {t.type_name:<{max_type}}  '
                f'{t.text!r}{m}  (第 {t.line} 行)'
            )
        return '\n'.join(lines)

    # ---- 校验保存 ----

    def check(self) -> dict:
        """语法检查，与 RuleEditorPlugin.check() 同接口。"""
        return {
            'ok': not self.has_errors,
            'errors': self.parse_errors,
            'container_count': len(self._containers),
            'token_count': len(self._tokens),
            'containers': self.containers(),
        }

    def save(self, output_path: str = None, backup: bool = True) -> dict:
        """校验并保存。返回 {'ok': bool, 'errors': [(line,col,msg),...]}."""
        from datetime import datetime

        # 构建修改后的文本
        text = self.source
        changes = sorted(self.pending_tokens(), key=lambda t: -t.char_start)
        for t in changes:
            text = (text[:t.char_start] + t.new_text +
                    text[t.char_stop + 1:])

        # 校验
        errors = self._validate_text(text)
        if errors:
            return {'ok': False, 'errors': errors}

        # 写入
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
        """对修改后文本做 ANTLR 解析，返回错误列表。"""
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


# ============================================================
# TokenEditorPlugin — 声明式批量修改
# ============================================================

class TokenEditorPlugin:
    """TokenEditor 的便捷包装，接口与 RuleEditorPlugin 一致。"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._editor = TokenEditor(filepath)

    @property
    def editor(self) -> TokenEditor:
        return self._editor

    def check(self) -> dict:
        return self._editor.check()

    def show(self, container: str) -> tuple:
        return (self._editor.annotated_text(container),
                self._editor.annotated_legend(container))

    def replace_by_text(self, container: str, old_text: str,
                        new_text: str) -> bool:
        return self._editor.replace_by_text(container, old_text, new_text)

    def replace_by_index(self, container: str, index: int,
                         new_text: str) -> bool:
        return self._editor.replace_by_index(container, index, new_text)

    def save(self, output_path: str = None, backup: bool = True) -> dict:
        return self._editor.save(output_path=output_path, backup=backup)

    def discard(self):
        self._editor.clear_changes()

    @property
    def pending_count(self) -> int:
        return len(self._editor.pending_tokens())


# ============================================================
# 命令行入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print('用法: python full_token_editor.py <pvrs_file> [选项]')
        print()
        print('  --show NAME    显示指定容器的标注视图（含所有 token）')
        print('  --sample       在所有容器上运行修改示例')
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f'错误: 文件不存在 — {filepath}')
        sys.exit(1)

    te = TokenEditor(filepath)
    info = te.check()

    if info['ok']:
        print('[语法] 正确')
    else:
        print(f'[语法错误] {len(info["errors"])} 个错误')
        for line, col, msg in info['errors'][:5]:
            print(f'  [{line}:{col}] {msg}')

    print(f'[摘要] {info["container_count"]} 个容器, '
          f'{info["token_count"]} 个 token')
    for c in info['containers']:
        print(f'  [{c["kind"]}] {c["name"]}: '
              f'{c["count"]} tokens ({", ".join(c["types"][:5])}...)')

    # --show
    if '--show' in sys.argv:
        idx = sys.argv.index('--show')
        if idx + 1 < len(sys.argv):
            name = sys.argv[idx + 1]
            print(f'\n========== {name} ==========')
            print(te.annotated_text(name))
            print(te.annotated_legend(name))

    # --sample
    if '--sample' in sys.argv:
        names = te.container_names
        if not names:
            print('没有可演示的容器。')
            sys.exit(0)
        c = names[0]

        print(f'\n========== 修改示例（容器: {c}）==========\n')

        plugin = TokenEditorPlugin(filepath)

        print('[示例1] replace_by_text — 批量替换文本')
        ok = plugin.replace_by_text(c, 'M1', 'METAL1')
        print(f'  结果: {ok}')

        print(f'\n[示例2] replace_by_index — 按编号替换')
        ok = plugin.replace_by_index(c, 3, 'M99')
        print(f'  结果: {ok}')

        print(f'\n[示例3] 标注视图:')
        text, legend = plugin.show(c)
        print(text)
        print(legend)

        result = plugin.save(backup=False)
        if result['ok']:
            print(f'\n[保存] 成功')
        else:
            print(f'\n[保存] 失败 — {len(result["errors"])} 个错误')
        plugin.discard()


if __name__ == '__main__':
    main()
