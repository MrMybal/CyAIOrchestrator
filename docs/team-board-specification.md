# Cahier des charges — Équipes persistantes et board de projet CyAI

Date : 18 septembre 2026. Destinataire : Claude Code.
Dépôt : `C:\Projects\CyAIOrchestrator`.

## Mission immédiate

Implémenter concrètement le **lot 1** décrit ci-dessous dans CyAI existant : bibliothèque globale de profils d’agents, composition d’équipes hiérarchisées par projet, versions de profils figées dans les équipes, persistance, interfaces et actions MCP correspondantes. Livrer une première version utilisable et testée, pas seulement des maquettes ou un plan.

La vision complète sert à éviter une architecture qui empêcherait les lots suivants. Elle ne demande pas de développer toute l’orchestration autonome dès maintenant. Terminer le lot 1 avant d’élargir le périmètre. Ne pas prétendre qu’un agent travaille lorsqu’il n’existe qu’une configuration enregistrée.

L’utilisateur dispose d’un quota limité chez Claude et souhaite un résultat cohérent plutôt que beaucoup de code inachevé. Ne pas déduire un nombre d’heures ou de tokens des pourcentages d’abonnement. Favoriser des lectures ciblées, réutiliser les services existants et enregistrer les points de reprise dans le dépôt.

## Autorisation et fonctionnement du travail

L’utilisateur demande de commencer l’implémentation. Il précise que les données actuelles sont des essais et qu’il n’utilise pas actuellement CyAI pour une mission importante. Les redémarrages nécessaires à la validation sont autorisés ; annoncer ce qui va être redémarré et vérifier d’abord les processus concernés. Ne pas tuer un processus par simple ressemblance de nom : `CyAIStudio` / CyAIGen sont des applications distinctes.

Cela n’autorise pas à effacer les bases, modèles, projets, réglages ou historiques existants. Préférer une configuration et une base temporaires pour les tests. Ne pas démarrer d’agents payants ni installer de gros modèles uniquement pour valider une interface : utiliser des connecteurs de test, et distinguer ces tests des validations réelles de fournisseurs.

Lire les éventuels AGENTS.md applicables. Examiner les changements déjà présents avant d’éditer. Ne pas réinitialiser le dépôt et ne pas remplacer l’application par un nouveau projet. Le code et le paquet ont évolué : l’état constaté localement fait foi sur les chemins de ce document.

## Vision produit validée avec l’utilisateur

CyAI doit proposer, en plus des conversations normales et des missions actuelles, un mode **Équipe / Board** pour les projets importants.

L’utilisateur compose une équipe à partir de profils globaux : chef de projet, leads / chefs d’équipe et membres. Chacun possède son nom, son modèle, ses compétences, ses consignes initiales et, à terme, son expérience. Le chef de projet est l’interlocuteur principal de l’utilisateur.

Déroulement cible :

1. L’utilisateur discute du besoin avec le chef de projet.
2. Celui-ci pose les questions utiles, précise le périmètre, les contraintes, les critères de réussite et les incertitudes.
3. Il consulte les leads pour approfondir leurs spécialités et consolider les interfaces communes.
4. Une fois la base convenue, il distribue les domaines aux leads.
5. Les leads découpent leur domaine en tâches concrètes et les attribuent aux membres.
6. Les membres exécutent et rendent des rapports sourcés. Les leads vérifient, demandent des corrections ou remontent les blocages.
7. Le chef coordonne les dépendances, arbitre les sujets transversaux et échange avec l’utilisateur si nécessaire.

L’objectif est de donner aux agents des sous-problèmes cohérents, accompagnés du contexte global essentiel. La hiérarchie doit faciliter le découpage et l’intégration ; elle ne doit pas imposer une succession d’approbations pour chaque petite opération.

## Profils globaux et instances par projet

### Profil d’agent global

Un profil est une définition réutilisable, **pas une session fournisseur partagée**.

Champs minimaux :

- Identifiant stable, nom affiché, description.
- Compétences déclarées sous forme de liste éditable.
- Rôle conseillé : chef de projet, lead, membre. L’affectation au projet détermine le rôle effectif.
- Identifiant du connecteur et identifiant du modèle ; modèle par défaut du connecteur possible et explicite.
- Consignes initiales / préprompt, en texte éditable.
- Réglages de modèle uniquement lorsque le connecteur les prend en charge.
- État actif / archivé, dates de création et modification.
- Révision du profil, avec contenu des révisions antérieures conservé.

