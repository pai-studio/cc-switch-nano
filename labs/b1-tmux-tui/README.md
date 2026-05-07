# cc-tmux — B1 方案

TUI + tmux 后端管理多个 Claude Code 会话。

## 原理

每个 Claude Code 实例运行在 tmux 的独立窗口中，统一归入 `cc-tmux` 会话管理。

## 安装

```bash
pip install -e .
```

需要系统中已安装 tmux：

```bash
brew install tmux    # macOS
apt install tmux     # Linux
```

## 使用

```bash
# TUI 仪表盘（推荐）
cc-tmux tui

# CLI 命令
cc-tmux list                    # 列出所有会话
cc-tmux new feat-api -p . -m sonnet  # 新建会话
cc-tmux attach feat-api         # 附着到会话
cc-tmux kill feat-api           # 销毁会话
cc-tmux model feat-api deepseek  # 切换模型
cc-tmux rename feat-api bugfix   # 重命名
```

## 优点

- 跨平台（依赖 tmux，macOS/Linux 均可）
- 会话持久化（tmux 管理进程，关闭 TUI 不会杀会话）
- 可集成 claude-switch 切换模型
- 实现简单，tmux 处理所有 PTY 复杂性
