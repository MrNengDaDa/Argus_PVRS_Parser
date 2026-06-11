"""
DRC 语法解析错误检测工具

对指定 DRC 文件执行完整的语法解析，收集并报告所有语法错误。
使用 SLL 预测模式以获得更快的解析速度。

用法:
    python test_errors.py [--all] <drc_file>

参数:
    drc_file  - 待解析的 DRC 规则文件路径
    --all     - 可选，报告所有错误（默认遇到第一个错误即停止）

输出:
    解析成功时提示无错误；否则输出错误总数及每个错误的行号、列号和描述（最多显示前 50 个）。
"""

import sys
import os

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'grammar', 'gen'))

from antlr4 import *
from antlr4.error.ErrorListener import ErrorListener
from antlr4.atn.PredictionMode import PredictionMode
from PVRSLexer import PVRSLexer as drcLexer
from PVRSParser import PVRSParser as drcParser

sys.setrecursionlimit(50000)


class FirstErrorException(Exception):
    """当 --first 模式下遇到首个语法错误时抛出，用于中断解析。"""
    pass


class CollectingErrorListener(ErrorListener):
    """自定义错误监听器，收集解析过程中的所有语法错误。"""

    def __init__(self, stop_on_first=False):
        super().__init__()
        self.errors = []
        self.stop_on_first = stop_on_first

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        short_msg = msg[:200] if len(msg) > 200 else msg
        self.errors.append((line, column, short_msg))
        if self.stop_on_first:
            raise FirstErrorException()


def main(argv):
    stop_on_first = '--all' not in argv
    files = [a for a in argv[1:] if not a.startswith('--')]
    if not files:
        print("Usage: test_errors.py [--all] <drc_file>")
        return

    # 构建词法分析器和语法解析器
    input_stream = FileStream(files[0], 'utf-8')
    lexer = drcLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = drcParser(stream)

    # 使用 SLL 模式加速解析
    parser._interp.predictionMode = PredictionMode.SLL

    # 替换默认错误监听器为自定义收集器
    parser.removeErrorListeners()
    error_listener = CollectingErrorListener(stop_on_first=stop_on_first)
    parser.addErrorListener(error_listener)

    try:
        tree = parser.pvrFile()
    except FirstErrorException:
        pass

    # 输出错误报告
    if error_listener.errors:
        print(f"Total errors: {len(error_listener.errors)}")
        for i, (line, col, msg) in enumerate(error_listener.errors[:50]):
            print(f"  [{i+1}] line {line}:{col} -> {msg}")
    else:
        print("No errors! Parsing successful.")


if __name__ == '__main__':
    main(sys.argv)
