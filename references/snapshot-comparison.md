# Safe snapshot and version comparison

The snapshot command converts the inspector's detailed local report into a small, portable allowlist. It is designed for detecting Codex client request-path changes without preserving credentials, account identifiers, local paths, or raw diagnostic output.

## Capture

Capture passive evidence:

```bash
python3 scripts/codex_snapshot.py capture --output codex-snapshot-before.json
```

When a live handshake is necessary and the user understands that the configured provider will be contacted, capture the allowlisted active diagnostic fields:

```bash
python3 scripts/codex_snapshot.py capture --doctor --output codex-snapshot-after.json
```

Use `--codex-path <path>` only when inspecting a specific installation. The executable path is used during inspection but is not retained in the snapshot.

## Compare

Create a machine-readable report:

```bash
python3 scripts/codex_snapshot.py compare codex-snapshot-before.json codex-snapshot-after.json --output codex-diff.json
```

Create a reviewable Markdown report:

```bash
python3 scripts/codex_snapshot.py compare codex-snapshot-before.json codex-snapshot-after.json --format markdown --output codex-diff.md
```

Add `--fail-on-change` in CI when any allowlisted change should return exit code 3. Invalid input or an unsupported schema returns exit code 2.

## Stored fields

- client version and installation-selection class;
- operating-system and machine architecture;
- allowlisted model, reasoning, verbosity, and service-tier settings;
- allowlisted active diagnostic provider, endpoint, handshake, WebSocket, and wire-API fields;
- binary-derived public endpoint candidates and protocol fragments;
- capture timestamp and snapshot tool version.

Endpoint query strings, fragments, passwords, and user information are removed. Unknown fields in a loaded snapshot are discarded before comparison.

## Interpretation

A change means only that an allowlisted observation or binary-derived string differs between snapshots. It does not prove the exact request body used by the client, establish that a binary string was exercised, or make a private ChatGPT backend a supported public API. Reverify integration decisions against current official documentation.
