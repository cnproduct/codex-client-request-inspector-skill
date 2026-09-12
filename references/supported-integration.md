# Supported integration boundary

## Current-client diagnosis

Codex may use a ChatGPT-authenticated private backend when the user signs in with ChatGPT. Report that route only as version-specific client evidence. It is not a contractual integration surface and may change without notice.

## Application integration

Build third-party applications against the official OpenAI Responses API documented at:

- <https://developers.openai.com/api/reference/cli/resources/responses/methods/create>
- <https://developers.openai.com/api/docs/models>

Recheck these pages before implementation because model names, supported reasoning efforts, transports, usage fields, and service tiers can change.

Keep API credentials on the application server. Never send them to a browser or ordinary desktop client. For metered products, correlate each request with the final response `usage` object and keep failure/cancellation handling separate from successful settlement.

## Safe public request skeleton

```json
{
  "model": "<current-supported-model>",
  "reasoning": {
    "effort": "<supported-effort>"
  },
  "input": "<user-input>"
}
```

Do not bake a model snapshot or endpoint discovered from a private client into production code without confirming it in official documentation.
