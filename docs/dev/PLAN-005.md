# PLAN-005: ccs session 管理 TUI

> 日期: 2026-05-08
> 状态: 计划中
> 范围: 先做 Claude Code session 管理 TUI，不做配置编辑器

## 1. 背景

`ccs` 已经具备 Claude Code 会话管理能力：

- `ccs claude --cc-model <model>`
- `ccs list`
- `ccs attach`
- `ccs kill`
- `ccs switch <name> [model]`
- `ccs models`
- `ccs providers`

现在缺少的是低负担的 session 管理入口。用户不应该频繁复制 session 名称，也不应该靠记忆命令完成 attach、kill、switch。

因此下一步做 `ccs tui`，目标是尽快把已有 CLI 能力可视化，而不是重新设计一套 session 系统。

## 2. 目标

### 2.1 用户目标

用户运行：

```bash
ccs tui
```

即可看到所有托管会话，并用键盘完成：

- 查看 session
- attach session
- 创建 Claude session
- 切换 session 模型
- kill session
- refresh

### 2.2 产品目标

- TUI 是 `ccs` 的 session dashboard
- TUI 不复制 session 逻辑
- TUI 直接调用 `SessionManager`
- TUI 使用现有 provider/model 语义
- TUI 默认低输入负担
- TUI 退出后不影响 tmux 中运行的会话

## 3. 非目标

本阶段不做：

- 不做 API key 管理
- 不做 provider 配置编辑
- 不做模型 profile 编辑器
- 不做 Codex/OpenCode session 管理
- 不做复杂多 pane 终端嵌入
- 不做 session 日志浏览
- 不做拖拽、鼠标优先交互
- 不做替代 tmux 的 terminal emulator

## 4. 用户接口定义

### 4.1 启动 TUI

```bash
ccs tui
```

规则：

- 不传参数时打开 session dashboard
- TUI 内所有操作作用于 tmux session `ccs`
- TUI 退出不 kill 任何 session
- 如果 `tmux` 缺失，显示错误并退出
- 如果没有 session，显示空表和创建提示

### 4.2 快捷键

| Key | Action | 说明 |
| --- | --- | --- |
| `Enter` | attach | 进入当前选中的 session |
| `n` | new | 新建 Claude session |
| `s` | switch | 切换当前 session 模型并重启 |
| `k` | kill | 删除当前 session |
| `r` | refresh | 刷新 session 列表 |
| `?` | help | 显示快捷键说明 |
| `q` | quit | 退出 TUI |

保留但不优先实现：

| Key | Action | 说明 |
| --- | --- | --- |
| `m` | models | 查看可用模型 |
| `p` | providers | 查看 provider/key 状态 |

原因：

- 第一版优先管理 session
- `ccs models` / `ccs providers` 已经能在 CLI 使用
- TUI 内模型列表可以第二阶段再做

## 5. 主界面设计

### 5.1 表格列

```text
Name                  Tool      Model          Project        PID      Status
----------------------------------------------------------------------------
api-review            claude    ds/flash       app            12345    running
plan                  claude    an/sonnet      app            12346    running
explore               claude    or/kimi-k2.6   sdk            -        stopped
```

字段来源：

- `Name`: `CodeSession.name`
- `Tool`: `CodeSession.tool`
- `Model`: `CodeSession.model`
- `Project`: `CodeSession.project_name`
- `PID`: `CodeSession.pid`
- `Status`: `running` / `stopped`

### 5.2 状态栏

底部显示：

```text
Enter attach  n new  s switch  k kill  r refresh  ? help  q quit
```

### 5.3 空状态

没有 session 时显示：

```text
No sessions.
Press n to create a Claude session.
```

## 6. 操作流程

### 6.1 Attach

用户按：

```text
Enter
```

行为：

- 获取当前选中 session
- 退出 TUI
- 调用 `SessionManager.attach(name)`

实现注意：

- 如果在 TUI 内直接 attach tmux，终端状态可能和 Textual 冲突
- 推荐 TUI 返回一个 action 给 `ccs.py`
- `ccs.py` 在 TUI 退出后执行 attach

建议接口：

```python
result = CcsTuiApp().run()
if result == ("attach", name):
    SessionManager().attach(name)
```

### 6.2 New Session

用户按：

```text
n
```

弹窗字段：

```text
Name:    optional, empty means auto-generate
Model:   default ds/flash
Project: default current working directory
Args:    optional Claude args
```

示例输入：

```text
Name:
Model:   ds/flash
Project: .
Args:    --permission-mode acceptEdits
```

行为：

- `Name` 为空时传 `name=None`
- `Model` 为空时使用 `ds/flash`
- `Project` 为空时使用 `.`
- `Args` 使用 `shlex.split()`
- 调用：

```python
SessionManager().create_claude(
    name=name or None,
    project=project or ".",
    model=model or "ds/flash",
    passthrough=args,
    attach=False,
    dry_run=False,
)
```

新建后：

- 刷新表格
- 选中新建 session
- 不自动 attach

理由：

- TUI 是管理面板，不应该新建后立刻打断用户
- 用户可以再按 `Enter` attach

### 6.3 Switch Model

用户按：

```text
s
```

弹窗字段：

```text
Current: ds/flash
Model:   ds/pro
```

行为：

- `Model` 为空则取消
- 调用：

```python
SessionManager().switch_model(
    name=session.name,
    model=model,
    attach=False,
)
```

成功后：

- 刷新表格
- 保持当前 session 选中

错误：

- unknown model spec
- missing API key
- project no longer exists
- tmux respawn failed

错误通过 TUI notification 展示，不退出 TUI。

