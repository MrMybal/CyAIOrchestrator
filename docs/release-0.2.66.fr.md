# 0.2.66 — Mise à jour du lecteur CyDoc

- Mise à jour du lecteur CyDoc embarqué : recherche dans l'en-tête, navigation hiérarchique, infobulles avec titre et description, et six thèmes.
- Publication de 30 pages dans chacune des deux langues, anglais et français, avec des captures localisées, des schémas statiques et une référence concise des API publiques d'intégration.
- Séparation des sources de rédaction dans `.CyDocBuild/` et des fichiers distribués : `Documentation/Documentation.html`, `DocAI.md` et les ressources `DocData/`.
- Exclusion des archives techniques, audits, historiques de migration et implémentations complètes du lecteur destiné aux utilisateurs.
- Conservation de l'aide contextuelle F1, des liens vers les réglages natifs et des alias des anciennes pages ; ouverture directe du lecteur par `file://`.
- Inclusion du manuel généré complet dans les distributions Windows et Python. Seul le module de médias image est utilisé pour les captures du manuel.

L'installateur Windows met à jour l'application en conservant la configuration existante et la version précédemment installée. Le manuel embarqué ne nécessite ni serveur documentaire ni connexion Internet.

## Statut

**CyAI Orchestrator 0.2.66 · Alpha.** Cette version est destinée aux essais et aux retours. Certaines fonctionnalités peuvent être incomplètes et les parcours peuvent évoluer avant une version stable.

## Limitations documentées

- L'installateur publié cible Windows x64 et n'est pas signé numériquement. Le runtime Microsoft Edge WebView2 doit être disponible. Aucun installateur Linux ou macOS n'est publié pour cette version.
- Les capacités des fournisseurs, les autorisations des outils natifs, les limites de contexte et l'utilisation de l'abonnement dépendent du connecteur choisi. Une limite ou un quota n'est affiché que si le connecteur le fournit ; une valeur indisponible n'est pas une mesure égale à zéro.
- Des missions indépendantes peuvent s'exécuter en parallèle, mais le moteur d'inférence local intégré traite une seule requête de modèle à la fois. Les besoins des modèles et de la voix dépendent du moteur et des poids téléchargés.
- Les poids volumineux, les moteurs natifs facultatifs, le CLI Claude Code et le composant FFmpeg facultatif de CyAnnota sont téléchargés séparément. Les fournisseurs natifs nécessitent leur propre authentification ; un abonnement à une application ne fournit pas automatiquement de crédit API.
- Les sauvegardes portables de l'application ne contiennent ni identifiants, ni fichiers de travail des projets, ni sessions natives des fournisseurs. Sauvegardez ces fichiers séparément. L'arrêt d'un agent n'annule pas les modifications qu'il a déjà apportées aux fichiers.

Il s'agit de limitations du produit, et non d'une liste de tickets de bugs confirmés. Cette version ne publie pas d'inventaire détaillé des bugs ; consultez le [suivi des problèmes](https://github.com/MrMybal/CyAIOrchestrator/issues) pour les signalements et les retours.

## Liens

- [Version publiée et installateur Windows](https://github.com/MrMybal/CyAIOrchestrator/releases/tag/v0.2.66)
- [Manuel en français](https://mrmybal.github.io/CyAIOrchestrator/Documentation.html#/fr/start)
- [English version notes](release-0.2.66.md)
- [README français](../README.fr.md)
