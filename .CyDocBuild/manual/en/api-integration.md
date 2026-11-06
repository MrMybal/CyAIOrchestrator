---
id: api-integration
title: Integration API
description: Connect external clients and use public local help links.
section: Developer reference
order: 40
revision: 1
---

## Connect an MCP client {#connection}

1. Start CyAI and open Settings → MCP.
2. Select the projects the client may access, the client format and its read/write scope. Generate the configuration and use the exact command shown there.
3. Restart or refresh the external client's MCP connection. Call `cyai_actions` to discover the schemas available to this connection.

The stdio bridge communicates with the running local CyAI service. `--project` can be repeated; it does not imply access to other projects. Writes require `--allow-write`. Global library writes require the separately granted `--allow-global` scope. The bridge uses the locally stored token; do not include credential values in examples or prompts.

## Discover and call operations {#operations}

`cyai_actions` takes an optional `domain` and returns action definitions with their `inputSchema`, scope, write flag and deferred flag. `cyai_call` takes `action` and `arguments`. Use the returned schema: action availability and permissions depend on the current connection.

```json
{"domain":"conversations"}
```

After discovering `get_conversation`, call `cyai_call` with an existing conversation ID:

```json
{"action":"get_conversation","arguments":{"conversation_id":"YOUR_CONVERSATION_ID"}}
```

Common domains cover projects, conversations, memory, missions, models, local models, plugins, skills and teams. For example, `context_preview` inspects selected context, `plugins_list` lists project integrations, and `mission_status` follows an existing mission. Requests are validated against their schema and project scope. The conversation's approval policy still applies to writes; the agent cannot change that policy through `agent_settings`.

## Results and background work {#results}

A prepared mission is not launched by `create_mission`; use the discovered launch operation. A mission ID identifies a run to follow to its terminal state. Deferred application operations return `job_id`: finish the current response and inspect `job_status` with `{"id":"YOUR_JOB_ID"}`. Download operations have separate jobs followed through `local_state`. Interrupted deferred work needs an explicit resume; it is not silently repeated.

```diagram
{"type":"flow","title":"Use the discovered API","nodes":[{"id":"discover","label":"Discover schema","x":0,"y":0},{"id":"call","label":"Call within scope","x":260,"y":0},{"id":"follow","label":"Follow result or job","x":520,"y":0}],"edges":[{"from":"discover","to":"call"},{"from":"call","to":"follow"}]}
```

## Python help links {#help-links}

The `cyai.documentation` module exposes the local URL helpers below. Importing it does not start the application service. The optional `pywebview` desktop dependency is loaded only when a window is opened. These helpers return routes and URLs; they do not expose the application's internal HTTP endpoints as a stable third-party API.

```python
from cyai.documentation import documentation_url

url = documentation_url(
    page_id="start", locale="fr", anchor="help-part-1",
    state={"media": "conversation", "zoom": 1.5}, theme="dark"
)
```

## Parameters and return values {#parameters}

See [documentation_url](doc:api-cyai-documentation-documentation-url-url) for the function signature, parameters and URL return value. [canonical_route](doc:api-cyai-documentation-canonical-route-route) performs the same validation and returns a route dictionary. Both read `DocData/manifest.json`. Invalid explicit anchors or media IDs raise `ValueError`; an unknown page returns to the home guide.

## Native window integration {#native}

`DocumentationWindows(open_settings=None).open(page_id='start', locale='en', anchor='', state=None, theme='dark')` creates or reuses the process's dedicated help window and returns an object containing `opened`, `url` and `reader`. Call it from an initialized pywebview host. Reopening navigates the existing reader without replacing the main workspace. The optional settings callback accepts only the application's known settings tabs; standalone reading follows the guide link instead.

[Local MCP setup](doc:mcp) · [Permissions](doc:permissions) · [Background evaluations](doc:background)
