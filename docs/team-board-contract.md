# Contrat d’extension — Équipes / Board

Ce document dit ce qui est acquis et ce qui reste à construire pour le board d’exécution.

**Implémenté** : profils globaux versionnés, équipes hiérarchisées par projet avec consultants, modèles d’équipe,
cartes de tâches et rapports, conversations de membres, exécution d’une carte, garde-fous de boucle, mémoire par
portée, évaluations et propositions d’amélioration — persistance, validations, API locale, actions MCP et interface.

**Pas encore implémenté** : l’automate de délégation, et la génération spontanée de propositions par les agents. La base ne contient aucune tâche factice, aucun faux rapport et aucune conversation
fabriquée : ces tables seront ajoutées au moment de leur implémentation.

Aucune opération décrite comme implémentée ne lance d’agent.

## Ce que le lot 1 garantit aux lots suivants

| Point d’appui | Où | Garantie |
| --- | --- | --- |
| Identité stable d’un agent dans un projet | `team_members.id` | Identifiant d’affectation unique, distinct du profil global. C’est lui qui doit porter les conversations, tâches, rapports et mémoire locale. |
| Définition effective d’un agent | `team_members.definition` + `profile_revision` | Copie figée au moment de l’affectation. Une exécution future doit lire cette copie, jamais la définition courante du profil global. |
| Hiérarchie | `team_members.manager_id` | Responsable dans la **même** équipe, sans cycle, validé côté service (`cyai/teams.py`). Une délégation peut s’appuyer dessus sans revalider la forme de l’arbre. |
| Équipe du projet | `teams` (une ligne par projet) | `status` vaut `draft` ou `ready`. `ready` signifie « composition valide », **pas** « prêt à exécuter ». |
| Diagnostic de composition | `teams.team_issues()` | Liste de `{code, message, member_id?, field?}`. Ajouter un nouveau code plutôt que réutiliser un code existant avec un autre sens. |
| Disponibilité réelle du fournisseur | `teams.execution_warnings()` | Avertissements non bloquants sur le connecteur et le modèle. C’est le point d’entrée naturel pour la vérification de faisabilité du lot 2. |
| Modèles d’équipe | `team_templates.composition` | JSON `{team_name, members:[{key, profile_id, profile_revision, definition, role, responsibility, manager_key, position}]}`. Les clés `key`/`manager_key` sont locales au modèle ; l’application génère de nouveaux identifiants d’affectation. |

## Points d’extension prévus

### Conversations de membres — implémentées

`cyai/team_runtime.py`. Le mode `conversations.mode = 'team'` a été ajouté sans toucher à `chat` ni `orchestrator`.
Une conversation porte `member_id` (l’affectation) et, si elle concerne une carte, `task_id`. Ses consignes sont
reconstruites depuis la **révision figée** de l’affectation, jamais depuis le profil global courant.

La table `sessions` possède déjà une colonne `purpose` et n’impose plus l’unicité `(conversation_id, connector, model)` :
plusieurs membres peuvent donc coexister sans partager une session native. La règle à conserver est « une seule écriture
active par session native ». Une session ne doit jamais être attachée au profil global : elle appartient au couple
(projet, affectation, usage).

### Exécution — implémentée pour une carte, pas pour la délégation

`task_execute` crée une mission ordinaire à une étape dans la conversation du responsable, avec le connecteur et le
modèle de sa révision figée. Le moteur n’a pas été modifié. `task_executions` suit chaque lancement ; `reconcile()`,
appelée à la lecture, matérialise l’issue même après un plantage.

Invariants à conserver :

- Le compte rendu d’un agent est stocké **verbatim**, avec `task_reports.source = 'agent'`. CyAI ne le découpe pas en
  champs qu’il ne peut pas vérifier et n’en déduit aucun test exécuté.
- Une exécution réussie amène la carte en revue, **jamais** en `done`.
- Une exécution échouée n’écrit aucun rapport et invite à vérifier les effets déjà produits.
- Le périmètre de fichiers est une **consigne** transmise à l’agent, pas une contrainte technique. Ne pas laisser
  croire le contraire dans l’interface.

Reste à construire : la délégation autonome (le chef décide, les leads découpent), avec remontée des boucles sans
progrès plutôt qu’une poursuite indéfinie, et la pause/reprise d’une exécution depuis le board.

### Consultants

Un quatrième rôle existe dans `team_members.role` : `consultant`. Il est **hors de la chaîne de commandement**
— il ne dirige personne et n’a pas besoin de responsable — et se sollicite sur une tâche précise pour ce qu’il
fait mieux qu’un membre permanent (recherche, modèle spécialisé, format particulier). Un référent facultatif
(`manager_id` vers un chef ou un lead) reste possible, sans être exigé.

