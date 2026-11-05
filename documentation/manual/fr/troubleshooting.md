---
id: troubleshooting
title: Dépannage
description: Identifier l’étape en échec avant de relancer.
section: Réglages et maintenance
order: 25
revision: 1
sourceRevision: 1
---


| Symptôme | À vérifier |
| --- | --- |
| Réglages en chargement | Attendez l’état visible puis réessayez la rubrique. Consultez son erreur dans Logs ; découverte de modèles et téléchargements sont distincts. |
| Agent sans réponse | Connecteur actif, authentification vérifiée, modèle exact, exécutable/adresse et dernière erreur. Abonnement CLI et crédit API sont distincts. |
| Attente d’autorisation | Politique, demande en attente, périmètre et règles natives. Consultez les détails. |
| Outils MCP absents | Enregistrement, activation du projet, attribution à l’agent, serveur actif et liste d’outils de la session. |
| Chemin hors des dossiers | Existence, pièce jointe d’origine, dossiers de travail et lien local. Joignez/importez ou enregistrez le dossier voulu. |
| Modèle impossible à charger | Compatibilité moteur, mémoire réelle, couches GPU, contexte et log de chargement. Orange reste une indication. |
| Dictée ou synthèse absente | Autorisation périphérique, moteur/voix, téléchargement terminé, langue et activation du micro/de la lecture. |
| Appel réussi sans résultat final | Cherchez l’identifiant job/mission et son état final ; les requêtes de suivi ne sont pas le résultat du travail. |
| Tests sans enchaînement | Vérifiez chaîne/automate et exécution de pilotage active. Un pilote fini ne lance pas un lot suivant non défini. |
| Matériaux 3D absents | Textures intégrées et extensions GLB/glTF prises en charge. OBJ ne charge pas les MTL ; les fichiers associés peuvent manquer. |
| Informations tardives ignorées | Vérifiez corpus complet livré et transport avant de conclure à un échec du modèle à cette taille. |
| Mission interrompue/échouée | Vérifiez erreur et effets sur les fichiers. Examinez les options de reprise ; annuler ne restaure pas les fichiers. |

## Préparer un diagnostic utile {#help-part-1}

1. Notez version CyAI, connecteur, modèle exact, action et heure.
2. Conservez erreur, identifiant et état dans le log pertinent. Retirez les données privées avant partage.
3. Diagnostiquer avec l’IA prépare un message. Relisez et envoyez-le ; sa préparation ne relance pas silencieusement le travail.

## Chapitres associés {#related}

- [Logs, ressources et consommation](doc:diagnostics)
- [Autorisations et lancement](doc:permissions)
- [Historique, exports et sauvegardes](doc:backups)
