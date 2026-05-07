# PLAN-001: cc-switch 设计审查与下一步计划

> 版本: v0.4.0 → v1.0.0 路线图
> 日期: 2026-05-07
> 状态: 审查完成，计划中

---

## 1. 当前设计审查

### 1.1 架构总览

```
┌─────────────┐     ┌───────────────┐     ┌──────────────────┐
│  Provider   │────→│   Profile     │────→│  settings.json   │
│  预设(锁定)  │     │  用户配置      │     │  claude-code 读   │
└─────────────┘     └───────────────┘     └──────────────────┘
   base_url 锁定       model + aliases       ANTHROPIC_MODEL
   env_key 绑定        auth_token(可选)       ANTHROPIC_BASE_URL
   auth_mode           settings(预留)         ANTHROPIC_AUTH_TOKEN
                       raw(预留)             ANTHROPIC_DEFAULT_*_MODEL
```

字段解析链：`Profile 显式值 → Provider 预设 → $ENV_VAR → 不写入`

### 1.2 已实现功能

| 功能 | 状态 | 说明 |
|------|------|------|
| Provider 预设系统 | ✅ | 3 个内置 (anthropic/deepseek/minimax)，支持自定义 |
| base_url 锁定 | ✅ | 内置 provider 的 base_url 不可被 profile 覆盖 |
| env_key 绑定 | ✅ | 每个 provider 绑定环境变量名 (如 $DEEPSEEK_API_KEY) |
| 字段解析链 | ✅ | Profile → Provider → Env → Skip 四级 fallback |
| 翻译引擎 | ✅ | 通用 profile → claude settings.json 完整映射 |
| aliases 场景映射 | ✅ | haiku/sonnet/opus 映射到具体模型 |
| 交互式 picker | ✅ | 按 provider 分组，编号+名称+fuzzy 匹配 |
| 切换回退 (-) | ✅ | 从历史记录回退到上一个 |
| 三层作用域 | ✅ | -u (user) / 默认 (project) / -l (local) |
| 子命令体系 | ✅ | list, show, log, providers, add, add-provider, rm |
| 兼容旧格式 | ✅ | 字符串 profile 自动归一化为 dict |

### 1.3 设计评分

| 维度 | 评分 | 说明 |
|------|------|------|
| Provider/Profile 分离 | ★★★★★ | 职责清晰，base_url 锁定正确 |
| 字段解析链 | ★★★★★ | 四级 fallback 设计正确 |
| 翻译引擎 | ★★★★☆ | 覆盖了主要字段，settings/raw 未打通 |
| 用户体验 | ★★★★☆ | picker 好用，但缺 edit/dry-run/preview |
| 错误处理 | ★★★☆☆ | 提示信息不够统一，缺验证 |
| 代码质量 | ★★★★☆ | 单文件 676 行，结构清晰，缺测试 |
| 可扩展性 | ★★★★☆ | provider 可扩展，但 profile schema 未完整体现 |

### 1.4 已发现的问题

#### Bug
1. **apply_profile 残留字段**：`cur.update(data)` 对 `env` 做了浅覆盖是正确的，但如果旧 settings 有 `alwaysThinkingEnabled: true` 而新 profile 没设，会残留。需显式清理。
2. **write_json 未使用**：line 76 的 `write_json` 函数被定义但不再被调用，应删除。
3. **profile_to_settings line 163**: `model = profile.get("model") or profile.get("model")` 自身重复，没意义。

#### UX 缺失
4. **无 edit 命令**：创建后无法修改，只能手动编辑 JSON。
5. **无 dry-run**：无法预览切换后的 settings.json 内容。
6. **无 inspect**：`list` 只有摘要，无法看单个 profile 的完整详情。
7. **无 profile 验证**：添加时不做任何合法性校验（provider 存不存在、model 是否为空）。
8. **add 缺 --thinking/--timeout**：settings/raw 字段在 schema 中有定义，但 CLI 无法设。

#### 健壮性
9. **find_project_root()**：只在目标目录有 `.claude/` 时才返回，否则回退到 cwd。从项目子目录运行会找不到。
10. **无配置迁移**：profile 格式变化时无版本号，无自动升级。
11. **无 shell 补全**：不支持 bash/zsh/fish 的 tab 补全。

---

## 2. 下一步计划 — 按优先级分阶段

### Phase 1: 打磨完善 (v0.5.0) ⭐⭐⭐

目标：修复 bug，补齐基本体验

