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

**输出**：`{index: [type_name, text, modified, line], ...}` — `index` 为标注编号，值列表包含类型名、文本、是否已修改、行号。可用 `TokenEditor.format_legend()` 转为可读字符串。

**使用样例**

```python
legend = te.annotated_legend("chk1")  # dict
print(TokenEditor.format_legend(legend))  # 格式化输出
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
print(TokenEditor.format_legend(te.annotated_legend("chk1")))
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

#### 9. `clear_changes()`

**功能**：撤销所有暂存修改，恢复原始状态。

**输入**：无

**输出**：无

**使用样例**

```python
te.replace_by_text("chk1", "M1", "METAL1")
print(len(te.pending_tokens()))  # 1

te.clear_changes()
print(len(te.pending_tokens()))  # 0 — 全部撤销
```

---

#### 10. `var_refs(container)`

**功能**：返回该容器内引用的所有 VAR 变量定义。扫描容器内的所有 token，匹配 `var_map` 中的变量名，返回对应的完整 `var(...)` 文本。

**输入**

| 参数 | 类型 | 说明 |
|------|------|------|
| `container` | `str` | 容器名 |

**输出**：`{var_name: var_full_text, ...}` — 变量名到完整 VAR 定义文本的映射。

**使用样例**

```python
for name, text in te.var_refs("chk1").items():
    print(f"{name} ← {text}")
# LAYER1 ← var(LAYER1 M1)
# LAYER2 ← var(LAYER2 M2)
```

---

#### 11. `fun_refs(container)`

**功能**：返回该容器内引用的所有 CALL_FUN 函数定义。扫描容器内的所有 token，匹配 `fun_map` 中的函数名，返回对应的完整 `define_fun(...) { ... }` 文本。

**输入**

| 参数 | 类型 | 说明 |
|------|------|------|
| `container` | `str` | 容器名 |

**输出**：`{fun_name: fun_full_text, ...}` — 函数名到完整 DEFINE_FUN 定义文本的映射。

**使用样例**

```python
for name, text in te.fun_refs("chk1").items():
    print(f"{name} ← {text}")
# SPACECHK ← define_fun SPACECHK la lb {
#     space( la lb < 0.5 )
# }
```

---

### 其他 API

---

#### `parse_errors`

**功能**：返回原始文件的语法错误列表。

**输入**：无

**输出**：`[(line, col, msg), ...]`

```python
for line, col, msg in te.parse_errors:
    print(f"[{line}:{col}] {msg}")
```

---

#### `has_errors`

**功能**：文件是否有语法错误。

**输入**：无

**输出**：`bool`

```python
if te.has_errors:
    print("文件存在语法错误")
```

---

#### `var_map`

**功能**：文件中所有 VAR 定义的映射。

**输入**：无

**输出**：`{var_name: "var(...)", ...}` — 变量名到完整 VAR 语句文本。

```python
for k, v in te.var_map.items():
    print(f"{k}: {v}")
# LAYER1: var(LAYER1 M1)
# LAYER2: var(LAYER2 M2)
```

---

#### `fun_map`

**功能**：文件中所有 DEFINE_FUN 定义的映射。

**输入**：无

**输出**：`{fun_name: "define_fun ... { ... }", ...}` — 函数名到完整定义文本。

```python
for k, v in te.fun_map.items():
    print(f"{k}: {v}")
```

---

#### `container_names`

**功能**：所有容器名列表（RULE 名 + DEF 名）。

**输入**：无

**输出**：`[str, ...]`

```python
print(te.container_names)
# ['check_m1_width', 'check_m2_width', 'P1']
```

---

#### `containers()`

**功能**：返回每个容器的摘要信息。

**输入**：无

**输出**：`[{name, kind, line, count, types}, ...]`

```python
for c in te.containers():
    print(f"[{c['kind']}] {c['name']}: {c['count']} tokens")
```

---

#### `tokens(container)`

**功能**：返回指定容器内的元素列表，按编号排序。

**输入**

| 参数 | 类型 | 说明 |
|------|------|------|
| `container` | `str` | 容器名 |

**输出**：`[TokenElement, ...]`

```python
for t in te.tokens("chk1"):
    print(f"<<{t.index}>> [{t.type_name}] {t.text!r}")
```

---

#### `all_tokens()`

**功能**：返回所有容器的所有元素。

**输入**：无

**输出**：`[TokenElement, ...]`

```python
for t in te.all_tokens():
    print(f"[{t.container}] <<{t.index}>> {t.text!r}")
```

---

#### `container_text(container)`

**功能**：返回容器原始文本（不含标注标记）。

**输入**

| 参数 | 类型 | 说明 |
|------|------|------|
| `container` | `str` | 容器名 |

**输出**：`str`

```python
print(te.container_text("chk1"))
# "RULE chk1 {\n   L1 = width ( M1 ...\n}"
```

---

#### `format_legend(legend)`

**功能**：将 `annotated_legend()` 返回的 dict 格式化为可读字符串。

**输入**

| 参数 | 类型 | 说明 |
|------|------|------|
| `legend` | `dict` | `annotated_legend()` 的返回值 |

**输出**：`str`

```python
legend = te.annotated_legend("chk1")
print(TokenEditor.format_legend(legend))
```

---

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
