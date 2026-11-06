---
id: local-models
title: Modèles locaux et mémoire
description: Installer un moteur, choisir un GGUF et régler son contexte.
section: Modèles et voix
order: 19
revision: 1
sourceRevision: 1
---


1. Ouvrez Paramètres → Modèles locaux. Choisissez le moteur llama.cpp adapté au CPU/GPU ou configurez Ollama séparément.
2. Téléchargez un GGUF compatible depuis le catalogue/dépôt Hugging Face ou importez un modèle existant. Attendez la fin.
3. Réglez CPU/GPU/hybride, couches GPU, threads et contexte. Les réglages par modèle peuvent remplacer les valeurs globales.
4. Chargez le modèle, suivez son état puis choisissez CyAI local dans la saisie. Arrêtez/déchargez le moteur pour libérer la mémoire.

Le contexte est une capacité locale configurée en tokens, distincte de la longueur de sortie. Architecture et moteur contraignent toujours le contexte utilisable. Un contexte plus grand peut demander beaucoup plus de mémoire de cache KV. Examinez les erreurs réelles plutôt que d’assimiler taille du fichier et RAM/VRAM requise.

```callout
{"type": "info", "title": "À retenir", "body": "Les estimations sont indicatives. Orange signale une marge faible sans interdire à lui seul le chargement. Rouge indique une VRAM totale inférieure à l’estimation, sans prouver le comportement de tous les moteurs. Le chargement réel peut échouer. Le moteur intégré traite une demande à la fois."}
```


[Ouvrir les modèles locaux](doc:local-models?app-settings=local)

## Chapitres associés {#related}

- [Téléchargements et composants](doc:downloads)
- [Contexte, mémoire et consommation](doc:context)
- [Logs, ressources et consommation](doc:diagnostics)
