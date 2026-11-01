# Plugins CyAI Orchestrator

Les extensions sont déclaratives : leur configuration ajoute des boutons et une source MCP. Aucun JavaScript tiers n’est injecté dans l’interface. Les plugins sont gérés depuis **Plugins**, puis associés à un projet depuis son onglet **Plugins**.

## Plugins livrés

- **CyAnnota** : le bouton avec son logo ouvre l’éditeur web directement dans la conversation. Collez directement une image avec Ctrl+V (ou utilisez les outils d’ouverture de CyAnnota), annotez-la, puis utilisez **Sauver dans CyAI**. Les corrections sont enregistrées et sélectionnées pour le prochain message ; le bouton **Reprendre** permet de continuer un document sauvegardé. Le bundle CyAnnota 0.3.10 est inclus, avec la licence AGPL-3.0 et les sources téléchargeables depuis la configuration du plugin. Aucun serveur CyAnnota séparé n’est nécessaire. Le mode Windows externe et l’import d’archives restent disponibles. Les images originales restent sous `.cyai-annotations` dans le projet ; les agents reçoivent leurs chemins et le document structuré des corrections. Les API textuelles ne reçoivent pas automatiquement de blocs visuels.
- **CyAICodex** : serveur MCP HTTP local, méthodes `get_context`, `search_methods`, `get_method` et ressources annoncées. Créez une connexion de lecture dans CyAICodex et renseignez son jeton dans le plugin. Ce jeton est stocké dans le coffre DPAPI, pas dans le manifeste.
- **CyProjectCodex** : serveur MCP stdio local. Activez-le, puis associez le projet CyAI à un projet de la bible. Les lectures des IA sont forcées sur cette association. La mémoire structurée automatique est facultative et limitée à 16 000 caractères ; sinon utilisez les recherches et lectures à la demande. Le contenu externe reste une donnée de référence, distincte de la mémoire manuellement validée.

Les plugins MCP sont exposés comme deux outils (`list_plugins`, `read_plugin`) à Codex et Claude Code, et comme outils équivalents à l’API Anthropic. Les autres connecteurs peuvent recevoir une référence jointe manuellement depuis « Consulter », ainsi que la mémoire structurée automatique. Les appels des plugins ne permettent pas les outils d’écriture des bibliothèques livrées.

## Manifeste personnalisé

Importer un fichier JSON dans **Plugins → Installer un manifeste**. Il est installé désactivé. Son activation autorise le lancement de sa commande MCP locale : n’activez que vos extensions de confiance. Les outils déclarés doivent réellement être des lectures.

```json
{
  "id": "ma-bibliotheque",
  "name": "Ma bibliothèque",
  "type": "mcp",
  "button": "Consulter ma bibliothèque",
  "enabled": false,
  "transport": "stdio",
  "command": "node",
  "args": ["D:/MesOutils/bibliotheque/mcp.mjs"],
  "read_tools": ["search", "get_entry"]
}
```

Pour HTTP : `transport: "http"`, `url: "http://127.0.0.1:PORT/mcp"`, sans `command` ni `args`. Les redirections sont refusées pour ne pas transmettre un jeton ailleurs. Le transport attend des réponses JSON ou SSE bornées et supporte les sessions MCP HTTP.

Les boutons utilisent le libellé `button`. Le champ optionnel `project_parameter` nomme l’argument de projet à imposer aux outils (exemple : `projectId`). Les associations se trouvent sous `projects` dans la configuration locale. L’injection automatique utilise `get_project` ; elle est conçue pour les bibles structurées exposant ce contrat.

Les archives d’annotations sont limitées à 50 Mo et 500 entrées. La sauvegarde JSON de l’historique conserve les consignes et références, mais les images importées restent dans le dossier du projet : sauvegardez aussi ce dossier.

## Claude local

CyAI utilise un CLI natif choisi dans la configuration du connecteur, puis un `claude.exe` local détecté, puis celui fourni avec le SDK. Le même chemin est utilisé pour le statut, l’ouverture du CLI et les échanges. **Utiliser le CLI local** réutilise une authentification valide ; sinon il ouvre le CLI interactif sans déclencher `auth login`. Vous pouvez vous authentifier dedans avec `/login` si nécessaire. Ce parcours officiel peut alors ouvrir votre navigateur.

La session d’une fenêtre Claude déjà ouverte n’est pas importée. CyAI ne lit pas ses jetons ni son stockage privé. L’ancien CLI npm 1.0.56 présent sur cette machine ne constitue pas un exécutable natif compatible avec le SDK actuel ; le CLI natif intégré sert de repli.

## Activation et vues

La page globale configure la connexion ou le type d’éditeur. Dans **Projet → Plugins**, les boutons activent ou désactivent uniquement l’usage pour ce projet. CyAICodex et CyProjectCodex ajoutent des onglets au projet et des entrées dans sa mémoire. L’association à une bible et l’ajout automatique restent des options propres au projet.
