---
id: extensions
title: Plugins & CyTools
description: Distinguish project views from tools assigned to agents.
section: Files, media & integrations
parent: files
order: 17
revision: 1
---


```image
{"id": "cytools", "src": "assets/images/cytools-en.png", "alt": "Official CyTools catalogue", "title": "Standalone applications; engines and model weights remain separate downloads.", "controls": "minimal"}
```


| Integration | Usage |
| --- | --- |
| Plugins | Configure globally, enable per project. Only enabled plugins declaring a project view become tabs. |
| CyTools | AudioStudio, AudioLibrary, AIChat, PersonaRP, Storyboard and MeshStudio; assign tool packs to profiles or assignments. |
| CyAICodex | Scoped token or MCP configuration for shared skills and visual references. |
| CyTask | Existing server URL and agent/API token; its bundled MCP bridge needs Node.js 22+. Downloading the desktop app does not create a server account. |

1. Add installed folder detects CyTool.json, app/CyTool.json, explicit MCP configurations and supported portable/virtual-environment Python runtimes.
2. For an official download, check GitHub releases then Download and connect. Follow Downloads. This installs the portable package, not its model weights.
3. Configure and enable the integration, assign tools to the agent and test a small operation. Keep the session open while following its job.

```callout
{"type": "info", "title": "Keep in mind", "body": "A job identifier means asynchronous work. A successful status query does not mean the operation succeeded: follow Completed, Failed or Cancelled. Previous registrations remain in the collapsed compatibility section."}
```


[Open CyTools](doc:extensions?app-settings=cytools)

## Related chapters {#related}

- [Local MCP servers & AI access](doc:mcp)
- [Downloads & optional components](doc:downloads)
- [Agent library & teams](doc:agents)
