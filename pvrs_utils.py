"""Shared utilities for Argus PVRS processing."""

import re


def strip_comments(text):
    """
    Remove PVRS comments using a state machine.

    Comment types (same precedence as Verilog):
      - //  : line comment to end of line
      - ;   : line comment to end of line
      - /* */ : multi-line block comment

    Whichever starts first wins:
      - /* inside // is ignored (part of line comment)
      - // inside /* */ is ignored (part of block comment)
    """
    result = []
    i = 0
    n = len(text)
    while i < n:
        # --- // line comment ---
        if i + 1 < n and text[i] == '/' and text[i + 1] == '/':
            nl = text.find('\n', i + 2)
            if nl == -1:
                # comment runs to EOF - keep trailing newline if present
                return ''.join(result)
            result.append('\n')
            i = nl + 1
            continue

        # --- ; line comment ---
        if text[i] == ';':
            nl = text.find('\n', i + 1)
            if nl == -1:
                return ''.join(result)
            result.append('\n')
            i = nl + 1
            continue

        # --- /* block comment ---
        if i + 1 < n and text[i] == '/' and text[i + 1] == '*':
            end = text.find('*/', i + 2)
            if end == -1:
                # unterminated comment, consume rest
                return ''.join(result)
            # preserve line count within block comment
            block = text[i + 2:end]
            result.append('\n' * block.count('\n'))
            i = end + 2
            continue

        # --- normal character ---
        result.append(text[i])
        i += 1

    return ''.join(result)
