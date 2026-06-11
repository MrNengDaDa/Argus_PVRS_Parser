#!/usr/bin/env python3
"""Count Argus PVRS keyword occurrences in a rule file."""

import os
import re
import sys
from collections import Counter
from pathlib import Path

from pvrs_utils import strip_comments

if getattr(sys, 'frozen', False):
    _BASE_DIR = sys._MEIPASS
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

KEYWORD_FILE = os.path.join(_BASE_DIR, 'argus_pvrs_keywords.txt')


def load_keywords():
    with open(KEYWORD_FILE, 'r', encoding='utf-8') as f:
        return {line.strip() for line in f if line.strip()}


def count_keywords(filepath, keywords):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Strip comments before counting
    content = strip_comments(content)

    # Build pattern: match any keyword as a whole word
    # Sort by length descending so longer matches take priority
    sorted_kw = sorted(keywords, key=len, reverse=True)
    pattern = r'\b(' + '|'.join(re.escape(kw) for kw in sorted_kw) + r')\b'
    matches = re.findall(pattern, content, re.IGNORECASE)
    # Normalize to uppercase for consistent counting
    return Counter(m.upper() for m in matches)


def main():
    if len(sys.argv) < 2:
        print(f'Usage: python {sys.argv[0]} <pvrs_rule_file>')
        sys.exit(1)

    filepath = sys.argv[1]
    if not Path(filepath).exists():
        print(f'Error: file not found: {filepath}')
        sys.exit(1)

    keywords = load_keywords()
    print(f'Loaded {len(keywords)} keywords from {os.path.basename(KEYWORD_FILE)}')

    counter = count_keywords(filepath, keywords)

    total = sum(counter.values())
    unique_found = len(counter)
    print(f'\nFile: {filepath}')
    print(f'Total keyword occurrences: {total}')
    print(f'Unique keywords found:     {unique_found} / {len(keywords)}')
    print(f'Coverage:                   {unique_found / len(keywords) * 100:.1f}%')
    print(f'\n{"Keyword":<45} {"Count":>6}')
    print('-' * 53)
    for kw, cnt in counter.most_common():
        print(f'{kw:<45} {cnt:>6}')

    not_found = sorted(keywords - set(counter.keys()))
    if not_found:
        print(f'\n--- Not found ({len(not_found)}) ---')
        for kw in not_found:
            print(f'  {kw}')


if __name__ == '__main__':
    main()
