# PLAN-004: ccs 内化模型管理与 provider/model 接口

> 日期: 2026-05-08
> 状态: 计划中
> 范围: 先完成 Claude Code；Codex/OpenCode 只保留接口预留

## 1. 背景

当前 `ccs` 已经可以用 tmux 管理多个 Claude Code 会话，并通过 `--cc-model` 为每个会话生成独立 settings。

现有问题：

- 主路径仍依赖用户理解 `claude-switch profile`
- 用户需要先知道 `claude-switch list`
- `deepseek-flash` 这类 profile 名称不如 `provider/model` 清晰
- `claude-switch` 和 `ccs` 是两个命令，增加认知负担
- API key 如果由工具托管，会引入额外安全风险

新的方向：

- `ccs` 成为唯一主命令
- 模型统一表达为 `provider/model`
- 内置常见 provider 和模型映射
- 用户不需要配置 profile 就能切换常用模型
- 不管理、不持久化 API key，只读取环境变量
- `claude-switch` 保留为兼容命令，但不再作为主入口

## 2. 目标

### 2.1 用户目标

用户可以用极低负担启动多个独立 Claude Code 会话：

```bash
ccs claude --cc-model ds/flash
ccs claude --cc-model ds/pro --cc-name backend
ccs claude --cc-model or/kimi-k2.6 --cc-name review
ccs claude --cc-model sonnet --cc-name plan
```

每个会话是：

```text
一个代码工具 + 一个模型 + 一个项目目录 + 一组原始工具参数
```

第一阶段只完整支持：

```text
Claude Code + provider/model + tmux session
```

### 2.2 产品目标

- `ccs --help` 能让用户直接学会使用
- `ccs models` 能直接看到可用模型
- `ccs providers` 能直接看到需要设置哪些环境变量
- `ccs claude --help` 仍然是原始 Claude help
- `ccs` 不截获 Claude 原始参数，只解析 `--cc-*`
- `ccs` 不存储用户 API key

## 3. 非目标

本阶段不做：

- 不实现 Codex/OpenCode 的完整 adapter
- 不实现 API key 管理命令，例如 `ccs key set`
- 不把 API key 写入自有长期配置文件
- 不引入远程网关或代理服务
- 不改变 Claude Code 本身的模型选择机制
- 不删除 `claude-switch` 兼容命令

## 4. 用户接口定义

### 4.1 启动 Claude 托管会话

```bash
ccs claude [claude args...] --cc-model <model-spec> [ccs options]
```

示例：

```bash
ccs claude --cc-model ds/flash
ccs claude --cc-model ds/pro --permission-mode acceptEdits
ccs claude --cc-model or/kimi-k2.6 --cc-name review
ccs claude --cc-model mm/m2.7 --cc-project ~/work/app
ccs claude --cc-model sonnet --cc-name plan
```

规则：

- `--cc-model` 的值使用新的 `model-spec`
- `model-spec` 推荐格式为 `provider/model`
- 没有 `--cc-*` 时完全透传给原始 `claude`
- `ccs` 只解析 `--cc-*`
- Claude 原始参数保持顺序并原样传递
- `--cc-name` 不填时自动生成会话名
- `--cc-project` 不填时使用当前目录
- 每个会话生成独立 Claude settings

### 4.2 原始 Claude 透传

```bash
ccs claude --help
ccs claude auth
ccs claude doctor
ccs claude mcp list
```

规则：

- 不创建 tmux session
- 不解析模型
- 不读取 provider API key
- 返回码等于原始 `claude`

### 4.3 查看内置模型

新增：

```bash
ccs models
ccs models <provider>
ccs models --json
```

默认输出：

```text
Provider     Alias     Model Spec                    Actual Model
----------------------------------------------------------------------------
anthropic    an        sonnet                        sonnet
anthropic    an        opus                          opus
deepseek     ds        ds/flash                      deepseek-v4-flash
deepseek     ds        ds/pro                        deepseek-v4-pro
openrouter   or        or/kimi-k2.6                  moonshotai/kimi-k2.6
openrouter   or        or/glm-5                      z-ai/glm-5
minimax      mm        mm/m2.7                       minimax-m2.7
```

