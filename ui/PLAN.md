# PVRS Editor UI — 任务计划

## 目标

用 PyQt5 实现图形界面，完成 PVRS 文件的解析、浏览、修改、保存。

## 窗口布局

```
┌─────────────────────────────────────────────────────────────┐
│  文件(F)  编辑(E)  帮助(H)                     [状态栏]      │
├──────────────────┬──────────────────────────────────────────┤
│                  │  详情面板 (QTabWidget)                     │
│  容器列表         │  ┌─ 标注视图 ─┬─ 编号表 ─┬─ VAR/FUN ─┐ │
│  (QListWidget)   │  │           │          │           │ │
│                  │  │ 带标注的   │ 可编辑的  │ VAR/CALL   │ │
│  □ RULE chk1     │  │ 原文文本   │ token 表  │ FUN 引用   │ │
│  □ RULE chk2     │  │           │ 格        │ 信息       │ │
│  □ DEF P1        │  │           │          │           │ │
│                  │  │           │          │           │ │
│                  │  └───────────┴──────────┴───────────┘ │
├──────────────────┴──────────────────────────────────────────┤
│  底部信息栏：语法错误警告 / 修改计数 / 文件路径              │
└─────────────────────────────────────────────────────────────┘
```

## 功能模块

### 1. 文件操作（菜单栏）
- 打开 PVRS 文件 (`QFileDialog`)
- 保存修改 (`te.save()`)
- 另存为 (`te.save(output_path)`)
- 撤销所有修改 (`te.clear_changes()`)

### 2. 容器列表（左侧面板）
- 显示所有容器（RULE / DEF），含名称、类型、元素数
- 点击容器 → 右侧详情面板刷新
- 容器有修改时显示 `*` 标记

### 3. 详情面板（右侧，3 个 Tab）

#### Tab 1: 标注视图
- 显示 `annotated_text(c)[0]` 的渲染文本
- 用 QTextEdit 展示，可修改元素高亮
- `<<N:value>>` 中的 N 和 value 以不同颜色显示
- 不可修改文本灰色显示
- 双击标注元素 → 弹出编辑对话框

#### Tab 2: 编号表（核心编辑界面）
- QTableWidget，列：编号 | 类型 | 原文 | 新值 | 行号 | 状态
- "新值" 列可编辑，编辑后自动触发 `replace_by_index`
- "原文" 列支持双击 → 弹出确认对话框 → 批量 `replace_by_text`
- 修改后行变色标记

#### Tab 3: VAR/FUN 引用
- 显示当前容器引用的 VAR 定义 (`var_refs`)
- 显示当前容器引用的 CALL_FUN 定义 (`fun_refs`)
- 用 QTextEdit / QLabel 只读展示完整定义文本

### 4. 底部信息栏
- 文件路径
- 语法错误数量（红色警告）
- 暂存修改数量
- 容器/元素总数

## 数据流

```
用户打开文件
    │
    ▼
TokenEditor(filepath) → te
    │
    ├── te.container_names → 填充容器列表
    ├── te.parse_errors  → 状态栏警告
    │
    ▼ 用户点击容器
    │
te.annotated_text(name) → 标注视图展示
te.annotated_legend(name) → 编号表填充
te.var_refs(name) / te.fun_refs(name) → VAR/FUN 面板
    │
    ▼ 用户编辑表格
    │
te.replace_by_index() 或 te.replace_by_text()
    │
    ▼ 刷新详情面板
    │
    ▼ 用户保存
    │
te.save() → 结果提示
```

## 任务分解

| 序号 | 任务 | 文件 | 说明 |
|------|------|------|------|
| 1 | 创建 ui 目录 | `ui/__init__.py` | |
| 2 | 主窗口框架 | `ui/main_window.py` | 菜单栏、工具栏、面板分区 |
| 3 | 容器列表面板 | `ui/container_list.py` | QListWidget + 自定义 item |
| 4 | 标注视图 Tab | `ui/annotated_view.py` | QTextEdit 渲染、高亮 |
| 5 | 编号表 Tab | `ui/legend_table.py` | QTableWidget 可编辑 |
| 6 | VAR/FUN 引用 Tab | `ui/var_fun_panel.py` | 只读文本展示 |
| 7 | 详情面板 | `ui/detail_panel.py` | 组合 3 个 Tab |
| 8 | 应用入口 | `ui/app.py` | `QApplication` + `MainWindow` |
| 9 | 编辑对话框 | `ui/edit_dialog.py` | 双击元素弹出编辑框 |
| 10 | 状态栏 | 内嵌在 main_window | 错误/修改/文件信息 |

## 依赖

```python
# requirements
PyQt5>=5.15
antlr4-python3-runtime==4.13.2
```

## 启动

```bash
python -m ui.app
# 或
python ui/app.py
```
