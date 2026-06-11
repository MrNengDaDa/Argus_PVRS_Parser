#!/usr/bin/env python3
"""
Expand DEFINE_FUN / CALL_FUN macros in Argus PVRS rule files.

- Removes DEFINE_FUN definitions
- Replaces CALL_FUN calls with the expanded function body (argument substitution)
- Recursively expands nested calls within function bodies
- Skips comments: /* */, //, and ; (semicolon)

Usage:
  python expand_macros.py <input_file> [output_file] [-v]
    -v   verbose: print parse/expansion log to stderr
"""

import os
import re
import sys
from pathlib import Path

from pvrs_utils import strip_comments

VERBOSE = False


def log(msg, depth=0):
    """Print log message to stderr if verbose mode is on."""
    if VERBOSE:
        prefix = '  ' * depth
        sys.stderr.write(f'{prefix}[LOG] {msg}\n')


def find_matching_brace(text, open_pos):
    """Return the position of the matching } for { at open_pos, or -1."""
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i
    return -1


def find_matching_paren(text, open_pos):
    """Return the position of the matching ) for ( at open_pos, or -1."""
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _count_lines(text):
    return text.count('\n') + (1 if text and not text.endswith('\n') else 0)


def _find_protected_ranges(text):
    """
    Find positions in text that are names of RULE / DEFINE_FUN / CALL_FUN.
    These positions should be protected from VAR substitution.
    Returns list of (start, end) ranges.
    """
    ranges = []

    # RULE name: from after RULE keyword to the opening {
    for m in re.finditer(r'\brule\b\s+', text, re.IGNORECASE):
        start = m.end()
        brace = text.find('{', start)
        if brace != -1:
            # Include everything up to '{' as the name (trim trailing whitespace)
            name_end = brace
            ranges.append((start, name_end))

    # DEFINE_FUN name: from after DEFINE_FUN keyword to the opening {
    for m in re.finditer(r'\bdefine_fun\b\s+', text, re.IGNORECASE):
        start = m.end()
        brace = text.find('{', start)
        if brace != -1:
            name_end = brace
            ranges.append((start, name_end))

    # CALL_FUN name: from after CALL_FUN( to next whitespace/comma/)
    for m in re.finditer(r'\bcall_fun\b\s*\(\s*', text, re.IGNORECASE):
        start = m.end()
        end = start
        while end < len(text) and text[end] not in ' \t\r\n,)':
            end += 1
        if end > start:
            ranges.append((start, end))

    return ranges


def parse_define_funs(text):
    """
    Find all DEFINE_FUN definitions.
    Returns dict: {NAME_UPPER: {name, args, body, block}}
    """
    funcs = {}
    pos = 0
    while True:
        m = re.search(r'\bdefine_fun\b', text[pos:], re.IGNORECASE)
        if not m:
            break
        kw_start = pos + m.start()
        after_kw = text[kw_start + len(m.group()):]

        brace_m = re.search(r'\{', after_kw)
        if not brace_m:
            pos = kw_start + 1
            continue

        header = after_kw[:brace_m.start()].strip()

        # Parse name and args from header. Name may be quoted.
        name, args = _parse_header_name_and_args(header)
        if not name:
            pos = kw_start + 1
            continue

        brace_pos = kw_start + len(m.group()) + brace_m.start()
        body_start = brace_pos + 1
        body_end = find_matching_brace(text, brace_pos)
        if body_end == -1:
            pos = kw_start + 1
            continue

        body = text[body_start:body_end]
        full_block = text[kw_start:body_end + 1]

        funcs[name.upper()] = {
            'name': name,
            'args': args,
            'body': body.strip(),
            'block': full_block,
        }

        log(f'DEFINE_FUN [{name}]  args=({", ".join(args)})  '
            f'body_lines={_count_lines(body)}  body_preview={repr(body.strip()[:120])}')

        pos = body_end + 1

    log(f'Parsed {len(funcs)} DEFINE_FUN(s): {", ".join(f["name"] for f in funcs.values())}')
    return funcs


