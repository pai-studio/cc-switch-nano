# PLAN-003: ccs Claude 会话闭环

> 日期: 2026-05-08
> 状态: 计划中
> 范围: 巩固 Claude 托管会话，不扩 Codex/OpenCode

## 1. 目标

在继续支持 Codex/OpenCode 之前，先把 Claude Code 的会话闭环做稳：

- 会话可创建、列出、进入、删除
- 会话可切换模型并重启
- 会话参数可被完整保留和复用
- 列表可被人读，也可被脚本读
- 行为可测试，不依赖真实 Claude 交互

本阶段不改变核心心智模型：

```bash
ccs claude --cc-model deepseek-flash --permission-mode acceptEdits
```

`ccs` 只解析 `--cc-*` 参数，其余参数全部属于 Claude。

## 2. 用户接口定义

### 2.1 启动托管会话

```bash
ccs claude [claude args...] --cc-model <profile> [ccs options]
```

示例：

```bash
ccs claude --cc-model deepseek-flash
ccs claude --cc-model sonnet --permission-mode acceptEdits
ccs claude --cc-model openrouter/kimi-k2.6 --add-dir ../shared
ccs claude --cc-model deepseek-pro --cc-name api-review
ccs claude --cc-model sonnet --cc-project ~/work/app
ccs claude --cc-model deepseek-flash --cc-no-attach
ccs claude --cc-model deepseek-flash --cc-dry-run
```

接口规则：

- 只有出现 `--cc-*` 时才进入托管模式
- 没有 `--cc-*` 时直接执行原始 `claude`
- `--cc-model` 的值是 `claude-switch` profile/model
- Claude 原始参数保持顺序并原样传递
- `--cc-name` 不填时自动生成
- `--cc-project` 不填时使用当前目录
- `--cc-dry-run` 不触碰 tmux，不写 settings

### 2.2 原始 Claude 透传

```bash
ccs claude --help
ccs claude auth
ccs claude doctor
ccs claude mcp list
```

接口规则：

- 以上命令不创建 tmux session
- 不读取 `claude-switch` profile
- 返回码等于原始 `claude` 返回码

### 2.3 列出会话

```bash
ccs list
ccs list --json
```

默认输出给人读：

```text
Name                                  Tool     Model                Project              PID      Status
--------------------------------------------------------------------------------------------------------
claude-deepseek-flash-app-1           claude   deepseek-flash       app                  12345    running
```

JSON 输出给脚本读：

```json
[
  {
    "name": "claude-deepseek-flash-app-1",
    "tool": "claude",
    "model": "deepseek-flash",
    "project": "/Users/me/work/app",
    "project_name": "app",
    "pid": 12345,
    "running": true,
    "tmux_session": "ccs",
    "tmux_window_index": 1,
    "settings": "/Users/me/.ccs/sessions/...",
    "argv": ["--permission-mode", "acceptEdits"]
  }
]
```

`ccs list --json` 规则：

- 输出合法 JSON 到 stdout
- 无会话时输出 `[]`
- 错误写 stderr，返回非零
- 不输出表头、提示语、颜色码

### 2.4 进入会话

```bash
ccs attach
ccs attach <name>
```

规则：

- 不传 name 时进入最近的会话
- 传 name 时进入指定会话
- 没有会话时报错：`Error: no sessions`
- 不存在时报错：`Error: session '<name>' not found`

### 2.5 删除会话

```bash
ccs kill <name>
```

规则：

- kill 对应 tmux window
- 删除该会话 settings 文件
- 不删除其他会话 settings
- 不存在时报错

### 2.6 切换/重启会话

推荐新增显式管理命令：

```bash
ccs switch <name> [profile]
```

示例：

```bash
ccs switch api-review deepseek-pro
ccs switch api-review sonnet
ccs switch api-review default
ccs switch api-review
```

行为：

- 找到已有会话
- 保留原工具、项目目录、Claude 透传参数
- 传入 profile 时，用新 profile 重新生成 settings
- 不传 profile 时，沿用当前模型重新生成 settings 并重启
- `default` 表示删除会话 settings，使用 Claude 默认配置
- 使用 `tmux respawn-window -k` 重启该 window
- 更新 tmux metadata

