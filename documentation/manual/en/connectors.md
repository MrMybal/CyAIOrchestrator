---
id: connectors
title: Connectors & models
description: Connect an account, API or local engine.
section: Getting started
order: 3
revision: 1
---


1. Open Settings → Connectors. Enable the integration and configure its model, executable or endpoint.
2. For a native CLI, install it and authenticate with the provider. For an API, enter the key in the dedicated field.
3. Check the connection, refresh its model catalogue if needed, then choose the connector and model in the composer.

| Connector | Behaviour |
| --- | --- |
| Codex | App Server, native sessions, streaming and supported tool approvals. |
| Claude Code | Local CLI/SDK; sessions are separate from Claude Desktop. CLI is an optional download. |
| OpenCode | Local server; approved file tools, with shell/delegation restricted by this adapter. |
| Anthropic API / OpenRouter | API key and model required. Tools depend on the adapter; generation alone is not a full native agent. |
| Ollama / CyAI local | Local generation. CyAI local uses a downloaded llama.cpp runtime and GGUF model. |
| Other native adapters | Command Code, CodeBuddy, Antigravity and Devin need their own CLI setup. Antigravity and Devin do not prepare orchestrator plans in this integration. |

```callout
{"type": "info", "title": "Keep in mind", "body": "Installed or configured does not mean verified. A ChatGPT or Claude subscription does not automatically provide API credit. Quotas, available models and reasoning/speed settings depend on the provider."}
```


[Open connectors](doc:connectors?app-settings=connectors)

## Related chapters {#related}

- [Local models & memory](doc:local-models)
- [Permissions & launch decisions](doc:permissions)
- [Logs, resources & usage](doc:diagnostics)
