# PLAN-002: ccs 统一会话命令

> 日期: 2026-05-08
> 状态: 实施中
> 首期范围: Claude Code + 任意 claude-switch 模型 + tmux 多会话

## 1. 目标

把 `claude_switch` 的模型/profile 能力和 `labs/b1-tmux-tui` 的 tmux 会话管理能力合并成一个低负担命令。

终极目标：

- 支持任意代码工具：Claude Code、Codex、OpenCode
- 支持任意模型/provider profile
- 管理多个独立会话
- 一个会话 = 一个代码工具 + 一个模型 + 一个项目目录 + 一个 tmux window
- 每个会话配置互相隔离，不覆盖项目级配置

首期只完整支持 Claude Code。

## 2. 用户接口

### 2.1 启动工具

用户把 `ccs` 当作工具启动器使用：

```bash
ccs claude --cc-model deepseek-flash
ccs claude --cc-model sonnet --permission-mode acceptEdits
ccs claude --help
```

规则：

- `ccs claude ...` 中，除 `--cc-*` 外的参数全部透传给原始 `claude`
- `ccs claude --help` 不创建会话，直接显示原始 `claude --help`
- `--cc-model` 表示 claude-switch profile/model，不使用 Claude 原生 `--model`
- 不要求用户指定 session name，默认自动生成

### 2.2 管理命令

保留极少量管理命令：

```bash
ccs list
ccs attach
ccs attach <name>
ccs kill <name>
```

这些命令不是工具名，不和原工具参数冲突。

`ccs tui` 暂不进入首期，避免为极简启动路径引入 Textual 依赖；后续确认命令体验稳定后再补。

## 3. 参数设计

`ccs` 只解析这些启动参数：

| 参数 | 说明 |
|------|------|
| `--cc-model <profile>` | 使用 claude-switch profile/model 生成会话配置 |
| `--cc-name <name>` | 指定会话名，不填则自动生成 |
| `--cc-project <dir>` | 指定项目目录，默认当前目录 |
| `--cc-no-attach` | 创建后不自动 attach |
| `--cc-reuse <name>` | 复用已有会话并重启 |
| `--cc-dry-run` | 打印将执行的命令和配置路径 |

避免使用 `--model`、`--name`、`--project` 等通用参数，防止和原工具冲突。

## 4. Claude 首期实现

### 4.1 会话配置

当用户指定 `--cc-model` 时：

1. 调用 `claude-switch --dry-run <profile>`
2. 写入会话级 settings：`~/.ccs/sessions/<name>.claude.settings.json`
3. 以 `0600` 权限保存 settings
4. 启动 Claude：

```bash
claude --settings <session-settings> <claude passthrough args...>
```

不指定 `--cc-model` 时：

- 不生成 settings
- 直接启动原始 `claude <passthrough args...>`
- Model 列显示 `default`

### 4.2 tmux 管理

所有会话放入 tmux session：`ccs`。

每个 tmux window 保存 metadata：

| Option | 说明 |
|--------|------|
| `@ccs_tool` | `claude` |
| `@ccs_model` | `deepseek-flash` / `default` |
| `@ccs_project` | 项目目录 |
| `@ccs_settings` | 会话 settings 文件 |
| `@ccs_argv` | 原工具透传参数 JSON |

### 4.3 自动命名

默认会话名：

```text
<tool>-<model>-<project>-<n>
```

示例：

```text
claude-deepseek-flash-cc-switch-nano-1
```

名称需要做 tmux-safe 处理。

## 5. 后续扩展

### Codex

首期只保留 adapter 位置，不承诺远程任意模型。

已知可支持路径：

```bash
codex --oss --local-provider ollama -m <model>
codex --oss --local-provider lmstudio -m <model>
```

OpenAI 之外的远程模型需要单独验证 Codex 是否支持自定义 base URL，或通过 LiteLLM/OpenAI-compatible 代理实现。

### OpenCode

后续新增 `OpenCodeAdapter`，把统一 profile 翻译为 opencode 自己的 provider/model 配置。

## 6. 实施步骤

1. 新增 `claude_switch/ccs.py` 作为统一命令入口
2. 新增 `claude_switch/session.py` 管理 tmux 会话
3. 从 `labs/b1-tmux-tui` 迁移必要的 tmux 管理逻辑
4. Claude adapter 生成会话 settings 和启动命令
5. `pyproject.toml` 新增 `ccs = "claude_switch.ccs:main"`
6. 保留 `claude-switch` 原命令不破坏兼容
7. 增加基础编译和隔离 tmux 行为验证
