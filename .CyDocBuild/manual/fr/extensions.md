---
id: extensions
title: Plugins et CyTools
description: Distinguer vues de projet et outils attribués aux agents.
section: Fichiers, médias et intégrations
parent: files
order: 17
revision: 1
sourceRevision: 1
---


```image
{"id": "cytools", "src": "assets/images/cytools-fr.png", "alt": "Catalogue officiel CyTools", "title": "Applications autonomes ; moteurs et poids se téléchargent séparément.", "controls": "minimal"}
```


| Intégration | Utilisation |
| --- | --- |
| Plugins | Configuration globale, activation par projet. Seuls les plugins actifs déclarant une vue deviennent des onglets. |
| CyTools | AudioStudio, AudioLibrary, AIChat, PersonaRP, Storyboard et MeshStudio ; attribuez leurs outils aux profils/affectations. |
| CyAICodex | Jeton limité au périmètre voulu ou configuration MCP pour skills et références visuelles. |
| CyTask | Serveur existant et jeton d’agent/API ; pont MCP avec Node.js 22+. Télécharger le logiciel ne crée pas de compte serveur. |

1. Ajouter un dossier installé détecte CyTool.json, app/CyTool.json, configurations MCP et moteurs Python portables/environnements pris en charge.
2. Vérifiez les releases puis Télécharger et connecter. Suivez Téléchargements. Le paquet est installé, pas ses modèles.
3. Configurez, activez et attribuez les outils à l’agent. Testez une opération et gardez sa session ouverte pendant le suivi du job.

```callout
{"type": "info", "title": "À retenir", "body": "Un identifiant de job signale un travail asynchrone. Une requête de statut réussie ne prouve pas la réussite de l’opération : suivez Completed, Failed ou Cancelled. Les anciennes intégrations restent dans la section de compatibilité."}
```


[Ouvrir CyTools](doc:extensions?app-settings=cytools)

## Chapitres associés {#related}

- [Serveurs MCP locaux et accès IA](doc:mcp)
- [Téléchargements et composants](doc:downloads)
- [Bibliothèque d’agents et équipes](doc:agents)
