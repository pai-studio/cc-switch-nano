"""tmux-backed session management for ccs."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Optional

from . import profile_to_settings
from .models import resolve_model_spec, resolved_to_profile, validate_runtime_key


@dataclass
class CodeSession:
    name: str
    tool: str
    model: str
    project: str
    index: int
    pid: Optional[int]
    running: bool
    settings: str = ""
    argv: list[str] | None = None

    @property
    def project_name(self) -> str:
        return Path(self.project).name if self.project else "?"

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "tool": self.tool,
            "model": self.model,
            "project": self.project,
            "project_name": self.project_name,
            "pid": self.pid,
            "running": self.running,
            "tmux_session": SessionManager.TMUX_SESSION,
            "tmux_window_index": self.index,
            "settings": self.settings,
            "argv": self.argv or [],
        }


class SessionManager:
    """Manage code-tool sessions in a single tmux session."""

    TMUX_SESSION = "ccs"
    PLACEHOLDER = "_"
    TOOL_OPTION = "@ccs_tool"
    MODEL_OPTION = "@ccs_model"
    PROJECT_OPTION = "@ccs_project"
    SETTINGS_OPTION = "@ccs_settings"
    ARGV_OPTION = "@ccs_argv"
    MAIN_PANE_OPTION = "@ccs_main_pane"
    SIDEBAR_PANE_OPTION = "@ccs_sidebar_pane"
    SIDEBAR_WIDTH = 34

    def __init__(self) -> None:
        if not shutil.which("tmux"):
            raise RuntimeError("tmux not found")
        self._ensure_session()

    def _raw(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["tmux", *args],
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
        r = self._raw("has-session", "-t", self.TMUX_SESSION)
        if r.returncode != 0:
            self._tmux(
                "new-session",
                "-d",
                "-s",
                self.TMUX_SESSION,
                "-n",
                self.PLACEHOLDER,
            )
        self._ensure_key_bindings()

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def list(self) -> list[CodeSession]:
        try:
            output = self._tmux(
                "list-windows",
                "-t",
                self.TMUX_SESSION,
                "-F",
                "#{window_index}\t#{window_name}\t#{pane_current_path}\t#{pane_pid}\t#{"
                + self.TOOL_OPTION
                + "}\t#{"
                + self.MODEL_OPTION
                + "}\t#{"
                + self.PROJECT_OPTION
                + "}\t#{"
                + self.SETTINGS_OPTION
                + "}\t#{"
                + self.ARGV_OPTION
                + "}\t#{"
                + self.MAIN_PANE_OPTION
                + "}",
            )
        except RuntimeError:
            return []

        sessions: list[CodeSession] = []
        for line in output.splitlines():
            parts = line.strip().split("\t", 9)
            if len(parts) < 10:
                continue
            idx_s, name, pane_path, pid_s, tool, model, project, settings, argv_s, main_pane = parts
            if name == self.PLACEHOLDER:
                continue
            if main_pane:
                main_info = self._main_pane_info(main_pane)
                if main_info is not None:
                    pane_path, pid_s = main_info
            pid = int(pid_s) if pid_s.isdigit() else None
            try:
                argv = json.loads(argv_s) if argv_s else []
            except json.JSONDecodeError:
                argv = []
            if not isinstance(argv, list):
                argv = []
            sessions.append(
                CodeSession(
                    name=name,
                    tool=tool or "?",
                    model=model or "default",
                    project=project or pane_path,
                    index=int(idx_s),
                    pid=pid,
                    running=self._pid_alive(pid) if pid else False,
                    settings=settings,
                    argv=[str(a) for a in argv],
                )
            )
        return sessions

    def create_claude(
        self,
        *,
        name: Optional[str],
        project: str,
        model: Optional[str],
        passthrough: list[str],
        attach: bool,
        dry_run: bool,
    ) -> CodeSession | None:
        project_path = os.path.abspath(os.path.expanduser(project))
        if not os.path.isdir(project_path):
            raise RuntimeError(f"directory not found: {project_path}")

        resolved_model = resolve_model_spec(model or "default")
        session_name = name or self._next_name("claude", resolved_model.canonical, project_path)
        if name and any(session.name == name for session in self.list()):
            return self.switch_model(
                name=session_name,
                model=model,
                passthrough=passthrough if passthrough else None,
                attach=attach,
                dry_run=dry_run,
            )
        self._validate_new_name(session_name)

        settings = None
        if resolved_model.actual_model != "default":
            validate_runtime_key(resolved_model)
            settings = self._settings_path(session_name, "claude")
            self._write_claude_settings(model or "default", settings)

        argv = self._claude_argv(session_name, settings, passthrough)
        if dry_run:
            print(f"name: {session_name}")
            print(f"project: {project_path}")
            print(f"tool: claude")
            print(f"model: {resolved_model.canonical}")
            print(f"settings: {settings or '(default)'}")
            print(f"command: {shlex.join(argv)}")
            return None

        self._tmux(
            "new-window",
            "-t",
            self.TMUX_SESSION,
            "-n",
            session_name,
            "-c",
            project_path,
            shlex.join(["exec", *argv]),
        )
        target = f"{self.TMUX_SESSION}:{session_name}"
        main_pane = self._tmux("display-message", "-p", "-t", target, "#{pane_id}")
        self._set_window_metadata(
            target=target,
            tool="claude",
            model=resolved_model.canonical,
            project=project_path,
            settings=str(settings) if settings else "",
            argv=passthrough,
            main_pane=main_pane,
        )
        self._ensure_sidebar(session_name)
        time.sleep(0.2)
        created = self._get(session_name)
        if attach:
            self.attach(session_name)
        return created

    def switch_model(
        self,
        *,
        name: str,
        model: Optional[str],
        passthrough: Optional[list[str]] = None,
        create: bool = False,
        project: str = ".",
        attach: bool = False,
        dry_run: bool = False,
    ) -> CodeSession | None:
        session = self._find(name)
        if session is None:
            if not create:
                raise RuntimeError(f"session '{name}' not found")
            return self.create_claude(
                name=name,
                project=project,
                model=model or "default",
                passthrough=passthrough or [],
                attach=attach,
                dry_run=dry_run,
            )
        if session.tool != "claude":
            raise RuntimeError(f"switch is not implemented for tool '{session.tool}'")
        if not os.path.isdir(session.project):
            raise RuntimeError(f"project '{session.project}' no longer exists")

        next_model = model or session.model
        resolved_model = resolve_model_spec(next_model)
        next_argv = session.argv or [] if passthrough is None else passthrough
        next_settings = None
        if resolved_model.actual_model != "default":
            validate_runtime_key(resolved_model)
            next_settings = self._settings_path(name, "claude")
            self._write_claude_settings(next_model, next_settings)

        argv = self._claude_argv(name, next_settings, next_argv)
        if dry_run:
            print(f"name: {name}")
            print(f"project: {session.project}")
            print("tool: claude")
            print(f"model: {resolved_model.canonical}")
            print(f"settings: {next_settings or '(default)'}")
            print(f"command: {shlex.join(argv)}")
            return None

        target = f"{self.TMUX_SESSION}:{session.index}"
        old_settings = session.settings
        self._tmux(
            "respawn-window",
            "-k",
            "-t",
            target,
            "-c",
            session.project,
            shlex.join(["exec", *argv]),
        )
        main_pane = self._tmux("display-message", "-p", "-t", target, "#{pane_id}")
        self._set_window_metadata(
            target=target,
            tool="claude",
            model=resolved_model.canonical,
            project=session.project,
            settings=str(next_settings) if next_settings else "",
            argv=next_argv,
            main_pane=main_pane,
        )
        self._ensure_sidebar(name)
        if old_settings and old_settings != str(next_settings or ""):
            self._remove_settings(Path(old_settings))
        updated = self._get(name)
        if attach:
            self.attach(name)
        return updated

    def attach(self, name: Optional[str] = None) -> None:
        sessions = self.list()
        if not sessions:
            raise RuntimeError("no sessions")
        target_session = sessions[-1] if name is None else None
        if name is not None:
            for session in sessions:
                if session.name == name:
                    target_session = session
                    break
        if target_session is None:
            raise RuntimeError(f"session '{name}' not found")
        self._ensure_sidebar(target_session.name)
        self._tmux("select-window", "-t", f"{self.TMUX_SESSION}:{target_session.index}")
        if not os.environ.get("TMUX"):
            subprocess.run(["tmux", "attach-session", "-t", self.TMUX_SESSION])

    def kill(self, name: str) -> None:
        for session in self.list():
            if session.name == name:
                settings = self._tmux(
                    "show-option",
                    "-wqv",
                    "-t",
                    f"{self.TMUX_SESSION}:{session.index}",
                    self.SETTINGS_OPTION,
                )
                self._tmux("kill-window", "-t", f"{self.TMUX_SESSION}:{session.index}")
                if settings:
                    self._remove_settings(Path(settings))
                return
        raise RuntimeError(f"session '{name}' not found")

    def _set_window_metadata(
        self,
        *,
        target: str,
        tool: str,
        model: str,
        project: str,
        settings: str,
        argv: list[str],
        main_pane: str | None = None,
    ) -> None:
        values = {
            self.TOOL_OPTION: tool,
            self.MODEL_OPTION: model,
            self.PROJECT_OPTION: project,
            self.SETTINGS_OPTION: settings,
            self.ARGV_OPTION: json.dumps(argv),
        }
        if main_pane is not None:
            values[self.MAIN_PANE_OPTION] = main_pane
        for key, value in values.items():
            self._tmux("set-option", "-w", "-t", target, key, value)

    def _ensure_sidebar(self, name: str) -> None:
        session = self._find(name)
        if session is None:
            return
        target = f"{self.TMUX_SESSION}:{session.index}"
        main_pane = self._window_option(target, self.MAIN_PANE_OPTION)
        if not main_pane:
            main_pane = self._tmux("display-message", "-p", "-t", target, "#{pane_id}")
            self._tmux("set-option", "-w", "-t", target, self.MAIN_PANE_OPTION, main_pane)

        sidebar_pane = self._window_option(target, self.SIDEBAR_PANE_OPTION)
        if sidebar_pane and self._raw("display-message", "-p", "-t", sidebar_pane, "#{pane_id}").returncode == 0:
            self._tmux("select-pane", "-t", main_pane)
            return

        command = shlex.join([sys.executable, "-m", "claude_switch.ccs", "sidebar", "--current", name])
        sidebar_pane = self._tmux(
            "split-window",
            "-h",
            "-b",
            "-d",
            "-P",
            "-F",
            "#{pane_id}",
            "-l",
            str(self.SIDEBAR_WIDTH),
            "-t",
            main_pane,
            command,
        )
        self._tmux("set-option", "-w", "-t", target, self.SIDEBAR_PANE_OPTION, sidebar_pane)
        self._tmux("select-pane", "-t", main_pane)

    def _main_pane_info(self, pane_id: str) -> tuple[str, str] | None:
        r = self._raw("display-message", "-p", "-t", pane_id, "#{pane_current_path}\t#{pane_pid}")
        if r.returncode != 0:
            return None
        parts = r.stdout.strip().split("\t", 1)
        if len(parts) != 2:
            return None
        return parts[0], parts[1]

    def _window_option(self, target: str, key: str) -> str:
        return self._tmux("show-option", "-wqv", "-t", target, key)

    def _ensure_key_bindings(self) -> None:
        session_check = f"#{{==:#{{session_name}},{self.TMUX_SESSION}}}"
        bindings = {
            "F2": "choose-tree -Zw",
            "F3": "previous-window",
            "F4": "next-window",
            "F10": "detach-client",
        }
        for key, command in bindings.items():
            self._tmux(
                "bind-key",
                "-n",
                key,
                "if-shell",
                "-F",
                session_check,
                command,
                f"send-keys {key}",
            )

    def _get(self, name: str) -> CodeSession:
        session = self._find(name)
        if session is not None:
            return session
        raise RuntimeError(f"session '{name}' created but not found")

    def _find(self, name: str) -> CodeSession | None:
        for session in self.list():
            if session.name == name:
                return session
        return None

    def _validate_new_name(self, name: str) -> None:
        if name == self.PLACEHOLDER:
            raise RuntimeError(f"session name '{self.PLACEHOLDER}' is reserved")
        if any(session.name == name for session in self.list()):
            raise RuntimeError(f"session '{name}' already exists")

    def _next_name(self, tool: str, model: str, project: str) -> str:
        base = "-".join(
            [
                self._slug(tool),
                self._slug(model),
                self._slug(Path(project).name or "project"),
            ]
        )
        existing = {session.name for session in self.list()}
        i = 1
        while f"{base}-{i}" in existing:
            i += 1
        return f"{base}-{i}"

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
        return slug or "x"

    @staticmethod
    def _claude_argv(
        name: str,
        settings: Optional[Path],
        passthrough: list[str],
    ) -> list[str]:
        argv = ["claude"]
        if settings:
            argv.extend(["--settings", str(settings)])
        if "--name" not in passthrough and "-n" not in passthrough:
            argv.extend(["--name", name])
        argv.extend(passthrough)
        return argv

    @staticmethod
    def _state_dir() -> Path:
        base = os.environ.get("XDG_STATE_HOME")
        if base:
            return Path(base) / "ccs" / "sessions"
        return Path.home() / ".ccs" / "sessions"

    @classmethod
    def _settings_path(cls, name: str, tool: str) -> Path:
        digest = sha1(f"{tool}:{name}".encode("utf-8")).hexdigest()[:8]
        safe = cls._slug(name)
        return cls._state_dir() / f"{safe}-{digest}.{tool}.settings.json"

    @staticmethod
    def _remove_settings(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _write_claude_settings(model: str, path: Path) -> None:
        resolved = resolve_model_spec(model)
        validate_runtime_key(resolved)
        data = profile_to_settings(resolved_to_profile(resolved))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        path.chmod(0o600)
