#!/usr/bin/env python3
"""
Interactive tool to view and modify elements within RULE blocks of PVRS files.

Usage:
    python modify_rules.py <pvrs_file>

Workflow:
    1. Parses the file and lists all RULE blocks
    2. User selects a RULE by number
    3. Shows all modifiable elements grouped by type
    4. User picks an element and enters new text
    5. Repeat or apply changes and save

The original file is backed up as <file>.bak before saving.
"""

import sys
import os
from rule_editor import RuleEditor, Element, get_element_types, iter_elements_by_rule


# ---- display helpers ----

def _divider(char='-', width=50):
    print(char * width)


def _select_from_list(items, prompt='Select'):
    """Let user pick from a numbered list. Returns index or -1 on cancel."""
    while True:
        try:
            raw = input(f'{prompt} (0=back): ').strip()
            if not raw:
                continue
            idx = int(raw) - 1
            if idx == -1:
                return -1
            if 0 <= idx < len(items):
                return idx
            print(f'  Out of range (1-{len(items)})')
        except ValueError:
            print('  Enter a number')
        except (EOFError, KeyboardInterrupt):
            return -1


# ---- main interactive flow ----

def show_rules(editor):
    """Display all RULE blocks and let user pick one."""
    summaries = editor.rule_summaries()
    if not summaries:
        print('No RULE blocks found in file.')
        return None

    print(f'Found {len(summaries)} RULE block(s):')
    _divider()
    for i, s in enumerate(summaries):
        types_str = ', '.join(s['types'])
        print(f'  [{i+1}] RULE {s["name"]}  (line {s["line"]}, '
              f'{s["count"]} elements: {types_str})')
    _divider()

    idx = _select_from_list(summaries, 'Select RULE')
    if idx < 0:
        return None
    return summaries[idx]['name']


def show_elements(editor, rule_name):
    """Display elements in a RULE, grouped by type, with global indices."""
    grouped = iter_elements_by_rule(editor.elements, rule_name)
    if not grouped:
        print(f'No modifiable elements in RULE {rule_name}')
        return None, []

    # Build flat list with type-group headers
    flat: list = []   # list of either (type_header_str, []) or (elem, index)
    total = 0
    for etype in sorted(grouped.keys()):
        elems = grouped[etype]
        flat.append((f'--- {etype} ({len(elems)} found) ---', None))
        for e in elems:
            total += 1
            flat.append((e, total))

    for item, idx_or_none in flat:
        if idx_or_none is None:
            print(f'\n{item}')
        else:
            elem, num = item, idx_or_none
            marker = ' *' if elem.modified else ''
            print(f'  [{num}] {elem.text!r}{marker}  (line {elem.line})')
    _divider()

    return grouped, flat


def modify_element(editor, grouped, flat):
    """Interactive modify loop within a RULE."""
    while True:
        elems_only = [(e, n) for e, n in flat if n is not None]
        idx = _select_from_list(elems_only, 'Modify element')
        if idx < 0:
            break

        elem, _ = elems_only[idx]
        print(f'  Type: {elem.element_type}')
        print(f'  Current: {elem.text!r}')

        try:
            new_text = input('  New value: ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not new_text or new_text == elem.text:
            print('  (no change)')
            continue

        editor.add_change(elem, new_text)
        print(f'  [OK] {elem.text!r} -> {new_text!r}')


def confirm_save(editor):
    """Show pending changes and ask for save confirmation."""
    pending = editor.pending_changes()
    if not pending:
        print('No changes to save.')
        return False

    print(f'\n{len(pending)} change(s) pending:')
    _divider()
    for e in pending:
        print(f'  RULE {e.rule_name} / {e.element_type}: '
              f'{e.text!r} -> {e.new_text!r}')
    _divider()

    try:
        ans = input('Save to file? (y/n): ').strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False

    return ans in ('y', 'yes')


def main():
    if len(sys.argv) < 2:
        print(f'Usage: python {sys.argv[0]} <pvrs_file>')
        print()
        print('Interactive tool to view and modify elements inside RULE blocks.')
        print('Creates a .bak backup before overwriting the original file.')
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f'Error: file not found: {filepath}')
        sys.exit(1)

    print(f'Parsing: {filepath}')
    try:
        editor = RuleEditor(filepath)
    except Exception as e:
        print(f'Parse error: {e}')
        sys.exit(1)

    if editor.has_errors:
        print(f'\n  WARNING: {len(editor.parse_errors)} syntax error(s) found!')
        print(f'  Elements may be unreliable. Fix errors before editing.')
        for i, (line, col, msg) in enumerate(editor.parse_errors[:5]):
            print(f'    [{i+1}] line {line}:{col} -> {msg}')
        if len(editor.parse_errors) > 5:
            print(f'    ... and {len(editor.parse_errors)-5} more')
        print()
        ans = input('  Continue anyway? (y/n): ').strip().lower()
        if ans not in ('y', 'yes'):
            sys.exit(0)

    print(f'  {len(editor.rule_names())} RULE(s), '
          f'{len(editor.elements)} element(s) found.')
    print(f'  Supported types: '
          f'{", ".join(t["label"] for t in get_element_types())}')
    print()

    # Main loop
    while True:
        rule_name = show_rules(editor)
        if rule_name is None:
            print('Exiting.')
            break

        print(f'\n=== RULE {rule_name} ===')
        grouped, flat = show_elements(editor, rule_name)
        if grouped is None:
            continue

        modify_element(editor, grouped, flat)

        # Return to rule list, ask if done
        try:
            ans = input('\nModify another RULE? (y/n): ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if ans not in ('y', 'yes'):
            break

    # Save
    if confirm_save(editor):
        editor.save()
        print(f'Saved: {filepath}')
        print(f'Backup: {filepath}.bak')
    else:
        print('Changes discarded.')


if __name__ == '__main__':
    main()
