---
id: context
title: Context, memory & usage
description: Understand what reaches the model and what counters mean.
section: Your workspace
parent: projects
order: 5
revision: 1
---


```diagram
{"type": "flow", "title": "A request’s context", "nodes": [{"id": "node-0", "label": "You", "x": 0, "y": 0, "w": 220, "h": 72}, {"id": "node-1", "label": "Conversation", "x": 260, "y": 0, "w": 220, "h": 72}, {"id": "node-2", "label": "Selected context", "x": 520, "y": 0, "w": 220, "h": 72}, {"id": "node-3", "label": "Connector", "x": 780, "y": 0, "w": 220, "h": 72}, {"id": "node-4", "label": "Response & trace", "x": 1040, "y": 0, "w": 220, "h": 72}], "edges": [{"from": "node-0", "to": "node-1"}, {"from": "node-1", "to": "node-2"}, {"from": "node-2", "to": "node-3"}, {"from": "node-3", "to": "node-4"}]}
```


CyAI combines the instruction, selected history, validated memory and attachments. The connector delivers the request and returns results and events.

1. Inspect context before sending. Select specific messages or attachments when relevant.
2. Put stable decisions in shared memory; review and validate proposed entries.
3. For a long conversation, review its summary/compaction options. A fresh native session changes what the provider retains.

| Display | Interpretation |
| --- | --- |
| Input / output tokens | Reported request usage, not guaranteed remaining context. |
| Context limit | Provider-reported capacity or local configuration where available. Unknown capacity stays unknown. |
| Remaining subscription quota | Only available when supplied by the connector. Missing does not mean zero. |
| Local context / RAM | Configured context and available measurements. A larger context generally needs more memory. |

```callout
{"type": "info", "title": "Keep in mind", "body": "The preview describes CyAI’s selection. Native providers may add their own history, instructions or transport restrictions. Inspect the transmitted trace before blaming a model for missing context."}
```


## Related chapters {#related}

- [Background evaluations](doc:background)
- [Local models & memory](doc:local-models)
- [Logs, resources & usage](doc:diagnostics)
