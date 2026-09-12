#!/usr/bin/env python3
"""Read-only, credential-safe inspection of a local Codex installation."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SAFE_CONFIG_KEYS = (
    "model",
    "model_reasoning_effort",
    "model_reasoning_summary",
    "model_verbosity",
    "service_tier",
)

DOCTOR_FIELDS = {
    "auth_mode": ("checks", "auth.credentials", "details", "stored auth mode"),
    "configured_model": ("checks", "config.load", "details", "model"),
    "model_provider": ("checks", "network.websocket_reachability", "details", "model provider"),
    "provider_name": ("checks", "network.websocket_reachability", "details", "provider name"),
    "endpoint": ("checks", "network.websocket_reachability", "details", "endpoint"),
    "handshake_result": ("checks", "network.websocket_reachability", "details", "handshake result"),
    "supports_websockets": ("checks", "network.websocket_reachability", "details", "supports websockets"),
    "wire_api": ("checks", "network.websocket_reachability", "details", "wire API"),
}

URL_CANDIDATES = (
    "https://chatgpt.com/backend-api/",
    "https://chatgpt.com/backend-api/codex",
    "https://api.openai.com/v1",
)


def command_output(command: list[str], timeout: int = 15) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        return result.returncode, result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, f"unavailable: {type(exc).__name__}"


def discover_codex() -> list[dict[str, str]]:
    discovered: list[dict[str, str]] = []
    candidate = shutil.which("codex")
    if candidate:
        discovered.append({"source": "PATH", "path": str(Path(candidate).resolve())})
    mac_candidate = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
    if mac_candidate.is_file():
        discovered.append({"source": "ChatGPT.app bundled", "path": str(mac_candidate)})

    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in discovered:
        if item["path"] not in seen:
            seen.add(item["path"])
            unique.append(item)
    return unique


def select_codex(explicit_path: str | None, discovered: list[dict[str, str]]) -> tuple[Path | None, str]:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        return (candidate, "explicit --codex-path") if candidate.is_file() else (None, "explicit path not found")
    for item in discovered:
        if item["source"] == "ChatGPT.app bundled":
            return Path(item["path"]), "preferred current desktop bundle"
    if discovered:
        return Path(discovered[0]["path"]), "PATH fallback"
    return None, "no installation found"


def load_safe_config() -> dict[str, Any]:
    config_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    config_path = config_home / "config.toml"
    result: dict[str, Any] = {"path": str(config_path), "values": {}}
    if not config_path.is_file():
        result["status"] = "not_found"
        return result
    try:
        import tomllib

        allowed = set(SAFE_CONFIG_KEYS)
        values: dict[str, Any] = {}
        with config_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                match = re.match(r"^([A-Za-z0-9_]+)\s*=", line)
                if not match or match.group(1) not in allowed:
                    continue
                parsed_line = tomllib.loads(line)
                key = match.group(1)
                values[key] = parsed_line[key]
        result["values"] = values
        result["status"] = "emitted_allowlisted_keys_only"
    except Exception as exc:
        result["status"] = f"parse_failed:{type(exc).__name__}"
    return result


def sanitize_login_status(value: str) -> str:
    first_line = value.splitlines()[0] if value else "unavailable"
    first_line = re.sub(r"[\w.+-]+@[\w.-]+", "<redacted-email>", first_line)
    first_line = re.sub(r"(?i)(bearer\s+)[^\s]+", r"\1<redacted>", first_line)
    return first_line[:240]


def scan_binary(binary: Path) -> dict[str, Any]:
    strings_cmd = shutil.which("strings")
    if not strings_cmd:
        return {"status": "strings_unavailable", "endpoint_candidates": []}
    code, output = command_output([strings_cmd, str(binary)], timeout=30)
    if code != 0:
        return {"status": "scan_failed", "endpoint_candidates": []}

    candidates = [candidate for candidate in URL_CANDIDATES if candidate in output]
    fragments = [
        fragment
        for fragment in ("codex/responses", "/responses", "supports_websockets", "wire_api")
        if fragment in output
    ]
    return {
        "status": "passive_binary_strings",
        "endpoint_candidates": candidates,
        "protocol_fragments": fragments,
    }


def nested_value(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def safe_doctor(codex: Path) -> dict[str, Any]:
    code, output = command_output([str(codex), "doctor", "--json"], timeout=45)
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return {"status": "invalid_json", "exit_code": code}

    selected = {name: nested_value(payload, path) for name, path in DOCTOR_FIELDS.items()}
    selected = {name: value for name, value in selected.items() if value is not None}
    return {
        "status": "active_allowlisted_diagnostics",
        "exit_code": code,
        "fields": selected,
    }


def inspect(run_doctor: bool, explicit_path: str | None) -> dict[str, Any]:
    discovered = discover_codex()
    codex, selected_reason = select_codex(explicit_path, discovered)
    report: dict[str, Any] = {
        "schema_version": 1,
        "safety": {
            "credentials_read": False,
            "raw_auth_files_read": False,
            "tls_interception": False,
        },
        "host": {"system": platform.system(), "machine": platform.machine()},
        "configuration": load_safe_config(),
        "discovered_installations": discovered,
    }
    if codex is None:
        report["client"] = {"status": "not_found"}
        return report

    version_code, version = command_output([str(codex), "--version"])
    login_code, login_status = command_output([str(codex), "login", "status"])
    report["client"] = {
        "status": "found",
        "executable": str(codex),
        "selected_reason": selected_reason,
        "version": version if version_code == 0 else "unavailable",
        "login_status": sanitize_login_status(login_status) if login_code == 0 else "unavailable",
    }
    report["passive_evidence"] = scan_binary(codex)
    report["active_diagnostics"] = safe_doctor(codex) if run_doctor else {"status": "not_requested"}
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect Codex request transport without reading or exposing credentials."
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run Codex's authenticated network diagnostics and emit allowlisted fields only.",
    )
    parser.add_argument(
        "--codex-path",
        help="Inspect this executable instead of preferring the ChatGPT desktop bundle.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    report = inspect(args.doctor, args.codex_path)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("client", {}).get("status") == "found" else 1


if __name__ == "__main__":
    sys.exit(main())
