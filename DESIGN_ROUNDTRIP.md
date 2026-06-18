# PVRS 文本 展开 → 修改 → 逆向还原 方案设计 v2

## 核心思想

不是"修改原始文件"，而是**从展开文本重建**一个新文件：
将展开文本中的标记段（`/*:...*/`）按规则还原为 VAR 引用或 CALL_FUN 调用，
原文段落（identity）直接保留。

```
展开文本 (带标记) + 修改列表
        │
        ▼ 从左到右扫描
        │
    ┌───┴───┬───────────┬───────────┐
    │ identity│ VAR 标记段 │ FUNC 标记段 │
    │ 段落    │           │           │
    └───┬───┴─────┬─────┴─────┬─────┘
        │         │           │
        ▼         ▼           ▼
    直接复制   变了吗？    入参改了吗？
              /    \       /      \
           变了   没变   没改/只改入参  改了非入参
            │     │       │           │
            ▼     ▼       ▼           ▼
         字面量  VAR引用  CALL_FUN   保持展开
```

---

## 一、展开标记格式

### 1.1 VAR 标记

```
原始:  space( LAYER1 LAYER2 < 0.5 )
展开:  space( /*:V:LAYER1=M1*/ M1 /*:V*/ /*:V:LAYER2=M2*/ M2 /*:V*/ < 0.5 )
```

**开始**: `/*:V:变量名=展开值*/`
**结束**: `/*:V*/`

标记之间的内容为展开后的值。

### 1.2 FUNC 标记

```
原始:  CALL_FUN( SPACECHK LAYER1 5 )
展开:  /*:F:SPACECHK:la=LAYER1:lb=5*/
         space( LAYER1 5 < 0.5 )
       /*:FEND*/
```

**开始**: `/*:F:函数名:arg1=val1:arg2=val2*/`
**结束**: `/*:FEND*/`

开始标记内记录了每个形参→实参的映射。标记之外的区域是完整的函数展开体。

### 1.3 标记嵌套

```
/*:F:OUTER:a=LAYER1*/
  inner_result = /*:F:INNER:x=LAYER1*/ geom_area( /*:V:LAYER1=M1*/ M1 /*:V*/ > 0 ) /*:FEND*/
/*:FEND*/
```

嵌套时从外向内匹配 `/*:F:...*/` 和 `/*:FEND*/`。

---

## 二、展开流程（expand_macros.py）

### 输出

| 参数 | 说明 |
|------|------|
| `--annotate` | 展开时嵌入 `/*:...*/` 标记 |
| `--info meta.json` | 输出元信息（变量/函数定义列表，供参考） |

### 元信息 meta.json

```json
{
  "vars": {"LAYER1": "M1", "LAYER2": "M2"},
  "funcs": {
    "SPACECHK": {"args": ["la", "lb"], "body": "space( la lb < 0.5 )", "line": 10}
  }
}
```

### 展开示例

输入：
```
var(LAYER1 M1)
var(LAYER2 M2)

define_fun SPACECHK la lb {
    space( la lb < 0.5 )
}

RULE chk {
    CALL_FUN( SPACECHK LAYER1 5 )
}
```

输出（带标记）：
```
var(LAYER1 M1)
var(LAYER2 M2)

define_fun SPACECHK la lb {
    space( la lb < 0.5 )
}

RULE chk {
    /*:F:SPACECHK:la=LAYER1:lb=5*/
    space( /*:V:LAYER1=M1*/ M1 /*:V*/ 5 < 0.5 )
    /*:FEND*/
}
```

---

## 三、修改流程（不变）

用 `full_token_editor` 修改展开文本，收集修改列表：

```python
te = TokenEditor("expanded.pvrs")
te.replace_by_text("chk", "M1", "M99")
te.save()
```

修改列表：`[(char_start=150, char_stop=151, new_text='M99'), ...]`

---

## 四、逆向流程（revert_expanded.py）

### 输入

| 输入 | 说明 |
|------|------|
| `modified_expanded.pvrs` | 修改后的带标记展开文本 |
| 修改列表 | 来自 full_token_editor 的 changes |
| `meta.json` | 可选，供参考 |

### 算法：从左到右扫描重建

```python
def revert(modified_text, changes):
    """
    扫描 modified_text，逐段重建输出文本。
    changes: {char_start: new_text} 字典
    """
    output = []
    pos = 0

    while pos < len(modified_text):
        # 找下一个标记
        next_marker = find_next_marker(modified_text, pos)

        if next_marker is None:
            # 剩余全是 identity 段落，应用修改后复制
            segment = apply_changes(modified_text[pos:], changes, offset=pos)
            output.append(segment)
            break

        # 处理标记之前的 identity 段落
        if next_marker.start > pos:
            segment = apply_changes(modified_text[pos:next_marker.start],
                                    changes, offset=pos)
            output.append(segment)

        # 根据标记类型处理
        if next_marker.type == 'VAR':
            output.append(revert_var(next_marker, modified_text, changes))
        elif next_marker.type == 'FUNC':
            output.append(revert_func(next_marker, modified_text, changes))

        pos = next_marker.end  # 跳过已处理区域

    return ''.join(output)
```

### 4.1 identity 段落处理

```python
def apply_changes(segment, changes, offset):
    """对 identity 段落应用修改"""
    result = list(segment)
    for (cs, ce, new_text) in changes:
        local_start = cs - offset
        local_stop = ce - offset
        if 0 <= local_start < len(segment):
            result[local_start:local_stop+1] = new_text
    return ''.join(result)
```

### 4.2 VAR 标记段处理（规则 1）

