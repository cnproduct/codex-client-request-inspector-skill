#!/usr/bin/env python3
"""Fail when distributable source contains likely credentials or local identity data."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {"", ".md", ".py", ".yaml", ".yml", ".json", ".toml", ".txt"}
EXCLUDED_PARTS = {".git", "__pycache__", "dist"}

PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "provider_token": re.compile(r"\b(?:sk|gh[opsu]|xox[baprs])-[_A-Za-z0-9-]{16,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "bearer_value": re.compile(r"(?i)\bBearer\s+(?!<|\$\{)[A-Za-z0-9._~-]{12,}"),
    "local_user_path": re.compile(r"(?:/Users/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+|CloudStorage)"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b"),
}


def candidate_files() -> list[Path]:
    files = {
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in EXCLUDED_PARTS for part in path.parts)
    }
    try:
        output = subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-files"], text=True, stderr=subprocess.DEVNULL
        )
        files.update(ROOT / line for line in output.splitlines() if line)
    except (OSError, subprocess.CalledProcessError):
        pass
    return sorted(files)


def scan() -> list[str]:
    findings: list[str] = []
    for path in candidate_files():
        if (
            path.resolve() == Path(__file__).resolve()
            or any(part in EXCLUDED_PARTS for part in path.parts)
            or path.suffix.lower() not in TEXT_SUFFIXES
        ):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(lines, 1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{path.relative_to(ROOT)}:{line_number}:{label}")
    return findings


if __name__ == "__main__":
    problems = scan()
    if problems:
        print("SENSITIVE_SCAN_FAILED", file=sys.stderr)
        for problem in problems:
            print(problem, file=sys.stderr)
        raise SystemExit(1)
    print("SENSITIVE_SCAN_OK")