def _parse_header_name_and_args(header):
    """Parse name and args from a DEFINE_FUN header string.
    Name can be unquoted (my.func) or quoted ("my func").
    Returns (name, args_list)."""
    if not header:
        return None, []
    header = header.strip()
    if header.startswith('"'):
        end_quote = header.find('"', 1)
        if end_quote == -1:
            return None, []
        name = header[1:end_quote]
        rest = header[end_quote + 1:].strip()
    else:
        parts = header.split(None, 1)
        name = parts[0]
        rest = parts[1] if len(parts) > 1 else ''

    args = rest.split() if rest else []
    return name, args


def substitute_args(body, def_args, call_args, func_name):
    """Replace each def_arg with the corresponding call_arg (whole-word match)."""
    result = body
    for da, ca in zip(def_args, call_args):
        before = result
        result = re.sub(r'\b' + re.escape(da) + r'\b', ca, result, flags=re.IGNORECASE)
        count = len(re.findall(r'\b' + re.escape(da) + r'\b', before, flags=re.IGNORECASE))
        if count > 0:
            log(f'    sub  {da} -> {ca}  ({count} occurrence(s))', depth=2)
    return result


def _call_name_pattern():
    """Regex for CALL_FUN function name — any non-space, non-paren character sequence."""
    # Name can include dots, quotes, dashes, colons, etc. — anything but space or )
    return r'[^)\s]+'


def _call_arg_pattern():
    """Regex for a single CALL_FUN argument — quoted string or non-space token."""
    return r'"[^"]*"|[^\s,()]+'


def expand_call_in_text(text, funcs, phase=''):
    """Replace a single level of CALL_FUN calls. Returns (new_text, changed)."""
    name_pat = _call_name_pattern()
    arg_pat = _call_arg_pattern()
    pattern = re.compile(
        rf'(?i)\bcall_fun\s*\(\s*({name_pat})((?:\s+(?:{arg_pat}))*)\s*\)'
    )

    changed = False
    total_replaced = 0

    def replacer(m):
        nonlocal changed, total_replaced
        fname = m.group(1).upper()
        args_str = m.group(2).strip()
        call_args = re.findall(arg_pat, args_str) if args_str else []

        if fname not in funcs:
            log(f'CALL_FUN [{m.group(1)}] -> UNDEFINED, kept as-is', depth=1)
            return m.group(0)

        changed = True
        total_replaced += 1
        info = funcs[fname]
        expanded = substitute_args(info['body'], info['args'], call_args, fname)

        log(f'CALL_FUN [{info["name"]}]  call_args=({", ".join(call_args)})  '
            f'def_args=({", ".join(info["args"])})  '
            f'expanded_lines={_count_lines(expanded)}  '
            f'preview={repr(expanded.strip()[:120])}',
            depth=1)
        return expanded

    new_text = pattern.sub(replacer, text)
    if total_replaced:
        log(f'{phase}Expanded {total_replaced} CALL_FUN occurrence(s)')
    return new_text, changed


def remove_define_funs(text, funcs):
    """Remove all DEFINE_FUN blocks from text."""
    result = text
    for info in funcs.values():
        before = result
        result = result.replace(info['block'], '')
        if result != before:
            log(f'Removed DEFINE_FUN [{info["name"]}] block ({len(info["block"])} chars)')
    return result


def parse_vars(text):
    """
    Find all VAR definitions.
    Syntax: VAR(name {value [value ...] | ENV})
    Returns dict: {NAME: value_string}
    Name supports any chars except space and ).
    """
    vars_map = {}
    pattern = re.compile(
        r'(?i)\bvar\s*\(\s*([^)\s]+)\s+((?:ENV|(?:[\w.\-]+(?:\s+[\w.\-]+)*)))\s*\)'
    )

    for m in pattern.finditer(text):
        name = m.group(1)
        raw_value = m.group(2).strip()

        if raw_value.upper() == 'ENV':
            value = os.environ.get(name, '')
            log(f'VAR [{name}] = ENV -> "{value}"')
        else:
            value = raw_value
            log(f'VAR [{name}] = "{value}"')

        vars_map[name] = value

    log(f'Parsed {len(vars_map)} VAR(s): {", ".join(vars_map.keys())}')
    return vars_map


