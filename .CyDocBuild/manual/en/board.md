---
id: board
title: Task board & delegation
description: Separate assignment, execution, report and acceptance.
section: Agents & background work
parent: agents
order: 9
revision: 1
---


```image
{"id": "task-board", "src": "assets/images/task-board-en.png", "alt": "Task assignments and review columns", "title": "Sample cards illustrate workflow, not benchmark results.", "controls": "minimal"}
```


1. Create the team, then add a board card with objective, owner, file scope, dependencies and acceptance criteria.
2. Move it to Ready when prerequisites are satisfied. Start its agent from the card or use the delegation controller.
3. Inspect the run’s report, changed files, executed checks and limitations. A returned report needs review.
4. Accept reviewed results or request corrections. The user or an eligible reviewer records that decision.

| State | Meaning |
| --- | --- |
| To prepare / Ready | Define scope and dependencies before launch. |
| In progress / Awaiting information | Work started or needs information. Open its card for available pause, stop and consultation actions. |
| In review / To correct | Report awaiting review, or changes requested. |
| Done / Failed / Cancelled | Final decision recorded. Done follows acceptance, not a success sentence. |

The controller preview lists eligible actions. Advancing one step performs one pass; automatic mode keeps advancing according to its configured policy. Monitor active runs, reviews and waits. Stop the controller explicitly to prevent further delegation. A card colour alone does not prove an agent is running.

## Related chapters {#related}

- [Agent library & teams](doc:agents)
- [Plans, missions & parallel work](doc:orchestration)
- [Logs, resources & usage](doc:diagnostics)