使用场景：

- 切换模型：`ccs switch api-review deepseek-pro`
- 原模型重启：`ccs switch api-review`
- 切回默认：`ccs switch api-review default`
- 重新加载更新后的 profile：`ccs switch api-review`

错误规则：

- 会话不存在：`Error: session '<name>' not found`
- profile 不存在：`Error: claude-switch profile '<profile>' not found`
- 项目目录不存在：`Error: project '<path>' no longer exists`
- 重启失败时保留旧 metadata，并提示用户手动检查 tmux

### 2.7 switch 创建模式

`switch` 默认只操作已有会话。为了降低常用场景成本，可以显式加 `--create`：

```bash
ccs switch <name> [profile] --create
```

示例：

```bash
ccs switch api-review deepseek-pro --create
ccs switch api-review --create
ccs switch api-review deepseek-pro --create --cc-project ~/work/app
ccs switch api-review deepseek-pro --create --cc-no-attach
```

规则：

- 会话存在时：行为等同普通 `switch`
- 会话不存在且有 `--create`：创建新会话
- 会话不存在且没有 `--create`：报错
- `--create` 未传 profile 时：使用 `default`
- `--create` 项目目录默认当前目录
- `--create` 支持 `--cc-project`
- `--create` 支持 `--cc-no-attach`
- `--create` 不支持 Claude 原始参数透传

不支持 Claude 原始参数透传的原因：

- `switch` 是管理命令，不是工具启动器
- 复杂创建应该使用完整启动接口：

```bash
ccs claude --cc-name api-review --cc-model deepseek-pro --permission-mode acceptEdits
```

### 2.8 创建或更新会话

`ccs claude --cc-name <name>` 可以作为完整创建/更新接口：

```bash
ccs claude --cc-name api-review --cc-model deepseek-pro
ccs claude --cc-name api-review --cc-model deepseek-pro --permission-mode acceptEdits
```

规则：

- `--cc-name` 指向不存在的会话：创建
- `--cc-name` 指向已有会话：更新并重启
- 未传 `--cc-model` 且会话已存在：沿用旧模型
- 未传 Claude args 且会话已存在：沿用旧 argv
- 传入 Claude args 且会话已存在：替换旧 argv
- 不传 `--cc-name`：永远创建自动命名的新会话

`--cc-reuse` 废弃，不再推荐。

## 3. 内部接口定义

### 3.1 CodeSession

```python
@dataclass
class CodeSession:
    name: str
    tool: str
    model: str
    project: str
    index: int
    pid: int | None
    running: bool
    settings: str
    argv: list[str]
```

要求：

- `settings` 为空字符串表示默认配置
- `argv` 是原工具透传参数，不包含 `claude`、`--settings`、自动 `--name`
- `project_name` 保持 property
- JSON 输出直接由该结构转换

### 3.2 SessionManager 公共方法

```python
class SessionManager:
    def list(self) -> list[CodeSession]: ...
    def attach(self, name: str | None = None) -> None: ...
    def kill(self, name: str) -> None: ...
    def create_claude(
        self,
        *,
        name: str | None,
        project: str,
        model: str | None,
        passthrough: list[str],
        attach: bool,
        dry_run: bool,
    ) -> CodeSession | None: ...
    def switch_model(
        self,
        *,
        name: str,
        model: str | None,
        passthrough: list[str] | None = None,
        create: bool = False,
        project: str = ".",
        attach: bool = False,
    ) -> CodeSession: ...
```

### 3.3 tmux metadata

继续使用 window options：

| Option | 说明 |
| --- | --- |
| `@ccs_tool` | `claude` |
| `@ccs_model` | 当前 profile/model |
| `@ccs_project` | 绝对项目目录 |
| `@ccs_settings` | settings 文件路径，默认配置时为空 |
| `@ccs_argv` | JSON 编码的原工具透传参数 |

新增要求：

- `list()` 必须读取 `@ccs_settings`
- `list()` 必须读取并解析 `@ccs_argv`
- `@ccs_argv` 解析失败时返回空列表并保留会话可见

