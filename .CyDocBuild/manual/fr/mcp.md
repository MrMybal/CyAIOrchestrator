---
id: mcp
title: Serveurs MCP locaux et accès IA
description: Enregistrer les outils, les exposer et suivre leurs jobs.
section: Fichiers, médias et intégrations
parent: extensions
order: 18
revision: 2
sourceRevision: 2
---


1. Dans Paramètres → MCP, enregistrez le serveur, par exemple Blender, avec transport et commande/arguments ou adresse HTTP. Importez une configuration compatible si disponible.
2. Vérifiez logiciels, moteur et identifiants. L’enregistrement seul ne prouve pas une connexion fonctionnelle.
3. Exposez l’intégration au projet/profil et à ses outils. Lectures et écritures suivent permissions déclarées et politique de la conversation.
4. Testez un petit appel et consultez Opérations MCP dans Logs. Suivez les jobs jusqu’à leur état final.

```diagram
{"type": "flow", "title": "Une opération MCP", "nodes": [{"id": "node-0", "label": "Agent", "x": 0, "y": 0, "w": 220, "h": 72}, {"id": "node-1", "label": "Outil exposé", "x": 260, "y": 0, "w": 220, "h": 72}, {"id": "node-2", "label": "Autorisations", "x": 520, "y": 0, "w": 220, "h": 72}, {"id": "node-3", "label": "Serveur MCP", "x": 780, "y": 0, "w": 220, "h": 72}, {"id": "node-4", "label": "Job / résultat", "x": 1040, "y": 0, "w": 220, "h": 72}], "edges": [{"from": "node-0", "to": "node-1"}, {"from": "node-1", "to": "node-2"}, {"from": "node-2", "to": "node-3"}, {"from": "node-3", "to": "node-4"}]}
```


L’agent voit les outils attribués. Les appels pris en charge suivent les autorisations, atteignent le serveur et retournent un résultat ou un job à suivre.

CyAI expose aussi son pont MCP vers le service local actif. Générez la configuration client, choisissez projets et accès lecture/écriture et utilisez la commande fournie dans l’agent externe. Le service CyAI doit être actif. Le périmètre évite l’accès implicite à tous les projets.

```callout
{"type": "info", "title": "À retenir", "body": "Installer Blender ou trouver un dossier MCP n’expose pas automatiquement ses outils à une session active. Vérifiez enregistrement, attribution, serveur et liste d’outils actualisée. Utilisez les champs de configuration dédiés pour les identifiants."}
```


[Ouvrir les réglages MCP](doc:mcp?app-settings=mcp)

## Chapitres associés {#related}

- [Plugins et CyTools](doc:extensions)
- [Autorisations et lancement](doc:permissions)
- [Logs, ressources et consommation](doc:diagnostics)

[API d’intégration et exemples courts](doc:api-integration)
