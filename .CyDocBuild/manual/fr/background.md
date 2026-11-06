---
id: background
title: Évaluations en arrière-plan
description: Lancer des essais isolés sans remplir la liste des conversations.
section: Agents et arrière-plan
parent: methods
order: 11
revision: 1
sourceRevision: 1
---


1. Définissez corpus, réponses et notation. Choisissez les variantes exactes.
2. Préparez des exécutions indépendantes dans les espaces cachés ; ne réutilisez pas l’historique des candidats.
3. Autorisez le lancement. Suivez conversation de pilotage, cartes ou logs ; masquez les cartes pour gagner de la place.
4. Attendez les états finaux et distinguez cas terminés, échoués, annulés et non testés avant comparaison.

Pour les grands contextes, vérifiez le contenu livré par le connecteur. Conservez taille, identifiant du modèle, contexte annoncé et erreurs. Un petit pilote ne mesure pas le contexte massif. Si les outils sont interdits, examinez leurs traces avant notation.

```callout
{"type": "info", "title": "À retenir", "body": "Un accusé de lancement ou identifiant n’est pas un test terminé. La poursuite doit être configurée dans la chaîne, l’automate ou une exécution active ; enregistrer un résultat ne garantit pas le réveil d’une conversation inactive."}
```


## Chapitres associés {#related}

- [Méthodes, tests et révisions](doc:methods)
- [Plans, missions et travail parallèle](doc:orchestration)
- [Logs, ressources et consommation](doc:diagnostics)
