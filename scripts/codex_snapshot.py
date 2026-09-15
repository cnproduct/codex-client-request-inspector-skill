#!/usr/bin/env python3
"""Capture and compare credential-safe Codex client snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inspect_codex import inspect, sanitize_allowlisted_value, sanitize_endpoint


INSPECTOR_VERSION = "1.1.0"
SNAPSHOT_SCHEMA_VERSION = 1
COMPARISON_SCHEMA_VERSION = 1

CONFIGURATION_KEYS = (
    "model",
    "model_reasoning_effort",
    "model_reasoning_summary",
    "model_verbosity",
    "service_tier",
)

TRANSPORT_KEYS = (
    "auth_mode",
    "configured_model",
    "model_provider",
    "provider_name",
    "endpoint",
    "handshake_result",
    "supports_websockets",
    "wire_api",
)

COMPARE_FIELDS = {
    "client.version": ("info", "Installed Codex client version changed."),
    "client.selection": ("info", "The selected installation source changed."),
    "configuration.model": ("attention", "Configured model changed."),
    "configuration.model_reasoning_effort": ("attention", "Configured reasoning effort changed."),
    "configuration.model_reasoning_summary": ("info", "Reasoning summary preference changed."),
    "configuration.model_verbosity": ("info", "Model verbosity preference changed."),
    "configuration.service_tier": ("attention", "Configured service tier changed."),
    "transport.auth_mode": ("attention", "Allowlisted authentication mode changed."),
    "transport.configured_model": ("attention", "Model reported by active diagnostics changed."),
    "transport.model_provider": ("attention", "Active diagnostic provider changed."),
    "transport.provider_name": ("attention", "Active diagnostic provider name changed."),
    "transport.endpoint": ("attention", "Active diagnostic endpoint changed."),
    "transport.handshake_result": ("attention", "Active handshake result changed."),
    "transport.supports_websockets": ("attention", "Reported WebSocket capability changed."),
    "transport.wire_api": ("attention", "Reported wire API changed."),
    "passive.endpoint_candidates": ("info", "Binary-derived endpoint candidates changed."),
    "passive.protocol_fragments": ("info", "Binary-derived protocol fragments changed."),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_scalar(value: Any) -> str | int | float | bool | None:
    return sanitize_allowlisted_value(value)


def build_snapshot(report: dict[str, Any], captured_at: str | None = None) -> dict[str, Any]:
    client = report.get("client", {}) if isinstance(report.get("client"), dict) else {}
    config = report.get("configuration", {}) if isinstance(report.get("configuration"), dict) else {}
    config_values = config.get("values", {}) if isinstance(config.get("values"), dict) else {}
    active = report.get("active_diagnostics", {})
    active = active if isinstance(active, dict) else {}
    active_fields = active.get("fields", {}) if isinstance(active.get("fields"), dict) else {}
    passive = report.get("passive_evidence", {})
    passive = passive if isinstance(passive, dict) else {}
    host = report.get("host", {}) if isinstance(report.get("host"), dict) else {}

    transport: dict[str, Any] = {}
    for key in TRANSPORT_KEYS:
        if key not in active_fields:
            continue
        value = active_fields[key]
        transport[key] = sanitize_endpoint(value) if key == "endpoint" else safe_scalar(value)

    return {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "captured_at": captured_at or utc_now(),
        "inspector_version": INSPECTOR_VERSION,
        "capture_mode": (
            "active_allowlisted" if active.get("status") == "active_allowlisted_diagnostics" else "passive"
        ),
        "platform": {
            "system": safe_scalar(host.get("system")),
            "machine": safe_scalar(host.get("machine")),
        },
        "client": {
            "status": safe_scalar(client.get("status")),
            "version": safe_scalar(client.get("version")),
            "selection": safe_scalar(client.get("selected_reason")),
        },
        "configuration": {
            key: safe_scalar(config_values[key]) for key in CONFIGURATION_KEYS if key in config_values
        },
        "transport": transport,
        "passive": {
            "status": safe_scalar(passive.get("status")),
            "endpoint_candidates": sorted(
                sanitize_endpoint(value)
                for value in passive.get("endpoint_candidates", [])
                if isinstance(value, str)
            ),
            "protocol_fragments": sorted(
                str(value)[:120]
                for value in passive.get("protocol_fragments", [])
                if isinstance(value, str)
            ),
        },
        "safety": {
            "credentials_stored": False,
            "account_identifiers_stored": False,
            "local_paths_stored": False,
            "raw_diagnostics_stored": False,
        },
    }


def canonical_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(f"unsupported snapshot schema: {payload.get('snapshot_schema_version')!r}")

    result: dict[str, Any] = {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "captured_at": safe_scalar(payload.get("captured_at")),
        "inspector_version": safe_scalar(payload.get("inspector_version")),
        "capture_mode": safe_scalar(payload.get("capture_mode")),
    }
    for section, keys in (
        ("platform", ("system", "machine")),
        ("client", ("status", "version", "selection")),
        ("configuration", CONFIGURATION_KEYS),
        ("transport", TRANSPORT_KEYS),
    ):
        source = payload.get(section, {})
        source = source if isinstance(source, dict) else {}
        result[section] = {
            key: (sanitize_endpoint(source[key]) if key == "endpoint" else safe_scalar(source[key]))
            for key in keys
            if key in source
        }

    passive = payload.get("passive", {})
    passive = passive if isinstance(passive, dict) else {}
    result["passive"] = {
        "status": safe_scalar(passive.get("status")),
        "endpoint_candidates": sorted(
            sanitize_endpoint(value)
            for value in passive.get("endpoint_candidates", [])
            if isinstance(value, str)
        ),
        "protocol_fragments": sorted(
            str(value)[:120]
            for value in passive.get("protocol_fragments", [])
            if isinstance(value, str)
        ),
    }
    result["safety"] = {
        "credentials_stored": False,
        "account_identifiers_stored": False,
        "local_paths_stored": False,
        "raw_diagnostics_stored": False,
    }
    return result


def get_path(payload: dict[str, Any], dotted: str) -> Any:
    value: Any = payload
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def compare_snapshots(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    old = canonical_snapshot(baseline)
    new = canonical_snapshot(current)
    changes: list[dict[str, Any]] = []
    for field, (severity, interpretation) in COMPARE_FIELDS.items():
        before = get_path(old, field)
        after = get_path(new, field)
        if before != after:
            changes.append(
                {
                    "field": field,
                    "before": before,
                    "after": after,
                    "severity": severity,
                    "interpretation": interpretation,
                }
            )

    return {
        "comparison_schema_version": COMPARISON_SCHEMA_VERSION,
        "status": "changed" if changes else "no_change",
        "baseline": {
            "captured_at": old.get("captured_at"),
            "client_version": get_path(old, "client.version"),
        },
        "current": {
            "captured_at": new.get("captured_at"),
            "client_version": get_path(new, "client.version"),
        },
        "changes": changes,
        "evidence_boundary": (
            "Snapshot differences are allowlisted observations or binary-derived evidence. "
            "They are not captured request bodies and do not establish a supported private API."
        ),
        "safety": {
            "credentials_included": False,
            "account_identifiers_included": False,
            "local_paths_included": False,
        },
    }


def markdown_report(comparison: dict[str, Any]) -> str:
    baseline = comparison["baseline"]
    current = comparison["current"]
    lines = [
        "# Codex client snapshot comparison",
        "",
        f"Status: **{comparison['status']}**",
        "",
        f"- Baseline: `{baseline.get('client_version') or 'unknown'}` at `{baseline.get('captured_at') or 'unknown'}`",
        f"- Current: `{current.get('client_version') or 'unknown'}` at `{current.get('captured_at') or 'unknown'}`",
        "",
    ]
    if comparison["changes"]:
        lines.extend(["| Field | Severity | Before | After |", "|---|---|---|---|"])
        for change in comparison["changes"]:
            before = json.dumps(change["before"], ensure_ascii=False).replace("|", "\\|")
            after = json.dumps(change["after"], ensure_ascii=False).replace("|", "\\|")
            lines.append(
                f"| `{change['field']}` | {change['severity']} | `{before}` | `{after}` |"
            )
        lines.append("")
    else:
        lines.extend(["No allowlisted request-path changes were detected.", ""])
    lines.extend(["## Evidence boundary", "", comparison["evidence_boundary"], ""])
    return "\n".join(lines)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("snapshot must be a JSON object")
    return payload


def emit(content: str, output: str | None) -> None:
    if not output or output == "-":
        print(content)
        return
    path = Path(output).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content + ("" if content.endswith("\n") else "\n"), encoding="utf-8")
    temporary.replace(path)
    print(f"WROTE {path}")


def capture_command(args: argparse.Namespace) -> int:
    report = inspect(args.doctor, args.codex_path)
    snapshot = build_snapshot(report)
    emit(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True), args.output)
    return 0 if snapshot.get("client", {}).get("status") == "found" else 1


def compare_command(args: argparse.Namespace) -> int:
    comparison = compare_snapshots(load_json(Path(args.baseline)), load_json(Path(args.current)))
    content = (
        markdown_report(comparison)
        if args.format == "markdown"
        else json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True)
    )
    emit(content, args.output)
    return 3 if args.fail_on_change and comparison["status"] == "changed" else 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Capture and compare credential-safe Codex client snapshots.")
    commands = root.add_subparsers(dest="command", required=True)

    capture = commands.add_parser("capture", help="Capture an allowlisted snapshot.")
    capture.add_argument("--output", required=True, help="Snapshot path, or - for stdout.")
    capture.add_argument("--doctor", action="store_true", help="Include allowlisted live diagnostics.")
    capture.add_argument("--codex-path", help="Inspect an explicit Codex executable.")
    capture.set_defaults(handler=capture_command)

    compare = commands.add_parser("compare", help="Compare two snapshots.")
    compare.add_argument("baseline", help="Earlier snapshot JSON path.")
    compare.add_argument("current", help="Current snapshot JSON path.")
    compare.add_argument("--format", choices=("json", "markdown"), default="json")
    compare.add_argument("--output", help="Report path, or - for stdout.")
    compare.add_argument(
        "--fail-on-change",
        action="store_true",
        help="Return exit code 3 when an allowlisted field changed.",
    )
    compare.set_defaults(handler=compare_command)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"SNAPSHOT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
