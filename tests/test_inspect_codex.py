from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "inspect_codex.py"
SPEC = importlib.util.spec_from_file_location("inspect_codex", MODULE_PATH)
assert SPEC and SPEC.loader
inspect_codex = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspect_codex)


class ConfigSafetyTests(unittest.TestCase):
    def test_only_allowlisted_config_keys_are_emitted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            config.write_text(
                'model = "gpt-test"\n'
                'model_reasoning_effort = "high"\n'
                'api_key = "do-not-emit"\n'
                '[provider]\n'
                'authorization = "do-not-emit-either"\n',
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"CODEX_HOME": directory}, clear=False):
                result = inspect_codex.load_safe_config()
        self.assertEqual(result["values"], {"model": "gpt-test", "model_reasoning_effort": "high"})
        self.assertNotIn("do-not-emit", json.dumps(result))

    def test_login_status_redacts_email_and_bearer_value(self) -> None:
        address = "person" + "@" + "example.net"
        email = inspect_codex.sanitize_login_status(f"Logged in as {address}\nmore")
        bearer = inspect_codex.sanitize_login_status("Bearer " + "abcdefghijklmnopqrstuvwxyz")
        self.assertEqual(email, "Logged in as <redacted-email>")
        self.assertEqual(bearer, "Bearer <redacted>")


class SimulatedInstallationTests(unittest.TestCase):
    def test_macos_desktop_bundle_is_preferred(self) -> None:
        discovered = [
            {"source": "PATH", "path": "/mock/path/codex"},
            {"source": "ChatGPT.app bundled", "path": "/mock/app/codex"},
        ]
        selected, reason = inspect_codex.select_codex(None, discovered)
        self.assertEqual(selected.parts[-3:], ("mock", "app", "codex"))
        self.assertIn("desktop", reason)

    def test_linux_path_install_is_the_fallback(self) -> None:
        discovered = [{"source": "PATH", "path": "/usr/local/bin/codex"}]
        selected, reason = inspect_codex.select_codex(None, discovered)
        self.assertEqual(selected.parts[-4:], ("usr", "local", "bin", "codex"))
        self.assertEqual(reason, "PATH fallback")

    def test_windows_explicit_executable_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "codex.exe"
            executable.write_bytes(b"mock")
            selected, reason = inspect_codex.select_codex(str(executable), [])
        self.assertEqual(selected, executable.resolve())
        self.assertEqual(reason, "explicit --codex-path")

    def test_mock_client_report_preserves_evidence_boundaries(self) -> None:
        fake = Path("/mock/codex")
        commands = {
            (str(fake), "--version"): (0, "codex-cli 9.9.9"),
            (str(fake), "login", "status"): (0, "Logged in using ChatGPT"),
        }

        def output(command: list[str], timeout: int = 15) -> tuple[int, str]:
            return commands[tuple(command)]

        with (
            mock.patch.object(inspect_codex, "discover_codex", return_value=[{"source": "PATH", "path": str(fake)}]),
            mock.patch.object(inspect_codex, "load_safe_config", return_value={"status": "not_found", "values": {}}),
            mock.patch.object(inspect_codex, "command_output", side_effect=output),
            mock.patch.object(
                inspect_codex,
                "scan_binary",
                return_value={"status": "passive_binary_strings", "endpoint_candidates": []},
            ),
        ):
            report = inspect_codex.inspect(False, None)

        self.assertEqual(report["client"]["version"], "codex-cli 9.9.9")
        self.assertEqual(report["active_diagnostics"]["status"], "not_requested")
        self.assertFalse(report["safety"]["credentials_read"])


class DoctorFilteringTests(unittest.TestCase):
    def test_doctor_output_is_allowlisted(self) -> None:
        payload = {
            "checks": {
                "auth.credentials": {
                    "details": {
                        "stored auth mode": "chatgpt",
                        "secret token": "must-not-escape",
                    }
                },
                "config.load": {"details": {"model": "gpt-test"}},
                "network.websocket_reachability": {
                    "details": {
                        "endpoint": "wss://example.invalid/redacted",
                        "handshake result": "HTTP 101 Switching Protocols",
                        "supports websockets": "true",
                        "wire API": "responses",
                        "authorization": "must-not-escape",
                    }
                },
            }
        }
        with mock.patch.object(inspect_codex, "command_output", return_value=(1, json.dumps(payload))):
            result = inspect_codex.safe_doctor(Path("/mock/codex"))
        serialized = json.dumps(result)
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["fields"]["wire_api"], "responses")
        self.assertNotIn("must-not-escape", serialized)
        self.assertNotIn("authorization", serialized)

    def test_endpoint_sanitizer_fails_closed_on_an_invalid_port(self) -> None:
        self.assertEqual(
            inspect_codex.sanitize_endpoint("https://example.invalid:not-a-port/responses"),
            "<redacted-endpoint>",
        )

    def test_allowlisted_container_value_fails_closed(self) -> None:
        self.assertEqual(
            inspect_codex.sanitize_allowlisted_value({"nested": "do-not-emit"}),
            "<unsupported-value>",
        )


if __name__ == "__main__":
    unittest.main()