规则：

- 只展示模型名称，不展示 API key
- `ccs models ds` 只展示 DeepSeek 模型
- `ccs models --json` 输出稳定 JSON，方便脚本使用
- 自定义 profile 可以单独显示在 `Custom profiles` 区域

### 4.4 查看 provider

新增：

```bash
ccs providers
ccs providers --json
```

默认输出：

```text
Provider     Aliases       Env Key              Key
-------------------------------------------------------
anthropic    an            ANTHROPIC_API_KEY    set
deepseek     ds            DEEPSEEK_API_KEY     missing
openrouter   or            OPENROUTER_API_KEY   set
minimax      mm            MINIMAX_API_KEY      missing
```

规则：

- 只显示 `set` / `missing`
- 不打印 API key 内容
- 不读取自有密钥文件
- provider 缺少 key 时，在创建会话前报错

### 4.5 解析单个模型

新增：

```bash
ccs model show <model-spec>
```

示例：

```bash
ccs model show ds/flash
ccs model show or/kimi-k2.6
ccs model show deepseek-flash
ccs model show sonnet
```

输出：

```text
Input:       ds/flash
Provider:    deepseek
Env Key:     DEEPSEEK_API_KEY
Key:         set
Model:       deepseek-v4-flash
Canonical:   deepseek/flash
Source:      builtin
```

规则：

- 用于解释 `--cc-model` 会如何被解析
- 不打印 API key
- 不创建会话
- 不写 settings

### 4.6 切换已有会话

继续保留：

```bash
ccs switch <name> [model-spec]
```

示例：

```bash
ccs switch backend ds/pro
ccs switch review or/kimi-k2.6
ccs switch plan sonnet
ccs switch backend
ccs switch backend ds/flash --create
```

规则：

- 传 `model-spec` 时切换模型并重启
- 不传 `model-spec` 时沿用当前模型重启
- `--create` 允许在会话不存在时创建
- `--create` 未传 `model-spec` 时使用 `default`
- `switch` 是管理命令，不透传 Claude 原始参数

## 5. model-spec 规范

### 5.1 推荐格式

```text
provider/model
```

含义：

- `provider` 表示 API key 和 endpoint 的来源
- `model` 表示该 provider 下的模型别名或实际模型 ID

示例：

```text
ds/flash
ds/pro
or/kimi-k2.6
or/glm-5
mm/m2.7
anthropic/sonnet
```

### 5.2 Provider 内置别名

| Canonical | Aliases | Env Key |
| --- | --- | --- |
| `anthropic` | `an`, `anthropic` | `ANTHROPIC_API_KEY` |
| `deepseek` | `ds`, `deepseek` | `DEEPSEEK_API_KEY` |
| `openrouter` | `or`, `openrouter` | `OPENROUTER_API_KEY` |
| `minimax` | `mm`, `minimax` | `MINIMAX_API_KEY` |

### 5.3 内置模型映射

| Model Spec | Actual Model | Legacy Profile |
| --- | --- | --- |
| `sonnet` | `sonnet` | `sonnet` |
| `opus` | `opus` | `opus` |
| `haiku` | `haiku` | `haiku` |
| `default` | `default` | `default` |
| `ds/flash` | `deepseek-v4-flash` | `deepseek-flash` |
| `ds/pro` | `deepseek-v4-pro` | `deepseek-pro` |
| `mm/m2.7` | `minimax-m2.7` | `minimax-m2.7` |
| `or/kimi-k2.6` | `moonshotai/kimi-k2.6` | `openrouter/kimi-k2.6` |
| `or/glm-5` | `z-ai/glm-5` | `openrouter/glm-5` |
| `or/gemini-2.5-flash` | `google/gemini-2.5-flash` | `openrouter/gemini-flash` |

