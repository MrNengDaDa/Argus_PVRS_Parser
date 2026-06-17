# full_token_editor — 基于 ANTLR Token 流的 PVRS 元素修改器

## 安装

```bash
cd Argus_PVRS_Parser
pip install -e .
```

## 快速开始

```python
from full_token_editor import TokenEditor

te = TokenEditor("rules.pvrs")

# 查看元素
for c in te.container_names:
    print(te.annotated_text(c))

# 修改
te.replace_by_text("chk1", "M1", "METAL1")
te.replace_by_index("chk1", 3, "M99")

# 保存
result = te.save()
print(result)  # {'ok': True, 'errors': []}
```

命令行：

```bash
full-token-editor rules.pvrs --show chk1
full-token-editor rules.pvrs --sample
```

---

## TokenElement

单个可修改元素，位于 RULE / derived_layer_def 容器内。

| 属性 | 类型 | 说明 |
|------|------|------|
| `text` | `str` | 原文 |
| `type_name` | `str` | 类型名，如 `"WIDTH"`, `"Op_layer"`, `"Constraint"`, `"IntOption"`, `"layerRef"` |
| `line` | `int` | 行号（1 起始） |
| `char_start` | `int` | 源文本起始偏移 |
| `char_stop` | `int` | 源文本结束偏移 |
| `container` | `str` | 所属容器名 |
| `index` | `int` | 容器内编号（1 起始，对应标注视图的 `<<N>>`） |
| `modified` | `bool` | 是否已暂存修改 |
| `new_text` | `str \| None` | 暂存的替换文本 |

---

## API 参考

### 主要 API

---

#### 1. `TokenEditor(filepath)`

**功能**：解析 PVRS 规则文件，收集所有 RULE 和 derived_layer_def 容器内 op_statement 的直接子节点。

**输入**

| 参数 | 类型 | 说明 |
|------|------|------|
| `filepath` | `str` | PVRS 规则文件路径 |

**输出**：`TokenEditor` 实例。

**使用样例**

```python
from full_token_editor import TokenEditor

te = TokenEditor("rules.pvrs")
print(te.container_names)  # 查看所有容器名
```

---

#### 2. `check()`

**功能**：对原始文件执行 ANTLR 语法检查，返回语法错误列表和文件摘要。

**输入**：无

**输出**

```python
{
    'ok': bool,              # True = 语法正确
    'errors': [(line, col, msg), ...],  # 语法错误列表
    'container_count': int,  # 容器总数
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

**使用样例**

```python
info = te.check()
if info['ok']:
    print(f"语法正确，{info['container_count']} 个容器，{info['token_count']} 个元素")
else:
    for line, col, msg in info['errors']:
        print(f"[{line}:{col}] {msg}")
```

---

#### 3. `annotated_text(container)`

**功能**：返回带 `<<N:value>>` 标注的容器原文。每个可修改元素被包裹显示，已修改元素显示新值。括号 `()`、`[]` 不会出现在标注中。

**输入**

| 参数 | 类型 | 说明 |
|------|------|------|
| `container` | `str` | 容器名（RULE 名或赋值语句左侧变量名） |

**输出**：`str` — 标注后的文本。

**使用样例**

```python
text = te.annotated_text("chk1")
print(text)
```

输出示例：

```
RULE check_m1_width {
   <<1:L1>> = <<2:width>> ( <<3:M1>> <<4:< 0.5>> <<5:adjacent < 90>> ... )
   <<9:L2>> = <<10:width>> ( <<11:METAL1>> <<12:< 0.5>> ... )
   <<18:geom_or>> ( <<19:L1>> <<20:L2>> )
}
```

---

#### 4. `annotated_legend(container)`

**功能**：返回标注视图的编号说明表，列出每个 `<<N>>` 的元素类型、当前值、行号和修改状态。

**输入**

| 参数 | 类型 | 说明 |
|------|------|------|
| `container` | `str` | 容器名 |

**输出**：`str` — 编号说明表。

**使用样例**

```python
legend = te.annotated_legend("chk1")
print(legend)
```

输出示例：

```
--- Token 编号说明（18 个）---
  <<1>> layerRef    'L1'  (第 2 行)
  <<2>> WIDTH       'width'  (第 2 行)
  <<3>> Op_layer    'M1' [已修改]  (第 2 行)
  <<4>> Constraint  '< 0.5'  (第 2 行)
  ...
```

---

#### 5. `replace_by_text(container, old_text, new_text)`

**功能**：在指定容器中查找所有文本匹配的元素，全部替换为 `new_text`。匹配为精确字符串比较。

**输入**

| 参数 | 类型 | 说明 |
|------|------|------|
| `container` | `str` | 容器名 |
| `old_text` | `str` | 要匹配的原始文本（精确匹配） |
| `new_text` | `str` | 替换为目标文本（对所有匹配项） |

**输出**：`bool` — `True` 表示找到并修改了匹配元素，`False` 表示无匹配。

**使用样例**

```python
# 将容器中所有 "M1" 替换为 "METAL1"
ok = te.replace_by_text("chk1", "M1", "METAL1")
print(ok)  # True（修改了所有匹配的 Op_layer 元素）

# 替换所有约束 "< 0.5" → "< 1.0"
ok = te.replace_by_text("chk1", "< 0.5", "< 1.0")
print(ok)  # True

