#!/usr/bin/env python3
"""
Extract lines from a PVRS file that contain keywords.

Usage:
  python extract_keyword_lines.py <pvrs_file> [options]

Options:
  -c, --comments   Include comment lines (default: skip comments)
  -v, --verbose    Show matched keyword list per line
  -k, --keyword X  Filter: only show lines containing keyword X
  -o, --output F   Write output to file instead of stdout
"""

import os
import re
import sys
from collections import defaultdict
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


def build_pattern(keywords):
    sorted_kw = sorted(keywords, key=len, reverse=True)
    return re.compile(r'\b(' + '|'.join(re.escape(kw) for kw in sorted_kw) + r')\b', re.IGNORECASE)


def extract_lines(filepath, keywords, pattern, include_comments=False, filter_kw=None):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        raw_lines = f.readlines()

    if include_comments:
        lines = raw_lines
    else:
        # Strip comments first, then split back to lines
        cleaned = strip_comments(''.join(raw_lines))
        lines = cleaned.split('\n')
        # Re-attach newlines for output
        lines = [l + '\n' for l in lines]

    results = []
    for i, line in enumerate(lines):
        matches = pattern.findall(line)
        if not matches:
            continue

        matched_kw = sorted(set(m.upper() for m in matches))

        if filter_kw and filter_kw.upper() not in matched_kw:
            continue

        results.append({
            'lineno': i + 1,
            'keywords': matched_kw,
            'text': line.rstrip('\n'),
        })

    return results


def main():
    args = sys.argv[1:]
    filepath = None
    include_comments = False
    verbose = False
    filter_kw = None
    output_file = None

    i = 0
    while i < len(args):
        a = args[i]
        if a in ('-c', '--comments'):
            include_comments = True
        elif a in ('-v', '--verbose'):
            verbose = True
        elif a in ('-k', '--keyword'):
            i += 1
            filter_kw = args[i]
        elif a in ('-o', '--output'):
            i += 1
            output_file = args[i]
        elif not filepath:
            filepath = a
        i += 1

    if not filepath:
        print(f'Usage: python {sys.argv[0]} <pvrs_file> [-c] [-v] [-k KEYWORD] [-o output]')
        sys.exit(1)

    if not Path(filepath).exists():
        print(f'Error: file not found: {filepath}')
        sys.exit(1)

    keywords = load_keywords()
    pattern = build_pattern(keywords)

    results = extract_lines(filepath, keywords, pattern, include_comments, filter_kw)

    kw_line_count = defaultdict(int)
    for r in results:
        for kw in r['keywords']:
            kw_line_count[kw] += 1

    if output_file:
        # File output: raw text only
        with open(output_file, 'w', encoding='utf-8') as f:
            for r in results:
                f.write(r['text'] + '\n')
        print(f'Output written to: {output_file}')
        print(f'Lines: {len(results)}')
    else:
        # Console output
        outlines = []
        outlines.append(f'File: {filepath}')
        outlines.append(f'Keywords loaded: {len(keywords)}')
        outlines.append(f'Lines with keywords: {len(results)}')
        outlines.append(f'Comments: {"included" if include_comments else "stripped"}')
        if filter_kw:
            outlines.append(f'Filter: {filter_kw}')
        outlines.append('-' * 60)

        for r in results:
            if verbose:
                kw_list = ', '.join(r['keywords'])
                outlines.append(f'[{r["lineno"]:>5}] [{kw_list}]\n       {r["text"]}')
            else:
                outlines.append(f'[{r["lineno"]:>5}] {r["text"]}')

        if verbose:
            outlines.append('')
            outlines.append('=' * 60)
            outlines.append('Keyword Summary:')
            for kw, cnt in sorted(kw_line_count.items(), key=lambda x: -x[1]):
                outlines.append(f'  {kw:<45} {cnt:>3} lines')

        print('\n'.join(outlines))


if __name__ == '__main__':
    main()