def substitute_vars(text, vars_map):
    """
    Replace all VAR references with their values.
    Names immediately following RULE, DEFINE_FUN, CALL_FUN are protected.
    Protection is checked against the CURRENT string state to handle
    text shifted by prior substitutions.
    """
    if not vars_map:
        return text

    result = text
    for name, value in vars_map.items():
        pattern = r'\b' + re.escape(name) + r'\b'
        current_protected = _find_protected_ranges(result)

        def make_replacer(current_value, protected_ranges):
            def is_protected(pos):
                for s, e in protected_ranges:
                    if s <= pos < e:
                        return True
                return False

            def replacer(m2):
                if is_protected(m2.start()):
                    return m2.group(0)
                return current_value
            return replacer

        before = result
        result = re.sub(pattern, make_replacer(value, current_protected), result, flags=re.IGNORECASE)
        total_found = len(re.findall(pattern, before, flags=re.IGNORECASE))
        remaining = len(re.findall(pattern, result, flags=re.IGNORECASE))
        count = total_found - remaining
        if count > 0:
            log(f'  VAR sub  {name} -> "{value}"  ({count}/{total_found} occurrence(s), '
                f'{remaining} protected)')
    return result


def remove_vars(text):
    """Remove all VAR(...) statements from text."""
    return re.sub(r'(?i)\bvar\s*\([^)]+\)', '', text)


def expand_all(text):
    """Full pipeline: strip comments, expand macros recursively, remove DEFINE_FUNs."""
    log('=' * 60)
    log('STEP 1: Strip comments')
    before_len = len(text)
    text = strip_comments(text)
    log(f'  {before_len} -> {len(text)} chars (-{before_len - len(text)})')

    log('=' * 60)
    log('STEP 2: Parse and expand VAR definitions')
    vars_map = parse_vars(text)
    if vars_map:
        text = substitute_vars(text, vars_map)
        text = remove_vars(text)
        # collapse '- number' into '-number' after VAR substitution
        text = re.sub(r'(?<=[\s(])-\s+(?=[\d.])', '-', text)

    log('=' * 60)
    log('STEP 3: Parse DEFINE_FUN definitions')
    funcs = parse_define_funs(text)

    if not funcs:
        log('No DEFINE_FUN found, nothing to expand.')
        return text

    log('=' * 60)
    log('STEP 4: Expand CALL_FUN within DEFINE_FUN bodies (pre-expand)')
    for name, info in funcs.items():
        body = info['body']
        changed = True
        iteration = 0
        while changed:
            iteration += 1
            body, changed = expand_call_in_text(body, funcs,
                                                phase=f'  [{info["name"]}] iter{iteration}: ')
        if iteration > 1:
            log(f'  [{info["name"]}] converged after {iteration} iterations')
        info['body'] = body

    log('=' * 60)
    log('STEP 5: Remove DEFINE_FUN blocks from text')
    text = remove_define_funs(text, funcs)

    log('=' * 60)
    log('STEP 6: Expand CALL_FUN in main text')
    changed = True
    iteration = 0
    while changed:
        iteration += 1
        text, changed = expand_call_in_text(text, funcs,
                                            phase=f'  Main iter{iteration}: ')
    if iteration > 1:
        log(f'  Main converged after {iteration} iterations')

    log('=' * 60)
    log('DONE')
    return text


def main():
    global VERBOSE

    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    flags = [a for a in sys.argv[1:] if a.startswith('-')]
    VERBOSE = '-v' in flags or '--verbose' in flags

    if len(args) < 1:
        print(f'Usage: python {sys.argv[0]} <input_file> [output_file] [-v]')
        print(f'  -v   verbose: print parse/expansion log to stderr')
        sys.exit(1)

    input_path = Path(args[0])
    if not input_path.exists():
        print(f'Error: file not found: {input_path}')
        sys.exit(1)

    log(f'Input file: {input_path}')
    with open(input_path, 'r', encoding='utf-8', errors='replace') as f:
        original = f.read()
    log(f'File size: {len(original)} chars, {_count_lines(original)} lines')

    result = expand_all(original)

    output_path = args[1] if len(args) >= 2 else None
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f'Expanded output written to: {output_path}')
    else:
        print(result)


if __name__ == '__main__':
    main()
