---
id: permissions
title: Autorisations et lancement
description: Choisir une politique et comprendre son périmètre.
section: Agents et arrière-plan
parent: orchestration
order: 6
revision: 1
sourceRevision: 1
---


La conversation peut hériter de la politique globale ou la remplacer. Le mode automatique autorise à votre place les outils pris en charge dans le périmètre configuré. Le mode manuel attend votre décision. Le fournisseur natif peut imposer des règles supplémentaires.

1. Choisissez la politique et vérifiez dossiers de travail et accès.
2. Pour une orchestration, relisez puis lancez explicitement le plan. La politique des outils ne lance pas toutes les campagnes futures.
3. Si un travail attend, consultez la demande dans les détails. Pour un refus natif, vérifiez réglages et logs du fournisseur.

```callout
{"type": "info", "title": "À retenir", "body": "Certaines demandes natives ne peuvent pas être relayées. Elles sont signalées comme non prises en charge ; le mode automatique ne crée pas une capacité absente. Une annulation termine la tentative sans annuler ses effets passés."}
```


## Chapitres associés {#related}

- [Plans, missions et travail parallèle](doc:orchestration)
- [Serveurs MCP locaux et accès IA](doc:mcp)
- [Dépannage](doc:troubleshooting)
