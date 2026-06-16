# full_token_editor — 基于 ANTLR Token 流的 PVRS 元素修改器

## 安装

```bash
pip install git+https://github.com/MrNengDaDa/Argus_PVRS_Parser.git
```

或本地开发：

```bash
git clone https://github.com/MrNengDaDa/Argus_PVRS_Parser.git
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
print(result)           # {'ok': True, 'errors': []}
```

命令行：

```bash
full-token-editor rules.pvrs --show chk1
full-token-editor rules.pvrs --sample
```

---

# API 参考

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

## TokenEditor

### 构造

```python
te = TokenEditor(filepath)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `filepath` | `str` | PVRS 规则文件路径 |

---

### 属性

#### `parse_errors` → `[(line, col, msg), ...]`

语法错误列表。

#### `has_errors` → `bool`

文件是否有语法错误。

#### `container_names` → `[str, ...]`

所有容器名列表（RULE 名 + DEF 名）。

```python
te.container_names
# ['check_m1_width', 'check_m2_width', 'P1']
```

---

### 查询

#### `containers() → [{name, kind, line, count, types}, ...]`

容器摘要列表。

```python
for c in te.containers():
    print(f"{c['kind']} {c['name']}: {c['count']} tokens")
```

#### `tokens(container) → [TokenElement, ...]`

指定容器内的元素列表（按编号顺序）。

```python
for t in te.tokens("chk1"):
    print(f"<<{t.index}>> [{t.type_name}] {t.text!r}")
```

#### `all_tokens() → [TokenElement, ...]`

所有容器的所有元素。

#### `container_text(container) → str`

容器原文。

```python
print(te.container_text("chk1"))
# "RULE chk1 {\n   L1 = width ( M1 ...\n}"
```

---

### 标注视图

#### `annotated_text(container) → str`

带 `<<N:value>>` 标注的容器文本。已修改元素显示新值。

```python
print(te.annotated_text("chk1"))
```

输出示例：

```
RULE check_m1_width {
   <<1:L1>> = <<2:width>> ( <<3:M1>> <<4:< 0.5>> <<5:adjacent < 90>> ... )
   <<9:L2>> = <<10:width>> ( <<11:M1>> <<12:< 0.5>> ... )
   <<18:geom_or>> ( <<19:L1>> <<20:L2>> )
}
```

#### `annotated_legend(container) → str`

编号说明表。

```python
print(te.annotated_legend("chk1"))
```

输出示例：

```
--- Token 编号说明（22 个）---
  <<1>> layerRef    'L1'  (第 2 行)
  <<2>> WIDTH       'width'  (第 2 行)
  <<3>> Op_layer    'M1'  (第 2 行)
  <<4>> Constraint  '< 0.5'  (第 2 行)
  <<5>> IntOption   'adjacent < 90'  (第 2 行)
  ...
```

---

### 修改

#### `replace_by_text(container, old_text, new_text) → bool`

文本匹配，全部替换。返回 `True`（有修改）或 `False`（无匹配）。

```python
# 所有 "M1" → "METAL1"
ok = te.replace_by_text("chk1", "M1", "METAL1")
print(ok)  # True

# 约束替换
ok = te.replace_by_text("chk1", "< 0.5", "< 1.0")
```

#### `replace_by_index(container, index, new_text) → bool`

按编号精确修改单个元素。返回 `True`（成功）或 `False`（越界）。

```python
# 修改 <<3>> 号元素
ok = te.replace_by_index("chk1", 3, "MET2")
print(ok)  # True

# 越界
ok = te.replace_by_index("chk1", 999, "X")
print(ok)  # False
```

#### `pending_tokens() → [TokenElement, ...]`

已修改的元素列表。

```python
for t in te.pending_tokens():
    print(f"{t.text!r} → {t.new_text!r}")
```

#### `clear_changes()`

撤销所有修改。

---

### 校验与保存

#### `check() → dict`

语法检查（基于原始文件，非修改后文本）。

```python
info = te.check()
# {
#     'ok': True,
#     'errors': [],
#     'container_count': 3,
#     'token_count': 48,
#     'containers': [{...}, ...]
# }
```

#### `save(output_path=None, backup=True) → dict`

校验修改后文本 → 通过则写入。返回 `{'ok': bool, 'errors': [(line,col,msg),...]}`。

```python
result = te.save()
if result['ok']:
    print("已保存")
else:
    for line, col, msg in result['errors']:
        print(f"[{line}:{col}] {msg}")
    # 修改仍保留，修正后重新 save()
```

---

## TokenEditorPlugin

TokenEditor 的便捷包装，接口与 `RuleEditorPlugin` 一致。

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

括号 `(`, `)`, `[`, `]` 不可修改，标注视图中保持为普通文本。
