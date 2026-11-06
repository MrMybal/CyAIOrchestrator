---
id: voice
title: Dictée, synthèse et voix
description: Configurer les moteurs et contrôler l’activation du micro.
section: Modèles et voix
parent: local-models
order: 20
revision: 1
sourceRevision: 1
---


1. Ouvrez Paramètres → Voix. Choisissez moteur de transcription, langue et réglages micro disponibles. Installez les seuls composants nécessaires.
2. Pour la synthèse, choisissez voix Windows ou moteur local comme Piper. Installez une voix, choisissez son locuteur si disponible et testez-la.
3. Le micro sert à dicter : relisez le texte reconnu avant envoi.
4. La discussion directe envoie les phrases, lit les réponses et rouvre le micro. Recliquez pour l’arrêter. La lecture des réponses peut être activée séparément.

| Option | Utilisation |
| --- | --- |
| Whisper / Phonon | Transcription facultative. Phonon-2 est anglais ; Phonon-2.5 gère français et autres langues. Moteur et poids se téléchargent séparément. |
| Piper | Synthèse locale légère. Le catalogue indique langues, qualités et locuteurs ; les modèles multi-locuteurs partagent leurs fichiers. |
| Autres moteurs | Matériel, langues, clonage et mémoire dépendent du moteur. Consultez sa fiche et son état réel. |

```callout
{"type": "info", "title": "À retenir", "body": "Micro et lecture automatique démarrent désactivés. L’autorisation navigateur/Windows reste nécessaire. Testez une phrase courte avant le mode mains libres. La transcription peut être imparfaite ; autoriser le micro n’installe pas le modèle."}
```


[Ouvrir les réglages voix](doc:voice?app-settings=voice)

## Chapitres associés {#related}

- [Téléchargements et composants](doc:downloads)
- [Modèles locaux et mémoire](doc:local-models)
- [Dépannage](doc:troubleshooting)
