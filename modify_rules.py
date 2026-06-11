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
    3. 选择 RULE → 按类型分组展示可修改元素
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
from rule_editor import RuleEditor, Element, get_element_types, iter_elements_by_rule


# ============================================================
# 界面辅助函数
# ============================================================

def _divider(char='-', width=50):
    """打印一行视觉分隔线。"""
    print(char * width)


def _select_from_list(items, prompt='Select'):
    """
    让用户从编号列表中选择一项。

    参数
    ----
    items  : list – 待选列表
    prompt : str  – 提示文字

    返回
    ----
    int – 选中的索引（从 0 开始），-1 表示用户输入 0（返回）或 Ctrl+C
    """
    while True:
        try:
            raw = input(f'{prompt} (0=返回): ').strip()
            if not raw:
                continue
            idx = int(raw) - 1            # 用户看到的是 1 起始编号
            if idx == -1:
                return -1                 # 用户输入了 0
            if 0 <= idx < len(items):
                return idx
            print(f'  超出范围 (1-{len(items)})')
        except ValueError:
            print('  请输入数字')
        except (EOFError, KeyboardInterrupt):
            return -1


# ============================================================
# 交互流程各步骤
# ============================================================

def show_rules(editor):
    """
    展示所有 RULE 块列表，让用户选择一个。

    返回
    ----
    str – 选中的 RULE 名称，None 表示返回/退出
    """
    summaries = editor.rule_summaries()
    if not summaries:
        print('文件中未找到 RULE 块。')
        return None

    print(f'找到 {len(summaries)} 个 RULE 块：')
    _divider()
    for i, s in enumerate(summaries):
        types_str = ', '.join(s['types'])
        print(f'  [{i+1}] RULE {s["name"]}  '
              f'(第 {s["line"]} 行, {s["count"]} 个元素: {types_str})')
    _divider()

    idx = _select_from_list(summaries, '选择 RULE')
    if idx < 0:
        return None
    return summaries[idx]['name']


def show_elements(editor, rule_name):
    """
    展示某个 RULE 内的所有可修改元素，按类型分组。

    每个元素分配一个全局编号，方便用户在 modify_element() 中
    按编号选择，无需关心类型。

    返回
    ----
    (grouped, flat) – grouped 是 {type: [Element]} 字典，
    flat 是 [(header_str, None) | (Element, num)] 混合列表
    """
    grouped = iter_elements_by_rule(editor.elements, rule_name)
    if not grouped:
        print(f'RULE {rule_name} 中没有可修改元素。')
        return None, []

    # 构建混合展示列表：类型标题行 + 元素行
    flat: list = []
    total = 0
    for etype in sorted(grouped.keys()):
        elems = grouped[etype]
        flat.append((f'--- {etype}（{len(elems)} 个）---', None))
        for e in elems:
            total += 1
            flat.append((e, total))

    # 渲染输出：标题前加空行，元素前显示编号和修改标记
    for item, idx_or_none in flat:
        if idx_or_none is None:
            print(f'\n{item}')
        else:
            elem, num = item, idx_or_none
            marker = ' [已修改]' if elem.modified else ''
            print(f'  [{num}] {elem.text!r}{marker}  (第 {elem.line} 行)')
    _divider()

    return grouped, flat


def modify_element(editor, grouped, flat):
    """
    交互式修改循环。

    用户输入元素编号 → 显示当前值和类型 → 输入新文本 →
    通过 editor.add_change() 暂存修改（不立即写入磁盘）。
    输入 0 或 Ctrl+C 返回上级菜单。
    """
    while True:
        # 从 flat 中提取纯元素列表（去掉标题行）
        elems_only = [(e, n) for e, n in flat if n is not None]
        idx = _select_from_list(elems_only, '修改元素')
        if idx < 0:
            break

        elem, _ = elems_only[idx]
        print(f'  类型: {elem.element_type}')
        print(f'  当前值: {elem.text!r}')

        try:
            new_text = input('  新值: ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not new_text or new_text == elem.text:
            print('  (无变化)')
            continue

        editor.add_change(elem, new_text)
        print(f'  [已暂存] {elem.text!r} → {new_text!r}')


def confirm_save(editor):
    """
    显示所有暂存修改的摘要，询问用户是否确认保存。

    返回
    ----
    bool – True 表示用户确认写入
    """
    pending = editor.pending_changes()
    if not pending:
        print('没有需要保存的修改。')
        return False

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
        return False

    return ans in ('y', 'yes')


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
    # ---- 参数检查 ----
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

    # ---- 第二步：交互主循环 ----
    while True:
        rule_name = show_rules(editor)
        if rule_name is None:
            print('退出。')
            break

        print(f'\n===== RULE {rule_name} =====')
        grouped, flat = show_elements(editor, rule_name)
        if grouped is None:
            continue

        modify_element(editor, grouped, flat)

        # 询问是否继续修改其他 RULE
        try:
            ans = input('\n是否继续修改其他 RULE? (y/n): ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if ans not in ('y', 'yes'):
            break

    # ---- 第三步：确认并保存 ----
    if confirm_save(editor):
        editor.save()
        print(f'已保存: {filepath}')
        print(f'备份: {filepath}.bak')
    else:
        print('修改已丢弃。')


if __name__ == '__main__':
    main()
