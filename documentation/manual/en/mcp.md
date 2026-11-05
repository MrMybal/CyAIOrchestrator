---
id: mcp
title: Local MCP servers & AI access
description: Register tools, expose them deliberately and follow their jobs.
section: Files, media & integrations
order: 18
revision: 1
---


1. In Settings → MCP, register an existing server, such as Blender, with its transport and command/arguments or HTTP endpoint. Import a supported configuration where available.
2. Check the required software/runtime and credentials. Registering the configuration alone does not prove the server works.
3. Expose the integration to the intended project/profile and tool assignment. Read-only and write tools follow their declared permissions and the conversation policy.
4. Run a small tool call and inspect MCP operations in Logs. Follow asynchronous jobs to a terminal state.

```diagram
{"type": "flow", "title": "An MCP operation", "nodes": [{"id": "node-0", "label": "Agent", "x": 0, "y": 0, "w": 220, "h": 72}, {"id": "node-1", "label": "Exposed tool", "x": 260, "y": 0, "w": 220, "h": 72}, {"id": "node-2", "label": "Permissions", "x": 520, "y": 0, "w": 220, "h": 72}, {"id": "node-3", "label": "MCP server", "x": 780, "y": 0, "w": 220, "h": 72}, {"id": "node-4", "label": "Job / result", "x": 1040, "y": 0, "w": 220, "h": 72}], "edges": [{"from": "node-0", "to": "node-1"}, {"from": "node-1", "to": "node-2"}, {"from": "node-2", "to": "node-3"}, {"from": "node-3", "to": "node-4"}]}
```


The agent sees assigned tools. Supported requests pass through their permission policy, reach the server and return a result or a job to follow.

CyAI also exposes its own MCP bridge to the running local service. Generate client configuration in MCP settings, select project scope and read/write access, and use the generated command in the external agent. The bridge requires CyAI’s service to be running. Scope prevents a project client from implicitly accessing every project.

```callout
{"type": "info", "title": "Keep in mind", "body": "Installing Blender or finding an MCP folder does not automatically expose its tools to an active session. Check registration, assignment, server availability and the session’s refreshed tool list. Never paste credential values into a conversation to configure a server."}
```


[Open MCP settings](doc:mcp?app-settings=mcp)

## Related chapters {#related}

- [Plugins & CyTools](doc:extensions)
- [Permissions & launch decisions](doc:permissions)
- [Logs, resources & usage](doc:diagnostics)
