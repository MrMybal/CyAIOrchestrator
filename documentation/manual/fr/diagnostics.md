---
id: diagnostics
title: Logs, ressources et consommation
description: Consulter traces et mesures dans le temps.
section: Réglages et maintenance
order: 23
revision: 1
sourceRevision: 1
---


1. Ouvrez Logs. Choisissez Journal, RAW, Opérations MCP, Connecteurs ou Ressources dans les onglets verticaux.
2. Filtrez par source, niveau ou texte. Examinez l’opération plutôt que de conclure à partir de son titre.
3. RAW donne les événements structurés ; Opérations MCP montre appels d’outils et résultats.
4. Dans Ressources, consultez historique CPU, RAM, GPU, VRAM et disque disponible. Exportez les diagnostics utiles.

Les connecteurs distinguent désactivé, configuré, installé, opérationnel et erreur. Des mesures peuvent manquer selon les compteurs Windows/GPU. Mémoire du processus CyAI, du modèle local et utilisation système sont différentes. La saisie affiche consommation et quota seulement si fournis.

```callout
{"type": "info", "title": "À retenir", "body": "Une mesure inconnue n’est pas zéro. Un export peut contenir consignes, chemins ou réponses : relisez-le avant partage. Un appel de suivi MCP peut réussir alors que le job continue ou a échoué."}
```


## Chapitres associés {#related}

- [Dépannage](doc:troubleshooting)
- [Contexte, mémoire et consommation](doc:context)
- [Serveurs MCP locaux et accès IA](doc:mcp)
