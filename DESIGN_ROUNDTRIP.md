# PVRS 文本 展开 → 修改 → 逆向还原 方案设计

## 目标

1. 将原始 PVRS（含 DEFINE_FUN / CALL_FUN / VAR）展开为平坦文本
2. 用 `full_token_editor` 修改展开文本中的少量 token
3. 将修改**逆映射**回原始文本，恢复宏和变量结构

## 核心约束

- **VAR 定义值不可变**：`VAR(LAYER1 M1)` 中 `M1` 不能通过修改展开文本来更改。
  如果要改 `M1`，应直接修改原始文件中的 VAR 语句，而非修改展开后的 token。
  修改位置落在 VAR 替换区域时，逆向脚本会跳过并打印提示。
- **可逆向的修改**：仅对**非宏展开的原文段落**（identity）和 **DEFINE_FUN 函数体内部**
  的修改才能逆向映射回原始文本。

---

## 一、注释标记格式

所有标记均为 ANTLR `BLOCK_COMMENT`（`/* ... */`），会被 lexer 自动跳过，
不影响语法解析。统一前缀 `/*:` 用于逆向脚本唯一识别。

### 1.1 VAR 变量替换标记

```
原始:   space( LAYER1 LAYER2 < 0.5 )
展开:   space( LAYER1 /*:V:LAYER2=M2*/ M2 /*:V*/ < 0.5 )
                         ^──────────^   ^^  ^──^
                         开始标记      值   结束标记
```

**开始标记**: `/*:V:变量名=展开值*/`
**结束标记**: `/*:V*/`

开始标记内的 `变量名` 和 `展开值` 供逆向脚本查询。如果展开后的值被手动修改
（如 `M2` 改为 `M99`），逆向脚本会跳过此项并打印提示——VAR 定义中的值不可
通过修改展开文本来变更，应直接修改原始文件中的 VAR 语句。

### 1.2 CALL_FUN 函数展开标记

CALL_FUN 展开为多行时，需要在展开体的**开始**和**结束**位置各放一个标记。

```
原始:
CALL_FUN( SPACECHK LAYER1 LAYER2 )

展开后:
/*:F:SPACECHK:1:la=LAYER1:lb=LAYER2*/
space( LAYER1 LAYER2 < 0.5 )
/*:FEND:SPACECHK*/
```

**开始标记**: `/*:F:函数名:调用序号:参数1=传入值1:参数2=传入值2*/`
- 调用序号用于区分同一函数的多次调用，从 1 开始
- 参数列表记录每个形参→实参的映射

**结束标记**: `/*:FEND:函数名*/`

### 1.3 DEFINE_FUN 内部嵌套展开标记

DEFINE_FUN 的 body 内部如果有 CALL_FUN 嵌套调用，同样用上述标记。
展开后的 body 被 `/*:F:...*/` ... `/*:FEND:...*/` 包裹。

---

## 二、expand_macros.py 改动

### 2.1 新增 `--annotate` 参数

```bash
python expand_macros.py input.pvrs expanded.pvrs --annotate
```

### 2.2 新增 `--info` 参数（输出元信息文件）

```bash
python expand_macros.py input.pvrs expanded.pvrs --annotate --info meta.json
```

`meta.json` 记录所有变量和函数定义的结构化信息，供逆向脚本快速查询。

### 2.3 展开逻辑改动

#### VAR 替换

```python
# 原: result = re.sub(pattern, value, result, ...)
# 改: 在 value 前后包裹标记
marked_value = f'/*:V:{name}={value}*/ {value} /*:V*/'
result = re.sub(pattern, marked_value, result, ...)
```

**特殊情况**：如果同一个变量名在原文中出现多次，每处都包裹标记。

**特殊情况**：如果值是纯数字（`M1`、`1000`），且未被 VAR 替换过，标记仍然包裹。
这样即使值相同，逆向脚本也能识别该位置的来源。

#### CALL_FUN 展开

```python
# 在展开体前后包裹标记
expanded_body = substitute_args(info['body'], info['args'], call_args, fname)
call_index = get_next_call_index(fname)  # 全局计数
arg_list = ':'.join(f'{a}={v}' for a, v in zip(info['args'], call_args))
marked = f'/*:F:{fname}:{call_index}:{arg_list}*/\n{expanded_body}\n/*:FEND:{fname}*/'
```

