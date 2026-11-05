---
id: connectors
title: Connecteurs et modèles
description: Connecter un compte, une API ou un moteur local.
section: Premiers pas
order: 3
revision: 1
sourceRevision: 1
---


1. Ouvrez Paramètres → Connecteurs. Activez l’intégration et renseignez modèle, exécutable ou adresse.
2. Pour un CLI natif, installez-le et authentifiez-vous. Pour une API, entrez la clé dans le champ dédié.
3. Vérifiez la connexion, actualisez si besoin le catalogue, puis choisissez connecteur et modèle dans la saisie.

| Connecteur | Fonctionnement |
| --- | --- |
| Codex | App Server, sessions natives, streaming et autorisations d’outils prises en charge. |
| Claude Code | CLI/SDK local ; sessions distinctes de Claude Desktop. CLI en téléchargement facultatif. |
| OpenCode | Serveur local ; outils de fichiers approuvés, shell/délégation restreints dans cet adaptateur. |
| API Anthropic / OpenRouter | Clé API et modèle requis. Outils selon l’adaptateur ; la génération seule ne constitue pas un agent natif complet. |
| Ollama / CyAI local | Génération locale. CyAI local utilise un moteur llama.cpp et un modèle GGUF téléchargés. |
| Autres adaptateurs natifs | Command Code, CodeBuddy, Antigravity et Devin demandent leur CLI. Antigravity et Devin ne préparent pas les plans d’orchestration dans cette intégration. |

```callout
{"type": "info", "title": "À retenir", "body": "Installé ou configuré ne signifie pas connexion vérifiée. Un abonnement ChatGPT ou Claude ne fournit pas automatiquement du crédit API. Quotas, modèles et réglages de raisonnement/vitesse dépendent du fournisseur."}
```


[Ouvrir les connecteurs](doc:connectors?app-settings=connectors)

## Chapitres associés {#related}

- [Modèles locaux et mémoire](doc:local-models)
- [Autorisations et lancement](doc:permissions)
- [Logs, ressources et consommation](doc:diagnostics)
