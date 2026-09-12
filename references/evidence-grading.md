# Evidence grading

Use these labels verbatim when they clarify the answer.

## Observed

Directly returned by the installed executable, an allowlisted local configuration key, or `codex doctor --json`. Examples include the client version, configured model, configured reasoning effort, wire API, and a successful WebSocket handshake.

## Binary-derived

Static strings found in the installed executable. A complete URL is evidence that the build contains that URL, not proof that the current request used it. A base URL and a nearby path fragment may be combined only when clearly labeled as a derivation.

## Documented

Supported behavior stated in current official OpenAI documentation. Use this grade for the public Responses endpoint, model capabilities, request fields, and event schemas.

## Inferred

A reconstructed request shape based on observed settings plus documented schemas. Never claim an inferred request body is a captured packet. Optional fields and headers can vary by client version, account mode, and rollout.

## Not established

Anything requiring TLS interception, secret access, packet-body capture, or a raw OAuth session should remain unverified. Do not weaken the safety boundary to close this grade.

