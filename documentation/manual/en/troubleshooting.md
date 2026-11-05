---
id: troubleshooting
title: Troubleshooting
description: Identify the failed stage before retrying an operation.
section: Settings & maintenance
order: 25
revision: 1
---


| Symptom | What to check |
| --- | --- |
| Settings keep loading | Wait for the visible loading state, then retry that section. Check Logs for its actual error; model discovery and downloads are separate operations. |
| No response from an agent | Enabled connector, verified authentication, exact model, native executable/endpoint and last provider error. A CLI subscription is different from API credit. |
| Waiting for authorization | Conversation policy, pending request, access scope and native-provider rules. Inspect execution details. |
| MCP tools absent | Registered integration, active project binding, assigned agent tool pack, server availability and current session’s tool list. |
| Path outside conversation folders | File existence, original attachment, registered work folders and correct local link. Attach/import or register the intended folder. |
| Model fails to load | Runtime compatibility, actual memory, GPU offload, context configuration and loading log. Orange estimates are guidance. |
| No dictation or speech | Device permission, selected engine/voice, completed download, language support and whether recording/reading is enabled. |
| A successful tool returned no final result | Look for a job/mission identifier and inspect its terminal status; follow-up queries are not the underlying result. |
| Background tests do not continue | Check the campaign graph/controller and active orchestrating run. A finished pilot does not automatically launch an unspecified next batch. |
| 3D materials are missing | Embedded textures and supported GLB/glTF extensions. OBJ loads geometry without MTL; external companion resources may be unavailable. |
| Context test omitted late information | Verify the complete delivered corpus and transport trace before concluding the model failed at that context size. |
| Interrupted or failed mission | Inspect its error and existing file effects. Review the retry options; cancellation does not roll changes back. |

## Prepare a useful diagnostic {#help-part-1}

1. Record the CyAI version, connector, exact model, action and timestamp.
2. Open the relevant log/event and preserve its error, job identifier and status. Remove private information before sharing.
3. Use Diagnose with AI to prepare a message in the conversation. Review and send it yourself; preparing it does not silently relaunch the failed work.

## Related chapters {#related}

- [Logs, resources & usage](doc:diagnostics)
- [Permissions & launch decisions](doc:permissions)
- [History, exports & backups](doc:backups)
