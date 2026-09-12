---
name: codex-client-request-inspector
description: Safely inspect a locally installed Codex client's current model, reasoning effort, Responses transport, and endpoint evidence without extracting credentials or replaying private ChatGPT sessions. Use for Codex request-path diagnostics, version comparisons, and supported API migration planning.
---

# Codex Client Request Inspector

Inspect the installed client read-only and report what is observed, derived, or merely inferred. The goal is reproducible protocol diagnosis, not credential extraction or unofficial API access.

## Non-negotiable boundaries

- Never read or print `auth.json`, browser storage, cookies, keychain entries, OAuth tokens, API keys, request authorization headers, or environment-variable values.
- Never intercept TLS, install a certificate, bypass certificate pinning, patch the client, attach a debugger to capture secrets, or generate replay code for a private ChatGPT request.
- Never present `chatgpt.com/backend-api/*` as a supported third-party API. It may be reported as current-client evidence only.
- Use the official OpenAI Responses API for implementation guidance. Keep server credentials server-side.
- If the user asks to reuse a Plus/Pro login outside the official Codex client, explain the boundary and offer the supported API design instead.

## Workflow

1. Run the passive inspector first:

   ```bash
   python3 scripts/inspect_codex.py --json
   ```

   On macOS the script prefers the Codex executable bundled with `ChatGPT.app` and also reports other discovered installations. Use `--codex-path <path>` when the user explicitly wants a different CLI installation inspected.

2. Read [references/evidence-grading.md](references/evidence-grading.md) and classify every conclusion. Do not combine a binary string with a live observation without labeling the derivation.
3. When a current network handshake is required, tell the user that the check will contact the configured Codex provider using the client's existing login, then run:

   ```bash
   python3 scripts/inspect_codex.py --doctor --json
   ```

   The script selects only allowlisted diagnostic fields and never emits the raw doctor payload.
4. For an integration or migration request, read [references/supported-integration.md](references/supported-integration.md). Use official documentation to reverify the current model and Responses fields because endpoints and capabilities can change.
5. Report four separate sections when applicable:

   - installed client and configuration;
   - live transport evidence;
   - binary-derived endpoint candidates;
   - supported public API equivalent.

## Acceptance criteria

- State the Codex version and executable actually inspected.
- State the configured model and reasoning effort only when observed from allowlisted configuration or diagnostics.
- State whether transport evidence is passive or from an active handshake.
- Redact all account identifiers and credentials.
- Mark exact request bodies as schemas or informed reconstructions unless a safe official trace supplied them.
- Cite official OpenAI documentation for supported public integration claims.