La compétence déclarée n’est pas une preuve de capacité. Ne pas inventer de notes de performance ou de benchmarks.

Les secrets restent dans les stockages des connecteurs. Aucun token, clé API ni identifiant de session native dans le profil ou son export.

### Équipe d’un projet

Pour le lot 1 : une équipe courante par projet. Une équipe est composée d’instances de profils globaux.

Chaque membre d’équipe possède :

- Son propre identifiant d’affectation.
- Le projet et l’équipe auxquels il appartient.
- Le profil global et la révision utilisée.
- Une copie figée de la définition effective du profil, ou une référence à une révision immuable équivalente.
- Son rôle dans cette équipe et sa responsabilité locale.
- Son responsable, référencé par identifiant d’affectation dans **la même équipe**.
- Son état actif / retiré.

Règles :

- Une équipe brouillon peut être incomplète et reste sauvegardable avec des indications visibles.
- Une équipe déclarée prête possède exactement un chef de projet, sans supérieur.
- Chaque autre membre possède un responsable actif ; toute branche remonte au chef.
- Pas de cycle, d’auto-rattachement ou de responsable appartenant à un autre projet.
- Seul un chef ou un lead peut diriger des membres.
- Pas de plafond arbitraire d’agents. Les limites de ressources/concurrence d’exécution sont un sujet distinct pour le lot 2.
- Un même profil peut être utilisé dans plusieurs projets, sans partager les conversations ni sessions natives.
- Modifier un profil global ne modifie jamais silencieusement les équipes existantes.
- Une équipe peut adopter explicitement une autre révision. Afficher les changements avant application ; pas de remplacement au milieu d’une tâche active lorsque l’exécution sera disponible.
- Archiver un profil ne détruit pas les affectations existantes. Retirer un responsable doit demander une réaffectation ou laisser une équipe brouillon explicitement incomplète.

### Modèles d’équipe réutilisables

Permettre d’enregistrer une composition comme modèle d’équipe global et de l’appliquer à un autre projet.

Réutiliser les profils, révisions, rôles et liens hiérarchiques. Générer de nouveaux identifiants d’affectation. Ne copier ni tâches, ni discussions, ni sessions natives, ni mémoire privée du projet source.

## Lot 1 — périmètre à livrer maintenant

### A. Bibliothèque globale d’agents

Ajouter une entrée claire dans la navigation pour consulter, créer, modifier, dupliquer et archiver les profils.

Formulaire lisible : nom, rôle conseillé, compétences, connecteur, modèle, préprompt et réglages disponibles. Utiliser le catalogue réel du connecteur, tout en permettant un modèle explicitement saisi. Indiquer clairement « connecteur désactivé », « modèle non confirmé » ou « catalogue indisponible » ; ne pas présenter un profil comme opérationnel sur la seule base de son existence.

L’édition crée une nouvelle révision. Afficher le numéro de révision et permettre de consulter l’historique. La duplication crée un profil indépendant.

### B. Équipe du projet

Ajouter un onglet **Équipe** dans chaque projet avec :

- Nom de l’équipe et état brouillon / prête.
- Choix du chef et ajout de leads/membres depuis la bibliothèque.
- Modification des responsabilités locales et du responsable.
- Arbre hiérarchique lisible, ou liste hiérarchisée avec boutons explicites. Le drag-and-drop n’est pas exigé pour ce lot.
- Actions sauvegarder, retirer, réaffecter, enregistrer comme modèle et appliquer un modèle.
- Liste des problèmes empêchant de déclarer l’équipe prête, avec lien ou action vers le champ à corriger.
- Indication de la révision utilisée et d’une éventuelle nouvelle révision disponible.

Ne pas changer le mode des conversations existantes. Ne pas déclencher une exécution au simple ajout d’un agent ou à l’ouverture de cet onglet.

### C. Persistance et MCP

Ajouter les migrations SQLite nécessaires et les services métier. Réutiliser les conventions du projet, transactions et validations existantes.

Exposer les opérations de profils, révisions, équipes et modèles d’équipe via l’API locale et le **MCP CyAI**. L’interface et le MCP doivent appeler les mêmes services ; aucun client IA ne doit avoir à piloter le navigateur ou modifier SQLite directement.