| ID | 任务 | 说明 |
|----|------|------|
| P1.1 | 修复 apply_profile 残留 | 切换 profile 时清理上一个 profile 的 extra 字段 (alwaysThinkingEnabled 等) |
| P1.2 | 删除 dead code | 移除未使用的 `write_json`，修正重复表达式 |
| P1.3 | dry-run 模式 | `cc-switch <name> --dry-run` 只输出将要写入的 JSON，不实际写入 |
| P1.4 | preview 模式 | 在 picker 中选择后先展示 preview，确认再写入 (`cc-switch --preview`) |
| P1.5 | profile 详情 | `cc-switch show <name>` 展示单个 profile 的完整配置（含解析后的 token 来源） |
| P1.6 | 验证 add 参数 | provider 存在性检查、model 非空、name 不与内置/已有冲突 |
| P1.7 | 统一错误信息 | 所有错误输出格式统一，中英文消息归类 |
| P1.8 | find_project_root 增强 | 从任意子目录向上查找 `.claude/`，兜底创建 `.claude/` |

### Phase 2: CRUD 完整化 (v0.6.0) ⭐⭐⭐

目标：补齐 profile 的全生命周期管理

| ID | 任务 | 说明 |
|----|------|------|
| P2.1 | edit 命令 | `cc-switch edit <name>` 用 `$EDITOR` (或 vi/vim/nano) 打开 profile JSON 编辑 |
| P2.2 | edit --field 直改 | `cc-switch edit <name> --haiku M --sonnet M` 直接修改字段 |
| P2.3 | clone 命令 | `cc-switch clone <src> <dst>` 复制 profile |
| P2.4 | rename 命令 | `cc-switch rename <old> <new>` 重命名 |
| P2.5 | settings 字段曝光 | `add --thinking` / `--timeout N` / `--no-telemetry` 控制 settings 字段 |
| P2.6 | raw 透传 | `add --raw '{"key":"val"}'` 透传任意字段到 settings.json |

### Phase 3: DX 增强 (v0.7.0) ⭐⭐

目标：改善开发体验和可安装性

| ID | 任务 | 说明 |
|----|------|------|
| P3.1 | Shell 补全 | 生成 bash/zsh/fish completion 脚本：`cc-switch completion bash` |
| P3.2 | install 脚本 | `install.sh` 或 `make install` 复制到 `~/.local/bin`，添加 PATH |
| P3.3 | --json 输出 | `list --json` / `show --json` 输出 JSON 格式供脚本消费 |
| P3.4 | --plain 输出 | `list --plain` 只输出 profile 名称，适合管道 |
| P3.5 | 配置迁移 | profile/ provider 文件加 version 字段，启动时自动迁移旧格式 |
| P3.6 | 健康检查 | `cc-switch check`：检查所有 profile 的 provider 存在性、token 可达性 |

### Phase 4: 高级特性 (v0.8.0+) ⭐

目标：生态和高级场景

| ID | 任务 | 说明 |
|----|------|------|
| P4.1 | 导入/导出 | `cc-switch export > profiles.json` / `cc-switch import < profiles.json` |
| P4.2 | 内置更多 Provider | 调研并添加：openrouter, together.ai, fireworks, groq 的 Anthropic-compatible 端点 |
| P4.3 | 临时切换 | `cc-switch --tmp <name>` 设置 `ANTHROPIC_MODEL` env 但不写入 settings.json |
| P4.4 | 默认 profile | `cc-switch default <name>` 设置某个 profile 为默认（新终端自动用它） |
| P4.5 | 条件切换 | `cc-switch auto` 根据时间/目录/任务类型自动选择 profile |
| P4.6 | profile 模板 | `cc-switch init` 生成 `templates/deepseek.json` 模板文件 |

---

## 3. 数据流改进

### 3.1 当前 apply_profile 流程

```
profile → profile_to_settings() → data dict
settings.json → read_json() → cur dict
cur.update(data)  →  merged dict
write to settings.json
```

**问题**：`cur.update(data)` 只覆盖 data 中的 key。旧 profile 的 `alwaysThinkingEnabled: true` 在切换到不含此字段的 profile 时会残留。

**改进**：在 merge 前显式删除可能残留的顶层 key：

```python
KEYS_TO_CLEAN = {"alwaysThinkingEnabled"}
for k in KEYS_TO_CLEAN:
    if k in cur and k not in data:
        del cur[k]
cur.update(data)
```

### 3.2 新增 dry-run 流程

```
profile → profile_to_settings() → data dict
print(json.dumps(data, indent=2))
# 不写文件，标记 --dry-run
```

