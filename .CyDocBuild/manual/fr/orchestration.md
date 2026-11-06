---
id: orchestration
title: Plans, missions et travail parallèle
description: Transformer un objectif en tâches et suivre leur exécution.
section: Agents et arrière-plan
parent: agents
order: 7
revision: 1
sourceRevision: 1
---


1. Créez une conversation orchestrateur avec un connecteur compatible.
2. Décrivez objectif, livrables, contraintes et vérifications. Demandez des branches indépendantes pour le parallèle.
3. Relisez étapes, connecteurs/modèles, dépendances, concurrence et durée ; autorisez ensuite le lancement.
4. Suivez les détails. Après interruption, vérifiez les effets existants avant la reprise des étapes non réussies.

```diagram
{"type": "flow", "title": "Branches parallèles et revue", "nodes": [{"id": "node-0", "label": "Objectif", "x": 0, "y": 130, "w": 220, "h": 72}, {"id": "node-1", "label": "Plan et accord", "x": 260, "y": 130, "w": 220, "h": 72}, {"id": "node-2", "label": "Site web", "x": 540, "y": 0, "w": 220, "h": 72}, {"id": "node-3", "label": "Assets 3D", "x": 540, "y": 130, "w": 220, "h": 72}, {"id": "node-4", "label": "Documentation", "x": 540, "y": 260, "w": 220, "h": 72}, {"id": "node-5", "label": "Revue finale", "x": 820, "y": 130, "w": 220, "h": 72}], "edges": [{"from": "node-0", "to": "node-1"}, {"from": "node-1", "to": "node-2"}, {"from": "node-1", "to": "node-3"}, {"from": "node-1", "to": "node-4"}, {"from": "node-2", "to": "node-5"}, {"from": "node-3", "to": "node-5"}, {"from": "node-4", "to": "node-5"}]}
```


Après lancement, les branches indépendantes peuvent tourner ensemble. La revue finale attend la réussite de ses prérequis.

Une mission manuelle peut aussi contenir plusieurs étapes. Une étape réussie signifie exécution terminée, pas livrable accepté. La reprise conserve les étapes réussies. Coordonnez les fichiers si les branches écrivent dans le même projet.

```callout
{"type": "info", "title": "À retenir", "body": "Le moteur local intégré traite une génération à la fois. La concurrence ne lui permet pas des requêtes simultanées. La durée limite inclut attentes et autorisations, pas seulement la génération."}
```


## Chapitres associés {#related}

- [Board et délégation](doc:board)
- [Évaluations en arrière-plan](doc:background)
- [Autorisations et lancement](doc:permissions)
