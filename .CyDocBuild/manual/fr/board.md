---
id: board
title: Board et délégation
description: Distinguer affectation, exécution, compte rendu et acceptation.
section: Agents et arrière-plan
parent: agents
order: 9
revision: 1
sourceRevision: 1
---


```image
{"id": "task-board", "src": "assets/images/task-board-fr.png", "alt": "Affectations et colonnes de revue", "title": "Les cartes illustrent le fonctionnement, pas des résultats de benchmark.", "controls": "minimal"}
```


1. Créez l’équipe, puis une carte : objectif, responsable, fichiers, dépendances et critères.
2. Placez-la en Prête quand les prérequis sont satisfaits. Lancez l’agent depuis sa fiche ou avec l’automate.
3. Examinez compte rendu, fichiers, vérifications et limites. Un rapport doit être relu.
4. Acceptez le résultat vérifié ou demandez des corrections. L’utilisateur ou un responsable habilité décide.

| État | Sens |
| --- | --- |
| À préparer / Prête | Définir périmètre et dépendances avant lancement. |
| En cours / En attente d’informations | Travail commencé ou information manquante. Consultez la fiche pour pause, arrêt ou demande d’avis. |
| En revue / À corriger | Rapport à examiner ou correction demandée. |
| Terminée / Échouée / Annulée | Décision finale. Terminée suit une acceptation, pas une phrase de succès. |

L’aperçu de l’automate liste les actions possibles. Avancer une étape effectue un passage ; le mode automatique poursuit selon sa politique. Surveillez exécutions, revues et attentes. Arrêtez l’automate pour empêcher de nouvelles délégations. La couleur d’une carte ne prouve pas qu’un agent travaille.

## Chapitres associés {#related}

- [Bibliothèque d’agents et équipes](doc:agents)
- [Plans, missions et travail parallèle](doc:orchestration)
- [Logs, ressources et consommation](doc:diagnostics)