### 5.4 兼容输入

以下输入继续支持：

```bash
ccs claude --cc-model deepseek-flash
ccs claude --cc-model deepseek-pro
ccs claude --cc-model openrouter/kimi-k2.6
ccs claude --cc-model minimax-m2.7
```

兼容规则：

- 旧 profile 名称能解析到对应 `provider/model`
- 自定义 profile 继续支持，但作为高级能力
- 带 `/` 的输入优先按 `provider/model` 解析
- 不带 `/` 的输入先匹配内置短名，再匹配旧 profile

### 5.5 OpenRouter 特殊支持

OpenRouter 本身使用 `author/model` 作为模型 ID，例如：

```text
moonshotai/kimi-k2.6
z-ai/glm-5
google/gemini-2.5-flash
```

但 `ccs` 的用户接口仍保持严格的两段式：

```text
provider/model
```

因此 OpenRouter 使用本地模型别名映射：

```text
or/kimi-k2.6          -> moonshotai/kimi-k2.6
or/glm-5              -> z-ai/glm-5
or/gemini-2.5-flash   -> google/gemini-2.5-flash
```

解析结果：

```text
input        = or/kimi-k2.6
provider     = openrouter
model        = kimi-k2.6
actual_model = moonshotai/kimi-k2.6
```

规则：

- `model-spec` 严格保持 `provider/model`
- OpenRouter 的 `author/model` 只出现在内部 `actual_model`
- 常用 OpenRouter 模型提供内置别名
- 内置列表只放常用示例，不把所有模型都做简称
- 不推荐 `or/kimi`、`or/glm` 这类过短简称，避免含义不稳定
- 旧 profile 名称继续兼容，例如 `openrouter/kimi-k2.6`

为了支持任意 OpenRouter 模型，新增本地模型映射命令：

```bash
ccs models add or/qwen3-coder qwen/qwen3-coder
ccs models add or/my-sonnet anthropic/claude-sonnet-4
```

规则：

- 左侧必须是严格 `provider/model-alias`
- 右侧是 provider 接收的真实模型 ID
- 该映射不保存 API key
- 该映射只保存模型名和 provider 信息
- `ccs models rm or/qwen3-coder` 删除映射
- `ccs models` 同时展示内置模型和用户自定义模型映射

### 5.6 未知输入错误

示例：

```bash
ccs claude --cc-model flash
```

错误：

```text
Error: unknown model spec 'flash'

Try:
  ccs models
  ccs claude --cc-model ds/flash
```

## 6. API Key 策略

### 6.1 明确不做密钥管理

`ccs` 不提供：

```bash
ccs key set
ccs store-key
ccs provider login
```

原因：

- 本地文件保存 API key 会扩大泄露面
- 第三方程序可能读取用户目录下的配置文件
- 不同系统的密钥存储方案差异大
- 极简 CLI 不应该承担 secret manager 职责

### 6.2 只读取环境变量

用户自己设置：

```bash
export DEEPSEEK_API_KEY="sk-xxx"
export OPENROUTER_API_KEY="sk-or-v1-xxx"
export MINIMAX_API_KEY="sk-xxx"
```

`ccs` 只读取：

```text
ANTHROPIC_API_KEY
DEEPSEEK_API_KEY
OPENROUTER_API_KEY
MINIMAX_API_KEY
```

### 6.3 缺少 key 的行为

创建或切换到第三方 provider 时，如果环境变量缺失：

```text
Error: DEEPSEEK_API_KEY is not set for provider 'deepseek'

Set it with:
  export DEEPSEEK_API_KEY="sk-..."
```

规则：

- 缺少 key 时不创建会话
- 缺少 key 时不写 settings
- `ccs models` 不要求 key
- `ccs model show` 可以显示 `Key: missing`

### 6.4 会话 settings 中的 token 风险

Claude Code 当前通过 settings 接收 provider 配置时，可能需要把 token 写入会话 settings。

