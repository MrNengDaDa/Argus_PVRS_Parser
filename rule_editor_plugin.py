"""
RuleEditor 插件 — 声明式批量修改 PVRS 规则文件。

将重复的 打开 → 检查 → 浏览 → 修改 → 保存 流程封装为可复用的
Plugin 类，也支持命令行直接运行。

作为模块使用
------------
    from rule_editor_plugin import RuleEditorPlugin, ModSpec

    plugin = RuleEditorPlugin("input.pvrs")
    plugin.check()                    # 语法检查 + 显示摘要
    plugin.show("chk1")               # 查看标注视图

    # 批量修改
    plugin.replace("chk1", "M1", "METAL1", element_type="layerRef")
    plugin.replace("chk1", "< 0.5", "< 1.0", element_type="constraint")

    plugin.save()                     # 校验并保存

命令行
------
    python rule_editor_plugin.py <file>              # 仅显示摘要
    python rule_editor_plugin.py <file> --show chk1  # 显示某 RULE 的标注视图
"""

import sys
import os

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'grammar', 'gen'))

from rule_editor import RuleEditor, Element


# ============================================================
# ModSpec — 单条修改指令
# ============================================================

class ModSpec:
    """
    一条修改指令：在指定容器中查找匹配元素并替换。

    参数
    ----
    container : str         – 容器名（RULE 名 或 赋值名）
    old_text  : str         – 要匹配的原文
    new_text  : str         – 替换为
    element_type : str|None – 限制元素类型，None = 不限
    """
    def __init__(self, container: str, old_text: str, new_text: str,
                 element_type: str = None):
        self.container = container
        self.old_text = old_text
        self.new_text = new_text
        self.element_type = element_type

    def __repr__(self):
        t = f' ({self.element_type})' if self.element_type else ''
        return f'{self.container}{t}: {self.old_text!r} -> {self.new_text!r}'


# ============================================================
# RuleEditorPlugin — 插件主体
# ============================================================

class RuleEditorPlugin:
    """
    PVRS 规则文件编辑插件。

    封装标准操作流程，支持链式调用和批量修改。

    用法
    ----
        plugin = RuleEditorPlugin("file.pvrs")
        plugin.check().replace(...).save()
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._editor = RuleEditor(filepath)

    # ---- 属性 ----

    @property
    def editor(self) -> RuleEditor:
        """内部 RuleEditor 实例，可访问全部 API。"""
        return self._editor

    @property
    def has_errors(self) -> bool:
        return self._editor.has_errors

    @property
    def parse_errors(self) -> list:
        return self._editor.parse_errors

    @property
    def pending_count(self) -> int:
        return len(self._editor.pending_changes())

    # ---- 操作 ----

    def check(self) -> dict:
        """
        语法检查并返回摘要信息。

        返回
        ----
        dict – {
            'ok': bool,
            'errors': [(line, col, msg), ...],
            'container_count': int,
            'element_count': int,
            'summaries': [RuleEditor.rule_summaries(), ...]
        }
        """
        ed = self._editor
        return {
            'ok': not ed.has_errors,
            'errors': list(ed.parse_errors),
            'container_count': len(ed.rule_names()),
            'element_count': len(ed.elements),
            'summaries': ed.rule_summaries(),
        }

    def show(self, container: str) -> tuple:
        """
        返回指定容器的标注视图和编号说明表。

        返回 (annotated_text, annotated_legend)
        """
        ed = self._editor
        return (ed.annotated_text(container),
                ed.annotated_legend(container))

    def replace(self, container: str, old_text: str, new_text: str,
                element_type: str = None) -> int:
        """
        在指定容器中查找匹配元素并替换。

        参数
        ----
        container    : str       – 容器名
        old_text     : str       – 要匹配的原文
        new_text     : str       – 新文本
        element_type : str|None  – 类型过滤，None = 不限

        返回
        ----
        int – 修改的元素个数
        """
        elems = self._editor.elements_by_rule(container)
        if element_type:
            elems = [e for e in elems if e.element_type == element_type]
        matched = [e for e in elems if e.text == old_text]
        for e in matched:
            self._editor.add_change(e, new_text)
        return len(matched)

    def apply(self, specs: list) -> int:
        """
        批量应用修改指令。

        参数 specs : list[ModSpec]，返回修改总数。
        """
        total = 0
        for spec in specs:
            n = self.replace(spec.container, spec.old_text,
                             spec.new_text, spec.element_type)
            total += n
        return total

    def save(self, output_path: str = None, backup: bool = True) -> tuple:
        """
        校验并保存。

        返回
        ----
        (ok: bool, message: str) – ok=True 表示保存成功。
        失败时 message 包含错误详情，修改保留。
        """
        try:
            self._editor.save(output_path=output_path, backup=backup)
            return (True, f'Saved: {output_path or self.filepath}')
        except SyntaxError as e:
            msg = str(e)
            return (False, msg)

    def discard(self) -> None:
        """撤销所有修改。"""
        self._editor.clear_changes()


# ============================================================
# 命令行入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print('用法: python rule_editor_plugin.py <pvrs_file> [--show <容器名>]')
        print()
        print('  --show NAME   显示指定容器的标注视图')
        print('  --rule NAME   仅显示此容器的详情')
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f'错误: 文件不存在 — {filepath}')
        sys.exit(1)

    plugin = RuleEditorPlugin(filepath)

    # 语法检查 + 摘要
    info = plugin.check()
    if info['ok']:
        print('[语法] 正确')
    else:
        print(f'[语法错误] 发现 {len(info["errors"])} 个错误：')
        for line, col, msg in info['errors'][:5]:
            print(f'  [{line}:{col}] {msg}')
        if len(info['errors']) > 5:
            print(f'  ... 还有 {len(info["errors"]) - 5} 个')

    print(f'[摘要] {info["container_count"]} 个容器, '
          f'{info["element_count"]} 个元素')
    for s in info['summaries']:
        print(f'  [{s["kind"]}] {s["name"]}: '
              f'{s["count"]} elements ({", ".join(s["types"])})')

    # --show 参数：显示标注视图
    if '--show' in sys.argv:
        idx = sys.argv.index('--show')
        if idx + 1 < len(sys.argv):
            name = sys.argv[idx + 1]
            text, legend = plugin.show(name)
            print(f'\n=== {name} ===')
            print(text)
            print(legend)

    # --rule 参数：仅显示一个容器的详情
    if '--rule' in sys.argv:
        idx = sys.argv.index('--rule')
        if idx + 1 < len(sys.argv):
            name = sys.argv[idx + 1]
            elems = plugin.editor.elements_by_rule(name)
            print(f'\n=== {name} ({len(elems)} elements) ===')
            for e in elems:
                print(f'  {e}')


if __name__ == '__main__':
    main()
