---
id: orchestration
title: Plans, missions & parallel work
description: Turn a goal into dependent tasks and follow execution.
section: Agents & background work
parent: agents
order: 7
revision: 1
---


1. Create an orchestrator conversation with a connector supporting planning.
2. Describe objective, deliverables, constraints and checks. Request independent branches for parallel work.
3. Review steps, connector/model assignments, dependencies, concurrency and time settings; then approve launch.
4. Follow execution details. After interruption, check existing changes before retrying unsuccessful steps.

```diagram
{"type": "flow", "title": "Parallel branches and review", "nodes": [{"id": "node-0", "label": "Goal", "x": 0, "y": 130, "w": 220, "h": 72}, {"id": "node-1", "label": "Plan & approval", "x": 260, "y": 130, "w": 220, "h": 72}, {"id": "node-2", "label": "Website", "x": 540, "y": 0, "w": 220, "h": 72}, {"id": "node-3", "label": "3D assets", "x": 540, "y": 130, "w": 220, "h": 72}, {"id": "node-4", "label": "Documentation", "x": 540, "y": 260, "w": 220, "h": 72}, {"id": "node-5", "label": "Final review", "x": 820, "y": 130, "w": 220, "h": 72}], "edges": [{"from": "node-0", "to": "node-1"}, {"from": "node-1", "to": "node-2"}, {"from": "node-1", "to": "node-3"}, {"from": "node-1", "to": "node-4"}, {"from": "node-2", "to": "node-5"}, {"from": "node-3", "to": "node-5"}, {"from": "node-4", "to": "node-5"}]}
```


Independent branches can run concurrently after launch. Final review waits for its successful prerequisites.

A manually composed mission can also have multiple steps. A successful step means that execution completed, not that the deliverable was accepted. Retry preserves successful steps. Coordinate file ownership when branches write to the same project.

```callout
{"type": "info", "title": "Keep in mind", "body": "The integrated local engine handles one generation at a time. Concurrency cannot make it serve simultaneous model requests. A mission timeout includes waiting and approvals, not just generation."}
```


## Related chapters {#related}

- [Task board & delegation](doc:board)
- [Background evaluations](doc:background)
- [Permissions & launch decisions](doc:permissions)
