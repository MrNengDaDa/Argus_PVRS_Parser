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
        print('文件中未找到 RULE 块。')
        return None

    print(f'找到 {len(summaries)} 个 RULE 块：')
    _divider()
    for i, s in enumerate(summaries):
        types_str = ', '.join(s['types'])
        print(f'  [{i+1}] RULE {s["name"]}  '
              f'(第 {s["line"]} 行, {s["count"]} 个元素: {types_str})')
    _divider()

    idx, chosen = _select_from_list(
        summaries,
        key_fn=lambda s: s['name'].strip('"'),
        prompt='选择 RULE',
    )
    if idx < 0:
        return None

    # 输出标注后的 RULE 文本 + 编号说明表
    rule_name = chosen['name']
    count = chosen['count']
    print(f'\n  RULE {rule_name} 原文标注 (共 {count} 个可修改元素):')
    _divider()
    print(editor.annotated_text(rule_name))
    _divider()
    print(editor.annotated_legend(rule_name))
    _divider()
    return rule_name


def modify_element(editor, elems):
    """
    交互式修改循环。

    用户输入标注文本中的 [N] 编号 → 显示当前值和类型 →
    输入新文本 → 通过 editor.add_change() 暂存修改。
    输入 0 或 Ctrl+C 返回上级菜单。
    """
    if not elems:
        print('该 RULE 中没有可修改元素。')
        return

    while True:
        sel_idx, elem = _select_from_list(
            elems,
            key_fn=lambda e: e.text,
            prompt='修改元素 (输入标注 [N])',
        )
        if sel_idx < 0:
            break

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
        # 立即刷新标注视图，显示修改后的状态
        print(f'  [已暂存] {elem.text!r} → {new_text!r}')
        print()
        print(editor.annotated_text(elem.rule_name))
        _divider()
        print(editor.annotated_legend(elem.rule_name))
        _divider()


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

        # 标注视图已展示编号和类型，直接进入修改循环
        elems = editor.elements_by_rule(rule_name)
        modify_element(editor, elems)

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
