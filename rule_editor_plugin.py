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
    一条修改指令。支持两种匹配模式：

    - 按文本匹配：by_text
    - 按索引匹配：by_index（对应 annotated_legend 中的 <<N>> 编号）

    用法
    ----
        ModSpec.by_text("chk1", "M1", "METAL1", element_type="layerRef")
        ModSpec.by_index("chk1", 2, "METAL1")  # 修改编号 <<2>> 的元素
    """
    def __init__(self, container: str, mode: str, match, new_text: str,
                 element_type: str = None):
        self.container = container
        self.mode = mode              # 'text' | 'index'
        self.match = match            # str (for text) | int (for index)
        self.new_text = new_text
        self.element_type = element_type

    @classmethod
    def by_text(cls, container: str, old_text: str, new_text: str,
                element_type: str = None) -> 'ModSpec':
        """按文本匹配创建修改指令。"""
        return cls(container, 'text', old_text, new_text, element_type)

    @classmethod
    def by_index(cls, container: str, index: int, new_text: str) -> 'ModSpec':
        """按 annotated_legend 中的 <<N>> 编号创建修改指令。"""
        return cls(container, 'index', index, new_text)

    def __repr__(self):
        t = f' ({self.element_type})' if self.element_type else ''
        mode = f'[#{self.match}]' if self.mode == 'index' else repr(self.match)
        return f'{self.container}{t}: {mode} -> {self.new_text!r}'


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

    def replace_by_text(self, container: str, old_text: str, new_text: str,
                         element_type: str = None) -> int:
        """
        在指定容器中查找文本匹配的元素并全部替换。

        参数
        ----
        container    : str       – 容器名
        old_text     : str       – 要匹配的原文（精确比较）
        new_text     : str       – 新文本
        element_type : str|None  – 类型过滤，None = 不限

        返回
        ----
        bool – True 表示找到并修改了元素，False 表示无匹配
        """
        elems = self._editor.elements_by_rule(container)
        if element_type:
            elems = [e for e in elems if e.element_type == element_type]
        matched = [e for e in elems if e.text == old_text]
        if not matched:
            return False
        for e in matched:
            self._editor.add_change(e, new_text)
        return True

    def replace_by_index(self, container: str, index: int,
                         new_text: str) -> bool:
        """
        按 annotated_legend 中的 <<N>> 编号修改单个元素。

        参数
        ----
        container : str  – 容器名
        index     : int  – 编号（1 起始，对应标注视图中的 <<N>>）
        new_text  : str  – 新文本

        返回
        ----
        bool – True 表示修改成功，False 表示索引越界
        """
        elems = self._editor.elements_by_rule(container)
        if index < 1 or index > len(elems):
            return False
        self._editor.add_change(elems[index - 1], new_text)
        return True

    def apply(self, specs: list) -> int:
        """
        批量应用修改指令。自动根据 ModSpec.mode 选择匹配方式。

        参数 specs : list[ModSpec]，返回修改总数。
        """
        total = 0
        for spec in specs:
            if spec.mode == 'index':
                if self.replace_by_index(spec.container, spec.match,
                                         spec.new_text):
                    total += 1
            else:
                if self.replace_by_text(spec.container, spec.match,
                                        spec.new_text, spec.element_type):
                    total += 1
        return total

    def save(self, output_path: str = None, backup: bool = True) -> dict:
        """
        校验并保存。先调用 editor.validate() 检查语法，
        通过后写入磁盘，失败则保留修改。

        返回 dict – 与 check() 相同的结构：
            {'ok': bool, 'errors': [(line, col, msg), ...]}
            ok=False 时 errors 为校验失败详情，修改仍保留。
        """
        ed = self._editor
        # 先校验
        errors = ed.validate()
        if errors:
            return {'ok': False, 'errors': errors}

        # 通过，写入
        try:
            ed.save(output_path=output_path, backup=backup)
            return {'ok': True, 'errors': []}
        except SyntaxError as e:
            # save 内置校验也失败（正常不会走到这里，validate 已拦下）
            return {'ok': False, 'errors': list(ed.parse_errors)}

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

    # --sample 参数：在所有容器上运行修改示例
    if '--sample' in sys.argv:
        print('\n========== 修改示例 ==========\n')

        # 拿到第一个容器名
        containers = plugin.editor.rule_names()
        if not containers:
            print('没有可演示的容器。')
            sys.exit(0)
        c = containers[0]

        # 示例 1：按文本批量替换
        print(f'[示例1] replace_by_text("{c}", ...) ')
        ok = plugin.replace_by_text(c, 'M1', 'METAL1')
        print(f'  结果: {ok}  (True=成功)')
        if ok:
            _, legend = plugin.show(c)
            print(legend)

        # 示例 2：按文本 + 类型过滤
        print(f'\n[示例2] replace_by_text("{c}", "< 0.5", "< 1.0", element_type="constraint")')
        ok = plugin.replace_by_text(c, '< 0.5', '< 1.0', element_type='constraint')
        print(f'  结果: {ok}')

        # 示例 3：按索引修改
        print(f'\n[示例3] replace_by_index("{c}", 2, "M99")')
        ok = plugin.replace_by_index(c, 2, 'M99')
        print(f'  结果: {ok}')

        # 示例 4：apply 批量
        print(f'\n[示例4] apply([ModSpec.by_text(...), ModSpec.by_index(...)])')
        n = plugin.apply([
            ModSpec.by_text(c, 'L1', '1'),
            ModSpec.by_index(c, 3, '1'),
        ])
        print(f'  结果: {n} 个修改')

        # 展示最终修改后的视图
        print(f'\n[结果] 共 {plugin.pending_count} 项暂存修改：')
        text, legend = plugin.show(c)
        print(text)

        # 保存
        result = plugin.save(backup=False)
        if result['ok']:
            print(f'\n[保存] 成功')
        else:
            print(f'\n[保存] 失败 — {len(result["errors"])} 个语法错误')
            for line, col, msg in result['errors'][:3]:
                print(f'  [{line}:{col}] {msg}')

        plugin.discard()

if __name__ == '__main__':
    main()