Conséquences déjà implémentées : `team_issues` exempte les consultants des règles de branche ; l’arbre de
l’onglet Équipe les présente dans une section distincte ; et pour l’acceptation d’une tâche, faute de supérieur
hiérarchique, la décision remonte à un chef de projet actif, ou à l’utilisateur.

La **sollicitation** est implémentée : table `task_consultations`, actions `task_consult` et `task_consult_answer`.
Un avis ne déplace pas la carte, ne transfère pas sa responsabilité et ne vaut jamais acceptation ; le responsable d’une
tâche ne se consulte pas lui-même. La colonne `answer_source` distingue une réponse saisie par l’utilisateur d’une
réponse réellement rendue par l’agent : l’exécution devra la renseigner honnêtement, et ne jamais marquer `agent`
pour un texte recopié à la main.

Attention à ne pas déduire une capacité d’un rôle : déclarer un consultant « recherche web » ou « images » ne prouve
pas que son connecteur sache le faire. `teams.definition_status()` dit ce qui est vérifié du connecteur et du modèle ;
tout le reste est une compétence déclarée, pas une capacité constatée.

### Tâches et rapports — implémentés

`cyai/tasks.py` porte les cartes de tâches et les rapports, avec les tables `tasks` et `task_reports`.
Ce qui est acquis et ne doit pas être contourné par le board :

- `assignee_id` et `author_id` référencent `team_members.id`, avec `ON DELETE SET NULL` : retirer une affectation
  ne détruit ni la carte, ni son historique, ni ses rapports.
- Les neuf statuts et la table `TRANSITIONS` ; `done` et `to_correct` ne sont **pas** atteignables par un simple
  changement de statut.
- `task_report` met la carte en revue mais ne la termine jamais. `task_accept` exige l’état `in_review`, l’existence
  d’un rapport, des preuves non vides, et un validateur habilité (`eligible_reviewers`).
- `eligible_reviewers` : supérieurs hiérarchiques du responsable ; à défaut (consultant ou chef de projet), les chefs
  actifs ; et toujours l’utilisateur via `by_user`.
- Dépendances et parent : existence, appartenance à l’équipe et absence de cycle vérifiées **à la création comme à la
  mise à jour**. `ready` est refusé tant qu’une dépendance n’est pas `done`.

Reste au board : l’exécution, la délégation chef → leads → membres, les conversations de membres, les indicateurs
d’activité, la pause/reprise et la réconciliation après crash. Rien de tout cela n’est dans `tasks.py`, qui ne lance
aucun agent.

### Mémoire — implémentée

`cyai/learning.py`, table `agent_memory` avec un discriminant `scope`. Trois portées, à ne jamais fusionner :

1. **Projet** — table `memory` et `project_memory.project_foundation()`.
2. **Agent dans le projet** — `scope='member'`, vers `team_members.id`. Ne part jamais ailleurs d’elle-même.
3. **Profil global** — `scope='profile'`, vers `agent_profiles.id`, `transferable=1` obligatoire et au moins une source.

Changer la portée d’une mémoire existante est refusé : le passage de la portée agent à la portée profil se fait par une
proposition adoptée, jamais par une mise à jour en place.

Le mécanisme de révision du lot 1 est le support de l’adoption explicite : une amélioration de préprompt proposée par un
lead doit créer une **nouvelle révision** du profil global (`agent_profile_save`), que chaque projet adopte ensuite par
`team_adopt_revision` après avoir consulté `team_revision_preview`. Aucune équipe ne change en silence.

### Évaluations et propositions — implémentées

`task_evaluations` conserve auteur, date, carte, révision du préprompt, connecteur et modèle effectivement utilisés,
durée mesurée et consommation quand le fournisseur la fournit. Le commentaire est obligatoire, un agent ne s’évalue pas
lui-même, et **rien n’écrit dans `model_ratings`** : ne pas brancher ces notes sur une sélection automatique de modèle.

`improvement_proposals` porte les propositions de consignes ou de mémoire transférable. Invariants : motif et sources
obligatoires, auteur chef ou lead, adoption créant une révision que chaque projet adopte ensuite explicitement, refus
conservé avec son motif. Une proposition à source unique est signalée comme possiblement isolée.

## Règles à ne pas casser

- Modifier un profil global ne modifie jamais une équipe existante : seule `team_adopt_revision` change une copie figée.
- Archiver un profil ne supprime ni ses révisions ni ses affectations.
- Un responsable appartient toujours à la même équipe et au même projet ; les cycles sont refusés côté service.
- L’interface et le MCP appellent les mêmes services (`cyai/teams.py` via `Service.action`). Ne pas ajouter d’écriture
  qui contourne cette couche.
- Les opérations globales sont marquées `scope='global'` dans `cyai/app_mcp.py` et leurs écritures exigent
  `--allow-global` pour un client externe, ou une autorisation interactive de l’utilisateur pour un agent interne.
- Aucun secret (clé API, jeton, identifiant de session native) dans un profil, une équipe, un modèle d’équipe ou leur export.