```python
def revert_var(marker, text, changes):
    """
    规则 1:
    - 值被修改 → 输出字面量（新值）
    - 值未被修改 → 输出 VAR 引用（变量名）
    """
    var_name = marker.var_name       # 如 "LAYER1"
    var_value = marker.var_value     # 如 "M1"
    value_start = marker.value_start  # 值区域起始 pos
    value_end = marker.value_end      # 值区域结束 pos

    # 检查值区域是否被修改
    modified = False
    effective = var_value
    for (cs, ce, new_text) in changes:
        if cs >= value_start and ce <= value_end:
            effective = new_text
            modified = True
            break

    if modified:
        return effective       # 字面量 M99
    else:
        return var_name        # VAR 引用 LAYER1
```

### 4.3 FUNC 标记段处理（规则 2）

```python
def revert_func(marker, text, changes):
    """
    规则 2:
    - 只有入参被修改（或无修改）→ 输出 CALL_FUN(...)，入参更新
    - 非入参被修改 → 保持展开形式（标记段原样输出，应用修改）
    """
    func_body = text[marker.body_start:marker.body_end]
    args = marker.args  # [('la', 'LAYER1'), ('lb', '5')]

    # 检查修改是否全部在入参区域
    for (cs, ce, new_text) in changes:
        if marker.contains(cs, ce):
            if not any(is_in_arg(cs, ce, arg) for arg in args):
                # 非入参被修改 → 保持展开
                return apply_changes_to_body(func_body, changes,
                                             offset=marker.body_start)

    # 入参被修改或无修改 → 重建 CALL_FUN
    call_args = []
    for arg_name, arg_value in args:
        effective = arg_value
        for (cs, ce, new_text) in changes:
            if marker.contains(cs, ce) and is_in_arg(cs, ce, (arg_name, arg_value)):
                effective = new_text
                break
        call_args.append(effective)

    return f'CALL_FUN( {marker.func_name} {" ".join(call_args)} )'
```

### 4.4 嵌套处理

`/*:F:...*/` 和 `/*:FEND*/` 配对匹配。扫描时如果在内层 FUNC 标记内再次遇到 `/*:F:...*/`，递归进入，直到匹配到对应的 `/*:FEND*/`。

```python
def find_matching_fend(text, func_start_pos):
    """从 /*:F:...*/ 位置找到匹配的 /*:FEND*/"""
    depth = 0
    pos = func_start_pos
    while pos < len(text):
        if text.startswith('/*:F:', pos):
            depth += 1
        elif text.startswith('/*:FEND', pos):
            depth -= 1
            if depth == 0:
                return pos + len('/*:FEND*/')
        pos += 1
    return -1
```

---

## 五、完整示例

### 输入

原始：
```
var(LAYER1 M1)
define_fun SPACECHK la lb { space( la lb < 0.5 ) }
RULE chk { CALL_FUN( SPACECHK LAYER1 5 ) }
```

展开后（带标记）：
```
var(LAYER1 M1)
define_fun SPACECHK la lb { space( la lb < 0.5 ) }
RULE chk {
    /*:F:SPACECHK:la=LAYER1:lb=5*/
    space( /*:V:LAYER1=M1*/ M1 /*:V*/ 5 < 0.5 )
    /*:FEND*/
}
```

### 场景 A：修改 VAR 值（M1 → M99）

修改：`M1` (pos=150-151) → `M99`

逆向输出：
```
var(LAYER1 M1)
define_fun SPACECHK la lb { space( la lb < 0.5 ) }
RULE chk {
    /*:F:SPACECHK:la=LAYER1:lb=5*/
    space( M99 5 < 0.5 )        ← M1 被改了，写回字面量 M99
    /*:FEND*/
}
```

### 场景 B：修改 CALL_FUN 入参（LAYER1 → MET1）

修改：第一个 `LAYER1` (pos=120-125) → `MET1`

这是 FUNC 标记内、入参 `la` 对应的区域（该区域又嵌套了 VAR 标记）。
入参值从 `LAYER1` 改为 `MET1`。

逆向输出：
```
var(LAYER1 M1)
define_fun SPACECHK la lb { space( la lb < 0.5 ) }
RULE chk {
    CALL_FUN( SPACECHK MET1 5 )   ← 展开体恢复为 CALL_FUN，入参更新
}
```

### 场景 C：修改非入参（0.5 → 1.0）

修改：`0.5` (pos=160-162) → `1.0`

这是 FUNC 标记内、但不在入参区域（0.5 是函数 body 硬编码值）。

逆向输出：
```
var(LAYER1 M1)
define_fun SPACECHK la lb { space( la lb < 0.5 ) }
RULE chk {
    /*:F:SPACECHK:la=LAYER1:lb=5*/
    space( /*:V:LAYER1=M1*/ M1 /*:V*/ 5 < 1.0 )   ← 保持展开，应用修改
    /*:FEND*/
}
```

### 场景 D：未修改任何入参

修改：无

逆向输出：
```
var(LAYER1 M1)
define_fun SPACECHK la lb { space( la lb < 0.5 ) }
RULE chk {
    CALL_FUN( SPACECHK LAYER1 5 )   ← 恢复为完整的 CALL_FUN
}
```

---

## 六、文件清单

| 文件 | 说明 |
|------|------|
| `expand_macros.py --annotate` | 展开时嵌入标记（新增功能） |
| `full_token_editor` | 修改展开文本（不变） |
| `revert_expanded.py` | 逆向重建脚本（新增） |
| `DESIGN_ROUNDTRIP.md` | 本设计文档 |
