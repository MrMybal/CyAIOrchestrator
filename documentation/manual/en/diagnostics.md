---
id: diagnostics
title: Logs, resources & usage
description: Inspect execution evidence and measurements over time.
section: Settings & maintenance
order: 23
revision: 1
---


1. Open Logs from the rail. Select Journal, RAW, MCP operations, Connectors or Resources in its vertical navigation.
2. Filter the journal by source, level or text. Open the relevant operation rather than inferring success from its title.
3. Use RAW for structured events and MCP operations for application tool calls and returned results.
4. In Resources, inspect CPU, RAM, GPU, VRAM and disk history where available. Export relevant diagnostics for troubleshooting.

Connector status distinguishes disabled, configured, installed, operational and error states. Measurements can be missing depending on Windows/GPU counters. CyAI process memory, local-model memory and total system usage are different quantities. The composer shows provider usage and quota only when supplied.

```callout
{"type": "info", "title": "Keep in mind", "body": "Unknown readings are not zero. Exported diagnostics may contain project prompts, paths or provider output; review the export before sharing it. An MCP poll may succeed while the underlying job is still running or has failed."}
```


## Related chapters {#related}

- [Troubleshooting](doc:troubleshooting)
- [Context, memory & usage](doc:context)
- [Local MCP servers & AI access](doc:mcp)
