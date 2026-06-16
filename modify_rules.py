#!/usr/bin/env python3
"""
交互式 PVRS RULE 块元素修改工具。

快速上手
--------
    python modify_rules.py <pvrs_file>

操作流程
--------
    1. 使用 ANTLR4 解析 PVRS 文件，如有语法错误立即报告
    2. 列出所有 RULE 块及其可修改元素概况
    3. 选择 RULE（按序号或直接输入名称）→ 显示该 RULE 完整文本
       → 按类型分组展示可修改元素
    4. 选择元素 → 输入新文本值
    5. 可继续修改其他元素，最终确认保存

保存前自动创建原文件的 .bak 备份。

依赖
----
    rule_editor.py          – RuleEditor 类（解析、查询、修改、保存）
    grammar/gen/*           – ANTLR4 生成的解析器
"""

import sys
import os
import glob
from rule_editor import RuleEditor, Element, get_element_types


# ============================================================
# 界面辅助函数
# ============================================================

def _divider(char='-', width=50):
    """打印一行视觉分隔线。"""
    print(char * width)


def _select_from_list(items, key_fn, prompt='选择'):
    """
    让用户从列表中按序号或名称选择一项。

    支持两种输入方式：
        - 数字：按序号选择（1 起始）
        - 字符串：按 key_fn(item) 精确匹配名称

    返回 (index, item) 元组，(-1, None) 表示返回/退出。
    """
    while True:
        try:
            raw = input(f'{prompt} (序号/名称, 0=返回): ').strip()
            if not raw:
                continue
            # 尝试按数字解析
            try:
                idx = int(raw) - 1
            except ValueError:
                idx = None

            if idx is not None:
                if idx == -1:
                    return -1, None
                if 0 <= idx < len(items):
                    return idx, items[idx]
                print(f'  超出范围 (1-{len(items)})')
            else:
                # 按名称匹配
                name = raw.strip('"')
                for i, item in enumerate(items):
                    if key_fn(item) == name:
                        return i, item
                print(f'  未找到名称: {raw!r}')
        except (EOFError, KeyboardInterrupt):
            return -1, None


# ============================================================
# 交互流程各步骤
# ============================================================

def show_rules(editor):
    """
    展示所有 RULE 块列表，用户可按序号或名称选择。
    选中后输出该 RULE 的完整原文。

    返回
    ----
    str – 选中的 RULE 名称，None 表示返回/退出
    """
    summaries = editor.rule_summaries()
    if not summaries:
        print('文件中未找到可修改容器（RULE / 赋值）。')
        return None

    rule_items = [s for s in summaries if s['kind'] == 'RULE']
    def_items  = [s for s in summaries if s['kind'] == 'DEF']

    print(f'找到 {len(rule_items)} 个 RULE, {len(def_items)} 个赋值语句：')
    _divider()
    for i, s in enumerate(summaries):
        prefix = 'RULE' if s['kind'] == 'RULE' else '  DEF'
        types_str = ', '.join(s['types'])
        print(f'  [{i+1}] {prefix} {s["name"]}  '
              f'(第 {s["line"]} 行, {s["count"]} 个元素: {types_str})')
    _divider()

    idx, chosen = _select_from_list(
        summaries,
        key_fn=lambda s: s['name'].strip('"'),
        prompt='选择容器',
    )
    if idx < 0:
        return None

    # 输出标注后的原文 + 编号说明表
    container_name = chosen['name']
    count = chosen['count']
    kind_label = 'RULE' if chosen['kind'] == 'RULE' else '赋值语句'
    print(f'\n  {kind_label} {container_name} 原文标注 (共 {count} 个可修改元素):')
    _divider()
    print(editor.annotated_text(container_name))
    _divider()
    print(editor.annotated_legend(container_name))
    _divider()
    return container_name