本阶段策略：

- `ccs` 不把 key 写入长期 profile 文件
- 会话 settings 只作为运行期文件
- 会话 settings 权限固定为 `0600`
- `ccs kill <name>` 删除对应 settings
- `ccs switch <name> default` 删除旧 settings
- README 明确说明该限制

如果未来 Claude Code 支持在 settings 中引用环境变量而不是展开 token，应优先改成环境变量引用，避免 token 出现在任何文件中。

## 7. 内部数据模型

新增内部 registry 模块，建议文件：

```text
claude_switch/models.py
```

### 7.1 ProviderSpec

```python
@dataclass(frozen=True)
class ProviderSpec:
    id: str
    aliases: tuple[str, ...]
    name: str
    base_url: str | None
    env_key: str | None
    auth_mode: str
    desc: str
```

### 7.2 ModelSpec

```python
@dataclass(frozen=True)
class ModelSpec:
    provider: str
    name: str
    actual_model: str
    aliases: tuple[str, ...]
    legacy_profiles: tuple[str, ...]
    desc: str
```

### 7.3 ResolvedModel

```python
@dataclass(frozen=True)
class ResolvedModel:
    input: str
    provider: str
    provider_alias: str
    model: str
    actual_model: str
    canonical: str
    legacy_profile: str | None
    source: Literal["builtin", "legacy_profile", "custom_profile", "custom_mapping"]
    env_key: str | None
    env_is_set: bool
```

## 8. 模型解析算法

输入：`model-spec`

流程：

1. 如果输入包含 `/`，按严格 `provider/model` 解析
2. 将 provider alias 归一化，例如 `ds -> deepseek`
3. 在该 provider 下解析 model alias，例如 `flash -> deepseek-v4-flash`
4. 如果 provider 是 `openrouter`，将 model alias 映射到 OpenRouter 真实 `author/model`
5. 如果 provider/model 不存在，再匹配用户自定义模型映射
6. 如果仍不存在，再检查是否是旧 profile 名称
7. 如果输入不包含 `/`，先匹配内置短名，例如 `sonnet`
8. 再匹配旧 profile，例如 `deepseek-flash`
9. 再匹配自定义 profile
10. 全部失败时报错，并提示 `ccs models`

冲突处理：

- `provider/model` 优先级高于旧 profile
- 内置短名优先级高于自定义 profile
- 自定义 profile 如果与内置名冲突，输出 warning，仍使用内置名

## 9. 与现有 claude-switch 的关系

### 9.1 主入口迁移

新的主入口：

```bash
ccs models
ccs providers
ccs claude --cc-model ds/flash
```

旧入口继续可用：

```bash
claude-switch list
claude-switch deepseek-flash
```

### 9.2 代码复用

不应复制两套 provider/profile 逻辑。

建议拆分：

```text
claude_switch/models.py       provider/model registry 和解析
claude_switch/settings.py     ResolvedModel -> Claude settings
claude_switch/ccs.py          ccs CLI
claude_switch/__init__.py     claude-switch 兼容 CLI
```

### 9.3 兼容策略

- `claude-switch` 命令保留
- `claude-switch list` 可以逐步改为复用新 registry
- `claude-switch add` 继续服务高级自定义 profile
- README 主文档只推荐 `ccs`
- `claude-switch` 在 README 中移动到兼容和高级章节

## 10. ccs help 设计

`ccs --help` 必须包含完整可执行示例：

```text
QUICK START
  ccs models
  export DEEPSEEK_API_KEY="sk-..."
  ccs claude --cc-model ds/flash
  ccs list
  ccs switch api-review ds/pro
  ccs attach api-review

MODEL SPEC
  sonnet        Anthropic Sonnet
  ds/flash      DeepSeek Flash
  ds/pro        DeepSeek Pro
  or/kimi-k2.6  OpenRouter Kimi K2.6
  mm/m2.7       MiniMax M2.7

RULE
  ccs only parses --cc-*.
  Everything else after 'claude' is passed to Claude.
  Model spec is provider/model.
  OpenRouter author/model ids are mapped internally.

EXAMPLES
  ccs claude --help
  ccs claude --cc-model ds/flash --permission-mode acceptEdits
  ccs claude --cc-name review --cc-model or/kimi-k2.6 --add-dir ../shared
```

