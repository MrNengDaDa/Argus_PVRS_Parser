"""TokenEditor — 主编辑器。"""

import sys, os
from typing import List, Dict, Any
from datetime import datetime

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'grammar', 'gen'))

from antlr4 import InputStream, CommonTokenStream
from PVRSLexer import PVRSLexer
from PVRSParser import PVRSParser as _PVRSParser
from .collector import _ContainerBoundCollector, _ErrorCollector
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

    def __init__(self, filepath: str):
        self.filepath = filepath
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
        collector = _ContainerBoundCollector(self.source)
        collector.visit(self._tree)
        self._containers = collector.containers

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

    def annotated_text(self, container: str) -> str:
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

        for t in reversed(ts):
            local_start = t.char_start - bounds_start
            local_stop = t.char_stop - bounds_start
            effective = t.new_text if t.modified else t.text
            marker = f'<<{t.index}:{effective}>>'
            text = text[:local_start] + marker + text[local_stop + 1:]
        return text

    def annotated_legend(self, container: str) -> str:
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
        return {
            'ok': not self.has_errors,
            'errors': self.parse_errors,
            'container_count': len(self._containers),
            'token_count': len(self._tokens),
            'containers': self.containers(),
        }

    def save(self, output_path: str = None, backup: bool = True,
             original_path: str = None) -> dict:
        """
        Save changes. If the expanded text contains /*:...*/ markers and
        original_path is given, reverse-map changes to the original file.
        Otherwise, normal save.
        """
        # Detect annotated mode
        has_markers = '/*:' in self.source
        if has_markers and original_path:
            return self._reverse_save(original_path, backup)

        # Normal save
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

    def _has_markers(self) -> bool:
        return '/*:' in self.source

    def _reverse_save(self, original_path: str, backup: bool = True) -> dict:
        """
        Scan the annotated expanded text left-to-right. For each /*:...*/
        marker region, apply reverse mapping rules. Collector identity text
        is copied with direct changes applied.

        Returns the reversed text and writes it to original_path.
        """
        import re
        changes = {(cs, ce): nt for cs, ce, nt in
                   [(t.char_start, t.char_stop, t.new_text)
                    for t in self.pending_tokens()]}

        out = []
        pos = 0
        text = self.source

        while pos < len(text):
            ms = text.find('/*:', pos)
            if ms == -1:
                out.append(self._apply_direct(text[pos:], changes, pos))
                break

            # Identity text before marker
            if ms > pos:
                out.append(self._apply_direct(text[pos:ms], changes, pos))

            me = text.find('*/', ms + 3)
            if me == -1:
                out.append(text[ms:])
                break

            marker = text[ms:me + 2]

            if marker.startswith('/*:V:'):
                var_name, var_value, handled_to = self._parse_var_marker(text, ms, me, changes)
                out.append(var_value if var_name is None else var_name)
                pos = handled_to

            elif marker.startswith('/*:F:'):
                func_result, handled_to = self._parse_func_marker(text, ms, me, changes)
                out.append(func_result)
                pos = handled_to

            elif marker.startswith('/*:A:'):
                # Skip over ARG region entirely (processed inside FUNC)
                aend = text.find('/*:A*/', me + 2)
                pos = (aend + 5) if aend != -1 else (me + 2)  # /*:A*/ = 5 chars

            else:
                out.append(marker)
                pos = me + 2

        result = ''.join(out)
        # Merge reversed RULE bodies into the original file
        merged = self._merge_into_original(result, original_path)

        target = original_path
        if backup:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            with open(f'{target}.{ts}.bak', 'w', encoding='utf-8', newline='') as f:
                with open(target, 'r', encoding='utf-8', errors='replace') as fin:
                    f.write(fin.read())

        if self._crlf:
            merged = merged.replace('\n', '\r\n')
        with open(target, 'w', encoding='utf-8', newline='') as f:
            f.write(merged)
        return {'ok': True, 'errors': [], 'reversed': True,
                'target': target}

    def _merge_into_original(self, reversed_text, original_path):
        """
        Replace RULE bodies in the original file with the reversed content.
        Keeps VAR and DEFINE_FUN definitions intact.
        """
        # Read original file
        with open(original_path, 'r', encoding='utf-8', errors='replace') as f:
            orig = f.read()

        # Find RULE boundaries in both files
        # Use simple brace matching on original to find RULE positions
        import re
        orig_rules = {}
        for m in re.finditer(r'\bRULE\s+(\S+)', orig):
            name = m.group(1).strip('"')
            brace = orig.find('{', m.end())
            if brace == -1:
                continue
            depth = 0
            end = -1
            for i in range(brace, len(orig)):
                if orig[i] == '{':
                    depth += 1
                elif orig[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end != -1:
                orig_rules[name] = (brace + 1, end)  # exclusive end

        # Find RULE boundaries in reversed text
        reversed_rules = {}
        for m in re.finditer(r'\bRULE\s+(\S+)', reversed_text):
            name = m.group(1).strip('"')
            brace = reversed_text.find('{', m.end())
            if brace == -1:
                continue
            depth = 0
            end = -1
            for i in range(brace, len(reversed_text)):
                if reversed_text[i] == '{':
                    depth += 1
                elif reversed_text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end != -1:
                reversed_rules[name] = reversed_text[brace + 1:end]

        # Replace RULE bodies in original from right to left
        replacements = []
        for name, (body_start, body_end) in orig_rules.items():
            if name in reversed_rules:
                replacements.append((body_start, body_end,
                                     reversed_rules[name]))
        replacements.sort(key=lambda x: -x[0])

        for rs, re_pos, new_body in replacements:
            orig = orig[:rs] + new_body + orig[re_pos:] + ''
        return orig

    # ---- marker parsing helpers ----

    def _apply_direct(self, seg, changes, offset):
        """Apply pending changes directly to an identity segment."""
        result = list(seg)
        for (cs, ce), nt in changes.items():
            ls, le = cs - offset, ce - offset
            if 0 <= ls < len(seg) and 0 <= le < len(seg):
                result[ls:le + 1] = nt
        return ''.join(result)

    def _parse_var_marker(self, text, ms, me, changes):
        """
        Parse /*:V:name=value*/ ... /*:V*/.
        Returns (var_name, resolved_value, new_pos) where var_name=None
        means use resolved_value as literal.
        """
        import re
        m = re.match(r'/\*:V:([^=]+)=(.*?)\*/', text[ms:me + 2])
        if not m:
            return (None, text[ms:me + 2], me + 2)
        var_name = m.group(1)
        var_value = m.group(2)

        end_marker = text.find('/*:V*/', me + 2)
        if end_marker == -1:
            return (None, text[ms:me + 2], me + 2)

        val_start = me + 2
        val_end = end_marker - 1
        effective = var_value
        modified = False
        for (cs, ce), nt in changes.items():
            if cs >= val_start and ce <= val_end:
                effective = nt
                modified = True
                break

        if modified:
            return (None, effective, end_marker + 6)  # literal, skip /*:V*/
        return (var_name, None, end_marker + 6)  # VAR ref

    def _parse_func_marker(self, text, ms, me, changes):
        """
        Parse /*:F:name:idx:args*/ body /*:FEND*/.
        Returns (result_text, new_pos).
        """
        import re
        m = re.match(r'/\*:F:([^:]+):(\d+):(.*?)\*/', text[ms:me + 2])
        if not m:
            return (text[ms:me + 2], me + 2)

        func_name = m.group(1)
        arg_map_str = m.group(3)
        args = re.findall(r'([^:=]+)=([^:]*)', arg_map_str)

        fend = text.find('/*:FEND*/', me + 2)
        if fend == -1:
            return (text[ms:me + 2], me + 2)

        body_start = me + 2
        body_end = fend
        body = text[body_start:body_end]

        # Check consistency: each arg's occurrences must all be either
        # unchanged or changed to the same value
        new_arg_values = {}  # {arg_name: new_value}
        for arg_name, arg_val in args:
            effective_vals = set()
            for am in re.finditer(rf'/\*:A:{re.escape(arg_name)}:(\d+)\*/', body):
                aend = body.find('/*:A*/', am.end())
                if aend == -1:
                    continue
                val = body[am.end():aend].strip()
                abs_s = body_start + am.end()
                abs_e = body_start + aend - 1
                was_modified = False
                for (cs, ce), nt in changes.items():
                    if cs >= abs_s and ce <= abs_e:
                        val = nt
                        was_modified = True
                        break
                if was_modified:
                    effective_vals.add(re.sub(r'/\*:V[^*/\n]*\*/\s*', '', val).strip())
                else:
                    effective_vals.add(arg_val)
            if len(effective_vals) > 1:
                return (self._keep_expanded(body, changes, body_start), fend + 9)
            if effective_vals and effective_vals != {arg_val}:
                new_arg_values[arg_name] = effective_vals.pop()

        # Check body for non-arg changes
        for (cs, ce), nt in changes.items():
            if cs >= body_start and ce <= body_end:
                if not self._in_arg_range(cs, ce, body, body_start):
                    return (self._keep_expanded(body, changes, body_start), fend + 9)

        # Build CALL_FUN
        call_args = ' '.join(new_arg_values.get(a, v) for a, v in args)
        return (f'CALL_FUN( {func_name} {call_args} )', fend + 9)

    def _in_arg_range(self, cs, ce, body, body_offset):
        """Check if a change position falls within any /*:A:...*/ region."""
        import re
        for am in re.finditer(r'/\*:A:[^:]+:\d+\*/', body):
            aend = body.find('/*:A*/', am.end())
            if aend == -1:
                continue
            abs_s = body_offset + am.end()
            abs_e = body_offset + aend - 1
            if cs >= abs_s and ce <= abs_e:
                return True
        return False

    def _keep_expanded(self, body, changes, offset):
        """Apply direct changes to body text and return it."""
        result = body
        for (cs, ce), nt in sorted(changes.items(), key=lambda x: -x[0]):
            if cs >= offset and ce <= offset + len(body):
                ls, le = cs - offset, ce - offset
                result = result[:ls] + nt + result[le + 1:]
        return result

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
