---
id: install
title: Installation et cycle de vie
description: Installer, démarrer, mettre à jour et fermer l’application.
section: Premiers pas
order: 1
revision: 1
sourceRevision: 1
---


1. Téléchargez l’installateur Windows depuis les Releases GitHub du projet et lancez-le. En portable, conservez tout le dossier, y compris _internal.
2. Vérifiez la présence de Microsoft Edge WebView2. Ouvrez le raccourci CyAI. L’anglais est utilisé par défaut, sauf préférence déjà enregistrée.
3. Configurez un connecteur ou installez moteur et modèle locaux. Les poids des modèles et moteurs facultatifs se téléchargent séparément.

Fermer la fenêtre masque CyAI dans la zone de notification Windows. Un double-clic sur l’icône la rouvre. Quitter arrête le service lancé par cette instance, avec confirmation si un travail est actif. Un service lancé séparément reste indépendant. Fermer un onglet navigateur n’arrête ni le service ni ses missions.

Les données sont séparées du programme. Arrêtez les travaux et créez une sauvegarde avant mise à jour ; sauvegardez séparément les dossiers de projets. Installez la version et vérifiez le numéro dans la barre latérale. L’exécutable Windows n’est actuellement pas signé.

```callout
{"type": "info", "title": "À retenir", "body": "Le mode source nécessite Python 3.11+. Lancez python -m cyai, ou python -m cyai.desktop pour la fenêtre. Adresse par défaut : http://127.0.0.1:8766. Changer le port change aussi les adresses des clients."}
```


## Chapitres associés {#related}

- [Téléchargements et composants](doc:downloads)
- [Historique, exports et sauvegardes](doc:backups)
- [Paramètres, langue et dossiers](doc:settings)