### 3.3 新增 edit 流程

```
edit <name>:
  1. 读 ~/.cc-switch-profiles.json 中的 <name>
  2. 写入临时文件
  3. $EDITOR 打开临时文件
  4. 用户编辑保存
  5. 读回临时文件，验证 JSON
  6. 更新 ~/.cc-switch-profiles.json
```

---

## 4. Profile Schema 完整定义

```jsonc
{
  "<name>": {
    // ── 必填 ──
    "model": "deepseek-v4-pro",          // 模型 ID → ANTHROPIC_MODEL
    
    // ── 可选：Provider 绑定 ──
    "provider": "deepseek",              // 不填则为 "custom"
    
    // ── 可选：覆盖 Provider 预设 ──
    "base_url": "...",                   // 仅自定义 provider 可覆盖
    "auth_token": "...",                 // 显式 token，优先级高于 $ENV
    "auth": {                            // 结构化认证 (与 auth_token 二选一)
      "type": "bearer",                  // bearer | api-key
      "token": "..."
    },
    "api_key": "...",                    // x-api-key 模式
    
    // ── 可选：场景映射 ──
    "aliases": {                         // /model <alias> → 具体模型
      "haiku": "deepseek-v4-flash",
      "sonnet": "deepseek-v4-pro",
      "opus": "deepseek-v4-pro"
    },
    
    // ── 可选：高级设置 ──
    "settings": {                        // 翻译到 settings.json
      "alwaysThinkingEnabled": true,
      "apiTimeoutMs": "3000000",
      "disableNonessentialTraffic": true
    },
    
    // ── 可选：透传 ──
    "raw": {                             // 直接 merge 到 settings.json
      "availableModels": ["deepseek-v4-pro", "deepseek-v4-flash"]
    },
    
    // ── 可选：元信息 ──
    "desc": "DeepSeek V4 Pro"
  }
}
```

### 字段优先级

| 字段 | 优先级 (高→低) |
|------|---------------|
| model | profile 显式 |
| base_url | 自定义 provider: profile > provider; 内置 provider: provider 锁定 |
| auth_token | profile 显式 > env_key 环境变量 > profile.api_key |
| aliases | profile 显式 |
| settings | profile 显式 |
| raw | profile 显式 |

---

## 5. 测试计划

| ID | 测试场景 | 预期 |
|----|---------|------|
| T1 | `add dp -p deepseek` (无 -t) | profile 不存 auth_token，切换时读 $DEEPSEEK_API_KEY |
| T2 | `add mm -p minimax -t xxx --haiku M --sonnet M --opus M` | aliases 全部设置 |
| T3 | 从 dp 切换到 sonnet | env 中 ANTHROPIC_BASE_URL 清除 |
| T4 | 从 minimax (thinking=true) 切换到 sonnet | alwaysThinkingEnabled 清除 |
| T5 | `--dry-run` 不写入 | settings.json 不变，stdout 出 JSON |
| T6 | `edit <name>` 修改 aliases | profile 文件更新 |
| T7 | `add --think` | settings.alwaysThinkingEnabled 正确 |
| T8 | 模糊匹配 "dp" → "dp-pro" | 前缀匹配成功 |
| T9 | `-` 回退到上一个 | 历史倒数第二条 |
| T10 | `-` 首次使用无历史 | 报错提示 |

---

## 6. 里程碑

| 版本 | 阶段 | 关键变化 | 预计行数 |
|------|------|---------|---------|
| v0.5.0 | 打磨 | P1.1~P1.8 | ~900 |
| v0.6.0 | CRUD | P2.1~P2.6 | ~1200 |
| v0.7.0 | DX | P3.1~P3.6 | ~1600 |
| v0.8.0+ | 高级 | P4.1~P4.6 | ~2000+ |

---

## 7. 决定与讨论点

1. **是否需要拆分为多个 .py 文件？**
   - 建议：v0.7.0 之前保持单文件。安装简单，`curl` 即用。超 2000 行后再拆。

2. **是否引入第三方依赖？**
   - 建议：不引入。Python 标准库足够。shell completion 用生成脚本。

3. **provider 预设如何维护？**
   - 建议：内置 3-5 个主流。其余的通过 `add-provider` 社区共享。考虑 `cc-switch provider search` 连接一个预设仓库。

4. **配置文件的敏感信息保护？**
   - 建议：`auth_token` 存 profile 是明文的，跟 `.env` 一样。文档应该建议用户用 `env_key`（环境变量）方式。未来加 `cc-switch auth` 加密存储。