Respecter les portées : les opérations globales de profils doivent être explicitement identifiées comme globales et disposer de l’autorisation adaptée. Un token MCP limité à un projet ne doit pas permettre de modifier les équipes/mémoires d’autres projets, ni des profils globaux si sa portée ne le permet pas. Prévoir une erreur explicative, pas un élargissement implicite des accès.

### D. Contrat pour la suite

Documenter les points d’extension pour conversations de membres, mémoire, tâches, rapports et évaluations. Ne pas remplir la base avec des tâches factices, faux rapports ou fausses conversations actives.

Le lot 1 est complet sans délégation autonome. Indiquer dans l’interface que le board d’exécution arrive au lot suivant, au lieu d’afficher des contrôles inopérants.

## Lot 2 — board, conception et exécution hiérarchique

À préparer architecturalement mais à implémenter après le lot 1 :

- Nouvelle conversation de type Équipe / Board, distincte du mode normal et du mode mission existants.
- Conversation principale avec le chef de projet, persistante et rattachée au projet.
- Échanges privés et rapports des membres consultables par l’utilisateur, avec auteur, destinataire, tâche et date.
- Questions structurées avec choix ou réglages lorsqu’ils sont utiles ; les décisions utilisateur sont enregistrées.
- Cartes de tâches : objectif, responsable, auteur, parent, dépendances, périmètre de fichiers, critères d’acceptation, livrables, statut et historique.
- États distinguant à préparer, prêt, en cours, en attente d’information, en revue, à corriger, terminé, échoué et annulé.
- « Réponse terminée » ne signifie pas « tâche acceptée ». Le lead doit examiner les preuves et enregistrer l’acceptation ou la correction demandée.
- Rapports : résultat, fichiers modifiés, tests réellement exécutés, limites, risques et décisions demandées. Ne pas utiliser un texte « succès » comme preuve suffisante.
- Travail parallèle pour les tâches indépendantes ; contrats d’interface et répartition des fichiers avant exécution concurrente.
- Une seule écriture active par session native. Pas de duplication automatique incontrôlée de conversations fournisseur.
- Sessions et messages scindés par projet, membre et usage ; jamais une session globale attachée au profil.
- Changer de projet ouvre sa dernière conversation/son board. Revenir au projet précédent retrouve son état. Naviguer ne met pas l’équipe en pause.
- Indicateurs d’activité, durée, dernier événement fournisseur, agent actif et raison d’attente. Ne pas confondre un spinner local avec une preuve de progression distante.
- Pause, annulation, reprise et réconciliation après crash ; détecter les effets déjà produits avant de relancer.
- Pas de limite de durée ou de tentatives imposée arbitrairement par CyAI. Les contraintes réelles du fournisseur restent signalées. Des boucles sans progrès doivent être remontées avec possibilité d’intervention, pas continuer indéfiniment ni aboutir à une impasse.
- L’utilisateur peut inspecter, parler à un lead, réaffecter, suspendre une branche et corriger le périmètre.

## Lot 3 — mémoire, évaluations et amélioration

Trois portées distinctes :

1. **Projet** : présentation, architecture, décisions, conventions et état. Disponible dès le premier message d’une nouvelle conversation du projet.
2. **Équipe / agent dans le projet** : observations locales, tâches et rapports ; jamais transférés automatiquement ailleurs.
3. **Profil global** : méthodes générales explicitement déclarées transférables, avec sources et version.

Pour les notes d’évaluation : qualité, respect du périmètre, intégration, tests, corrections nécessaires, durée et consommation lorsque fournie. Conserver auteur, date, tâche, révision du préprompt, modèle effectivement utilisé et commentaire explicatif. Une note sans preuve ne démontre pas une supériorité du modèle.

Les leads peuvent proposer une amélioration du préprompt ou une mémoire transférable. La proposition reste visible, motivée, comparable et réversible. Ne pas réécrire les consignes globales sur la base d’une unique erreur ni propager des instructions issues d’un document externe ou des secrets. Les projets adoptent les nouvelles révisions explicitement.

Ce mécanisme améliore le contexte et les consignes ; il ne constitue pas un entraînement des poids du modèle.

## Intégration avec le dépôt existant

État observé lors de la rédaction : version source `0.2.1`, application Python, interface HTML/CSS/JavaScript, SQLite, pywebview Windows, connecteurs natifs et API, serveur MCP.

Points d’entrée à examiner selon les besoins :