### 6.4 Kill Session

用户按：

```text
k
```

弹窗：

```text
Kill session 'api-review'?
[Kill] [Cancel]
```

行为：

- 确认后调用 `SessionManager.kill(name)`
- 刷新表格
- 清理对应 settings 文件

### 6.5 Refresh

用户按：

```text
r
```

行为：

- 调用 `SessionManager.list()`
- 刷新表格

### 6.6 Help

用户按：

```text
?
```

显示 modal：

```text
Enter  attach selected session
n      new Claude session
s      switch selected session model
k      kill selected session
r      refresh
q      quit
```

## 7. 技术方案

### 7.1 依赖选择

优先使用 Textual。

原因：

- `labs/b1-tmux-tui` 已有 Textual TUI 原型
- DataTable、ModalScreen、Footer 已经满足第一版
- 不需要自己处理复杂终端绘制

需要更新 `pyproject.toml`：

```toml
dependencies = [
  "textual>=0.80",
]
```

如果希望保持零依赖，需要改成 curses。但 curses 在 macOS/Linux 兼容性和输入体验上会增加实现成本，不适合当前“尽快管理 session”的目标。

### 7.2 文件结构

新增：

```text
claude_switch/tui.py
```

修改：

```text
claude_switch/ccs.py
pyproject.toml
README.md
test_ccs.py
```

不直接复用：

```text
labs/b1-tmux-tui/cc_tmux/manager.py
```

原因：

- 旧 manager 使用 `cc-tmux` 语义
- 当前主逻辑已经在 `claude_switch/session.py`
- TUI 应该调用 `SessionManager`，避免两套行为分叉

可参考复用：

```text
labs/b1-tmux-tui/cc_tmux/tui.py
```

可复用内容：

- `DataTable` 布局
- `ModalScreen` 模式
- button/input 交互结构
- notification 方式

需要替换内容：

- `Manager` -> `SessionManager`
- `m` model 快捷键 -> `s` switch 快捷键
- `name required` -> `name optional`
- `model/profile` 文案 -> `provider/model`
- 默认 model -> `ds/flash`

### 7.3 ccs.py 集成

新增 management command：

```python
MANAGEMENT = {..., "tui"}
```

新增：

```python
def _run_tui(args: list[str]) -> None:
    if args:
        raise SystemExit("ccs: usage: ccs tui")
    from .tui import run_tui
    action = run_tui()
    if action and action[0] == "attach":
        SessionManager().attach(action[1])
```

### 7.4 TUI 对 SessionManager 的调用

读取：

```python
sessions = SessionManager().list()
```

创建：

```python
SessionManager().create_claude(...)
```

切换：

```python
SessionManager().switch_model(...)
```

删除：

```python
SessionManager().kill(...)
```

attach：

```python
return ("attach", name)
```

## 8. 错误处理

### 8.1 Textual 未安装

如果用户运行 `ccs tui` 但缺少 Textual：

```text
Error: textual is required for ccs tui.
Install with:
  pip install -e .
```

如果 `pyproject.toml` 已声明 dependency，正常安装不会遇到。

### 8.2 tmux 不存在

```text
Error: tmux not found
```

TUI 不启动。

### 8.3 Claude 不存在

新建 session 时由 `SessionManager` 或实际启动命令暴露错误。

如果能提前检查，更好：

```text
Error: claude not found
```

但不作为第一版必需。

### 8.4 API key 缺失

例如用户切换到 `ds/flash` 但没有 `DEEPSEEK_API_KEY`：

```text
DEEPSEEK_API_KEY is not set for provider 'deepseek'
export DEEPSEEK_API_KEY="sk-..."
```

通过 notification 展示。

## 9. 测试计划

第一版不做完整 Textual UI 自动化测试，只做薄层可测逻辑：

- `ccs tui --bad` 返回 usage error
- `ccs --help` 包含 `ccs tui`
- `run_tui()` import Textual 缺失时错误清晰
- New modal result name 可为空
- New modal args 使用 `shlex.split`
- TUI action attach 返回 `("attach", name)`，不在 Textual 内直接 attach

手工验收：

```bash
ccs tui
```

验收项：

- 空 session 能打开
- `n` 可创建 `ds/flash` session
- 表格显示新 session
- `s` 可切到 `ds/pro`
- `k` 可 kill session
- `Enter` 可 attach
- `q` 可退出且 session 不受影响

## 10. 实施顺序

### Phase 1: 文档冻结

- 写入本计划

### Phase 2: 依赖和命令入口

- `pyproject.toml` 增加 `textual`
- `ccs --help` 增加 `ccs tui`
- `ccs --help-zh` 增加 `ccs tui`
- `ccs.py` 增加 `tui` management command

### Phase 3: TUI MVP

- 新增 `claude_switch/tui.py`
- 实现 session table
- 实现 refresh
- 实现 attach action return
- 实现 kill confirm

### Phase 4: 创建和切换

- 实现 new session modal
- name 允许为空
- model 默认 `ds/flash`
- project 默认 `.`
- args 支持 `shlex.split`
- 实现 switch model modal

### Phase 5: 验证

- 运行 `python test_ccs.py`
- 运行 `python -m compileall claude_switch`
- 手工运行 `ccs tui`

## 11. 验收标准

必须满足：

- `ccs tui` 可启动
- 不需要用户输入 session name 即可新建 session
- 默认模型为 `ds/flash`
- TUI 中能 attach、new、switch、kill、refresh
- TUI 不保存 API key
- TUI 不直接编辑 provider/profile 配置
- TUI 退出不影响 tmux session
- 所有实际 session 操作复用 `SessionManager`

