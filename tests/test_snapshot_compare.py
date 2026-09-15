from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "codex_snapshot.py"
SPEC = importlib.util.spec_from_file_location("codex_snapshot", MODULE_PATH)
assert SPEC and SPEC.loader
codex_snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(codex_snapshot)


def report(
    *,
    version: str = "codex-cli 1.0.0",
    model: str = "gpt-example",
    endpoint: str = "wss://example.invalid/codex/responses",
    websocket: bool = True,
) -> dict:
    return {
        "host": {"system": "TestOS", "machine": "test64"},
        "client": {
            "status": "found",
            "version": version,
            "selected_reason": "PATH fallback",
            "executable": "/private/path/codex",
            "login_status": "Logged in as hidden account",
        },
        "configuration": {
            "path": "/private/path/config.toml",
            "status": "emitted_allowlisted_keys_only",
            "values": {"model": model, "model_reasoning_effort": "high"},
        },
        "active_diagnostics": {
            "status": "active_allowlisted_diagnostics",
            "fields": {
                "endpoint": endpoint,
                "supports_websockets": websocket,
                "wire_api": "responses",
                "configured_model": model,
            },
            "raw": "must not be stored",
        },
        "passive_evidence": {
            "status": "passive_binary_strings",
            "endpoint_candidates": ["https://api.openai.com/v1"],
            "protocol_fragments": ["/responses", "wire_api"],
        },
    }


class SnapshotSafetyTests(unittest.TestCase):
    def test_snapshot_excludes_paths_login_and_raw_diagnostics(self) -> None:
        snapshot = codex_snapshot.build_snapshot(report(), captured_at="2026-01-01T00:00:00Z")
        serialized = json.dumps(snapshot)
        self.assertNotIn("/private/path", serialized)
        self.assertNotIn("hidden account", serialized)
        self.assertNotIn("must not be stored", serialized)
        self.assertEqual(snapshot["transport"]["wire_api"], "responses")
        self.assertTrue(snapshot["transport"]["supports_websockets"])

    def test_endpoint_removes_userinfo_query_and_fragment(self) -> None:
        unsafe = "wss://name:password" + "@" + "example.invalid/codex?token=value#fragment"
        snapshot = codex_snapshot.build_snapshot(report(endpoint=unsafe))
        self.assertEqual(snapshot["transport"]["endpoint"], "wss://example.invalid/codex")
        self.assertNotIn("password", json.dumps(snapshot))
        self.assertNotIn("token=value", json.dumps(snapshot))

    def test_canonical_snapshot_discards_unknown_fields(self) -> None:
        snapshot = codex_snapshot.build_snapshot(report())
        snapshot["secret"] = "must not survive"
        snapshot["transport"]["authorization"] = "must not survive either"
        canonical = codex_snapshot.canonical_snapshot(snapshot)
        serialized = json.dumps(canonical)
        self.assertNotIn("must not survive", serialized)
        self.assertNotIn("authorization", serialized)


class SnapshotComparisonTests(unittest.TestCase):
    def test_timestamps_alone_do_not_create_a_change(self) -> None:
        old = codex_snapshot.build_snapshot(report(), captured_at="2026-01-01T00:00:00Z")
        new = codex_snapshot.build_snapshot(report(), captured_at="2026-01-02T00:00:00Z")
        comparison = codex_snapshot.compare_snapshots(old, new)
        self.assertEqual(comparison["status"], "no_change")
        self.assertEqual(comparison["changes"], [])

    def test_model_version_endpoint_and_websocket_changes_are_reported(self) -> None:
        old = codex_snapshot.build_snapshot(report(), captured_at="2026-01-01T00:00:00Z")
        new = codex_snapshot.build_snapshot(
            report(
                version="codex-cli 2.0.0",
                model="gpt-next",
                endpoint="https://api.example.invalid/v2/responses",
                websocket=False,
            ),
            captured_at="2026-01-02T00:00:00Z",
        )
        comparison = codex_snapshot.compare_snapshots(old, new)
        fields = {change["field"] for change in comparison["changes"]}
        self.assertEqual(comparison["status"], "changed")
        self.assertTrue(
            {
                "client.version",
                "configuration.model",
                "transport.configured_model",
                "transport.endpoint",
                "transport.supports_websockets",
            }.issubset(fields)
        )

    def test_markdown_is_a_bounded_diff_report(self) -> None:
        old = codex_snapshot.build_snapshot(report(), captured_at="2026-01-01T00:00:00Z")
        new = codex_snapshot.build_snapshot(report(model="gpt-next"), captured_at="2026-01-02T00:00:00Z")
        markdown = codex_snapshot.markdown_report(codex_snapshot.compare_snapshots(old, new))
        self.assertIn("configuration.model", markdown)
        self.assertIn("Evidence boundary", markdown)
        self.assertNotIn("executable", markdown)
        self.assertNotIn("login_status", markdown)

    def test_unsupported_schema_is_rejected(self) -> None:
        old = codex_snapshot.build_snapshot(report())
        new = codex_snapshot.build_snapshot(report())
        old["snapshot_schema_version"] = 999
        with self.assertRaisesRegex(ValueError, "unsupported snapshot schema"):
            codex_snapshot.compare_snapshots(old, new)

    def test_compare_cli_can_write_markdown(self) -> None:
        old = codex_snapshot.build_snapshot(report(), captured_at="2026-01-01T00:00:00Z")
        new = codex_snapshot.build_snapshot(report(version="codex-cli 2.0.0"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.json"
            current = root / "current.json"
            output = root / "diff.md"
            baseline.write_text(json.dumps(old), encoding="utf-8")
            current.write_text(json.dumps(new), encoding="utf-8")
            args = codex_snapshot.parser().parse_args(
                ["compare", str(baseline), str(current), "--format", "markdown", "--output", str(output)]
            )
            result = args.handler(args)
            content = output.read_text(encoding="utf-8")
        self.assertEqual(result, 0)
        self.assertIn("client.version", content)


if __name__ == "__main__":
    unittest.main()
