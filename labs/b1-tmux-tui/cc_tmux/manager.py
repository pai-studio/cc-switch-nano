"""Tmux-based session management for Claude Code."""

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Session:
    """A Claude Code session running in a tmux window."""

    name: str
    project: str
    model: str
    index: int
    pid: Optional[int]
    running: bool

    @property
    def project_name(self) -> str:
        return Path(self.project).name if self.project else "?"


class Manager:
    """Manage Claude Code sessions via tmux."""

    SESSION = "cc-tmux"

    def __init__(self):
        if not shutil.which("tmux"):
            raise RuntimeError("tmux not found — install: brew install tmux")
        self._ensure_session()

    # ------------------------------------------------------------------
    # Internal tmux helpers
    # ------------------------------------------------------------------

    def _raw(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["tmux"] + list(args),
            capture_output=True,
            text=True,
            timeout=10,
        )

    def _tmux(self, *args: str) -> str:
        r = self._raw(*args)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or f"tmux exited {r.returncode}")
        return r.stdout.strip()

    def _ensure_session(self) -> None:
        """Create the cc-tmux session if it doesn't exist yet."""
        r = self._raw("has-session", "-t", self.SESSION)
        if r.returncode != 0:
            self._tmux("new-session", "-d", "-s", self.SESSION, "-n", "_")
            self._tmux("kill-window", "-t", f"{self.SESSION}:_")

    # ------------------------------------------------------------------
    # Model detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_model(project_path: str) -> str:
        """Read the model from .claude/settings.json in *project_path*."""
        settings = Path(project_path) / ".claude" / "settings.json"
        if not settings.exists():
            return "?"
        try:
            data = json.loads(settings.read_text())
        except (json.JSONDecodeError, OSError):
            return "?"
        model = data.get("model") or (data.get("models") or {}).get("default")
        if model:
            return model
        models = data.get("models")
        if isinstance(models, dict):
            for v in models.values():
                if isinstance(v, str):
                    return v
        return "?"

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Session operations
    # ------------------------------------------------------------------

    def list(self) -> list[Session]:
        """Return all Claude Code windows in the cc-tmux session."""
        try:
            output = self._tmux(
                "list-windows",
                "-t",
                self.SESSION,
                "-F",
                "#{window_index}\t#{window_name}\t#{pane_current_path}\t#{pane_pid}",
            )
        except RuntimeError:
            return []

        sessions: list[Session] = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 3)
            if len(parts) < 4:
                continue
            idx_s, name, path, pid_s = parts
            pid = int(pid_s) if pid_s.isdigit() else None
            running = self._pid_alive(pid) if pid else False
            sessions.append(
                Session(
                    name=name,
                    project=path,
                    model=self.detect_model(path),
                    index=int(idx_s),
                    pid=pid,
                    running=running,
                )
            )
        return sessions

    def new(
        self, name: str, project: str, model: Optional[str] = None
    ) -> Session:
        """Create a new tmux window running *claude* in *project*."""
        existing = [s for s in self.list() if s.name == name]
        if existing:
            raise RuntimeError(f"session '{name}' already exists")

        project = os.path.abspath(os.path.expanduser(project))
        if not os.path.isdir(project):
            raise RuntimeError(f"directory not found: {project}")

        if model:
            self._run_switch(model, project)

        self._tmux(
            "new-window",
            "-t",
            self.SESSION,
            "-n",
            name,
            "-c",
            project,
            "exec claude",
        )

        time.sleep(0.3)
        for s in self.list():
            if s.name == name:
                return s
        raise RuntimeError(f"session '{name}' created but not found in listing")

    def attach(self, name: str) -> None:
        """Bring a session window to the foreground."""
        for s in self.list():
            if s.name == name:
                self._tmux("select-window", "-t", f"{self.SESSION}:{s.index}")
                if not os.environ.get("TMUX"):
                    subprocess.run(
                        ["tmux", "attach-session", "-t", self.SESSION]
                    )
                return
        raise RuntimeError(f"session '{name}' not found")

    def kill(self, name: str) -> None:
        """Kill a session's tmux window."""
        for s in self.list():
            if s.name == name:
                self._tmux("kill-window", "-t", f"{self.SESSION}:{s.index}")
                return
        raise RuntimeError(f"session '{name}' not found")

    def set_model(self, name: str, model: str) -> None:
        """Switch the model for an existing session's project."""
        for s in self.list():
            if s.name == name:
                if not os.path.isdir(s.project):
                    raise RuntimeError(f"project '{s.project}' no longer exists")
                self._run_switch(model, s.project)
                return
        raise RuntimeError(f"session '{name}' not found")

    def rename(self, old: str, new: str) -> None:
        """Rename a tmux window."""
        for s in self.list():
            if s.name == old:
                self._tmux(
                    "rename-window", "-t", f"{self.SESSION}:{s.index}", new
                )
                return
        raise RuntimeError(f"session '{old}' not found")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _run_switch(model: str, cwd: str) -> None:
        r = subprocess.run(
            ["claude-switch", model],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            raise RuntimeError(
                f"claude-switch failed: {r.stderr.strip() or r.stdout.strip()}"
            )