`ccs --help-zh` 使用中文解释同样内容。

## 11. 测试计划

新增或更新测试：

- `ds/flash` 解析为 `deepseek-v4-flash`
- `deepseek/flash` 解析为同一模型
- `ds/pro` 解析为 `deepseek-v4-pro`
- `or/kimi-k2.6` 解析为 `moonshotai/kimi-k2.6`
- `ccs models add or/qwen3-coder qwen/qwen3-coder` 可以新增 OpenRouter 映射
- `or/qwen3-coder` 解析为 `qwen/qwen3-coder`
- `sonnet` 解析为 Anthropic 原生模型
- `deepseek-flash` 旧 profile 输入继续可用
- 未知 provider 报错并提示 `ccs providers`
- 未知 model 报错并提示 `ccs models`
- 缺少 provider key 时创建会话失败
- `ccs providers` 不打印 key 内容
- `ccs providers --json` 输出合法 JSON
- `ccs models --json` 输出合法 JSON
- `ccs claude --help` 仍然透传原始 Claude
- `ccs` 不创建任何 API key 存储文件
- 会话 settings 权限为 `0600`

## 12. 实施顺序

### Phase 1: 文档和接口冻结

- 写入本计划
- 更新 README 的主路径
- 更新 `ccs --help`
- 更新 `ccs --help-zh`

### Phase 2: Registry 抽取

- 新增 `claude_switch/models.py`
- 定义 `ProviderSpec`
- 定义 `ModelSpec`
- 定义 `ResolvedModel`
- 实现 `resolve_model_spec()`
- 实现 `list_builtin_models()`
- 实现 `list_providers()`
- 实现用户自定义模型映射的读写，不包含 API key

### Phase 3: ccs 内化命令

- 新增 `ccs models`
- 新增 `ccs providers`
- 新增 `ccs model show <model-spec>`
- 新增 `ccs models add <provider/model-alias> <actual-model>`
- 新增 `ccs models rm <provider/model-alias>`
- `ccs claude --cc-model` 改用 `resolve_model_spec()`
- `ccs switch` 改用 `resolve_model_spec()`

### Phase 4: Settings 生成收口

- 新增 `claude_switch/settings.py`
- 将 `profile_to_settings()` 的核心逻辑迁移到 `ResolvedModel -> settings`
- 保留旧 profile 转 settings 的兼容入口
- 移除 `ccs` 对 `claude-switch` CLI 语义的直接依赖

### Phase 5: 兼容和清理

- `claude-switch` 复用新 registry
- README 把 `claude-switch` 降级为高级兼容命令
- 保留旧 profile 文件读取
- 不新增 key 存储文件

### Phase 6: 测试

- 补齐解析测试
- 补齐 CLI help 测试
- 补齐 JSON 输出测试
- 补齐缺 key 失败测试
- 补齐自定义 OpenRouter 模型映射测试
- 运行 `python test_ccs.py`

## 13. 验收标准

用户只需要知道以下命令就能完成主路径：

```bash
ccs models
export DEEPSEEK_API_KEY="sk-..."
ccs claude --cc-model ds/flash
ccs list
ccs switch <name> ds/pro
ccs attach <name>
```

必须满足：

- 不要求用户先运行 `claude-switch`
- 不要求用户创建 profile
- 不要求用户把 API key 交给 `ccs` 保存
- `ccs claude --help` 是原始 Claude help
- `ccs --help` 和 `ccs --help-zh` 能直接教会基本使用
- 旧命令 `claude-switch deepseek-flash` 不被破坏
