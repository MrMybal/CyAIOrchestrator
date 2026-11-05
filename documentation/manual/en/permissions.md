---
id: permissions
title: Permissions & launch decisions
description: Choose a policy and understand its scope.
section: Agents & background work
order: 6
revision: 1
---


Conversation authorization can inherit the global policy or override it. Automatic approval authorizes supported tool requests on your behalf within the configured scope. Manual approval waits for your decision. Native providers may enforce additional access rules.

1. Choose the conversation policy and check its working folders/access scope.
2. For orchestration, review and explicitly launch the plan. A tool policy does not launch every future campaign.
3. If work waits, inspect the exact pending request in execution details. For a native CLI refusal, check its provider configuration and logs.

```callout
{"type": "info", "title": "Keep in mind", "body": "Some native permission requests cannot be relayed by an adapter. They are reported as unsupported; automatic approval cannot create missing capabilities. Cancellation ends the attempt but does not undo completed actions."}
```


## Related chapters {#related}

- [Plans, missions & parallel work](doc:orchestration)
- [Local MCP servers & AI access](doc:mcp)
- [Troubleshooting](doc:troubleshooting)
