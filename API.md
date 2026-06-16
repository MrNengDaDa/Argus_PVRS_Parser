# RuleEditor API 参考

`rule_editor.py` — 基于 ANTLR4 解析树的 PVRS RULE 块元素编辑器。

---

## 数据结构

### Element

单个可修改元素，对应 ANTLR 解析树中的一个语法节点。

| 属性 | 类型 | 说明 |
|------|------|------|
| `element_type` | `str` | 元素类型，如 `"layerRef"`、`"constraint"`、`"expr"` |
| `rule_name` | `str` | 所属容器名（RULE 名或赋值语句左侧名） |
| `text` | `str` | 原文文本 |
| `line` | `int` | 源文件行号（1 起始） |
| `char_start` | `int` | 在 LF 归一化源文本中的起始偏移（含） |
| `char_stop` | `int` | 结束偏移（含） |
| `context_type` | `str` | ANTLR 上下文类名（调试用） |
| `new_text` | `str \| None` | 暂存的替换文本，未修改时返回 `None` |
| `modified` | `bool` | 是否已暂存修改 |

---

## RuleEditor

### 构造

```python
editor = RuleEditor(filepath)
```

**参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `filepath` | `str` | PVRS 规则文件路径 |

自动完成：读取文件 → 归一化换行符 → ANTLR 解析 → 遍历收集元素。

---

### 属性（只读）

#### `parse_errors`

```python
editor.parse_errors  # [(line, col, msg), ...]
```

语法错误列表。每项为 `(行号, 列号, 错误描述)` 元组。

#### `has_errors`

```python
editor.has_errors  # bool
```

文件是否存在语法错误。为 `True` 时元素位置信息可能不可靠。

#### `elements`

```python
editor.elements  # [Element, ...]
```

所有收集到的可修改元素列表。

---

### 查询

#### `rule_names()`

```python
editor.rule_names()  # ["P1", "chk1", "check_m2_width", ...]
```

所有容器名称列表，按出现顺序。包括 RULE 名和顶层赋值语句名。

#### `rule_summaries()`

```python
editor.rule_summaries()
# [
#   {'name': 'P1', 'line': 5, 'count': 3, 'types': ['layerRef'], 'kind': 'DEF'},
#   {'name': 'chk1', 'line': 10, 'count': 5, 'types': ['constraint', 'layerRef'], 'kind': 'RULE'},
# ]
```

每个容器的摘要信息。`kind` 为 `'RULE'` 或 `'DEF'`（顶层赋值语句）。

#### `elements_by_rule(name)`

```python
editor.elements_by_rule("chk1")  # [Element, ...]
```

获取指定容器内的所有元素。`name` 可带或不带引号。

#### `elements_by_type(type)`

```python
editor.elements_by_type("layerRef")  # [Element, ...]
```

按类型筛选所有元素。类型字符串对应 `ELEMENT_TYPE_REGISTRY` 的 key。

#### `type_counts(name)`

```python
editor.type_counts("chk1")
# {'layerRef': 3, 'constraint': 2}
```

某个容器内各类型元素的个数统计。

---

### 原文/标注视图

#### `rule_text(name)`

```python
editor.rule_text("chk1")
# "RULE chk1 {\n   L1 = width ( M1 ...)\n   ...\n}"
```

返回指定容器的完整原始文本，含容器声明行。

#### `annotated_text(name)`

```python
editor.annotated_text("chk1")
# "RULE chk1 {\n   <<1:L1>> = width ( <<2:MET1>> <<3:< 1.0>> ...)\n}"
```

返回带 `<<N:有效值>>` 标注的容器文本。已修改的元素显示为 `new_text`，未修改显示原文。

#### `annotated_legend(name)`

```python
editor.annotated_legend("chk1")
# "--- 编号说明（5 个）---\n  <<1>> layerRef    L1  ...\n  <<2>> layerRef    MET1 ...\n"
```

返回与 `annotated_text` 配套的编号说明表，包含类型、原文、行号、修改标记。

---

### 修改

#### `add_change(element, new_text)`

```python
elem = editor.elements_by_rule("chk1")[1]  # <<2>> MET1
editor.add_change(elem, "MET2")
```

暂存一个修改。不立即写入文件。对同一元素多次调用只保留最后一次值。

**异常**：`ValueError` — 元素不属于当前编辑器实例。

#### `pending_changes()`

```python
editor.pending_changes()  # [Element, ...]
```

返回已暂存修改的元素列表。

#### `modified_text()`

```python
editor.modified_text()  # str
```

返回应用所有暂存修改后的完整源文本。

#### `clear_changes()`

```python
editor.clear_changes()
```

撤销所有暂存修改。

---

### 保存

#### `save(output_path=None, backup=True)`

```python
editor.save()                        # 覆盖原文件，创建时间戳备份
editor.save(output_path="out.pvrs")  # 写入新文件，不备份
editor.save(backup=False)            # 覆盖原文件，不备份
```

**参数**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `output_path` | `str \| None` | `None` | 输出路径。`None` 或空 = 覆盖原文件 |
| `backup` | `bool` | `True` | 覆盖原文件时是否创建 `.bak` 备份 |

**备份命名**：`<原文件名>.<YYYYMMDD_HHMMSS>.bak`

**换行符**：自动检测原文件 CRLF/LF 并保持一致。

---

## 模块级函数

### `get_element_types()`

```python
get_element_types()
# [{'key': 'layerRef', 'label': 'layerRef', 'desc': '层引用（名称、数字或带引号的字符串）'}, ...]
```

返回注册表中所有元素类型的列表。

### `iter_elements_by_rule(elements, name)`

```python
groups = iter_elements_by_rule(editor.elements, "chk1")
# {'layerRef': [Element, ...], 'constraint': [Element, ...]}
```

将某个容器内的元素按类型分组。

---

## 扩展：添加新的元素类型

在 `ELEMENT_TYPE_REGISTRY` 中注册：

```python
ELEMENT_TYPE_REGISTRY['funcName'] = _ElementTypeSpec(
    'funcName', 'visitFuncName',
    desc='函数名（如 area、perimeter）',
)
```

并在 `_RuleElementCollector` 中添加对应的 visitor 方法：

```python
def visitFuncName(self, ctx):
    """funcName 是叶子节点，收集后不递归。"""
    self._add_element('funcName', ctx)
    return None
```

---

## 使用示例

```python
from rule_editor import RuleEditor

# 打开文件
editor = RuleEditor("rules.pvrs")

# 检查语法
if editor.has_errors:
    for line, col, msg in editor.parse_errors:
        print(f"[{line}:{col}] {msg}")

# 浏览元素
for s in editor.rule_summaries():
    print(f"{s['kind']} {s['name']}: {s['count']} elements")

# 查看标注视图
print(editor.annotated_text("chk1"))
print(editor.annotated_legend("chk1"))

# 修改元素
for e in editor.elements_by_rule("chk1"):
    if e.text == "M1":
        editor.add_change(e, "METAL1")

# 保存
editor.save()
```

---

## 注意事项

1. **语法错误** — 文件有语法错误时，解析树可能不可靠，元素位置会偏移。务必在修改前修复语法错误。
2. **CRLF 兼容** — 内部统一使用 LF，读取/保存时自动检测和恢复原始换行符格式。
3. **字符偏移** — 所有偏移量基于 LF 归一化的文本，与 `self.source` 一致。
4. **修改顺序** — `modified_text()` 从右往左应用替换，保证前面的修改不影响后面元素的偏移量。