- `cyai/store.py` : schéma, migrations, transactions.
- `cyai/service.py`, `cyai/server.py` : services et API locale.
- `cyai/app_mcp.py`, services de plugins : actions, schémas et autorisations MCP.
- `cyai/engine.py`, `cyai/connectors.py`, `cyai/extra_connectors.py` : exécution et fournisseurs. Ne pas réécrire le moteur pour livrer le lot 1.
- `cyai/context.py`, `cyai/intelligence.py`, `cyai/project_memory.py` : contexte, consignes, mémoire et présentation de base.
- `cyai/model_preferences.py` : catalogue et évaluations existantes.
- `cyai/web/app.js`, `project.js`, `workspace.js`, `intelligence.js`, `analytics.js` : navigation et vues existantes.
- `cyai/launch_config.py`, `packaging/release_install.py`, `scripts/build_release.py`, `docs/releases.md` : lancement stable et distribution.
- `tests/` : conventions de fixtures et connecteurs simulés.

La configuration utilisateur actuelle est `C:\Projects\CyAIOrchestrator\config.json` ; elle référence `<dossier-données-CyAI>`. Les GGUF sont dans `<dossier-modèles>`. Ne pas inclure ces fichiers dans l’installateur.

Le lanceur installé est `%LOCALAPPDATA%\Programs\CyAIOrchestrator\CyAIOrchestrator.exe`. Les versions de l’application sont sous `versions/`. Les anciens dossiers `dist` sont des builds, pas une nouvelle source de vérité pour les données.

## Critères d’acceptation du lot 1

1. Créer trois profils avec des modèles différents, puis composer une équipe chef → lead → membre depuis l’interface.
2. Fermer et rouvrir l’application : retrouver profils, préprompts, révisions et hiérarchie.
3. Utiliser les mêmes profils dans deux projets : aucune affectation ou donnée locale partagée par accident.
4. Modifier un préprompt global : les équipes existantes conservent leur révision jusqu’à adoption explicite.
5. Un cycle ou un responsable d’un autre projet est refusé côté service, pas seulement masqué dans l’interface.
6. Une équipe incomplète est sauvegardable comme brouillon avec explication et moyen de correction.
7. Dupliquer un modèle d’équipe crée de nouveaux membres et reconstruit correctement les liens hiérarchiques, sans importer les sessions/mémoires du projet source.
8. Archiver un profil ne casse pas les équipes existantes ni l’historique des révisions.
9. Les opérations MCP autorisées fonctionnent sans navigateur. Les écritures hors portée sont refusées.
10. Un connecteur absent ou un modèle non confirmé ne provoque ni faux statut « prêt à exécuter », ni impossibilité de modifier la configuration.
11. Migration vérifiée sur une copie de base existante et sur une base neuve, sans perte de conversations ou mémoire.
12. Les modes normal et mission restent utilisables ; aucune exécution ne démarre lors de la configuration de l’équipe.

## Validation et livraison

- Tests métier et d’intégration pertinents : persistance, migrations, isolation des projets, versions figées, hiérarchie, duplication de modèle et périmètres MCP.
- Vérifier les parcours UI essentiels avec le moyen disponible. Une vérification de syntaxe JavaScript ne suffit pas à déclarer l’interface validée visuellement ; signaler toute limite de validation.
- Utiliser `.desktop-venv\Scripts\python.exe -m unittest discover -s tests` et les tests JavaScript pertinents. Ne pas changer des assertions pour masquer une régression ; expliquer les changements de contrat intentionnels.
- Produire une version installable avec la chaîne existante, après validation. Examiner les scripts de build : ne pas lancer la création du paquet avant la fin de la copie PyInstaller. Vérifier le contenu du paquet final.
- Incrémenter la version de façon cohérente après avoir vérifié les versions déjà présentes. Ajouter une note de version.
- Livrer un compte rendu : fonctions réellement disponibles, validations effectuées, limites et commandes exactes pour installer/lancer.
- Tenir à jour `docs/team-board-progress.md` au fil du travail : terminé, en cours, décisions, fichiers modifiés, résultats des tests et prochaine action. Si le quota s’épuise, permettre la reprise depuis ce fichier sans relire toute la conversation.

## Démarrage attendu

Inspecter les points d’intégration du lot 1, enregistrer un plan court dans le fichier de suivi, puis coder et tester. Faire les choix techniques ordinaires sans redemander l’approbation du périmètre déjà défini. Poser une question uniquement si un choix produit majeur reste réellement indéterminé et empêche d’avancer correctement.
