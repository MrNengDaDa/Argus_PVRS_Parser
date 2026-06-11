#!/bin/bash
# Build Linux executables for Argus PVRS Parser
# Run this script on a Linux system (or WSL) with Python 3.9+ and pip available

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Installing PyInstaller ==="
pip install pyinstaller

echo "=== Building test_errors ==="
pyinstaller --onefile test_errors.py \
    --distpath dist --workpath build --clean \
    --paths grammar/gen \
    --hidden-import PVRSLexer \
    --hidden-import PVRSParser \
    --hidden-import PVRSParserVisitor \
    --add-data "grammar/gen:grammar/gen" \
    --add-data "antlr-4.9.3-complete.jar:." \
    --add-data "argus_pvrs_keywords.txt:."

echo "=== Building expand_macros ==="
pyinstaller --onefile expand_macros.py \
    --distpath dist --workpath build \
    --hidden-import pvrs_utils \
    --add-data "argus_pvrs_keywords.txt:."

echo "=== Building count_keywords ==="
pyinstaller --onefile count_keywords.py \
    --distpath dist --workpath build \
    --hidden-import pvrs_utils \
    --add-data "argus_pvrs_keywords.txt:."

echo "=== Building extract_keyword_lines ==="
pyinstaller --onefile extract_keyword_lines.py \
    --distpath dist --workpath build \
    --hidden-import pvrs_utils \
    --add-data "argus_pvrs_keywords.txt:."

echo ""
echo "=== Build complete ==="
echo "Executables are in: $SCRIPT_DIR/dist/"
ls -la dist/

echo ""
echo "Usage:"
echo "  ./dist/test_errors <drc_file>           # Parse and report syntax errors"
echo "  ./dist/expand_macros <input> [output]    # Expand DEFINE_FUN/CALL_FUN/VAR macros"
echo "  ./dist/count_keywords <file>             # Count keyword occurrences"
echo "  ./dist/extract_keyword_lines <file>      # Extract lines containing keywords"