#### 元信息输出

```json
{
  "vars": {
    "LAYER1": {"value": "M1", "line": 5},
    "LAYER2": {"value": "M2", "line": 6}
  },
  "funcs": {
    "SPACECHK": {
      "line": 10,
      "args": ["la", "lb"],
      "body": "space( la lb < 0.5 )",
      "calls": [
        {"line": 25, "args": ["M1", "M2"], "index": 1}
      ]
    }
  },
  "annotation_count": {
    "VAR": 12,
    "FUNC": 3
  }
}
```

---

## 三、逆向脚本 revert_expanded.py

### 3.1 工作流程

```
展开后文本 (modified) + meta.json
        │
        ▼ 1. 解析所有 /*:V:...*/ /*:F...*/ 标记，建立展开位置→原始来源的索引
        │
        ▼ 2. 从 full_token_editor 获取修改列表 [(start, stop, new_text), ...]
        │
        ▼ 3. 对每个修改，二分查找索引，确定来源类型
        │
        ├── 来源=VAR 替换位置 → 跳过（VAR 定义值不可变）
        ├── 来源=函数体内部    → 修改 DEFINE_FUN 的 body 原文  
        ├── 来源=非宏原文      → 直接改原文对应位置
        └── 来源=标记本身      → 标记不应被修改，跳过
        │
        ▼ 4. 重建原始文件
```

### 3.2 核心数据结构

```python
@dataclass
class SourceMapping:
    """展开文本中一个字符范围到原文来源的映射"""
    exp_start: int      # 展开文本中起始位置
    exp_stop: int       # 展开文本中结束位置
    source_type: str    # 'identity' | 'var' | 'func_body' | 'annotation'
    detail: dict        # 来源详情
```

#### 索引构建

解析展开文本中的所有标记，构建映射表（按 `exp_start` 排序的列表）：

```python
mappings = []

# 扫描 VAR 标记
for m in re.finditer(r'/\*:V:([^=]+)=(.*?)\*/', text):
    var_name = m.group(1)
    value = m.group(2)
    # 找结束标记
    end_marker = '/*:V*/'
    end_pos = text.index(end_marker, m.end())
    # 标记之间的值区域
    value_start = m.end()
    value_end = text.index(end_marker, m.end()) - 1
    mappings.append(SourceMapping(
        exp_start=value_start,
        exp_stop=value_end,
        source_type='var',
        detail={'var_name': var_name, 'original_value': value}
    ))

# 扫描 FUNC 标记
for m in re.finditer(r'/\*:F:([^:]+):(\d+):(.+)'`', text):
    ...
```

### 3.3 逆向映射逻辑

```python
def revert(original: str, expanded: str, meta: dict,
           changes: List[Tuple[int, int, str]]) -> str:
    """
    changes: [(exp_start, exp_stop, new_text), ...]
    返回: 修改后的原始文本
    """
    index = build_index(expanded)  # 构建映射索引
    result = original
    failed = []

    for exp_start, exp_stop, new_text in changes:
        mapping = find_mapping(index, exp_start, exp_stop)

        if mapping is None:
            failed.append((exp_start, exp_stop, new_text,
                          '无法定位来源'))
            continue

        if mapping.source_type == 'var':
            # VAR 定义中的值不可改变，跳过逆向映射
            failed.append((exp_start, exp_stop, new_text,
                          f'VAR 替换位置 (变量={mapping.detail["var_name"]})，'
                          f'原值不可变，请修改 VAR 定义或源文本'))
            continue

        elif mapping.source_type == 'func_body':
            # 修改 DEFINE_FUN 的 body
            func_name = mapping.detail['func_name']
            result = update_function_body(result, func_name,
                                          mapping.orig_start,
                                          mapping.orig_stop,
                                          new_text)

        elif mapping.source_type == 'identity':
            # 直接映射到原文位置
            result = replace_range(result, mapping.orig_start,
                                   mapping.orig_stop, new_text)

        elif mapping.source_type == 'annotation':
            failed.append((exp_start, exp_stop, new_text,
                          '标记区域不可修改'))

    # 打印失败项
    for item in failed:
        print(f'[!] 无法逆向: pos={item[0]}-{item[1]}, '
              f'new_text={item[2]!r}, reason={item[3]}')

    # 恢复原始 VAR 和 DEFINE_FUN 定义（不被修改影响）
    result = restore_definitions(result, meta)

    return result
