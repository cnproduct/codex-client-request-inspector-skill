#!/usr/bin/env python3
"""Dependency-free structural validation for this repository-root Skill."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"


def fail(message: str) -> None:
    raise ValueError(message)


def frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if len(lines) < 4 or lines[0] != "---":
        fail("SKILL.md must start with YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("SKILL.md frontmatter is not closed") from exc
    result: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def validate() -> None:
    text = SKILL.read_text(encoding="utf-8")
    metadata = frontmatter(text)
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not re.fullmatch(r"[a-z0-9-]{1,63}", name):
        fail("frontmatter name must use lowercase letters, digits, and hyphens")
    if len(description) < 40:
        fail("frontmatter description is missing or not discriminating")
    if "TODO" in text or "[TODO" in text:
        fail("unfinished scaffold placeholder found")

    required = (
        ROOT / "agents" / "openai.yaml",
        ROOT / "scripts" / "inspect_codex.py",
        ROOT / "scripts" / "codex_snapshot.py",
        ROOT / "references" / "evidence-grading.md",
        ROOT / "references" / "snapshot-comparison.md",
        ROOT / "references" / "supported-integration.md",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        fail(f"missing required files: {', '.join(missing)}")

    for match in re.finditer(r"\[[^]]+\]\(([^)]+)\)", text):
        target = match.group(1)
        if "://" not in target and not (ROOT / target).is_file():
            fail(f"broken local reference: {target}")

    openai_yaml = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    if f"${name}" not in openai_yaml:
        fail("agents/openai.yaml default prompt must mention the Skill name")


if __name__ == "__main__":
    try:
        validate()
    except (OSError, ValueError) as exc:
        print(f"SKILL_VALIDATION_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print("SKILL_VALIDATION_OK")
