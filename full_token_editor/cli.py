"""命令行入口 — python -m full_token_editor <file> [选项]"""

import sys, os
from .core import TokenEditor
from .plugin import TokenEditorPlugin


def main():
    if len(sys.argv) < 2:
        print('用法: python -m full_token_editor <pvrs_file> [选项]')
        print()
        print('  --show NAME    显示指定容器的标注视图')
        print('  --sample       在所有容器上运行修改示例')
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f'错误: 文件不存在 — {filepath}')
        sys.exit(1)

    te = TokenEditor(filepath)
    info = te.check()

    if info['ok']:
        print('[语法] 正确')
    else:
        print(f'[语法错误] {len(info["errors"])} 个错误')
        for line, col, msg in info['errors'][:5]:
            print(f'  [{line}:{col}] {msg}')

    print(f'[摘要] {info["container_count"]} 个容器, '
          f'{info["token_count"]} 个 token')
    for c in info['containers']:
        print(f'  [{c["kind"]}] {c["name"]}: '
              f'{c["count"]} tokens ({", ".join(c["types"][:5])}...)')

    if '--show' in sys.argv:
        idx = sys.argv.index('--show')
        if idx + 1 < len(sys.argv):
            name = sys.argv[idx + 1]
            print(f'\n========== {name} ==========')
            print(te.annotated_text(name)[0])
            print(te.annotated_legend(name))

    if '--sample' in sys.argv:
        names = te.container_names
        if not names:
            print('没有可演示的容器。')
            sys.exit(0)
        c = names[0]

        print(f'\n========== 修改示例（容器: {c}）==========\n')

        plugin = TokenEditorPlugin(filepath)
        print('[示例1] replace_by_text — 批量替换文本')
        print(f'  结果: {plugin.replace_by_text(c, "M1", "METAL1")}')
        print(f'\n[示例2] replace_by_index — 按编号替换')
        print(f'  结果: {plugin.replace_by_index(c, 3, "M99")}')
        print(f'\n[示例3] 标注视图:')
        text, _, legend = plugin.show(c)
        print(text)
        print(legend)
        result = plugin.save(backup=False)
        status = "成功" if result["ok"] else f"失败 — {result['errors']}"
        print(f'\n[保存] {status}')
        plugin.discard()


if __name__ == '__main__':
    main()
