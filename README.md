# Codex Client Request Inspector Skill

A credential-safe Codex Skill for identifying the installed client's model, reasoning effort, Responses transport, and endpoint evidence.

It deliberately does **not** extract OAuth tokens, API keys, cookies, browser storage, keychain entries, or raw authorization headers. Private ChatGPT backend observations are diagnostic evidence only, not a supported integration API.

## Run the inspector

```bash
python3 scripts/inspect_codex.py --json
```

Run the optional allowlisted network diagnostic:

```bash
python3 scripts/inspect_codex.py --doctor --json
```

See [SKILL.md](SKILL.md) for the complete workflow and evidence rules.

## Validate the package

```bash
python3 scripts/validate_skill.py
python3 scripts/scan_sensitive.py
python3 -m unittest discover -s tests -v
```

GitHub Actions runs the same gates on macOS, Windows, and Linux. Version tags publish a platform-neutral ZIP and TAR.GZ with SHA-256 checksums.
