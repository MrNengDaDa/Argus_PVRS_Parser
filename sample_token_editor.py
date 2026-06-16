#!/usr/bin/env python3
"""
full_token_editor 使用样例。

演示 TokenEditor 的完整工作流：
    打开 → 检查语法 → 查看容器 → 标注视图 → 修改 → 保存

用法
----
    python sample_token_editor.py <pvrs_file>

    无参数时使用内置的示例文件。
"""

import sys
from pathlib import Path

from full_token_editor import TokenEditor


# ============================================================
# 内置示例文件（当未提供命令行参数时使用）
# ============================================================

SAMPLE_CONTENT = """
layer( M1   1 )
layer( M2   2 )
layer( GATE 3 )

// 非 RULE 内的赋值语句
P1 = geom_and( M1 GATE )

RULE check_m1_width {
   L1 = width ( M1 < 0.5 adjacent < 90 point_touch region )
   L2 = width ( M1 < 0.5 opposite angled_edge == 2 parallel_only region )
   geom_or ( L1 L2 )
}

RULE check_m2 {
   L1 = width ( M2 < 0.6 adjacent < 90 point_touch region )
   geom_flatten( L1 )
}
"""


def demo(filepath: str):
    """演示 TokenEditor 的完整工作流。"""

    # ================================================================
    # 1. 打开文件
    # ================================================================
    print("=" * 60)
    print("1. 打开文件")
    print("=" * 60)
    te = TokenEditor(filepath)
    print(f"   文件: {filepath}")

    # ================================================================
    # 2. 语法检查
    # ================================================================
    print(f"\n{'=' * 60}")
    print("2. 语法检查")
    print("=" * 60)
    info = te.check()
    if info['ok']:
        print("   语法: 正确")
    else:
        print(f"   语法: {len(info['errors'])} 个错误")
        for line, col, msg in info['errors'][:5]:
            print(f"     [{line}:{col}] {msg}")
    print(f"   容器数: {info['container_count']}")
    print(f"   元素数: {info['token_count']}")

    # ================================================================
    # 3. 列出所有容器及其元素概况
    # ================================================================
    print(f"\n{'=' * 60}")
    print("3. 容器列表")
    print("=" * 60)
    for c in te.containers():
        print(f"   [{c['kind']}] {c['name']}  (第 {c['line']} 行, "
              f"{c['count']} 个元素)")
        print(f"        类型: {', '.join(c['types'][:6])}")

    # ================================================================
    # 4. 标注视图 — 查看所有可修改元素的位置
    # ================================================================
    print(f"\n{'=' * 60}")
    print("4. 标注视图（第一个 RULE 容器）")
    print("=" * 60)

    # 找第一个 RULE 容器
    rule_name = None
    for c in te.containers():
        if c['kind'] == 'RULE':
            rule_name = c['name']
            break

    if rule_name:
        print(f"\n   容器: {rule_name}\n")
        print(te.annotated_text(rule_name))
        print(f"\n{te.annotated_legend(rule_name)}")

    # ================================================================
    # 5. 修改元素
    # ================================================================
    print(f"\n{'=' * 60}")
    print("5. 修改元素")
    print("=" * 60)

    if rule_name:
        # 5a. 按文本批量替换
        print(f"\n   [a] replace_by_text — 将所有 M1 → METAL1")
        ok = te.replace_by_text(rule_name, "M1", "METAL1")
        print(f"       结果: {'成功' if ok else '无匹配'}")

        # 5b. 按编号精确修改
        print(f"\n   [b] replace_by_index — 第 4 个元素改为 '< 1.0'")
        ok = te.replace_by_index(rule_name, 4, "< 1.0")
        print(f"       结果: {'成功' if ok else '越界'}")

    # 对 DEF 容器也做修改
    def_name = None
    for c in te.containers():
        if c['kind'] == 'DEF':
            def_name = c['name']
            break

    if def_name:
        print(f"\n   [c] 对 DEF 容器 '{def_name}' 中的 GATE → GATE_NEW")
        ok = te.replace_by_text(def_name, "GATE", "GATE_NEW")
        print(f"       结果: {'成功' if ok else '无匹配'}")

    # ================================================================
    # 6. 查看修改后的标注视图
    # ================================================================
    print(f"\n{'=' * 60}")
    print("6. 修改后的标注视图")
    print("=" * 60)

    if rule_name:
        print(f"\n   (已修改的元素显示新值)\n")
        print(te.annotated_text(rule_name))
        print(f"\n{te.annotated_legend(rule_name)}")

    # 显示待保存的修改
    pending = te.pending_tokens()
    print(f"\n   暂存修改: {len(pending)} 项")
    for t in pending:
        print(f"     <<{t.index}>> [{t.type_name}] {t.text!r} → {t.new_text!r}")

    # ================================================================
    # 7. 保存
    # ================================================================
    print(f"\n{'=' * 60}")
    print("7. 保存")
    print("=" * 60)

    result = te.save(backup=False)
    if result['ok']:
        print(f"   已保存: {filepath}")
    else:
        print(f"   保存失败 — {len(result['errors'])} 个语法错误:")
        for line, col, msg in result['errors'][:5]:
            print(f"     [{line}:{col}] {msg}")
        print(f"\n   修改已保留，修正后重新 save() 即可")

    # 撤销修改（演示用，实际使用中通常不撤销）
    te.clear_changes()
    print(f"\n   已撤销修改（恢复原文件）")


# ============================================================
# 入口
# ============================================================

def main():
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if not Path(filepath).exists():
            print(f"错误: 文件不存在 — {filepath}")
            sys.exit(1)
    else:
        # 无参数时，用内置示例
        filepath = "C:/tmp/_sample_token_editor.pvrs"
        with open(filepath, 'w') as f:
            f.write(SAMPLE_CONTENT.strip())
        print(f"[使用内置示例] {filepath}\n")

    demo(filepath)


if __name__ == '__main__':
    main()
