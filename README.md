# claude-switch

Multi-provider model switcher for claude-code. Switch between Anthropic, DeepSeek, MiniMax, OpenRouter — like opencode.

## Install

```bash
pip install .
```

Requires Python 3.10+. Zero dependencies.

## Quick Start

```bash
# Interactive picker
claude-switch

# Direct switch
claude-switch sonnet

# Go back
claude-switch -
```

## Add Profiles

```bash
# Simple: all aliases default to model name
claude-switch add dp deepseek-v4-pro -p deepseek

# Detailed: override specific aliases
claude-switch add dp deepseek-v4-pro -p deepseek --haiku deepseek-v4-flash

# OpenRouter example
claude-switch add or-sonnet anthropic/claude-sonnet-4-20250514 -p openrouter
```

## Commands

| Command | Description |
|---------|-------------|
| `claude-switch` | Interactive picker |
| `claude-switch <name>` | Switch by fuzzy name |
| `claude-switch -` | Back to previous |
| `claude-switch list` | List all profiles |
| `claude-switch show` | Active model (3 layers) |
| `claude-switch show <name>` | Profile detail |
| `claude-switch log` | Switch history |
| `claude-switch providers` | List providers |
| `claude-switch add ...` | Add profile |
| `claude-switch rm <name>` | Delete profile |
| `claude-switch add-provider <name> <url>` | Add custom provider |

## Scopes

| Flag | Scope | Path |
|------|-------|------|
| (default) | project | `<project>/.claude/settings.json` |
| `-l` | local | `<project>/.claude/settings.local.json` |
| `-u` | user | `~/.claude/settings.json` |

## Built-in Providers

| Provider | Base URL | Env Key |
|----------|----------|---------|
| anthropic | (native) | `$ANTHROPIC_API_KEY` |
| deepseek | api.deepseek.com/anthropic | `$DEEPSEEK_API_KEY` |
| minimax | api.minimax.io/anthropic | `$MINIMAX_API_KEY` |
| openrouter | openrouter.ai/api | `$OPENROUTER_API_KEY` |

Set keys in your shell:
```bash
export DEEPSEEK_API_KEY="sk-xxx"
export OPENROUTER_API_KEY="sk-or-v1-xxx"
```

## Advanced

```bash
claude-switch --dry-run dp     # preview JSON, don't write
claude-switch --preview dp     # confirm before writing
claude-switch --help           # full help
claude-switch --help-zh        # 中文帮助
```

## Docs

- [中文文档](README_zh.md)
- `claude-switch --help` / `claude-switch --help-zh`