def modify_element(editor, elems):
    """
    交互式修改循环。支持两种模式：

    - 输入编号（如 2）→ 修改单个元素
    - 输入名称/文本（如 M1）→ 修改当前 RULE 内所有文本匹配的元素

    输入 0 或 Ctrl+C 返回上级菜单。
    """
    if not elems:
        print('该 RULE 中没有可修改元素。')
        return

    while True:
        try:
            raw = input('修改元素 (输入标注 <<N>> 或名称): ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        # ---- 模式 1: 数字 → 按编号选择单个元素 ----
        try:
            idx = int(raw) - 1
            if idx == -1:                      # 用户输入 0
                break
            if 0 <= idx < len(elems):
                _modify_single(editor, elems[idx])
                continue
            print(f'  超出范围 (1-{len(elems)})')
            continue
        except ValueError:
            pass                              # 非数字，走名称匹配

        # ---- 模式 2: 字符串 → 匹配所有同名元素 ----
        _modify_by_name(editor, elems, raw)


def _modify_single(editor, elem):
    """修改单个元素。"""
    print(f'  类型: {elem.element_type}')
    print(f'  当前值: {elem.text!r}')

    try:
        new_text = input('  新值: ').strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if not new_text or new_text == elem.text:
        print('  (无变化)')
        return

    editor.add_change(elem, new_text)
    _show_current_state(editor, elem)


def _modify_by_name(editor, elems, name):
    """修改当前 RULE 内所有文本匹配的元素。"""
    name = name.strip('"')
    matched = [e for e in elems if e.text == name]

    if not matched:
        print(f'  未找到文本为 {name!r} 的元素')
        return

    print(f'  找到 {len(matched)} 个匹配元素:')
    for i, e in enumerate(matched):
        print(f'    <<{elems.index(e) + 1}>> {e.element_type}  (第 {e.line} 行)')
    print(f'  当前值: {name!r}')

    try:
        new_text = input('  新值: ').strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if not new_text or new_text == name:
        print('  (无变化)')
        return

    for e in matched:
        editor.add_change(e, new_text)
    print(f'  [已暂存] {name!r} → {new_text!r}  ({len(matched)} 处)')
    # 用第一个元素的 rule_name 刷新视图
    _show_current_state(editor, matched[0])


def _show_current_state(editor, elem):
    """刷新当前 RULE 的标注视图和编号说明表。"""
    rule = elem.rule_name
    print()
    print(editor.annotated_text(rule))
    _divider()
    print(editor.annotated_legend(rule))
    _divider()


def confirm_save(editor, default_path):
    """
    显示所有暂存修改的摘要，询问用户是否确认保存及输出路径。

    返回
    ----
    str – 输出路径（空字符串 = 覆盖原文件），None = 放弃
    """
    pending = editor.pending_changes()
    if not pending:
        print('没有需要保存的修改。')
        return None

    print(f'\n共 {len(pending)} 项修改待保存：')
    _divider()
    for e in pending:
        print(f'  RULE {e.rule_name} / {e.element_type}: '
              f'{e.text!r} → {e.new_text!r}')
    _divider()

    try:
        ans = input('确认保存到文件? (y/n): ').strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if ans not in ('y', 'yes'):
        return None

    # 询问输出文件名，留空 = 覆盖原文件
    msg = f'输出文件 (回车覆盖原文: {default_path}): '
    try:
        output = input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    return output if output else default_path


# ============================================================
# 主入口
# ============================================================

def main():
    """
    CLI 主函数。

    流程：
        1. 解析输入文件（RuleEditor）
        2. 有语法错误则警告，询问是否继续
        3. 主循环：选 RULE → 浏览元素 → 修改 → 继续或结束
        4. 退出时确认保存（自动创建 .bak 备份）
    """
    if len(sys.argv) < 2:
        print(f'用法: python {sys.argv[0]} <pvrs_file>')
        print()
        print('交互式 PVRS RULE 块元素修改工具。')
        print('可修改元素类型: layerRef（层引用）、constraint（约束）、expr（表达式）。')
        print('保存前自动创建 .bak 备份。')
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f'错误: 文件不存在 — {filepath}')
        sys.exit(1)

    # ---- 第一步：解析文件 ----
    print(f'正在解析: {filepath}')
    try:
        editor = RuleEditor(filepath)
    except Exception as e:
        print(f'解析失败: {e}')
        sys.exit(1)

    # ---- 第一步（续）：语法错误检查 ----
    if editor.has_errors:
        print(f'\n  警告: 发现 {len(editor.parse_errors)} 个语法错误！')
        print(f'  存在错误时元素定位可能不准确，建议先修复语法错误再编辑。')
        for i, (line, col, msg) in enumerate(editor.parse_errors[:5]):
            print(f'    [{i+1}] 第 {line} 行 第 {col} 列 → {msg}')
        if len(editor.parse_errors) > 5:
            print(f'    ... 还有 {len(editor.parse_errors)-5} 个错误')
        print()
        ans = input('  是否继续? (y/n): ').strip().lower()
        if ans not in ('y', 'yes'):
            sys.exit(0)

    print(f'  共 {len(editor.rule_names())} 个 RULE，'
          f'{len(editor.elements)} 个元素。')
    print(f'  可修改类型: '
          f'{", ".join(t["label"] for t in get_element_types())}')
    print()

    # ---- 第二步 + 第三步：修改 + 校验保存 ----
    retry_from_error = False
    while True:
        if not retry_from_error:
            rule_name = show_rules(editor)
            if rule_name is None:
                print('退出。')
                break

            elems = editor.elements_by_rule(rule_name)
            modify_element(editor, elems)

            try:
                ans = input('\n是否继续修改其他 RULE? (y/n): ').strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if ans in ('y', 'yes'):
                retry_from_error = False
                continue
        else:
            # 校验失败后返回修改：直接进入 RULE 选择
            retry_from_error = False

        # ---- 确认并保存 ----
        output_path = confirm_save(editor, filepath)
        if output_path is None:
            print('修改已丢弃。')
            break

        try:
            editor.save(output_path=output_path if output_path != filepath else None)
            print(f'已保存: {output_path or filepath}')
            if output_path == filepath or not output_path:
                backups = sorted(glob.glob(f'{filepath}.*.bak'))
                if backups:
                    print(f'备份: {backups[-1]}')
            break
        except SyntaxError as e:
            print(f'\n  {e}')
            ans = input('\n  返回修改? (y/n): ').strip().lower()
            if ans not in ('y', 'yes'):
                print('修改已丢弃。')
                break
            retry_from_error = True


if __name__ == '__main__':
    main()