```

### 3.4 失败处理

以下情况标记为"无法逆向转换"，打印详细信息后**跳过**：

1. **修改位置跨越标记边界**：修改范围同时包含标记和普通文本
2. **修改位置在标记上**：标记本身被修改（不应该发生，因为 full_token_editor 不收集注释 token）
3. **变量值被修改但不符合变量定义格式**：如将 `M1` 改为 `]@#$%`（包含非法字符）
4. **函数体多次被改且无法确定对应原始位置**：标记被删除或破坏

### 3.5 恢复原始定义

逆向后的文本需要保持 VAR 和 DEFINE_FUN 的原始定义不变（除非其值被明确修改）。

```python
def restore_definitions(text: str, meta: dict) -> str:
    """确保所有 VAR 和 DEFINE_FUN 定义存在于输出中"""
    for var_name, info in meta['vars'].items():
        if not var_still_exists(text, var_name):
            # VAR 定义被误删，恢复
            text = insert_var_definition(text, var_name, info)

    for func_name, info in meta['funcs'].items():
        if not func_still_exists(text, func_name):
            text = insert_func_definition(text, func_name, info)

    return text
```

---

## 四、总体数据结构汇总

### expand_macros.py 输出

| 产物 | 说明 |
|------|------|
| `expanded.pvrs` | 展开后的 PVRS 文本，含 `/*:...*/` 标记 |
| `meta.json` | 变量/函数定义的元信息 |
| 命令行: `--annotate --info meta.json` | |

### revert_expanded.py 输入/输出

| 输入 | 说明 |
|------|------|
| `original.pvrs` | 原始的含宏/VAR 的 PVRS 文件 |
| `expanded_modified.pvrs` | 修改后的展开文本（含标记） |
| `meta.json` | expand_macros 输出的元信息 |

| 输出 | 说明 |
|------|------|
| `original_modified.pvrs` | 逆向还原后的原始文件（宏/VAR 结构保持，值已更新） |
| stderr 输出 | 无法逆向的项（编号、位置、原因） |

---

## 五、使用示例

```bash
# 第一步：带标注展开
python expand_macros.py input.pvrs expanded.pvrs --annotate --info meta.json

# 第二步：用 full_token_editor 修改
python sample_token_editor.py expanded.pvrs
# 或用 API:
# te = TokenEditor("expanded.pvrs")
# te.replace_by_text("chk1", "M1", "METAL1")
# te.save()

# 第三步：逆向还原
python revert_expanded.py input.pvrs expanded.pvrs meta.json --output input_modified.pvrs
# 输出:
#   [✓] 3 项修改已逆向
#   [!] 1 项无法逆向: pos=150-155, new_text=']@#$%', reason=非法字符
```

---

## 六、边界情况处理

| 场景 | 处理方式 |
|------|---------|
| 修改位置来源于 VAR 替换 | 跳过逆向映射，打印提示：请修改 VAR 定义或源文本 |
| 同一变量出现多次，只改其中一次 | 跳过（VAR 值不可变） |
| 函数体内部 token 被修改 | 修改映射到 DEFINE_FUN 的 body 原文中 |
| 修改导致展开值 ≠ VAR 定义值 | 正常：正是需要逆向更新的情况 |
| 展开后被多个人/工具多次修改 | 无法处理，标记可能被破坏导致失败 |
| expand_macros.py 未展开（无 VAR/DEFINE_FUN） | meta.json 为空，revert 退化为纯位置映射 |
| 修改范围跨越了标记 | 标记 `/*:...*/` 可能被破坏，回退到原始值 |
| CALL_FUN 嵌套调用 | 每层嵌套各自用标记包裹，递归处理 |
