---
id: backups
title: Historique, exports et sauvegardes
description: Préserver les conversations sans les confondre avec les fichiers du projet.
section: Réglages et maintenance
order: 24
revision: 1
sourceRevision: 1
---


1. Recherchez les messages, y compris archivés, avec les filtres projet, fournisseur, dates ou état.
2. Exportez la conversation pour ses messages et missions. Archiver conserve la recherche ; supprimer est distinct.
3. Dans Sauvegarde, exportez ou restaurez après lecture de la confirmation de remplacement.
4. Sauvegardez séparément les dossiers de projets. Arrêtez le service avant copie complète du dossier de données.

| Inclus ou distinct | À prévoir |
| --- | --- |
| Historique SQLite | Conversations, missions, références et enregistrements de l’application. |
| Sauvegarde portable | N’inclut ni identifiants, ni fichiers de travail, ni sessions natives. Vérifiez références médias et conservez les originaux utiles. |
| Restauration | Remplace l’historique après accord ; une copie préalable est conservée. Ne restaure pas les dossiers de projets. |
| Identifiants | DPAPI lie les identifiants pris en charge au compte Windows. Copier les données ne transfère pas une connexion. |

[Ouvrir les sauvegardes](doc:backups?app-settings=backup)

## Chapitres associés {#related}

- [Pièces jointes, images et vidéos](doc:files)
- [Projets et messages privés](doc:projects)
- [Dépannage](doc:troubleshooting)
