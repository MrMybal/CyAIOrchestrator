---
id: background
title: Background evaluations
description: Run isolated trials without filling the conversation list.
section: Agents & background work
parent: methods
order: 11
revision: 1
---


1. Define corpus, expected outputs and scoring rules. Select exact model variants.
2. Prepare independent candidate runs in isolated background workspaces; do not reuse candidate history.
3. Authorize campaign launch. Follow its controlling conversation, cards or logs; hide background cards to reclaim space.
4. Wait for terminal states and distinguish completed, failed, cancelled and untested cases before comparing scores.

For large-context tests, inspect the content delivered through the connector. Record corpus size, model identifier, provider context information and transport errors. A short pilot does not measure massive-context performance. If tools are forbidden, check actual tool traces before grading.

```callout
{"type": "info", "title": "Keep in mind", "body": "A launch acknowledgement or mission identifier is not a completed test. Automatic follow-up must be configured in the chain/controller or an active orchestrating run; recording a result alone does not guarantee an idle conversation wakes up."}
```


## Related chapters {#related}

- [Methods, tests & revisions](doc:methods)
- [Plans, missions & parallel work](doc:orchestration)
- [Logs, resources & usage](doc:diagnostics)
