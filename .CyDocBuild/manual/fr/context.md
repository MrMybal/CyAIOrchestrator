---
id: context
title: Contexte, mémoire et consommation
description: Comprendre ce qui arrive au modèle et ce que mesurent les compteurs.
section: Votre espace de travail
parent: projects
order: 5
revision: 1
sourceRevision: 1
---


```diagram
{"type": "flow", "title": "Contexte d’une demande", "nodes": [{"id": "node-0", "label": "Vous", "x": 0, "y": 0, "w": 220, "h": 72}, {"id": "node-1", "label": "Conversation", "x": 260, "y": 0, "w": 220, "h": 72}, {"id": "node-2", "label": "Contexte choisi", "x": 520, "y": 0, "w": 220, "h": 72}, {"id": "node-3", "label": "Connecteur", "x": 780, "y": 0, "w": 220, "h": 72}, {"id": "node-4", "label": "Réponse et trace", "x": 1040, "y": 0, "w": 220, "h": 72}], "edges": [{"from": "node-0", "to": "node-1"}, {"from": "node-1", "to": "node-2"}, {"from": "node-2", "to": "node-3"}, {"from": "node-3", "to": "node-4"}]}
```


CyAI combine consigne, historique choisi, mémoire validée et pièces jointes. Le connecteur transmet la demande et retourne réponses et événements.

1. Inspectez le contexte avant l’envoi. Sélectionnez les messages ou fichiers pertinents.
2. Conservez les décisions stables en mémoire ; relisez et validez les propositions.
3. Pour une longue conversation, examinez résumé et compaction. Une nouvelle session native change ce que conserve le fournisseur.

| Affichage | Interprétation |
| --- | --- |
| Tokens entrée / sortie | Consommation rapportée, pas une garantie de contexte restant. |
| Limite de contexte | Capacité fournie ou configuration locale disponible. Une capacité inconnue reste inconnue. |
| Quota restant | Disponible seulement si le connecteur le transmet. Une absence ne signifie pas zéro. |
| Contexte local / RAM | Contexte configuré et mesures disponibles. Un contexte plus grand demande généralement plus de mémoire. |

```callout
{"type": "info", "title": "À retenir", "body": "L’aperçu décrit la sélection de CyAI. Les fournisseurs natifs peuvent ajouter historique, instructions ou contraintes de transport. Vérifiez la trace transmise avant d’attribuer une omission au modèle."}
```


## Chapitres associés {#related}

- [Évaluations en arrière-plan](doc:background)
- [Modèles locaux et mémoire](doc:local-models)
- [Logs, ressources et consommation](doc:diagnostics)
