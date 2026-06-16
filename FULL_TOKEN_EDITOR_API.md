# full_token_editor.py — TokenEditorPlugin API 参考

基于 ANTLR Token 流的 PVRS RULE / derived_layer_def 内 op_statement 子节点编辑器。

---

## 1. `TokenEditorPlugin(filepath)`

### 功能

解析 PVRS 规则文件，收集所有 RULE 块和 `derived_layer_def` 容器内的
op_statement 子节点元素。每个元素对应一个语法节点（操作名、括号、
层引用、约束、option 组等），可作为独立单元修改。

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| `filepath` | `str` | PVRS 规则文件路径 |

### 输出

`TokenEditorPlugin` 实例，内部持有 `TokenEditor` 对象。

### 使用样例

```python
from full_token_editor import TokenEditorPlugin

plugin = TokenEditorPlugin("rules.pvrs")

# 访问内部 TokenEditor 的完整 API
te = plugin.editor
print(te.container_names)    # 所有容器名
print(len(te.all_tokens()))  # 所有元素数
```

---

## 2. `check()`

### 功能

语法检查并返回摘要信息。解析原始文件（非修改后文本），报告语法错误、
容器总数、元素总数、每个容器的元素概况。

### 输入

无

### 输出

```python
{
    'ok': bool,              # True = 语法正确，False = 有语法错误
    'errors': [(line, col, msg), ...],  # 语法错误列表
    'container_count': int,  # 容器总数（RULE + DEF）
    'token_count': int,      # 元素总数
    'containers': [          # 每个容器的摘要
        {
            'name': str,     # 容器名
            'kind': str,     # 'RULE' | 'DEF'
            'line': int,     # 起始行号
            'count': int,    # 容器内元素数
            'types': [str],  # 元素类型名列表
        },
        ...
    ]
}
```

### 使用样例

```python
info = plugin.check()

if info['ok']:
    print("语法正确")
else:
    for line, col, msg in info['errors']:
        print(f"[{line}:{col}] {msg}")

for c in info['containers']:
    print(f"{c['kind']} {c['name']}: {c['count']} 个元素")
```

---

## 3. `show(container)`

### 功能

返回指定容器的标注视图和编号说明表。标注文本中用 `<<N:value>>`
包裹每个可修改元素，N 为 1 起始的容器内编号。说明表中列出每个元素的
类型、当前值、行号、修改标记。

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| `container` | `str` | 容器名（RULE 名或赋值语句左侧变量名） |

### 输出

```python
(
    annotated_text,    # str — 带 <<N:value>> 标注的容器原文
    annotated_legend,  # str — 编号说明表
)
```

**annotated_text 示例**:
```
RULE chk1 {
   <<1:L1>> = <<2:width>> <<3:(>> <<4:M1>> <<5:< 0.5>> <<6:adjacent < 90>> ...
}
```

**annotated_legend 示例**:
```
--- Token 编号说明（22 个）---
  <<1>> layerRef    'L1'  (第 2 行)
  <<2>> WIDTH       'width'  (第 2 行)
  <<3>> LPAREN      '('  (第 2 行)
  <<4>> Op_layer    'M1'  (第 2 行)
  <<5>> Constraint  '< 0.5'  (第 2 行)
  <<6>> IntOption   'adjacent < 90'  (第 2 行)
  ...
```

### 使用样例

```python
text, legend = plugin.show("check_m1_width")
print(text)     # 标注视图 — 看每个元素在原文中的位置
print(legend)   # 编号说明 — 看每个 <<N>> 的类型和当前值
```

---

## 4. `replace_by_text(container, old_text, new_text)`

### 功能

在指定容器中查找所有文本匹配的元素，全部替换为 `new_text`。
匹配为精确字符串比较（含空格和标点）。返回是否实际修改。

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| `container` | `str` | 容器名 |
| `old_text` | `str` | 要匹配的原始文本（精确匹配） |
| `new_text` | `str` | 替换为目标文本 |

### 输出

`bool` — `True` 表示找到并修改了匹配元素，`False` 表示无匹配。

**注意**: 如果容器内有多个相同文本的元素，全部都会被替换。
只替换第一个匹配的元素请用 `replace_by_index()`。

### 使用样例