# 无匹配
ok = te.replace_by_text("chk1", "NOT_EXISTS", "X")
print(ok)  # False
```

---

#### 6. `replace_by_index(container, index, new_text)`

**功能**：按标注视图中的 `<<N>>` 编号精确修改**单个**元素。编号对应 `annotated_text()` 和 `annotated_legend()` 中的 `<<N>>`。

**输入**

| 参数 | 类型 | 说明 |
|------|------|------|
| `container` | `str` | 容器名 |
| `index` | `int` | 元素编号（1 起始，对应 <<N>>） |
| `new_text` | `str` | 替换为目标文本（只替换一个元素） |

**输出**：`bool` — `True` 表示修改成功，`False` 表示索引越界。

**使用样例**

```python
# 先查看标注视图确认目标元素的编号
print(te.annotated_legend("chk1"))
# <<3>> Op_layer    'M1'   ...  ← 要修改这个

ok = te.replace_by_index("chk1", 3, "MET2")
print(ok)  # True

# 越界
ok = te.replace_by_index("chk1", 999, "X")
print(ok)  # False
```

---

#### 7. `pending_tokens()`

**功能**：返回所有已暂存修改的元素列表。可用于查看修改摘要或在保存前审查。

**输入**：无

**输出**：`[TokenElement, ...]` — 已修改元素的列表。每个元素的 `text` 为原文，`new_text` 为暂存值。

**使用样例**

```python
pending = te.pending_tokens()
print(f"共 {len(pending)} 项修改待保存：")
for t in pending:
    print(f"  <<{t.index}>> [{t.type_name}] {t.text!r} → {t.new_text!r}")
```

---

#### 8. `save(output_path=None, backup=True)`

**功能**：对修改后的文本执行语法校验，通过后写入磁盘。覆盖原文件时自动创建时间戳备份。

**输入**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `output_path` | `str \| None` | `None` | 输出路径，`None` 或空 = 覆盖原文件 |
| `backup` | `bool` | `True` | 覆盖原文件时是否创建 `<file>.<时间戳>.bak` 备份 |

**输出**

```python
{
    'ok': bool,                        # True = 保存成功
    'errors': [(line, col, msg), ...]  # 失败时为语法错误列表
}
```

失败时所有暂存修改保留，修正后可重新调用 `save()`。

**使用样例**

```python
result = te.save()
if result['ok']:
    print("已保存")
else:
    for line, col, msg in result['errors']:
        print(f"[{line}:{col}] {msg}")
    # 修改仍保留，返回编辑后重试

# 保存到其他文件（不创建备份）
te.save(output_path="output.pvrs", backup=False)
```

---

### 其他 API

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `parse_errors` | `[(line, col, msg), ...]` | 语法错误列表 |
| `has_errors` | `bool` | 文件是否有语法错误 |
| `container_names` | `[str, ...]` | 所有容器名列表 |

```python
print(te.container_names)
# ['check_m1_width', 'check_m2_width', 'P1']
```

#### 查询方法

##### `containers() → [dict, ...]`

容器摘要列表。

```python
for c in te.containers():
    print(f"[{c['kind']}] {c['name']}: {c['count']} tokens")
```

##### `tokens(container) → [TokenElement, ...]`

指定容器内的元素列表（按编号顺序）。

```python
for t in te.tokens("chk1"):
    print(f"<<{t.index}>> [{t.type_name}] {t.text!r}")
```

##### `all_tokens() → [TokenElement, ...]`

所有容器的所有元素。

##### `container_text(container) → str`

容器原文（不含标注）。

```python
print(te.container_text("chk1"))
```

#### 其他修改方法

##### `clear_changes()`

撤销所有暂存的修改，恢复原始状态。

```python
te.clear_changes()
print(len(te.pending_tokens()))  # 0
```


## TokenEditorPlugin

TokenEditor 的便捷包装，接口与 `RuleEditorPlugin` 一致。

| 方法 | 返回 | 说明 |
|------|------|------|
| `plugin.check()` | `dict` | 语法检查 + 摘要 |
| `plugin.show(name)` | `(annotated_text, legend)` | 标注视图 + 编号表 |
| `plugin.replace_by_text(...)` | `bool` | 文本匹配替换 |
| `plugin.replace_by_index(...)` | `bool` | 编号精确替换 |
| `plugin.save(...)` | `dict` | 校验并保存 |
| `plugin.discard()` | `None` | 撤销所有修改 |
| `plugin.pending_count` | `int` | 暂存修改数 |

```python
from full_token_editor import TokenEditorPlugin

plugin = TokenEditorPlugin("rules.pvrs")
plugin.check()
plugin.show("chk1")
plugin.replace_by_text("chk1", "M1", "METAL1")
plugin.replace_by_index("chk1", 5, "M99")
plugin.save()
plugin.discard()
```


## 元素粒度说明

收集的是 op_statement 的直接子节点：

| 元素类型 | 示例 | 说明 |
|---------|------|------|
| 操作关键字 | `WIDTH`, `GEOM_OR` | 操作名 |
| Op_layer | `M1`, `L1` | 层引用或嵌套操作 |
| Constraint | `< 0.5` | 约束表达式 |
| IntOption | `adjacent < 90`, `region` | 选项参数组 |
| layerRef | `L1` (赋值左侧) | derived_layer_def 的左侧变量 |

括号 `(` `)` `[` `]` 不可修改，标注视图中保持为普通文本。
