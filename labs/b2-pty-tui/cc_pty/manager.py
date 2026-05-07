"""Session metadata persistence for cc-pty."""

import json
import os
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

DATA_DIR = Path.home() / ".cc-pty"
SESSIONS_FILE = DATA_DIR / "sessions.json"


@dataclass
class Session:
    """Metadata for a Claude Code session."""
    name: str
    project: str
    model: str = "?"


class Manager:
    """Persist and retrieve session metadata."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._load()

    def _load(self) -> None:
        if not SESSIONS_FILE.exists():
            return
        try:
            raw = json.loads(SESSIONS_FILE.read_text())
            for name, info in raw.items():
                self._sessions[name] = Session(**info)
        except (json.JSONDecodeError, OSError, TypeError):
            self._sessions.clear()

    def _save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = {name: asdict(s) for name, s in self._sessions.items()}
        SESSIONS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, name: str, project: str, model: str = "?") -> Session:
        s = Session(
            name=name,
            project=os.path.abspath(os.path.expanduser(project)),
            model=model,
        )
        self._sessions[name] = s
        self._save()
        return s

    def remove(self, name: str) -> None:
        self._sessions.pop(name, None)
        self._save()

    def get(self, name: str) -> Optional[Session]:
        return self._sessions.get(name)

    def list(self) -> list[Session]:
        return list(self._sessions.values())

    def rename(self, old: str, new: str) -> Optional[Session]:
        s = self._sessions.pop(old, None)
        if s is not None:
            s.name = new
            self._sessions[new] = s
            self._save()
            return s
        return None

    def set_model(self, name: str, model: str) -> bool:
        s = self._sessions.get(name)
        if s is None:
            return False
        s.model = model
        self._save()
        return True

    # ------------------------------------------------------------------
    # Model helpers
    # ------------------------------------------------------------------

    @staticmethod
    def apply_model(project: str, model: str) -> None:
        r = subprocess.run(
            ["claude-switch", model],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            raise RuntimeError(
                f"claude-switch: {r.stderr.strip() or r.stdout.strip()}"
            )

    @staticmethod
    def detect_model(project: str) -> str:
        settings = Path(project) / ".claude" / "settings.json"
        if not settings.exists():
            return "?"
        try:
            data = json.loads(settings.read_text())
        except (json.JSONDecodeError, OSError):
            return "?"
        m = data.get("model") or (data.get("models") or {}).get("default")
        if m:
            return m
        models = data.get("models")
        if isinstance(models, dict):
            for v in models.values():
                if isinstance(v, str):
                    return v
        return "?"
