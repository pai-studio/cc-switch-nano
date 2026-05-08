"""Tests for the ccs command helpers."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_switch.ccs import HELP, HELP_ZH, _parse_cc_options, _run_tui
from claude_switch.models import add_model_mapping, list_providers, resolve_model_spec
from claude_switch.session import SessionManager
from claude_switch.tui import CcsTuiApp, DEFAULT_TUI_MODEL, parse_new_session_request


class CcsParseTests(unittest.TestCase):
    def test_plain_claude_help_is_passthrough(self):
        opts, passthrough, managed = _parse_cc_options(["--help"])

        self.assertFalse(managed)
        self.assertEqual(passthrough, ["--help"])
        self.assertIsNone(opts.model)

    def test_cc_model_preserves_claude_args_order(self):
        opts, passthrough, managed = _parse_cc_options(
            ["--cc-model", "deepseek-flash", "--permission-mode", "acceptEdits"]
        )

        self.assertTrue(managed)
        self.assertEqual(opts.model, "deepseek-flash")
        self.assertEqual(passthrough, ["--permission-mode", "acceptEdits"])

    def test_unknown_cc_option_exits(self):
        with self.assertRaises(SystemExit):
            _parse_cc_options(["--cc-nope"])

    def test_help_mentions_tui(self):
        self.assertIn("ccs tui", HELP)
        self.assertIn("ccs tui", HELP_ZH)

    def test_tui_rejects_extra_args(self):
        with self.assertRaises(SystemExit):
            _run_tui(["--bad"])


class SessionHelperTests(unittest.TestCase):
    def test_claude_argv_adds_settings_and_name(self):
        argv = SessionManager._claude_argv(
            "api-review",
            Path("/tmp/settings.json"),
            ["--permission-mode", "acceptEdits"],
        )

        self.assertEqual(
            argv,
            [
                "claude",
                "--settings",
                "/tmp/settings.json",
                "--name",
                "api-review",
                "--permission-mode",
                "acceptEdits",
            ],
        )

    def test_claude_argv_respects_existing_name(self):
        argv = SessionManager._claude_argv(
            "api-review",
            None,
            ["--name", "custom"],
        )

        self.assertEqual(argv, ["claude", "--name", "custom"])

    def test_write_claude_settings_uses_0600_permissions(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "session.settings.json"
            profiles = {"dp": {"model": "deepseek-v4-flash", "provider": "deepseek"}}
            with patch("claude_switch.models.load_profiles", return_value=profiles), patch.dict(
                os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=False
            ):
                SessionManager._write_claude_settings("dp", path)

            data = json.loads(path.read_text())
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(data["model"], "deepseek-v4-flash")
            self.assertEqual(mode, 0o600)

    def test_settings_path_uses_xdg_state_home(self):
        with tempfile.TemporaryDirectory() as td:
            old = os.environ.get("XDG_STATE_HOME")
            os.environ["XDG_STATE_HOME"] = td
            try:
                path = SessionManager._settings_path("api-review", "claude")
            finally:
                if old is None:
                    os.environ.pop("XDG_STATE_HOME", None)
                else:
                    os.environ["XDG_STATE_HOME"] = old

        self.assertIn("ccs/sessions", str(path))
        self.assertTrue(path.name.endswith(".claude.settings.json"))


class ModelRegistryTests(unittest.TestCase):
    def test_anthropic_alias_is_an(self):
        providers = {provider.id: provider for provider in list_providers()}

        self.assertIn("an", providers["anthropic"].aliases)
        self.assertNotIn("a", providers["anthropic"].aliases)

    def test_resolves_deepseek_provider_model(self):
        resolved = resolve_model_spec("ds/flash")

        self.assertEqual(resolved.provider, "deepseek")
        self.assertEqual(resolved.actual_model, "deepseek-v4-flash")
        self.assertEqual(resolved.canonical, "ds/flash")

    def test_resolves_anthropic_provider_model(self):
        resolved = resolve_model_spec("an/sonnet")

        self.assertEqual(resolved.provider, "anthropic")
        self.assertEqual(resolved.actual_model, "sonnet")

    def test_resolves_openrouter_short_model_to_actual_author_model(self):
        resolved = resolve_model_spec("or/kimi-k2.6")

        self.assertEqual(resolved.provider, "openrouter")
        self.assertEqual(resolved.actual_model, "moonshotai/kimi-k2.6")

    def test_resolves_legacy_openrouter_profile(self):
        resolved = resolve_model_spec("openrouter/kimi-k2.6")

        self.assertEqual(resolved.canonical, "or/kimi-k2.6")
        self.assertEqual(resolved.actual_model, "moonshotai/kimi-k2.6")

    def test_custom_openrouter_mapping_does_not_store_key(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "models.json"
            with patch.dict(os.environ, {"CCS_MODELS_FILE": str(path)}, clear=False):
                add_model_mapping("or/qwen3-coder", "qwen/qwen3-coder")
                resolved = resolve_model_spec("or/qwen3-coder")

            data = json.loads(path.read_text())
            self.assertEqual(resolved.actual_model, "qwen/qwen3-coder")
            self.assertEqual(data, {"models": {"or/qwen3-coder": "qwen/qwen3-coder"}})


class TuiHelperTests(unittest.TestCase):
    def test_new_session_request_allows_empty_name_and_defaults(self):
        request = parse_new_session_request(name="", project="", model="", args="")

        self.assertIsNone(request.name)
        self.assertEqual(request.project, ".")
        self.assertEqual(request.model, DEFAULT_TUI_MODEL)
        self.assertEqual(request.passthrough, [])

    def test_new_session_request_splits_claude_args(self):
        request = parse_new_session_request(
            name="api",
            project="~/app",
            model="an/sonnet",
            args="--permission-mode acceptEdits --add-dir ../shared",
        )

        self.assertEqual(request.name, "api")
        self.assertEqual(request.project, "~/app")
        self.assertEqual(request.model, "an/sonnet")
        self.assertEqual(
            request.passthrough,
            ["--permission-mode", "acceptEdits", "--add-dir", "../shared"],
        )

    def test_new_session_request_rejects_bad_args(self):
        with self.assertRaises(RuntimeError):
            parse_new_session_request(name="", project="", model="", args='"unterminated')

    def test_tui_mounts_headless_with_empty_sessions(self):
        class FakeManager:
            def list(self):
                return []

        async def autopilot(pilot):
            pilot.app.exit()

        CcsTuiApp(manager=FakeManager()).run(headless=True, auto_pilot=autopilot)

    def test_tui_create_then_attach_selects_created_session(self):
        from claude_switch.session import CodeSession
        from claude_switch.tui import NewSessionRequest

        class FakeManager:
            def __init__(self):
                self.sessions = []

            def list(self):
                return self.sessions

            def create_claude(self, **kwargs):
                session = CodeSession(
                    name=kwargs.get("name") or "auto-1",
                    tool="claude",
                    model=kwargs.get("model") or "ds/flash",
                    project=".",
                    index=1,
                    pid=123,
                    running=True,
                )
                self.sessions = [session]
                return session

        async def autopilot(pilot):
            app = pilot.app
            await pilot.pause()
            app._on_new_session(NewSessionRequest(None, ".", "ds/flash", []))
            await pilot.pause()
            app.action_attach()

        result = CcsTuiApp(manager=FakeManager()).run(headless=True, auto_pilot=autopilot)
        self.assertEqual(result, ("attach", "auto-1"))

    def test_tui_bindings_are_not_priority_global_bindings(self):
        keys = {binding.key: binding for binding in CcsTuiApp.BINDINGS}

        self.assertNotIn("enter", keys)
        for key in ("n", "s", "k", "r", "?", "q"):
            self.assertFalse(keys[key].priority)


if __name__ == "__main__":
    unittest.main()