### 3.4 Claude settings 生成

内部函数：

```python
def write_claude_settings(model: str, path: Path) -> None
```

规则：

- 使用 `load_profiles()` + `fuzzy_match()` + `profile_to_settings()`
- 不调用外部 `claude-switch --dry-run` 子进程
- 写入 JSON 使用 `ensure_ascii=False`
- 文件权限为 `0600`
- profile 不存在抛 `RuntimeError`

### 3.5 Claude 启动 argv

内部函数：

```python
def build_claude_argv(
    session_name: str,
    settings: Path | None,
    passthrough: list[str],
) -> list[str]
```

规则：

- 总是以 `["claude"]` 开头
- 有 settings 时追加 `["--settings", str(settings)]`
- 如果 passthrough 未包含 `--name` 或 `-n`，自动追加 `["--name", session_name]`
- 最后追加 passthrough

## 4. CLI 解析规则

### 4.1 `--cc-*`

`ccs claude ...` 中只解析：

```text
--cc-model <profile>
--cc-name <name>
--cc-project <dir>
--cc-no-attach
--cc-reuse <name>
--cc-dry-run
```

未知 `--cc-*` 必须报错。

非 `--cc-*` 参数必须保留原顺序。

### 4.2 管理命令参数

```text
ccs list [--json]
ccs attach [name]
ccs kill <name>
ccs switch <name> [profile] [--create] [--cc-project DIR] [--cc-no-attach]
```

管理命令不透传参数。

未知参数报错并返回 2。

`switch` 参数规则：

- `profile` 可选
- `--create` 可选
- `--cc-project` 仅在 `--create` 且会话不存在时生效
- `--cc-no-attach` 仅在 `--create` 且会话不存在时生效
- 不接受其他 Claude 原始参数

## 5. 测试计划

### 5.1 不依赖 tmux 的单元测试

| ID | 场景 | 预期 |
| --- | --- | --- |
| T1 | 解析 `ccs claude --help` | passthrough 为 `["--help"]`，managed=false |
| T2 | 解析 `--cc-model deepseek-flash --permission-mode acceptEdits` | model 正确，Claude 参数保序 |
| T3 | 未知 `--cc-foo` | 返回解析错误 |
| T4 | build argv 有 settings | 包含 `--settings` 和自动 `--name` |
| T5 | build argv 已有 `--name` | 不再自动追加 name |
| T6 | profile 不存在 | 抛 RuntimeError |
| T7 | settings 写入 | JSON 正确，权限 `0600` |
| T8 | 自动命名 | 名称 tmux-safe，按序号递增 |

### 5.2 隔离 tmux 集成测试

通过子类覆盖 `_raw()`，使用 `tmux -L <socket>`：

| ID | 场景 | 预期 |
| --- | --- | --- |
| I1 | create + list | 会话可见，metadata 正确 |
| I2 | create + kill | window 删除，settings 清理 |
| I3 | switch model | 同 window 重启，model/settings/argv 更新 |
| I4 | switch default | settings 清空，旧文件删除 |
| I5 | list --json | 输出合法 JSON |

### 5.3 手动验收

```bash
ccs --help
ccs --help-zh
ccs claude --help
ccs claude --cc-model deepseek-flash --cc-dry-run
ccs claude --cc-model sonnet --cc-name test --cc-no-attach
ccs list
ccs list --json
ccs switch test deepseek-flash
ccs switch test
ccs switch maybe-new deepseek-flash --create
ccs kill test
```

## 6. 实施顺序

1. 扩展 `CodeSession` 字段：`settings`、`argv`
2. 让 `list()` 读取完整 metadata
3. 增加 `ccs list --json`
4. 实现 `SessionManager.switch_model()`
5. 增加 `ccs switch <name> [profile]`
6. 增加 `switch --create`
7. 增加单元测试和隔离 tmux 测试
8. 更新 README / `ccs --help` / `ccs --help-zh`

## 7. 非目标

本阶段不做：

- Codex adapter
- OpenCode adapter
- Textual TUI
- 远程任意模型网关
- profile CRUD 重构

这些进入后续 PLAN。