```python
# 将 chk1 中所有 "M1" 替换为 "METAL1"
ok = plugin.replace_by_text("chk1", "M1", "METAL1")
print(ok)  # True（修改了 2 处 op_layer 中的 M1）

# 将约束 "< 0.5" 替换为 "< 1.0"
ok = plugin.replace_by_text("chk1", "< 0.5", "< 1.0")
print(ok)  # True（修改了 2 处 Constraint 元素）

# 替换不存在的值
ok = plugin.replace_by_text("chk1", "NOT_EXISTS", "X")
print(ok)  # False（无匹配，不修改任何元素）
```

---

## 5. `replace_by_index(container, index, new_text)`

### 功能

按标注视图中的 `<<N>>` 编号精确修改**单个**元素。编号对应 `show()` 方法
中标注文本和编号说明表的 `<<N>>`。

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| `container` | `str` | 容器名 |
| `index` | `int` | 元素编号（1 起始，对应标注视图中的 `<<N>>`） |
| `new_text` | `str` | 替换为目标文本 |

### 输出

`bool` — `True` 表示修改成功，`False` 表示索引越界。

### 使用样例

```python
# 先用 show() 确认目标元素的编号
text, legend = plugin.show("chk1")
print(legend)
# <<1>> layerRef    'L1'   (第 2 行)
# <<2>> WIDTH       'width' (第 2 行)
# <<3>> LPAREN      '('    (第 2 行)
# <<4>> Op_layer    'M1'   (第 2 行)  ← 要修改这个
# ...

# 按编号修改
ok = plugin.replace_by_index("chk1", 4, "MET1")
print(ok)  # True

# 越界索引
ok = plugin.replace_by_index("chk1", 999, "X")
print(ok)  # False

# 验证修改后的标注视图
text, legend = plugin.show("chk1")
print(text)
# <<4:MET1>>  ← 已更新
```

---

## 6. `save(output_path=None, backup=True)`

### 功能

校验并保存修改后的文本。

1. 生成修改后的完整文本（内部从右往左应用替换）
2. 对修改后的文本执行 ANTLR 语法解析
3. 语法正确 → 写入磁盘；有错误 → 拒绝保存，保留所有修改
4. 覆盖原文件时创建时间戳备份（`<file>.<YYYYMMDD_HHMMSS>.bak`）

### 输入

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `output_path` | `str \| None` | `None` | 输出路径，`None` 或空 = 覆盖原文件 |
| `backup` | `bool` | `True` | 覆盖原文件时是否创建时间戳 `.bak` 备份 |

### 输出

```python
{
    'ok': bool,              # True = 保存成功，False = 校验失败
    'errors': [(line, col, msg), ...],  # 失败时的语法错误列表
}
```

**重要**: `ok=False` 时所有暂存修改仍然保留，修正后可重新调用 `save()`。

### 使用样例

```python
# 正常保存（覆盖原文件 + 时间戳备份）
result = plugin.save()
if result['ok']:
    print("保存成功")
else:
    for line, col, msg in result['errors']:
        print(f"[{line}:{col}] {msg}")
    # 修改保留，返回 editor 修正后重新 save()

# 保存到新文件（不创建备份）
plugin.save(output_path="output.pvrs", backup=False)
```

---

## 7. `discard()`

### 功能

撤销所有暂存的修改，恢复为原始文件状态。

### 输入

无

### 输出

`None`

### 使用样例

```python
plugin.replace_by_text("chk1", "M1", "METAL1")
print(plugin.pending_count)  # 1

plugin.discard()
print(plugin.pending_count)  # 0 — 全部撤销
```

---

## 完整流程示例

```python
from full_token_editor import TokenEditorPlugin

# 1. 打开文件
plugin = TokenEditorPlugin("rules.pvrs")

# 2. 检查语法 + 查看摘要
info = plugin.check()
print(f"{info['container_count']} 个容器, {info['token_count']} 个元素")

# 3. 查看标注视图
text, legend = plugin.show("check_m1_width")
print(text)
print(legend)

# 4. 修改元素
plugin.replace_by_text("check_m1_width", "M1", "METAL1")        # 批量文本匹配
plugin.replace_by_index("check_m1_width", 6, "adjacent > 45")   # 按编号精确修改

# 5. 再次查看确认修改
text, legend = plugin.show("check_m1_width")
print(text)

# 6. 保存（自动校验语法）
result = plugin.save()
if result['ok']:
    print("已保存")
else:
    print("校验失败，请修正后重试")

# 7. 放弃修改（需要时）
# plugin.discard()
```
