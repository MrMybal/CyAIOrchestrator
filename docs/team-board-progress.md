# Suivi — Équipes / Board

Dernière mise à jour : **lot 1 livré** en 0.2.2, **lot 2 livré sauf l’automate de délégation** en 0.2.3,
**garde-fous d’exécution** en 0.2.4,
**lot 3** (mémoire par portée, évaluations, propositions) en 0.2.5,
**agents modifiables, spécialistes et méthodes** en 0.2.6,
**boîtes à outils et compétences attestées** en 0.2.7,
**interface façon Discord, étape 1** en 0.2.8,
**éditeur de méthodes nodal, catégories d’agents et messages privés** en 0.2.9,
**méthode comme skill** en 0.2.10,
**messages groupés et tableau blanc** (étape 2 de l’interface, première partie) en 0.2.11,
**carte de tâche dans le fil et salons graphe** en 0.2.12,
**outils de conversation** en 0.2.13,
**console de plugin** en 0.2.14,
**automate de délégation** en 0.2.15,
**propositions spontanées à la demande** en 0.2.16,
**deux corrections anciennes, suite de tests entièrement verte** en 0.2.17,
**relecture critique et essai de mise à jour sur une copie de la vraie base** en 0.2.18 (18 septembre 2026),
**méthodes comme fonctions — broches, contextes distribués, sous-méthodes, versions** en 0.2.19,
**consignes en grand, fichiers joints, atelier IA, entrées préparées** en 0.2.20,
**méthodes des agents, notes d’usage, logiciels localisés** en 0.2.21,
**tests, notes, vérification de compréhension, précisions par modèle, amélioration et boucle d’affinage** en 0.2.22,
**propositions des agents pendant l’usage, examen et discussion avec l’auteur** en 0.2.23,
**création de projet avec apparence et aperçu, logo réduit automatiquement, assistant du projet** en 0.2.24,
**collage d’images rétabli dans CyAnnota** en 0.2.25,
**bilan de l’équipe, verdicts et suites, curseurs, capacités des modèles et ordres de préférence** en 0.2.26,
**voix dans les conversations (jalon 1 : dictée, lecture des réponses, conversation vocale)** en 0.2.27,
**voix jalon 2 (Kyutai STT en direct, Pocket TTS, copie de voix, Whisper Large v3)** en 0.2.28,
**Codex relancé malgré la régression du bac à sable Windows, accès de Codex réglable, discussion vocale directe** en 0.2.29,
**dictée Kyutai réparée sous Windows (sans torch.compile), démarrage hors ligne** en 0.2.30
(19 septembre 2026). Le paquet `releases/CyAIOrchestrator-Setup-0.2.30.exe` contient tout ce qui est décrit ci-dessous.

## État

| Élément du lot 1 | État |
| --- | --- |
| A. Bibliothèque globale d’agents (création, édition, duplication, archivage, révisions) | Fait |
| B. Onglet Équipe par projet (hiérarchie, rôles, responsables, problèmes, modèles) | Fait |
| C. Persistance SQLite, services métier, API locale et actions MCP avec portées | Fait |
| D. Contrat d’extension documenté pour les lots suivants | Fait — `docs/team-board-contract.md` |
| Lot 2 (board d’exécution, conversations de membres, tâches, rapports) | En cours — voir plus bas |

Aucune exécution n’est déclenchée par ces écrans. Aucune tâche, conversation ou rapport factice n’a été inséré en base.

## Décisions techniques retenues

- Rôles stockés : `chief` (chef de projet), `lead`, `member`. Le responsable est `manager_id`, un identifiant
  **d’affectation** de la même équipe, jamais un identifiant de profil.
- Une seule équipe courante par projet pour ce lot : index unique `teams_current_project` sur `teams(project_id)`.
- `team_members.definition` contient la copie figée de la définition du profil au moment de l’affectation, avec
  `profile_revision`. Modifier un profil global ne change rien tant que `team_adopt_revision` n’est pas appelé.
- Distinction volontaire entre **problèmes bloquants** (`teams.team_issues`, empêchent de déclarer l’équipe prête) et
  **avertissements d’exécution** (`teams.execution_warnings`, connecteur désactivé/absent, modèle non confirmé,
  catalogue indisponible). Les seconds ne bloquent jamais la configuration et ne produisent jamais un statut
  « prêt à exécuter ».
- Cycle, auto-rattachement, responsable hors équipe/projet et responsable qui n’est ni chef ni lead sont refusés dans
  `cyai/teams.py`, donc identiquement pour l’interface et pour le MCP.
- Retirer ou rétrograder un responsable exige `reassign_to` **ou** `acknowledged` : le brouillon reste enregistrable
  explicitement incomplet, avec le problème signalé.
- Portée MCP : `scope='global'` pour la bibliothèque et les modèles d’équipe. Lecture globale autorisée (aucun secret),
  écriture globale refusée sans `--allow-global` pour un client stdio. Un agent interne à CyAI passe par l’autorisation
  interactive de l’utilisateur, et la demande indique la portée (« bibliothèque globale » ou « projet »).
- Sauvegarde globale passée en format 2 (inclut les nouvelles tables). Le format 1 reste restaurable : la bibliothèque
  globale est conservée telle quelle et les équipes des projets remplacés disparaissent avec eux (cascade).

## Fichiers modifiés ou ajoutés

Nouveaux : `cyai/teams.py`, `cyai/web/teams.js`, `tests/test_teams.py`, `tests/test_teams_mcp.py`,
`docs/team-board-contract.md`.

Modifiés : `cyai/store.py` (5 tables), `cyai/service.py` (dispatch, résumé d’équipe du projet, sauvegarde format 2,
option `allow_global` de la configuration client MCP), `cyai/app_mcp.py` (16 actions du domaine `teams`, portée globale),
`cyai/mcp.py`, `cyai/server.py`, `cyai/__main__.py` (`--allow-global`), `cyai/desktop.py` (contrôles UI des nouveaux
écrans dans `--verify-ui`), `cyai/web/index.html`, `app.js`, `project.js`, `workspace.js`, `i18n.js`, `styles.css`,
`cyai/__init__.py` et `pyproject.toml` (0.2.2), `docs/releases.md`.

## Validations effectuées

- `.desktop-venv\Scripts\python.exe -m unittest discover -s tests` → **192 tests**, 2 échecs **préexistants**, 2 ignorés.
  Les deux échecs (`test_intelligence.test_compaction_keeps_history_and_manual_selection` et
  `test_recovery_defaults.test_native_resume_sends_only_new_selected_messages`) existaient avant ce lot : la présentation
  de projet réinjecte la première demande utilisateur, que ces tests supposent absente. Aucune assertion n’a été modifiée.
- Après le lot 1 : **211 tests**, toujours les mêmes 2 échecs préexistants. 39 tests couvrent équipes, tâches et
  portées MCP.
- 20 nouveaux tests : révisions, duplication indépendante, refus de champs invalides, connecteur/modèle inconnus toujours
  éditables, hiérarchie relue après réouverture de la base, brouillon incomplet, refus des cycles et des responsables
  étrangers, réaffectation, isolation entre deux projets partageant les mêmes profils, adoption de révision, archivage,
  modèles d’équipe, sauvegarde/restauration formats 1 et 2, migration d’une base antérieure.
- Parcours interface réel dans le navigateur, sur une configuration et une base temporaires (port 8791,
  dossier de données temporaire) : trois profils avec trois modèles différents, équipe chef → lead → membre, déclaration
  « prête », édition d’un préprompt global, révision figée conservée puis comparatif et adoption, enregistrement d’un
  modèle d’équipe et application à un second projet, redémarrage du service et relecture complète.
- Application de bureau réelle (pywebview / WebView2) via `--verify-ui` : `agent_library` (page et fiches présentes),
  `project_team_tab` et `team_tab` valides, et tous les contrôles préexistants toujours au vert.
- MCP sans navigateur, via le vrai pont stdio (`python -m cyai mcp --config … --project … --allow-write`) : lecture de
  l’équipe autorisée et écriture projet acceptées ; écriture globale refusée avec le message expliquant `--allow-global` ;
  projet hors périmètre refusé. Avec `--allow-global`, création d’un profil global acceptée.
- Migration sur une **copie** de la base de production locale (31,5 Mo, ouverte en lecture seule pour la copie) :
  5 tables ajoutées, aucune table perdue, comptes identiques (4 conversations, 48 messages, 18 missions, 52 254
  événements, 204 fichiers, 1 mémoire).
- Paquet : `releases/CyAIOrchestrator-Setup-0.2.2.exe` (169,3 Mo), construit après la fin de la copie PyInstaller.
  Manifeste identique au contenu du zip (345 fichiers), `teams.js` présent et référencé par `index.html`, aucune donnée
  utilisateur embarquée, SHA-256 recalculé conforme au fichier `.sha256`.

## Limites connues

- Les deux échecs de tests préexistants ci-dessus ne sont pas corrigés : hors périmètre du lot 1, et les corriger
  supposerait de trancher si la présentation automatique de projet doit rester dans le contexte.
- L’installateur ne contient pas de `CyAI-MCP.exe`, alors que `Service.action('mcp_client_config')` le référence pour une
  installation figée. Ce décalage est antérieur à ce lot et n’a pas été traité ici.
- Le nombre d’agents n’est pas plafonné ; l’arbre n’a pas été éprouvé au-delà d’une dizaine d’affectations.
- Pas de glisser-déposer dans l’arbre (non exigé au lot 1) : réaffectation par boutons et listes déroulantes.
- Les avertissements d’exécution reposent sur le catalogue en cache du connecteur. Catalogue absent = « non confirmé »,
  jamais « invalide ».

## Lot 2 — en cours

### Fait

- **Rôle `consultant`** dans `cyai/teams.py` : hors de la chaîne de commandement, sollicité sur une tâche pour ce
  qu’il fait mieux (recherche, modèle spécialisé, format particulier). Il ne dirige personne, n’exige pas de
  responsable, et un référent facultatif reste possible. `team_issues` l’exempte des règles de branche ; l’onglet
  Équipe le présente dans une section distincte. Idée de l’utilisateur, retenue avant le board pour ne pas avoir à
  la rétrofitter.
- **Conversations de membres** (`cyai/team_runtime.py`) : chaque affectation a sa conversation persistante, mode
  `team`, avec le connecteur, le modele et les consignes de sa **revision figee**. Colonnes `conversations.member_id`
  et `conversations.task_id`. Rien n'est partage entre projets, ni avec le profil global : deux affectations du meme
  profil dans deux projets ont deux conversations distinctes. Les modes `chat` et `orchestrator` ne sont pas touches.
- **Execution d'une carte par son responsable** : `task_execute` lance l'agent dans sa propre conversation via le
  moteur existant, avec la carte comme instruction (objectif, perimetre de fichiers, criteres, livrables, avis rendus
  et corrections demandees). Table `task_executions` pour le suivi. Le compte rendu revient **marque `source='agent'`**
  et la carte passe en revue - jamais en « terminee ». Un echec n'invente aucun rapport : il est enregistre avec son
  erreur et invite a verifier les effets deja produits. `task_execution_cancel` arrete l'agent.
- **Reconciliation a la lecture** : `reconcile()` est appelee par `task_list` et `task_get`. Un plantage entre la fin
  d'une mission et l'ecriture de son rapport ne perd donc rien : l'issue est materialisee a la lecture suivante,
  y compris quand la mission a ete marquee interrompue au redemarrage.
- **Sollicitation des consultants** : table `task_consultations`, actions `task_consult` et `task_consult_answer`,
  section « Avis demandés » sur chaque carte. Un avis est **distinct d’un rapport** : il ne déplace pas la carte, ne
  transfère pas sa responsabilité, et ne vaut jamais acceptation. Le responsable d’une tâche ne peut pas être consulté
  sur sa propre tâche — il rend un rapport. Une réponse porte `answer_source` : « saisi par l’utilisateur » aujourd’hui,
  « rendu par l’agent » quand l’exécution existera, pour qu’une recopie manuelle ne passe jamais pour un travail d’agent.
- **Interface du board** (`cyai/web/board.js`) : onglet « Board » du projet, colonnes par statut, filtre par responsable,
  section repliable des cartes closes. Une carte s’ouvre sur son détail complet : périmètre de fichiers, critères
  d’acceptation, livrables, sous-tâches, dépendances bloquantes, rapports dépliables et historique intégral.
  Les transitions proposées sont exactement celles que le service autorise depuis l’état courant ; « Terminée » et
  « À corriger » ne sont jamais proposées comme un simple déplacement.
- **L’utilisateur est un acteur de plein droit** : `task_create` et `task_status` acceptent `by_user`, l’historique
  enregistre alors « Utilisateur ». Sans cela, déplacer une carte à la main aurait obligé à se faire passer pour un agent.
  Un `author_id` nul se lit « Utilisateur » ou « Affectation retirée » selon ce que dit la première entrée d’historique.
- **`cyai/tasks.py`** : cartes de tâches et rapports. Tables `tasks` et `task_reports` dans `store.py`, branchement
  dans `Service.action`, 9 actions MCP du domaine `tasks` toutes en portée `project_id`, sauvegarde format 2 étendue.
- **Base de départ produite par Antigravity** (`agy` 1.2.5, `gemini-3.1-pro-high`), en bac à sable isolé, sans accès
  au dépôt et sans droit d’écriture. Structure, table de transitions et messages français conservés ; trois défauts
  vérifiés par exécution puis corrigés : dépendances non validées sur le chemin de mise à jour, auto-acceptation
  possible par le responsable lui-même, absence de contrôle de portée projet. Expérience non reconduite :
  une seule tâche a consommé 32 % du quota Gemini hebdomadaire de l’utilisateur.

### Décisions techniques du lot 2

- Neuf statuts, table `TRANSITIONS` explicite. `done` et `to_correct` ne sont pas atteignables par un changement de
  statut ordinaire : ils passent par `task_accept` et `task_correction`, qui enregistrent qui décide et sur quoi.
- `task_report` fait passer une carte `in_progress` en `in_review` — un rapport rendu ne doit pas rester invisible —
  mais ne la termine jamais.
- `task_accept` exige l’état `in_review`, un rapport existant, des preuves non vides et un validateur habilité.
- `eligible_reviewers` : supérieurs hiérarchiques du responsable ; à défaut (consultant hors chaîne, ou chef de
  projet), les chefs actifs ; et toujours l’utilisateur via `by_user`. Un agent ne valide jamais son propre travail.
- `assignee_id` et `author_id` en `ON DELETE SET NULL` : retirer une affectation ne détruit ni carte, ni historique,
  ni rapport. L’affichage indique « Affectation retirée ».

### Validations du lot 2

- **233 tests**, toujours les 2 seuls échecs préexistants. 41 tests couvrent les cartes, les conversations
  de membres, l’exécution, la délégation par MCP et les garde-fous : création, liens refusés à la
  création comme à la mise à jour, dépendances bloquantes, transitions interdites, rapport qui ne termine pas,
  auto-acceptation refusée, cas consultant, cas chef de projet, suppression en cascade, survie des rapports au retrait
  d’une affectation, portées MCP, et les quatre cas de consultation : avis qui ne déplace rien, réponse saisie
  marquée comme telle, refus de consulter le responsable ou une carte close, avis décliné et motivé.
- **Parcours réel dans le navigateur**, base et configuration temporaires : création d’une carte par le lead pour le dev,
  passage « prête » puis « en cours », dépôt d’un rapport complet (résultat, fichiers, tests réellement exécutés, limites,
  risques, décisions demandées), passage automatique en revue, refus vérifié de l’auto-acceptation par le dev **côté
  service** et non seulement masqué dans l’interface, refus d’une acceptation sans preuve, puis acceptation par le lead.
  Historique final : `to_prepare · Nadia` → `ready · Nadia` → `in_progress · Tom` → `in_review · Tom` → `done · Nadia`.
- **Application de bureau réelle** via `--verify-ui` : `board_tab` → 9 colonnes et bouton de création présents,
  et les 21 autres contrôles toujours au vert.
- **Consultation vérifiée dans le navigateur** : profil consultant créé, affecté hors hiérarchie, avis demandé par
  l’utilisateur sur une carte dont Tom est responsable — Tom absent de la liste des consultables —, pastille « 1 avis
  attendu » sur la carte, réponse enregistrée. Après coup : carte toujours « à préparer », toujours 0 rapport,
  avis marqué « saisi par l’utilisateur ». L’onglet Équipe affiche bien la section « Consultants · sollicités à la tâche »
  et signale zéro problème de composition.
- **Exécution vérifiée par les tests d’intégration** avec les connecteurs de fixtures, jamais avec un fournisseur payant :
  compte rendu attribué à l’agent et carte arrêtée en revue, instruction réellement envoyée contenant la carte,
  auto-acceptation toujours refusée, échec sans rapport fabriqué, double lancement refusé, annulation, travail parallèle
  de deux membres, et simulation d’un plantage montrant que l’issue est retrouvée sans rapport inventé.
- **Interface vérifiée dans le navigateur** : conversations d’équipe visibles dans la barre latérale avec le connecteur
  du profil présélectionné et l’en-tête « Équipe · révision figée du profil » ; carte affichant « Lancer Tom · développeur »
  et « Conversation de l’agent » ; refus explicite au lancement quand le connecteur est désactivé, sans exécution
  enregistrée. Les gabarits « agent en cours » et « compte rendu de l’agent · non vérifié par CyAI » ont été rendus
  avec des données injectées côté client — **aucune exécution réelle n’a été lancée dans l’interface**, pour ne pas
  consommer le quota d’un fournisseur.

### Garde-fous d’exécution (0.2.4)

`team_runtime.stalled()` détecte une carte qui tourne sans avancer, **quel que soit celui qui la relance** : deux
échecs de suite (`repeated_failures`), trois corrections demandées (`correction_loop`, qui désigne l’énoncé plutôt
que le travailleur), trois exécutions sans acceptation (`no_progress`). Les seuils sont des constantes nommées en tête
du module. L’alerte apparaît sur la carte ; `task_execute` refuse alors de relancer sans `acknowledged`. CyAI remonte
le problème et laisse l’utilisateur trancher : il n’annule jamais une carte de lui-même. C’est aussi la pièce qui
manquait avant d’envisager un automate de délégation.

`task_execution_pause` met en pause ou reprend (`resume=true`) une exécution depuis le board, via le moteur existant.

### Ce que « exécution » couvre, et ce qu’elle ne couvre pas

Couvert : lancer l’agent responsable sur une carte, suivre son exécution, annuler, récupérer son compte rendu comme
rapport marqué « agent », réconcilier après un plantage. Deux membres différents travaillent **en parallèle**, chacun
dans sa conversation — vérifié par un test où une tâche courte se termine pendant qu’une longue tourne encore.
Le moteur n’a pas été modifié : `task_execute` crée une mission ordinaire à une étape.

**Chemin de délégation validé par les tests** (connecteurs de fixtures appelant réellement la passerelle MCP,
donc le même code qu’un vrai CLI) :

1. Un chef de projet, depuis **sa** conversation d’équipe, crée et attribue une carte par `cyai_call`. La carte
   apparaît « à préparer » : elle n’est pas lancée toute seule.
2. Le même agent qui vise un **autre projet** est refusé « hors périmètre MCP », et le refus intervient **avant**
   la demande d’autorisation.
3. Lancer un membre depuis l’intérieur d’une mission est **différé**, pas récursif : l’appel rend un `job_id` en
   attente et ne s’exécute qu’une fois aucune mission active. Une seule exécution en résulte. C’est le garde-fou
   contre un agent qui en lancerait un autre en chaîne.

Concrètement, une délégation fonctionne déjà : vous parlez au chef, il découpe en cartes, il demande le lancement
d’un membre, le membre travaille après la fin du tour du chef, son compte rendu arrive en revue. Chaque écriture passe
par votre autorisation.

**Non couvert — l’automate de délégation.** Le chef de projet ne décide pas seul de créer des cartes et de lancer ses
Il n’existe aucun automate qui relance le chef tant que le board n’est pas vide. La détection de boucle sans progrès,
elle, existe depuis 0.2.4. Le parcours n’a pas non plus été rejoué avec un vrai
fournisseur : les tests utilisent des connecteurs de fixtures. Ne pas présenter le lot 2 comme une délégation autonome.

Non couvert non plus : le périmètre de fichiers, qui est transmis à l’agent comme **consigne**
sans être imposé techniquement — l’interface le dit explicitement au lancement.

## Lot 3 — mémoire, évaluations et amélioration

### Fait

- **Trois portées de mémoire qui ne se mélangent jamais** (`cyai/learning.py`, table `agent_memory`) :
  le projet (déjà présent), l’**agent dans ce projet** et le **profil global**. Une observation locale ne quitte jamais
  son projet d’elle-même ; changer la portée d’une mémoire existante est refusé. Une mémoire de profil doit être
  **explicitement déclarée transférable** et citer au moins une source vérifiable, sinon elle est refusée.
- **Injection dans le contexte** (`cyai/context.py`, uniquement si la conversation porte un `member_id`) : l’agent reçoit
  ses observations locales, avec la consigne de ne pas les transposer ailleurs, et les méthodes transférables de son
  profil. La mémoire d’un autre agent ne fuit pas, et une conversation normale n’est pas touchée. Le tout reste visible
  dans « Inspecter le contexte ».
- **Évaluations** (table `task_evaluations`) : critères de 1 à 5 — qualité, respect du périmètre, intégration, tests
  réellement fournis, corrections nécessaires — avec **commentaire obligatoire**. Sont conservés l’auteur, la date, la
  carte, la révision du préprompt, le connecteur et le modèle effectivement utilisés, la durée mesurée et la
  consommation **lorsque le fournisseur la donne**. Refusé : évaluer une carte sans rapport, sans commentaire, sans
  note, hors barème, sur un critère inventé, ou évaluer son propre travail. Aucune note n’alimente `model_ratings` :
  une note ne démontre pas une supériorité de modèle.
- **Propositions d’amélioration** (table `improvement_proposals`) : un chef ou un lead — jamais l’agent concerné —
  propose de nouvelles consignes ou une mémoire transférable, avec motif et sources obligatoires. Une proposition ne
  s’appuyant que sur une source est enregistrée mais **signalée comme incident possiblement isolé**.
- **Adoption réversible** : adopter une proposition de consignes crée une **nouvelle révision du profil global** via
  `save_profile`. Aucune équipe ne change : chaque projet adopte la révision explicitement, comme au lot 1, et revenir
  en arrière consiste à réadopter la révision précédente. Une proposition écartée reste consultable avec son motif.

### Validations du lot 3

- **243 tests**, toujours les 2 seuls échecs préexistants ; 10 nouveaux couvrent les trois portées, l’étanchéité entre
  agents et entre projets, l’injection de contexte, les refus d’évaluation et de proposition, l’adoption et le retour
  en arrière.
- **Boucle complète rejouée dans l’application** : observation locale enregistrée sur un agent, proposition faite par
  le lead, adoption — révision 2 créée sur le profil global, équipe toujours en révision 1 avec « mise à jour
  disponible », consignes de l’équipe inchangées. Puis évaluation refusée quand l’agent se note lui-même, acceptée par
  son lead, avec révision du préprompt et connecteur enregistrés.
- **Paquet 0.2.5** : 346 fichiers, manifeste identique au zip, actions d’évaluation présentes dans le `board.js`
  embarqué et actions de proposition dans le `teams.js` embarqué, aucune donnée utilisateur, SHA-256 conforme.
  Application de bureau revérifiée : 22 contrôles, aucun en échec.

### Ce que ce lot ne fait pas

Il ne constitue **aucun entraînement de modèle** : il change le contexte et les consignes, rien d’autre. Aucune
proposition n’est générée automatiquement par les agents aujourd’hui — ils peuvent en créer par le MCP, sous votre
autorisation, mais rien ne les y pousse. Et rien n’empêche encore d’adopter une proposition mal fondée : CyAI signale
le nombre de sources, il ne juge pas à votre place.

## Au-delà des trois lots — demandé par l’utilisateur en cours de route

### Tout est modifiable sur un agent

Sur une affectation d’équipe : nom, icône, description, compétences, connecteur, modèle, consignes, réglages et
spécialistes appelables. La révision du profil reste la **base figée** ; les modifications sont stockées dans
`team_members.overrides` et fusionnées à la lecture par `teams.effective_definition()`. Conséquences tenues :

- le profil global et les autres projets ne bougent pas ;
- l’interface dit ce qui a été modifié sur place, et propose d’effacer pour revenir à la révision ;
- une surcharge reste **prioritaire après l’adoption d’une nouvelle révision** — `team_revision_preview` le signale,
  et il faut la retirer pour retrouver la valeur du profil.

`agent_profiles.icon` a été ajouté et versionné avec le reste de la définition. Attention pour la suite :
`save_profile` écrit des colonnes nommées ; tout nouveau champ de `DEFINITION_FIELDS` doit y être ajouté, faute de
quoi il ne sera lu que depuis les révisions (bug rencontré et corrigé sur l’icône).

### Un profil s’utilise partout

- Équipe : inchangé.
- **Conversation ordinaire** : `profile_conversation` crée un chat lié au profil (`conversations.profile_id` et
  `profile_revision`), sans composer d’équipe. La révision est figée à l’ouverture.
- **Chaîne** : une étape de mission peut porter `profile_id` au lieu d’un connecteur brut ; connecteur, modèle,
  consignes et réglages sont résolus dans `Service.action`, jamais dans le moteur.
- Une carte se confie directement à un spécialiste, sans lead. La revue remonte alors au chef, ou à l’utilisateur.

### Méthodes réutilisables

`cyai/methods.py`, table `method_templates`. Une méthode est une chaîne nommée d’étapes tenues par des profils, avec
dépendances par clé et un fichier attendu facultatif par étape, transformé en contrôle `file_exists` du moteur.
`method_apply` prépare la chaîne dans sa propre conversation **sans la lancer**. `{objectif}` est substitué là où
l’auteur l’a mis, sinon rappelé en tête. Une méthode **avance** : dépendre d’une étape suivante est refusé, parce
qu’un retour en arrière se pilote sur le board.

### Un agent qui appelle un spécialiste pendant son travail

`cyai/specialists.py`. Un profil déclare dans sa définition les profils qu’il a le droit d’appeler (`helpers`,
versionné et surchargeable). Pendant son étape, `plugins.gateway` lui expose l’outil `cyai_specialist`. L’appel
n’est **pas une mission** : il exécute le connecteur du spécialiste dans l’étape de l’appelant, sous son
`Control`. Quatre garde-fous, tous testés :

- chaque appel émet `specialist_requested`, `specialist_answered` ou `specialist_failed` dans les événements de la
  mission, avec la demande et la réponse — une chaîne ne cache jamais le travail qu’elle a fait faire ;
- un spécialiste reçoit `mcp_servers = {}` : **un seul niveau**, il ne peut pas en appeler un autre ;
- `MAX_CALLS` appels par étape, avec un message qui dit de conclure plutôt que de continuer à demander ;
- le `Control` enfant refuse toute demande d’autorisation : un spécialiste n’hérite d’aucun droit.

L’échec d’un spécialiste ne fait pas échouer l’appelant : il reçoit l’erreur et le conseil de poursuivre sans lui
en le signalant.

### Validations

- **272 tests**, toujours les 2 seuls échecs préexistants. 15 nouveaux couvrent les surcharges locales, les trois
  usages d’un profil, les méthodes et l’appel de spécialistes.
- Parcours réels dans l’application : modèle et icône modifiés sur une affectation sans toucher au profil global ;
  méthode « Vaisseau 3D » composée dans l’éditeur puis appliquée à « un croiseur minier cyberpunk », donnant une
  chaîne `pending` de quatre étapes avec les bonnes dépendances et trois contrôles de fichiers ; spécialistes
  déclarés sur un profil, visibles sur sa fiche et enregistrés dans une nouvelle révision.
- **Harnais de test** : `wait()` attendait 4 s qu’une mission asynchrone se termine, ce qui rendait
  `test_orchestrator_plan_waits_for_explicit_approval` instable maintenant que la suite lance de nombreux moteurs.
  Porté à 20 s. **Aucune assertion modifiée** ; seul le temps d’attente change.

### Boîtes à outils et compétences attestées (0.2.7)

`cyai/toolpacks.py`. Un profil déclare `tools` (identifiants de plugins MCP), versionné et surchargeable comme le
reste. Pendant son exécution, `plugins.gateway` expose les outils de ces plugins sous `outil__<plugin>__<outil>`,
découverts une fois par étape. Politique identique au reste de CyAI : plugin activé et non désactivé pour le projet ;
outil listé dans `read_tools` du plugin → libre ; autre outil → `control.approve`, donc la politique d’autorisation
de la conversation ; chaque appel émet `tool_called` / `tool_answered` / `tool_refused`. Un spécialiste appelé n’a
aucune boîte à outils (`mcp_servers = {}`).

Compétences : `learning.track_record()` agrège, pour un profil, tâches, acceptations, exécutions et moyennes
d’évaluation avec leur effectif — agrégats seulement, aucun contenu de tâche. `skill_attest` enregistre dans
`skill_attestations` une compétence **déclarée**, sur des preuves qui doivent être une tâche **acceptée** de ce profil
ou une évaluation de son travail ; les autres sources sont écartées et signalées.

Bug rencontré et corrigé pendant la vérification : les boutons « Attester » portaient un `${…}` littéral, parce que
l’interpolation était écrite dans une chaîne entre apostrophes et non dans un gabarit. Un balayage complet de
l’interface (bibliothèque, dialogues de profil, méthodes, onglets Équipe et Board, dialogues d’affectation, de
mémoire, de proposition et de carte) ne trouve plus aucune interpolation littérale.

**282 tests**, toujours les 2 seuls échecs préexistants.

### Interface façon Discord — étape 1 (0.2.8)

Demandée par l’utilisateur : les projets comme des serveurs, leurs vues comme des salons, l’équipe à droite. Étape 1
approuvée : la coque et les salons typés, en réutilisant les vues existantes.

Serveur : `cyai/channels.py`. `project_channels` calcule la liste des salons (catégories fixes *Conversations*,
*Agents*, *Équipe*, *Projet*) à partir des données existantes — conversations non archivées, rangées sous *Agents*
dès qu’elles portent un `member_id` ou un `profile_id` — avec des pastilles sur ce qui attend l’utilisateur (cartes
en revue, problèmes d’équipe). `presence()` déduit l’état de chaque membre actif des **missions actives de ses propres
conversations** : `awaiting` si une autorisation est en attente, `running` sinon, `unavailable` si le connecteur est
absent ou désactivé, `idle` autrement. Les lignes `task_executions` ne servent pas : elles restent `running` jusqu’à
leur réconciliation à la lecture, donc elles pourraient afficher un agent au travail après la fin de sa mission.
`project_pins` : notes de mémoire créées depuis un message (`source_ids` non vide), avec la conversation d’origine.
`project_media` : fichiers `kind='media'` des conversations du projet. Les trois actions sont en lecture et limitées
au projet par le MCP.

Interface : `cyai/web/channels.js` (chargé après `app.js`, déclaré dans la liste blanche de `server.py`).
`renderShell()` est appelée par `renderSidebar()` ; elle rend le rail, l’en-tête, les salons et les membres avec
`htmlIfChanged` pour ne pas recréer le DOM à chaque rafraîchissement, et recharge `project_channels` au plus toutes
les 1,4 s. Les identifiants existants (`#project-list`, `#new-project`, `#toggle-archives`, `#workspace`, `#page`,
`#inspector`) sont conservés : l’arborescence complète vit maintenant dans l’Accueil. Un salon système règle
`state.projectTab` puis `showView('project')` ; les onglets du projet sont masqués en CSS sauf sur téléphone, où la
liste des salons n’est pas affichée. Un écouteur en phase de capture remet `state.home` à faux avant que les
gestionnaires de `app.js` ne rendent la vue. Menus contextuels et glisser-déposer existants fonctionnent sur le rail
et les salons, puisqu’ils portent les mêmes `data-project` / `data-conversation`.

Aucune table ajoutée : les salons créés par l’utilisateur (graphe, tableau blanc, plugin) viendront avec le premier
type de salon qui en a besoin, à l’étape 2.

Validations : `tests/test_channels.py` (11 tests : catégories, rangement des conversations d’agent, archives exclues,
pastille du board, épinglés et origine, présence au repos / indisponible / en cours / en attente d’autorisation, projet
sans équipe, portée MCP). Suite complète : **293 tests**, toujours les 2 seuls échecs préexistants. Parcours navigateur
sur configuration temporaire (port 8791) : salons board, équipe, épinglés, médias ; fiche d’un membre et ses boutons ;
dialogue ＋ Agents et consultation directe d’un profil (crée bien un salon sous *Agents*) ; bascule Membres / Suivi ;
Accueil ; changement de projet par le rail ; largeurs tablette et téléphone sans défilement horizontal.
`--verify-ui` gagne le contrôle `discord_shell`.

Constaté en passant, non corrigé : dans `analytics.js`, les lignes 46 à 48 utilisent `$` au chargement, avant que
`app.js` ne le définisse. Elles lèvent donc une erreur et ne s’exécutent jamais — le rafraîchissement du catalogue de
modèles au focus du champ n’a jamais été branché. Le corriger activerait un comportement qui n’a jamais tourné : à
décider séparément.

### Corrections annotées de l’utilisateur sur la coque (0.2.8)

Reçues sous forme d’archive CyAnnota (capture annotée, 5 corrections), appliquées avant la construction du paquet :

1. **En-tête** « comme sur Discord » : `topbar` réduit à 48 px, glyphe du salon + titre, puis `#header-search`
   (recherche d’historique pré-filtrée sur le projet affiché ; Entrée ouvre la vue `search` et soumet son formulaire)
   et des icônes SVG. `renderConnectorStatus()` place désormais l’état des connecteurs et `#resource-usage` dans
   `.sidebar-footer`, au lieu de `.top-actions`.
2. **CyAnnota** : le bouton du plugin n’a plus de texte, seulement son logo, et vit dans la ligne de saisie à côté
   de l’envoi (`#plugin-toolbar` est déplacé dans `.composer-input`).
3. **Saisie** : `.composer-config` (agent, modèle, effort, vitesse, contexte) puis `.composer-input` (＋, champ, CyAnnota,
   envoi). Le champ fait une ligne et grandit jusqu’à 220 px ; `fitInstruction()` ne recalcule que si le texte ou la
   largeur a changé et jamais quand le champ est masqué — un premier calcul pendant la mise en page donnait 220 px.
   L’envoi reste sur Ctrl+Entrée : passer à Entrée comme Discord n’a pas été demandé.
4. **Onglets de conversation supprimés** : `renderConversationTabs()` retire la barre ; le bouton ⧉ du rail
   (`data-new-window`, géré par `tabs.js`) ouvre une nouvelle fenêtre. Les brouillons par conversation sont conservés.
5. **Membres et Détails** deviennent des icônes à droite de la recherche ; leur libellé passe dans `title` et
   `aria-label`, l’état ouvert dans la classe `active`.

Contrat de `--verify-ui` modifié en conséquence, volontairement : `tabs` vérifie maintenant l’**absence** de la barre
d’onglets et la présence du bouton de nouvelle fenêtre ; `compact_chrome.details` lit `aria-label` au lieu du texte du
bouton, qui n’en a plus.

### Retours de l’utilisateur après essai de la 0.2.8 (appliqués dans la même version)

- **Panneau de droite** : un seul état `state.rightPanel` ∈ `members` / `details` / `none`, mémorisé dans
  `localStorage` (`cyai-right-panel`, par défaut `members`). `setRightPanel(p)` bascule vers `p`, ou vers `none` si `p`
  est déjà sélectionné. `state.inspectorHidden` n’est plus qu’un dérivé, conservé pour le code existant. Les anciennes
  clés `cyai-inspector-hidden` et `cyai-members-hidden` ne sont plus lues.
- **Paramètres** : quand `state.view === 'settings'`, `.app` reçoit `settings-open` ; le rail, les salons, les membres
  et l’en-tête sont masqués, la navigation des paramètres prend l’allure de la liste des salons (compacte, alignée à
  droite d’un panneau), le contenu occupe le reste. `#settings-close` (✕ / Échap) rappelle `showView()` sur la dernière
  vue qui n’était pas les paramètres. Échap est ignoré quand un dialogue ou un menu contextuel est ouvert.
- Second retour annoté (archive CyAnnota) : trop de place perdue à gauche des paramètres. La navigation est désormais
  une colonne de 220 à 260 px collée au bord gauche, boutons pleine largeur (cette partie a été corrigée dans
  `styles.css` entre deux de mes passages, avec ses commentaires ; je l’ai conservée telle quelle), et ✕ ÉCHAP est en
  haut à gauche, au-dessus de « PARAMÈTRES », comme placé sur l’annotation.

### Méthodes en graphe, catégories, messages privés (0.2.9)

Demandes de l’utilisateur après essai de la 0.2.8 : Membres et Détails au même endroit ; la bibliothèque en grand avec
des catégories ; le logo comme les MP de Discord ; le nom du projet vers la vue d’ensemble ; un éditeur de méthode /
skill nodal, utilisable par n’importe quelle IA, éditable par une IA, exportable et importable avec avertissements.

**Méthodes** (`cyai/methods.py`, réécrit). Une tâche a un `executor` : `profile` (profil de la bibliothèque),
`any` (l’IA choisie à l’application : `method_apply` reçoit `connector`/`model` et refuse sans eux), `connector`
(connecteur et modèle fixés). `helpers` : profils appelables pendant la tâche, fusionnés par
`specialists.definition_for_step` avec ceux du profil (6 au plus) — une tâche sans profil peut donc appeler un agent.
`preprompt` précède chaque consigne ; `requirements` : `software` (cherché par `shutil.which` ou au chemin donné, donc
un logiciel installé hors du PATH donne un faux avertissement, dit comme tel), `plugin`, `connector`, `note`.
`position` {x, y} par tâche pour l’éditeur. L’ordre est un tri topologique stable ; une boucle est refusée avec le
même message qu’avant (« se pilote sur le board »). Une tâche sans consigne s’enregistre (brouillon) mais ne
s’applique pas. `check()` donne les avertissements de la machine, sans jamais bloquer ; `method_apply` reste ce qui
refuse. Export `cyai-method` v1 : la méthode et `current_definition` des profils utilisés ; import : profil retrouvé
par identifiant, puis par nom, puis recréé depuis l’export (sans ses agents appelables, et sans les plugins absents,
chacun signalé), sinon tâche confiée à n’importe quelle IA. Un export plus récent est refusé. Nouvelles actions MCP,
toutes globales : `method_get`, `method_check`, `method_export` (lecture), `method_import` (écriture).

**Éditeur** (`cyai/web/method-editor.js`, vue `method` en plein écran). Canevas avec monde transformé (translation +
zoom), nœuds positionnés par le DOM — la politique de sécurité de la page ignore les attributs `style` écrits en HTML,
d’où un premier rendu avec tous les nœuds empilés, corrigé par `placeNodes()`. Fils en courbes de Bézier dans un SVG
de 20 000 px décalé, pour rester cliquables partout. Glisser une sortie vers un nœud ajoute une dépendance ;
`wouldLoop()` refuse une boucle avant de la tracer. Inspecteur : tâche ou méthode. Quitter avec des modifications non
enregistrées demande confirmation ; Échap dans un champ ne fait que quitter le champ.

**Bibliothèque** : vue `agents` en plein écran (même mise en page que les paramètres), navigation par catégorie,
glisser-déposer d’une fiche sur une catégorie. `agent_profiles.category` n’entre pas dans la définition : ranger ne
crée pas de révision (`agent_profile_category`, action MCP globale).

**Messages privés** : `agent_direct_message` crée un espace libre isolé (`Service.free_workspace()`, partagé avec
`create_free_conversation`) et y ouvre une conversation du profil. Domaine MCP `conversations` et non `teams` : un
test garantit que toute action `teams` est de portée projet ou globale, et un MP n’est ni l’un ni l’autre.

**Membres / Détails** : `#member-list` est désormais dans `main`, à côté de `#workspace` et `#page`, avec la largeur de
l’inspecteur (302 px, 340 au-delà de 1550 px, 250 sous 1100 px) : même rectangle mesuré pour les deux panneaux.

Contrats de test modifiés volontairement : une dépendance vers une tâche placée plus loin est acceptée (seule la boucle
est refusée) ; `method_from_mission` sans profil garde le connecteur au lieu de refuser ; `--verify-ui` `free_chats`
cherche le bouton ＋ des messages privés, et un contrôle `method_editor` est ajouté.

Validations : `tests/test_library.py` (8), `tests/test_method_graph.py` (13), `test_methods.py` adapté. Suite complète :
**314 tests**, toujours les 2 seuls échecs préexistants. Parcours navigateur sur configuration temporaire : panneaux
Membres et Détails au même rectangle (1122, 48, 302×873) ; Accueil en messages privés et MP avec un agent ; catégorie
créée puis fiche glissée dessus ; nom du projet → vue d’ensemble ; éditeur : rendu, fil tracé au pointeur, boucle
refusée, changement d’exécutant, enregistrement, export puis import.

### Une méthode comme skill (0.2.10)

Suite de la 0.2.9, faite alors qu’il restait peu de quota. `method_as_skill {id, project_id | conversation_id}` écrit la
méthode en recette Markdown (`methods.skill_text` : cadre commun, tâches dans l’ordre avec leurs dépendances et
livrables, prérequis) et l’ajoute aux skills du projet ou de la conversation via `agent_settings`, avec
`source_id = "method:<id>"` : la réajouter remplace l’ancienne version. N’importe quelle IA de ce périmètre la reçoit
dans son contexte ; rien n’est lancé. Bouton « Comme skill… » sur chaque méthode de la bibliothèque (choix du projet) ;
action MCP `method_as_skill` (portée vérifiée par `project_id` / `conversation_id`). Test :
`test_a_method_becomes_a_skill_of_a_project_and_reaches_the_context`. Vérifié dans le navigateur sur configuration
temporaire : dialogue, envoi, skill « Méthode · Vaisseau 3D » présent dans les réglages du projet.

**Pour reprendre** : 1) essayer une méthode avec de vrais fournisseurs ; 2) étape 2 de l’interface ci-dessous.

### Étape 2 de l’interface, première partie (0.2.11)

**Messages groupés** : `messageAuthor(m)` (channels.js) donne la clé, le nom, l’initiale et le rôle de l’auteur — le
membre de l’équipe si la conversation porte un `member_id`, le profil si elle porte un `profile_id`, sinon le
connecteur ; `messageGrouped()` groupe un message avec le précédent si même auteur, même modèle et moins de 7 minutes.
Le gabarit de `renderMessages` (app.js) ne change que l’en-tête et les classes `role-*` / `grouped`.

**Salons créés** : `cyai/spaces.py`, table `project_spaces` (projet, type, nom, position, `data` JSON). Type
`whiteboard` : `{notes: [{id, x, y, text, color}], links: [{from, to, label}]}`, validé (couleurs d’une liste, liens
entre notes existantes et distinctes, 300 notes, 600 liens). `whiteboard_save` prend `base` = le `updated_at` lu : une
version différente est refusée (« modifié ailleurs »), l’interface l’affiche et propose de recharger. Listés par
`project_channels` sous la catégorie *Espaces* (champ `space`). Actions MCP de portée projet : `space_create`,
`space_get`, `space_rename`, `space_delete`, `whiteboard_save`. Sauvegarde : `project_spaces` rejoint les tables de
la sauvegarde v2 ; une sauvegarde v2 plus ancienne qui ne la contient pas est acceptée (table simplement vide).

**Interface** : `cyai/web/spaces.js`, vue `space`. Même mécanique de canevas que l’éditeur de méthodes (positions par
le DOM, SVG décalé), notes éditables sur place, autosauvegarde à 700 ms, suivi des changements extérieurs toutes les
3 s quand rien n’est en cours d’édition.

Contrat de test modifié volontairement : la liste des catégories de salons inclut *Espaces*.

Validations : `tests/test_spaces.py` (6). Navigateur (configuration temporaire) : création du salon par le dialogue,
notes ajoutées au double-clic et enregistrées, conflit simulé par une écriture « IA » refusant la sauvegarde suivante
puis rechargement, lien créé puis supprimé au clavier ; groupement et auteur « Nadia · lead backend » vérifiés par
script. Le panneau du navigateur étant masqué pendant ce test, `elementFromPoint` y renvoyait `null` : la fin du geste
de liaison a été simulée en fournissant la note cible, le reste du chemin est le code réel.

### Étape 2 de l’interface, suite : carte dans le fil et graphes (0.2.12)

**Carte dans le fil** : `taskBannerHTML()` (channels.js) lit `task_get` pour la conversation qui porte un `task_id`,
avec un cache de 5 s, et `renderMessages` la place en tête du fil — y compris quand le fil est encore vide, cas
courant d’un agent qui vient d’être lancé.

**Graphes** : type `graph` de `project_spaces`, dont seul `source` est stocké (`tasks` ou `team`). `graph_data` calcule
les nœuds et arêtes à chaque lecture — dépendances et parent pour les tâches, `manager_id` pour l’équipe. Vue en
colonnes par profondeur (spaces.js, `graphLayout`), lecture seule, rafraîchie toutes les 5 s si elle change ; un nœud
porte `data-task-open` ou `data-shell-member`, donc réutilise les dialogues existants.

Bugs trouvés pendant la vérification et corrigés :
- lister les salons plantait dès qu’un graphe existait (`channels.TYPES` ignorait `graph`) : ajouté, et une icône par
  défaut évite qu’un futur type fasse de même ; le test du graphe vérifie maintenant son apparition dans la liste ;
- ouvrir une carte depuis un graphe ou un fil échouait si le board du projet n’avait jamais été affiché
  (`boardState.data` vide) : le gestionnaire le charge désormais au besoin.

Validations : `tests/test_spaces.py` (8). Navigateur : création des deux graphes par le dialogue, nœuds et arêtes
attendus (organigramme Claire → Nadia → Tom, Iris à part), clic sur un membre et sur une carte, carte en tête d’une vraie
conversation liée à une tâche, ouverture depuis la carte.

### Outils de conversation (0.2.13)

Interprétation retenue faute de précision de l’utilisateur (« des outils pour les conversations ») : la barre d’actions
de Discord au survol d’un message. Les actions existantes (proposer en mémoire, branche, contexte) y deviennent des
icônes ; nouvelles : Répondre (citation Markdown `> auteur :` de 600 caractères au plus en tête de la saisie), Copier
(presse-papiers, avec repli `execCommand` si la fenêtre de bureau refuse l’API), Épingler (`save_memory` catégorie
« Épinglé », non validée, liée au message — donc visible dans le salon épinglés et non transmise aux agents avant
validation). Classe `in-context` sur un message joint au contexte. Vérifié dans le navigateur ; aucun code serveur
touché.

### Console de plugin (0.2.14)

L’utilisateur a répondu « continue » à la proposition : faite comme proposée. Type `plugin` de `project_spaces`, données
`{plugin_id, calls}`. Création : `plugins.plugin(id, projet)` doit accepter le plugin (présent, activé, pas désactivé
pour le projet) et il doit déclarer au moins un `read_tools`. `plugin_console` renvoie le catalogue de lecture
(`plugins.catalog`, déjà filtré sur `read_tools`) ou la raison pour laquelle il est indisponible, plus l’historique.
`plugin_console_call` passe par `plugins.read`, qui refuse tout outil non déclaré en lecture ; l’appel est journalisé
dans le salon (50 derniers, résultat tronqué à 20 000 caractères), réussite comme refus. Écriture MCP de portée projet,
puisque l’historique est modifié.

Validations : 2 tests (`test_spaces.py`, 10 au total), dont le refus d’un outil qui agit sans qu’il atteigne le
plugin. Navigateur, avec un **vrai processus MCP stdio** de test (`fake_mcp.py` dans le dossier de travail temporaire,
inscrit seulement dans la configuration temporaire) : création par le dialogue, seul l’outil de lecture proposé,
formulaire tiré du schéma (texte, entier), appel réel et réponse dans l’historique.

### Automate de délégation (0.2.15)

C’était le premier point « Reste à faire ». `cyai/autopilot.py`, état dans `teams.autopilot` (JSON : `enabled`,
`budget`, `max_parallel`, `reviews` {rapport → mission}, `stopped`, `since`, `launched`).

- `plan()` : lecture seule (réconcilie d’abord). Lançables : `ready`/`to_correct`, responsable actif, dépendances
  terminées, connecteur activé, pas d’exécution en cours, pas de `stalled()` — une carte bloquée va dans « en attente
  de vous » avec la raison, jamais relancée. Relectures : cartes `in_review` dont le dernier rapport n’a pas encore
  été envoyé, relues par le premier `eligible_reviewers` actif au connecteur activé ; sinon « revue à faire par vous ».
  Capacité = `max_parallel` − exécutions en cours − relectures en cours.
- `step()` : lance puis fait relire, dans la capacité (et le budget en mode automatique). Une relecture est une mission
  dans la conversation du relecteur liée à la carte, `request_key = review:<rapport>`, dont la consigne donne les
  identifiants pour `task_accept` / `task_correction`.
- Mode automatique : `tick()` toutes les 20 s dans un fil par service, démarré à l’activation. Arrêts : exécution
  échouée ou interrompue depuis l’activation, budget épuisé, plus rien à faire ni en cours. `stop_after_restart()` au
  démarrage du service : un pilote ne reprend jamais seul.
- MCP : seul `team_autopilot_plan` (lecture). `team_autopilot_step` et `team_autopilot_set` ne sont pas exposés et
  figurent dans `USER_ONLY` : lancer engage des dépenses.
  Contrat de test modifié volontairement : la liste figée des actions du domaine `tasks` inclut `team_autopilot_plan`
  (de portée projet, comme les autres).

Le texte d’aide du board, qui annonçait encore les agents « au lot 2 », est remplacé.

Validations : `tests/test_autopilot.py` (7) avec connecteurs simulés — plan sans lancement, lancement puis une seule
relecture par le supérieur, relecture sans décision qui laisse la carte en revue, capacité, budget, arrêt sur échec,
pas de reprise après redémarrage, pilote hors de portée des agents. Navigateur sur configuration temporaire **sans
aucun connecteur activé** (vérifié avant) : barre, dialogues, activation, arrêt automatique « plus rien ne peut
avancer », arrêt manuel. **Aucun agent réel n’a été lancé** : l’automate n’a jamais tourné sur un vrai fournisseur.

### Propositions spontanées (0.2.16)

Second point « Reste à faire ». Choix retenu, faute de décision explicite : **à la demande, désactivé par défaut**.
Option `invite_proposals` de l’état de l’automate (`team_autopilot_options`, réservé à l’utilisateur). Cochée, la
consigne de relecture (`autopilot._request_review`) ajoute l’invitation à `improvement_propose` avec tous les
identifiants nécessaires (relecteur, profil de l’agent, carte, rapport). La règle existante est respectée : seul un chef
ou un lead propose, jamais l’agent sur son propre travail. Test : la proposition formée exactement selon la consigne est
acceptée par `learning.create_proposal`. Case vérifiée dans le navigateur.

### Les deux problèmes anciens, corrigés (0.2.17)

D’abord signalés en tâches séparées, puis repris ici, faute d’autre travail en cours (aucune autre session active, fichiers
inchangés depuis des jours, vérifié avant d’y toucher).

1. **Les 2 tests en échec depuis le début** (`test_intelligence…compaction…`, `test_recovery_defaults…native_resume…`).
   Cause : `project_memory.project_foundation`, sans présentation configurée, prend un extrait de la première demande
   du projet ; `context.build_context` l’envoyait toujours, y compris à la conversation même qui la contient, quand sa
   session native est reprise (`last_seq`) ou qu’elle a été compactée (`summary_seq`). Les tests avaient raison
   (tokens renvoyés pour rien). Correctif étroit : dans ces deux cas seulement, et seulement si l’extrait vient de
   **cette** conversation, il est remplacé par une mention (« déjà présente dans la session native reprise / le résumé
   de reprise »). Aucune assertion modifiée ; test ajouté (`test_project_memory`) : envoyé normalement, pas en reprise,
   toujours reçu par une autre conversation.
2. **`analytics.js`** : trois lignes de premier niveau utilisaient `$` avant que `app.js` ne le définisse ; erreur à
   chaque chargement, écouteurs jamais branchés. L’activation telle quelle aurait appelé `list_models` à chaque focus
   du champ modèle, or cette action peut démarrer le connecteur et **réécrit config.json**. Corrigé avec des appels
   DOM directs et une demande au plus une fois par connecteur et par session, seulement si le connecteur est activé
   et son catalogue absent. Vérifié : `autocomplete="off"` appliqué, plus d’erreur, aucun appel pour un connecteur
   désactivé.

**Suite complète : 335 tests, aucun échec** — les « 2 échecs préexistants » mentionnés partout plus haut n’existent plus.

### Relecture critique et essai de mise à jour (0.2.18)

- **Concurrence de l’automate** (un pas manuel pendant un tour automatique) : sans risque. `Engine.create` est
  idempotent sur `request_key` (`review:<rapport>` renvoie la mission existante) et refuse une seconde mission active
  dans la même conversation, sous verrou ; deux lancements d’une même carte se heurtent donc à cette règle.
- **Budget** : il comptait déjà exécutions et relectures, mais l’interface ne parlait que de « lancements » ; précisé
  (barre, dialogue, message d’activation), puisque chaque relecture consomme aussi des crédits.
- **Mise à jour sur de vraies données** : la base réelle (`<dossier-données-CyAI>\cyai.sqlite3`, 31,5 Mo) a été copiée en
  **lecture seule** par l’API de sauvegarde SQLite dans le dossier temporaire (fichier réel inchangé, date vérifiée),
  puis ouverte par la version courante avec une copie de la configuration et des connecteurs simulés : colonnes et
  table ajoutées, 4 projets, salons, plans de l’automate et 4 contextes de conversation construits sans erreur. La
  copie a ensuite été supprimée.
- Risque noté, non traité : la consigne de relecture recopie le compte rendu d’un agent dans le contexte d’un autre.
  Un compte rendu malveillant ou mal formé pourrait y glisser des consignes ; les écritures du relecteur restent
  soumises aux autorisations de sa conversation, et la consigne présente le rapport comme une donnée à vérifier.

### Étape 2 de l’interface, suite (non commencée)

Salon *plugin* (voir ci-dessus). La table
`project_spaces` accueille les nouveaux types : ajouter le type dans `spaces.TYPES`, sa validation et sa vue.

### Ce qui reste ouvert

Rien n’empêche un agent de mal utiliser ses spécialistes ou ses outils : CyAI borne, enregistre et rend lisible, il
ne juge pas la qualité. Aucune de ces capacités n’a encore été éprouvée avec un vrai fournisseur ni un vrai serveur MCP
Blender : les tests utilisent des connecteurs et un plugin simulés.

### Reste à faire

1. ~~Automate de délégation~~ : fait en 0.2.15 (voir plus haut) ; reste à l’éprouver sur un vrai projet.
2. ~~Propositions spontanées~~ : faites à la demande en 0.2.16 ; ancien texte : aujourd’hui un agent peut créer une proposition par le MCP, mais rien ne l’y invite.
   À décider après usage réel : est-ce souhaitable, ou est-ce que cela produirait du bruit ?

**Prochaine action concrète** : installer la 0.2.5 et essayer le parcours complet avec un vrai fournisseur sur un
projet d’essai — composer une équipe, laisser le chef découper, lancer un membre, examiner son compte rendu, l’évaluer.
C’est cet usage qui dira si un automate de délégation vaut la peine, et si les propositions spontanées seraient utiles
ou bruyantes. Tout le reste est construit et testé ; ce qui manque est une décision produit, pas du code.

**Paquets 0.2.3 à 0.2.9**, construits de la même façon : construits après la fin de la copie PyInstaller, 346 fichiers, manifeste identique au zip,
`teams.js` et `board.js` présents et référencés par `index.html`, aucune donnée utilisateur embarquée, SHA-256
recalculé conforme. Application de bureau revérifiée après l’incrément : 22 contrôles au vert, dont `board_tab`.
**Paquet 0.2.8** (169,4 Mo) : 348 fichiers (`channels.js` en plus), manifeste identique au zip, `index.html` référence
`channels.js` et ne contient plus la barre d’onglets, aucune donnée utilisateur, SHA-256 conforme. Application de bureau
empaquetée revérifiée sur configuration temporaire : 23 contrôles au vert, dont `discord_shell`, `tabs` (nouveau contrat)
et `multiple_windows`. Rien n’a été testé avec un vrai fournisseur.
**Paquet 0.2.9** (169,4 Mo) : 349 fichiers (`method-editor.js` en plus), manifeste identique au zip, `index.html`
référence `method-editor.js`, aucune donnée utilisateur, SHA-256 conforme. Application empaquetée revérifiée sur
configuration temporaire : 24 contrôles au vert, dont `method_editor`, `free_chats` (nouveau contrat) et `discord_shell`.
**Paquet 0.2.10** (169,4 Mo) : 349 fichiers, manifeste identique au zip, bouton « Comme skill… » présent, aucune donnée
utilisateur, SHA-256 conforme ; 24 contrôles de l’application empaquetée au vert. Le numéro « 0.2.10 » est sans risque :
l’installateur enregistre explicitement la version courante et la précédente, il ne trie pas les versions.
**Paquet 0.2.11** (169,4 Mo) : 350 fichiers (`spaces.js` en plus), module `cyai.spaces` embarqué, manifeste identique
au zip, aucune donnée utilisateur, SHA-256 conforme ; 25 contrôles de l’application empaquetée au vert, dont
`whiteboard`.
**Paquet 0.2.12** (169,4 Mo) : 350 fichiers, manifeste identique au zip, code des graphes présent, aucune donnée
utilisateur, SHA-256 conforme ; 25 contrôles au vert (`whiteboard` vérifie aussi `renderGraphSpace` et `taskBannerHTML`).
**Paquet 0.2.13** (169,4 Mo) : 350 fichiers, barre d’actions des messages présente, aucune donnée utilisateur, SHA-256
conforme ; 25 contrôles au vert.
**Paquet 0.2.14** (169,4 Mo) : 350 fichiers, console de plugin présente, ni donnée utilisateur ni plugin de test
embarqué, SHA-256 conforme ; 25 contrôles au vert (`whiteboard` vérifie aussi `renderPluginSpace`).
**Paquet 0.2.15** (169,4 Mo) : 350 fichiers, module `cyai.autopilot` embarqué, barre de l’automate présente, aucune
donnée utilisateur, SHA-256 conforme ; 25 contrôles au vert, dont `board_tab`.
**Paquet 0.2.16** (169,4 Mo) : 350 fichiers, case des propositions présente, aucune donnée utilisateur, SHA-256
conforme ; 25 contrôles au vert.
**Paquet 0.2.17** (169,4 Mo) : 350 fichiers, correctif de `analytics.js` présent, aucune donnée utilisateur, SHA-256
conforme ; 25 contrôles au vert.
**Paquet 0.2.18** (169,4 Mo) : 350 fichiers, libellés du budget présents, aucune donnée utilisateur, SHA-256 conforme ;
25 contrôles au vert ; 335 tests, aucun échec.


## Éditeur de méthode avancé (demande « Éditeur de methode.cymd », 19 septembre 2026)

Demande de l’utilisateur (note CyAnnota, capture de l’éditeur 0.2.18) : clic droit pour ajouter des tâches ; des
méthodes dans les tâches, comme des fonctions ; plusieurs entrées et sorties « splittables » ; ouvrir la consigne en
grand avec une IA pour l’écrire ; images et fichiers dans la consigne ; une entrée « contexte global » déclinée
(complet, simplifié, spécial) et distribuée aux agents qui en ont besoin ; description et mode d’emploi de la méthode
pour l’IA qui l’applique ; méthodes préférées des agents, avec une note MD que l’agent écrit pour lui-même,
consultable depuis la méthode et depuis l’agent ; logiciels requis avec chemin d’installation, signalés à l’import et
dans la fiche de l’agent ; tests enregistrés avec la méthode, notés par vous ou par une IA, affinage par une IA
(boucle avec limite et accord) ; vérification de compréhension par le modèle exécutant, rapport lu par un meilleur
modèle qui affine la consigne pour ce modèle précis ; propositions d’amélioration pendant l’usage, examinées par le
meilleur modèle, avec discussion avec l’IA qui a proposé.

Découpage en cinq lots, chacun testé et empaqueté :

| Lot | Contenu | État |
| --- | --- | --- |
| 1 · Graphe | broches nommées (texte, contexte, fichier), entrées/sorties de méthode, tâches « à entrées seules », sections « ### Sortie : nom », sous-méthodes dépliées à l’application, clic droit, versions | **Fait en 0.2.19** |
| 2 · Consignes | éditeur de consigne en grand, images et fichiers joints aux tâches, assistant IA de rédaction (conversation réelle), préparation des contextes par une IA à l’application | **Fait en 0.2.20** |
| 3 · Agents et logiciels | méthodes préférées / imposées d’un profil, note MD de l’agent par méthode, logiciels avec chemin sur cette machine, marque dans la fiche de l’agent | **Fait en 0.2.21** |
| 4 · Tests et affinage | cas de test enregistrés, exécution, note (vous ou IA), vérification de compréhension, affinage par une IA, adaptations par modèle, boucle bornée avec accord | **Fait en 0.2.22** |
| 5 · Propositions en usage | propositions des agents pendant les chaînes, examen par le meilleur modèle, discussion avec l’auteur, adoption générale ou par modèle | **Fait en 0.2.23** |

### Lot 1 · ce qui est construit (0.2.19)

- `cyai/methods.py` : broches `inputs`/`outputs` par tâche (`source: {step, port}` sur chaque entrée, `@entrees`
  pour une entrée de méthode), `receives` (`inputs` par défaut pour une tâche à broches, `chain` pour les anciennes),
  entrées de méthode (`objectif` toujours présent et requis, `prepare`), sorties de méthode, `usage`, `layout`,
  nœuds `kind: "method"` (ports recopiés de la sous-méthode, contrôle d’inclusion et de profondeur ≤ 4),
  `_expand` qui déplie la méthode en tâches réelles, `_flat_instruction` (entrées statiques écrites, entrées de tâche
  résolues au lancement), `extract_section`, `wired_inputs`, versions (`method_revisions`, `method_history`,
  `method_restore`), export v2 avec `methods` (sous-méthodes, les plus profondes d’abord) et v1 conservé quand rien
  de nouveau n’est utilisé.
- `cyai/engine.py` : étape `isolated` (aucun message de la chaîne), `inputs` résolus au démarrage de l’étape depuis le
  résultat des étapes dont elle dépend, validation `files_exist`.
- Message d’ouverture d’une chaîne de méthode : nom, objectif et liste des tâches seulement (il recopiait toutes les
  consignes ; dans un projet neuf, il devenait la « demande initiale » envoyée à chaque tâche, contextes compris).
- `cyai/web/method-editor.js` réécrit : nœuds Entrées/Sorties, broches, fils colorés, dépôt sur un nœud qui crée
  l’entrée, menu clic droit, inspecteurs par type de nœud, versions, fenêtre « Appliquer » avec un champ par entrée.
  Collisions de noms globaux évitées (`refresh` et `pinsHTML` existaient déjà dans l’interface).
- `channels.js` : Échap ferme le menu clic droit sans quitter l’éditeur.
- Tests : `tests/test_method_ports.py` (13), connecteur de test capable de répondre selon le prompt (`answer`).
  Suite complète : 348 tests, aucun échec (2 ignorés).
- Vérifié dans le navigateur (configuration temporaire) : graphe, menus, branchement à la souris, dépôt sur un nœud,
  sous-méthode, enregistrement et relecture.

### Lot 2 · ce qui est construit (0.2.20)

- `cyai/methods.py` : table `method_assets` (fichiers dans `<données>/method-assets/<id>`), `upload_asset` (route
  `/api/upload?method_id=`), `locate_asset` (aperçu `/method-asset/<id>`, mêmes contrôles de cookie et d’hôte que
  `/media/`), `list_assets`, `delete_asset` (refus tant qu’une tâche l’utilise), `attachments` par tâche (8 au plus),
  copie dans les fichiers de la conversation de la chaîne à l’application (`_attach`) et `file_ids` par étape ;
  export des fichiers en base64 (15 Mo au total, le reste nommé dans `skipped_assets`), import qui recrée les fichiers
  après la méthode puis rebranche les tâches. Atelier : `workshop` (conversation libre « Atelier · nom », colonne
  `workshop`), `workshop_send` (brouillon JSON joint seulement s’il a changé, repéré par une empreinte ; proposition
  attendue en bloc ```consigne), `prepare_inputs` / `prepared_inputs` (sections « ### Entrée : nom »).
  `extract_section` lit aussi les titres « Entrée » et tolère « (contexte) — précision » après le nom.
- `cyai/engine.py` : `file_ids` par étape, vérifiés à la création (même conversation) et utilisés à la place de ceux
  de la mission pour cette étape.
- `cyai/web/method-writer.js` (nouveau, autorisé par `server.py` et chargé par `index.html`) : surimpression de
  l’éditeur, texte, fichiers (bouton, glisser-déposer, réutilisation), atelier (connecteur, modèle, demandes rapides,
  réponse en direct, adoption / annulation), lien vers la conversation. `method-editor.js` : boutons « ⤢ », menu,
  double-clic, préparation des entrées dans « Appliquer ». Échap ferme l’éditeur de consigne sans quitter la méthode.
- Tests : `tests/test_method_writer.py` (8). Suite complète : 356 tests, aucun échec (2 ignorés).
- Vérifié dans le navigateur (configuration temporaire, sans connecteur actif) : ouverture, fichiers texte et image
  téléversés et prévisualisés, rendu d’une proposition simulée, adoption, enregistrement avec les pièces jointes.
  L’atelier n’a pas été essayé avec une vraie IA.

### Lot 3 · ce qui est construit (0.2.21)

- `cyai/method_agents.py` (nouveau, branché dans la chaîne d’actions du service) : table `profile_methods`
  (profil × méthode : `mode` preferred/always/vide, `note`, `note_author` user/agent, dates ; suppression en cascade avec
  le profil ou la méthode), `set_link`, `save_note`, `profile_methods`, `method_agents`, `summary` (fiches de la
  bibliothèque), `preferences` (tri de `method_list`), `note_for`, `context_block` ; logiciels : `software_status`
  (chemin de cette machine d’abord, puis chemin ou commande de la méthode), `set_software_path` (chemin absolu qui
  existe, écrit dans `config.json` sous `software_paths`), `method_software`.
- `methods.py` : avertissement logiciel avec indication d’installation ; `method_list` accepte `profile_id` ;
  à l’application, chaque tâche reçoit les logiciels trouvés de sa méthode (« LocalMesh → chemin ») et, si elle est
  tenue par un profil, sa note d’usage de cette méthode.
- `context.py` : bloc « Méthodes de votre profil » pour les conversations de membre et de profil appelé directement.
- `app_mcp.py` : `profile_methods`, `method_agents` (lecture), `profile_method_set`, `method_note_save` (écriture
  globale ; depuis une conversation d’agent, seulement pour son propre profil, signée agent) ; `software_path_set`
  réservé à l’utilisateur.
- Interface : bouton « Méthodes » et lignes « Méthodes / Nécessite » sur les fiches (`teams.js`), fenêtre des méthodes
  d’un agent et notes (`methods.js`), section « Agents » et « Indiquer le chemin… » dans l’éditeur.
- Tests : `tests/test_method_agents.py` (5). Suite complète : 361 tests, aucun échec (2 ignorés).
- Vérifié dans le navigateur (configuration temporaire) : lien « à utiliser », fiche marquée « Nécessite LocalMesh ⚠ »,
  note enregistrée et affichée en Markdown, section Agents de la méthode, chemin refusé quand rien n’existe
  (Notepad est absent de cette machine LTSC) puis accepté, avertissement levé.

### Lot 4 · ce qui est construit (0.2.22)

- `methods.py` : `apply_method` découpé en `prepare_chain` (tâches dépliées et consigne exacte de chacune, mode
  `lenient` pour montrer une consigne sans toutes les entrées) et `create_chain` ; `validate_body` (ce que
  l’enregistrement stockerait, sans l’écrire) ; `adaptations` par tâche (`connecteur:modèle` → texte, 12 au plus,
  8 000 caractères) ajoutées par `adaptation_for` quand ce modèle exécute la tâche.
- `cyai/method_lab.py` (nouveau) : tables `method_tests`, `method_runs` (kinds test, evaluation, check, refine, improve ;
  état réconcilié à la lecture depuis la mission, résultat lu une fois), `method_loops`. Tests (`save_test`,
  `run_test` dans le projet « Tests de méthodes » sous `<données>/method-tests`), `rate`, `evaluate` (mission isolée,
  JSON 1–5), `check_understanding` (dans l’atelier, fichiers joints, entrées d’autres tâches nommées), `refine_for_model`
  (mission de trois étapes isolées reliées par des entrées branchées : questions du fort, réponses du vérifié, précisions
  finales), `set_adaptation`, `improve` (méthode complète en JSON, validée à blanc, changements résumés), `adopt`
  (fichiers, précisions et positions repris par clé), boucle (`start_loop` avec confirmation, 1–10 tours, note visée ;
  `tick` en arrière-plan toutes les 3 s ; arrêt au redémarrage).
- `app_mcp.py` : lecture `method_tests`, `method_runs`, écriture `method_test_save` ; tout ce qui dépense ou décide est
  dans `USER_ONLY`.
- Interface : `cyai/web/method-lab.js` (nouveau) — panneau « Tests & affinage », notes, évaluation, propositions,
  boucle ; section « Compréhension et précisions par modèle » dans l’inspecteur d’une tâche.
- Tests : `tests/test_method_lab.py` (11), dont le défaut trouvé en l’écrivant : l’affinage renvoyait au modèle la
  consigne encore entourée du cadre de vérification. Suite complète : 372 tests, aucun échec (2 ignorés).
- Vérifié dans le navigateur (sans connecteur actif) : panneau, création d’un test, section de l’inspecteur, précisions
  enregistrées, fenêtre de vérification. **Aucune exécution réelle** : les lancements, évaluations et boucles sont
  couverts par les tests avec des connecteurs simulés.

### Lot 5 · ce qui est construit (0.2.23)

- `methods.py` : `options` d’une méthode (`proposals`), versionnées et exportées ; `PROPOSAL_INVITE` ajouté aux consignes
  des tâches d’une méthode qui le demande ; `extract_section` coupe toute section « Proposition d’amélioration » avant de
  transmettre une entrée ou une sortie ; `create_chain` inscrit la chaîne dans `method_chains` ; `get_method` rend
  `proposals_new`.
- `method_lab.py` : `harvest` (une fois par chaîne terminée, `UNIQUE(step_id)`), `proposals`, `review` (un appel, ou trois
  avec l’auteur : questions, réponses branchées, verdict ; sections Verdict / Consigne / Précisions), `adopt_proposal`
  (consigne ou précisions pour `connecteur:modèle` de l’auteur, sous-méthodes comprises), `dismiss_proposal`.
- `app_mcp.py` : `method_proposals` en lecture ; examiner, adopter, écarter dans `USER_ONLY` ; description de
  `method_save` complétée (`attachments`, `adaptations`, `options`).
- Interface : case dans les propriétés de la méthode, compteur sur « 🧪 Tests & affinage », section « Propositions des
  agents » (examen, discussion, adoption, écarter).
- Tests : `tests/test_method_proposals.py` (5). Suite complète : 377 tests, aucun échec (2 ignorés).
- Vérifié dans le navigateur avec une proposition de démonstration insérée dans la base temporaire : compteur, liste,
  fenêtre d’examen, « Écarter », option enregistrée avec la méthode.
- **Copie de la vraie base** (lecture seule par l’API de sauvegarde SQLite, fichier réel inchangé, copie supprimée) :
  8 nouvelles tables et 7 colonnes ajoutées, 5 contextes de conversation construits. La vraie base ne contient encore
  ni méthode ni profil d’agent : aucune donnée à convertir.

### Ce qui reste ouvert après les cinq lots

- **Rien de tout cela n’a tourné avec un vrai fournisseur** : les chaînes, l’atelier, les vérifications, les évaluations,
  les affinages, les propositions et la boucle sont couverts par des connecteurs simulés. Le premier usage réel dira si
  les modèles respectent bien les titres « ### Sortie : … », « ### Entrée : … » et « ### Proposition d’amélioration ».
- Les sections sont reconnues par leur titre : un modèle qui ne les écrit pas transmet sa réponse entière (et CyAI le
  dit dans l’entrée) ; une évaluation sans note lisible échoue au lieu d’inventer une note.
- La boucle adopte automatiquement les propositions ; l’accord est demandé au lancement et chaque tour reste une
  version. À éprouver avec un budget faible (1 ou 2 tours) avant de s’y fier.


- **Lot 2** : table `method_assets` (fichiers sous `données/method-assets`), téléversement par
  `/api/upload?method_id=`, `attachments` par tâche ; à l’application, copie dans les fichiers de la conversation de
  la chaîne et `file_ids` par étape (le moteur les passe au connecteur, images comprises). Éditeur de consigne en
  surimpression ; assistant = vraie conversation « Atelier · méthode » dans l’espace libre, la proposition arrive dans
  un bloc que l’on adopte d’un clic. Préparation des contextes à l’application par une mission courte qui lit le mode
  d’emploi et « comment préparer ».
- **Lot 3** : `methods` dans la définition d’un profil (`preferred`/`always`), table `method_notes`
  (profil × méthode, contenu MD, auteur agent ou vous), action MCP pour qu’un agent écrive sa propre note ; contexte
  des conversations de membres ; logiciels : chemin local par machine (`software_paths` dans la configuration),
  indiqué depuis l’avertissement, écrit dans la consigne ; fiche d’agent marquée des logiciels requis.
- **Lot 4** : `tests` enregistrés avec la méthode (entrées, attendu), exécution = application + lancement explicite,
  notes (vous ou IA), vérification de compréhension (mission qui ne fait pas la tâche et dit ce qu’elle a compris),
  affinage par un meilleur modèle en dialogue (étapes alternées), `adaptations` par connecteur/modèle ; boucle
  bornée (nombre de tours obligatoire, arrêt au score visé ou au redémarrage), chaque tour gardé comme version.
- **Lot 5** : lecture des sections « ### Proposition d’amélioration » dans les résultats des chaînes de méthode
  (réconciliation à la lecture, comme l’automate) et action MCP ; examen par un meilleur modèle, discussion avec le
  modèle auteur (mission à étapes alternées), adoption générale ou comme adaptation de ce modèle.

**Paquet 0.2.19** (169,5 Mo) : 350 fichiers, manifeste identique au zip, nouvel éditeur présent, aucune donnée
utilisateur ni fichier de test, SHA-256 conforme ; application empaquetée revérifiée sur configuration temporaire :
tous les contrôles au vert, dont `method_editor` (nœuds Entrées/Sorties, broches, menu). 348 tests, aucun échec.
Rien n’a été lancé avec un vrai fournisseur.

**Paquet 0.2.20** (169,5 Mo) : 351 fichiers (`method-writer.js` en plus, référencé par `index.html`), manifeste
identique au zip, aucune donnée utilisateur ni fichier de test, SHA-256 conforme ; application empaquetée revérifiée
sur configuration temporaire : tous les contrôles au vert, dont `method_editor` (`writer`). 356 tests, aucun échec.

**Paquet 0.2.21** (169,5 Mo) : 351 fichiers, module `cyai.method_agents` embarqué, fenêtre des méthodes d’un agent
présente, aucune donnée utilisateur ni fichier de test, SHA-256 conforme ; application empaquetée revérifiée :
tous les contrôles au vert, dont `agent_library` (bouton « Méthodes » sur chaque fiche). 361 tests, aucun échec.

**Paquet 0.2.22** (169,5 Mo) : 352 fichiers (`method-lab.js` en plus, référencé par `index.html`), module
`cyai.method_lab` embarqué, aucune donnée utilisateur ni fichier de test, SHA-256 conforme ; application empaquetée
revérifiée : tous les contrôles au vert, dont `method_editor` (`lab`). 372 tests, aucun échec.

**Paquet 0.2.23** (169,6 Mo) : 352 fichiers, propositions présentes dans `method-lab.js`, aucune donnée utilisateur ni
fichier de test, SHA-256 conforme ; application empaquetée revérifiée : tous les contrôles au vert, dont
`method_editor` (`proposals`). 377 tests, aucun échec. Rien n’a été lancé avec un vrai fournisseur.


## Création de projet et assistant du projet (demande « CerationDeprojet.cymd », 0.2.24)

Demande : ne plus refuser un logo au-delà de 300 Ko (le réduire), choisir icône, catégorie et couleur dès la création
avec un aperçu, et une conversation « Projet » au-dessus des conversations — l’assistant qui met le projet en place
(reprise ou nouveau, présentation, équipe), avec des boutons de départ, mise en avant tant qu’on ne lui a pas parlé.

- `cyai/project_assistant.py` (nouveau) : `ensure` (conversation « Assistant du projet », `purpose='assistant'`, skill
  de conversation qui décrit son rôle et les actions MCP utiles), `find`, `fresh` (aucun message de l’utilisateur),
  action `project_assistant` (aussi au MCP, portée projet). Refusé pour une discussion libre.
- `service.py` : `create_project` accepte `color`, `icon`, `category` (catégorie créée si nouvelle ; projet retiré si
  l’apparence est invalide) et `assistant` ; les projets créés par l’application elle-même (discussions libres, tests
  de méthodes) n’ont pas d’assistant.
- `channels.py` : catégorie « Assistant » en tête ; l’entrée existe toujours (virtuelle tant que la conversation n’est
  pas créée), avec `fresh` et `exists` ; la conversation n’est pas répétée parmi les conversations.
- Interface : `workspace.js` (`resizeLogo` par canvas, 256 → 96 px, WebP puis PNG, ≤ 380 000 caractères ;
  `appearanceFieldsHTML`, aperçu `paintLogoPreview`), `app.js` (nouvelle fenêtre de création, ouverture de l’assistant
  une fois le projet chargé), `channels.js` (salon animé, premier écran et points de départ).
- Tests : `tests/test_project_assistant.py` (4) ; `test_channels` mis à jour (contrat). Suite complète : 381 tests,
  aucun échec (2 ignorés).
- Vérifié dans le navigateur (configuration temporaire) : image de 1 800 × 1 800 réduite en WebP de 84 Ko, aperçu à la
  bonne couleur, projet créé avec catégorie nouvelle et logo, assistant ouvert avec le nom du projet, point de départ
  qui remplit la saisie, ancien projet qui reçoit son assistant au premier clic. **L’assistant n’a pas été essayé avec
  une vraie IA.**

**Paquet 0.2.24** (169,6 Mo) : 352 fichiers, aucune donnée utilisateur ni fichier de test, SHA-256 conforme ;
application empaquetée revérifiée : tous les contrôles au vert, dont `project_setup` (nouveau).


## CyAnnota : collage d’images (note « Annota.md », 0.2.25)

Cause : dans CyAnnota 0.3.10, `loadImageFile` refuse toute image dès qu’une session d’intégration existe, alors que
`loadVideoFile` fait une exception pour `providerId === 'cyai'`. CyAI ouvre toujours CyAnnota en session d’intégration
(espace de travail ou média à reprendre) : coller, déposer ou choisir une image affichait « Le média lié à CyAI ne peut
pas être remplacé dans cette session ». Reproduit dans le navigateur par un collage simulé.

Correctif : même exception pour les images que pour les vidéos, dans le paquet livré
(`cyai/web/cyannota/assets/index-YXIovrHt.js`, fonction `zn`) et dans `cyannota/source.zip` (`app/page.tsx`, README
complété — l’AGPL impose que la source corresponde). Vérifié : l’image collée s’ouvre (« Image pasted from the
clipboard »). `tests/test_cyannota_bundle.py` garde ce comportement. Non modifié : le projet CyAnnota d’origine
(`C:\Projects\CyAnnota`), où la même correction est à faire.

**Paquet 0.2.25** (169,6 Mo) : 352 fichiers, correctif présent dans le paquet, aucune donnée utilisateur, SHA-256
conforme ; application empaquetée revérifiée : tous les contrôles au vert. 383 tests, aucun échec.


## Agents : bilan, curseurs, capacités des modèles (note « Agent.md », 0.2.26)

Demande : que les leads et surtout le chef notent les agents qu’ils encadrent, avec une note de projet sur leurs
capacités, pour les réaffecter, les remplacer ou les adapter ; que le chef règle des curseurs par projet et au moment
d’exécuter une tâche ; que les capacités de base des agents soient mieux renseignées selon le modèle, à partir de
plusieurs sources, toujours modifiables à la main, avec des ordres de préférence.

- `cyai/team_lead.py` (nouveau) : `member_assessments` (verdicts reliable/watch/reassign/adapt/replace, raisons,
  sources), autorité = chef, supérieurs de l’agent ou utilisateur (`_authority`) ; `scorecard` (faits par affectation
  + capacités du modèle + derniers bilans) ; `member_context` (dernier bilan pour l’agent ; faits de l’équipe encadrée
  pour chef et leads) branché dans `context.py` ; `reassign` (cartes ouvertes hors exécution, motif dans l’historique) ;
  `replace` (même rôle, responsable, subordonnés, cartes ouvertes ; ancien retiré) ; curseurs `CURSORS` (5 × 5 niveaux),
  `teams.cursors`, `tasks.cursors`, `effective` (projet < carte < lancement), `cursor_lines`, `effort_for`
  (Codex/Claude Code) branchés dans `team_runtime.execute_task`.
- `learning.save_evaluation` : un agent ne note plus que ceux qu’il encadre (ou le chef) — changement de règle voulu ;
  les tests existants notaient déjà par le lead.
- `cyai/model_capabilities.py` (nouveau) : estimation par domaine (vous > projets > benchmarks > estimation IA), succès
  technique à part, `overview` avec ordres suggérés, `set_order` (config `model_preferences.order`, conservé par
  l’action `model_preferences`), `estimate` (mission isolée dans une conversation libre « Estimation des modèles »,
  lecture à la réconciliation). `planning_preferences` lit l’ordre.
- MCP : `team_scorecard`, `member_assess`, `task_reassign`, `team_replace_member`, `team_cursors_set`,
  `task_cursors_set` (portée projet, écritures avec autorisation) ; `task_execute` accepte `cursors` ;
  `model_capabilities` en lecture ; `model_preference_order` et `model_estimate` réservés à l’utilisateur.
- Interface : `cyai/web/team-lead.js` (nouveau, autorisé par `server.py`) — bilan et curseurs dans l’onglet Équipe,
  curseurs de carte et de lancement (`board.js`), capacités et ordre dans Paramètres › Modèles (`analytics.js`),
  capacités sur les fiches et « Compléter depuis les capacités du modèle » (`teams.js`).
- Tests : `tests/test_team_lead.py` (9), `tests/test_model_capabilities.py` (5). Suite complète : 397 tests, aucun
  échec (2 ignorés). Vérifié dans le navigateur (configuration temporaire) : bilan enregistré, verdict affiché, curseurs
  du projet, curseurs dans la fenêtre d’une carte, ordre des modèles enregistré, détails d’un modèle, capacités sur les
  fiches. Copie de la vraie base : tables et colonnes ajoutées, salons et capacités construits, fichier réel intact.

**Paquet 0.2.26** (169,6 Mo) : 353 fichiers (`team-lead.js` en plus, référencé par `index.html`), aucune donnée
utilisateur, SHA-256 conforme ; application empaquetée revérifiée : tous les contrôles au vert, dont `team_lead`.
Rien n’a été lancé avec un vrai fournisseur.


## Voix dans les conversations, jalon 1 (0.2.27)

Demande : intégrer la voix (dictée et lecture) à partir d’un prompt rédigé sans connaître CyAI, corrigé d’abord pour
l’architecture réelle (voir la conversation : une conversation = une IA à la fois, envoi par le compositeur, pas de
salon multi-agents, flux interrogé toutes les 1,6 s). Condition posée par l’utilisateur : **l’activation de la voix est
toujours explicite**. Choix fait (« fais comme tu le sens ») : capter le micro dans le service, pas dans la fenêtre.

- `cyai/voice_audio.py` (nouveau) : micro et sortie par l’API multimédia de Windows (winmm, `ctypes`), aucune
  dépendance ajoutée ; périphériques choisis par nom, un périphérique disparu est une erreur (jamais un autre micro).
- `cyai/voice_backends.py` (nouveau) : `WhisperCpp` (whisper-cli, `-nt -np -otxt`, `-ng` hors GPU), `Piper` (processus
  gardé chargé, une ligne → un WAV dans un dossier temporaire), `WindowsVoices` (System.Speech par PowerShell,
  requêtes JSON ASCII). Processus arrêtés après 5 min sans usage (réglable).
- `cyai/voice_text.py` (nouveau) : `Segmenter` (phrases prêtes au fil du flux ; code, tableaux, liens, chemins, bloc de
  continuité, « Sortie : », propositions d’amélioration retirés ; limite de lecture), `planning_reply`,
  `usable_transcript` (filtre les sous-titres et étiquettes que Whisper invente sur du bruit).
- `cyai/voice.py` (nouveau) : `Voice` (état mémoire seulement, jamais restauré) — écoute de dictée ou de conversation,
  fin de phrase par silence après parole, transcription en fil séparé, transcript remis à la page ; lecture branchée sur
  `Store.listeners` (nouveau, appelé après chaque événement) : `delta` des connecteurs à flux propre, message final
  sinon, réponse orchestrateur sans JSON, annonces d’autorisation ; flux lus dans l’ordre (une voix à la fois), synthèse
  et lecture sur deux fils ; « Arrêter la voix » (génération incrémentée, missions en cours rendues muettes) distinct
  de l’annulation ; tour de parole et délais dans `_tick` (la base est lue avant de prendre le verrou de la voix).
  Voix : connecteur → générale → automatique (Piper puis Windows dans la langue de la dictée). Calcul automatique :
  processeur si le modèle local chargé est sur GPU. Catalogue figé (tailles, SHA-256, révisions, licences) ; installation
  par la file de `LocalModels` (visible dans Téléchargements), extraction sûre, fichier déjà présent et intact adopté.
- `store.py` : colonne `messages.input` ; `Store.message(..., input=)` ; `Store.listeners`. `engine.py` : le message
  utilisateur reprend `input="voice"` ; l’arrêt du moteur ferme le micro. `service.py` : `self.voice`, actions `voice_*`
  (aucune dans le MCP).
- Interface : `cyai/web/voice.js` (nouveau, autorisé par `server.py`) — 🎙 dans la saisie, « Conversation vocale »,
  « Lire les réponses », barre d’état (micro ouvert, niveau, transcription, lecture, autorisation), dictée en attente
  si la conversation est occupée, « Arrêter la voix », « Tout couper », extinction au changement de conversation,
  🔈 par message, marque « 🎙 voix », onglet Paramètres › Voix, fenêtre « La voix n’est pas encore prête ».
  `app.js` : envoi avec `input`, bloc de continuité masqué dans la vue en direct.
- `desktop.py` : contrôle `voice` de `--verify-ui`.
- Tests : `tests/test_voice.py` (19 : rien d’allumé sans clic et aucun outil MCP, dictée rendue sans envoi, silence et
  bruit ignorés, marque « voix » et IA de la barre, seuls les mots lus, connecteur lu à la fin, arrêter ≠ annuler,
  annuler fait taire, tours de parole, micro fermé pendant le travail, changement de conversation, lecture d’un message,
  réglages contrôlés, catalogue et fichier intact adopté sans téléchargement, VRAM laissée au modèle local, segmentation).
  Suite complète : 416 tests, aucun échec (2 ignorés).
- Vérifié hors tests : liste des 12 micros et 13 sorties (le micro n’a jamais été ouvert), lecture d’un silence
  inaudible, synthèse par la voix Windows Hortense en mémoire (22 050 Hz, sans jouer de son). Navigateur (configuration
  temporaire) : boutons, lecture activée puis coupée, micro refusé tant que whisper.cpp manque, onglet Voix (15
  éléments, 2 voix Windows, réglages enregistrés), marque « voix » et 🔈. Copie de la vraie base : colonne ajoutée,
  48 messages intacts, voix éteinte au démarrage, fichier réel inchangé.
- Non vérifié : aucun moteur ni modèle téléchargé, donc ni transcription Whisper réelle ni voix Piper réelle, et aucun
  son joué ; les formats de sortie de whisper-cli et de Piper suivent leur documentation et doivent être confirmés au
  premier essai réel.

**Paquet 0.2.27** (169,7 Mo) : 354 fichiers (`voice.js` en plus), aucun modèle ni donnée utilisateur, SHA-256
conforme. Application empaquetée : contrôle `voice` conforme (formulaire, 15 éléments, 2 voix Windows, boutons, micro
fermé). `team_tab` et `board_tab` y sont vides parce que l’instance de test se souvient du projet « CyMD », qui n’a pas
d’équipe ; le même code dans le navigateur, sur « Projet démo », montre l’onglet Équipe et les 9 colonnes.

Jalons suivants : essai réel (whisper.cpp + un modèle + Piper, avec votre accord pour les télécharger), reprise, pause
et annulation des téléchargements, Kyutai STT et Pocket TTS en flux, voix par profil d’agent, discussion de groupe comme
fonction CyAI, interruption en parlant, détection de voix, clonage.


## Voix, jalon 2 : les meilleurs modèles (0.2.28)

Demande : « je veux pouvoir tester avec les meilleurs modèles aussi » — ajouter Whisper Large v3 Turbo complet et q8_0,
et Pocket TTS (voix française, copie de voix) et la dictée Kyutai en direct, installés à la demande dans un environnement
isolé.

Faits vérifiés avant de coder (sources officielles) : Pocket TTS 3.1.0 (PyPI, Python 3.10–3.14, PyTorch ≥ 2.5, code MIT,
modèle CC BY 4.0) ; en français seul le modèle `french_24l` existe (672 Mo), avec une empreinte pour chacune des 26 voix
publiées ; les poids avec copie de voix sont dans `kyutai/pocket-tts` (accès à accepter, `gated=auto`), repli
automatique de la bibliothèque sur `kyutai/pocket-tts-without-voice-cloning`. Kyutai STT `kyutai/stt-1b-en_fr` (non
restreint, CC BY 4.0, 1,98 Go + Mimi 385 Mo), API de flux de `moshi` (exemple officiel `stt_from_file_pytorch.py` :
`CheckpointInfo.from_hf_repo`, `LMGen`, trames de 1 920 échantillons à 24 kHz, silence avant et délai après) ; moshi 0.2.13
(numpy < 2.3, torch < 2.10 : incompatible avec pocket-tts dans un même environnement, d’où deux environnements). uv
0.12.17 (`--torch-backend`, `UV_PYTHON_INSTALL_DIR`, `UV_CACHE_DIR`, `UV_PYTHON_PREFERENCE=only-managed`).

- `cyai/voice_python.py` (nouveau) : `Environments` (uv depuis GitHub avec SHA-256, `uv venv --python 3.12` et
  `uv pip install --no-cache --torch-backend cpu|auto` dans `runtimes/voice-pocket` et `runtimes/voice-kyutai`, premier
  chargement qui télécharge les poids dans `<modèles>/voice/huggingface` avec la progression mesurée sur le dossier,
  vérification, suppression de l’environnement et des poids) ; `_Worker` (processus JSON par ligne, première ligne =
  modèle chargé, mots en `piece`) ; `PocketTTS` (WAV par phrase) ; `KyutaiSTT` (begin/feed/finish, `partial`).
- `cyai/voice_workers/pocket.worker` et `kyutai.worker` (nouveaux, exécutés par le Python isolé ; extension `.worker`
  pour être empaquetés comme données) : sortie standard réservée au protocole, messages des bibliothèques vers stderr ;
  message clair si la copie de voix n’est pas accessible.
- `cyai/voice.py` : catalogue (Large v3 Turbo complet/q8_0, Large v3, Pocket TTS, Kyutai STT), `stt.engine`, capture à
  24 kHz pour Kyutai, audio tamponné pendant le chargement puis transmis dans l’ordre (verrou dédié, jamais celui de
  la voix dans le fil du micro), `partial` et `loading` dans l’état, voix `pocket:<langue>:<voix>` et
  `pocket:<langue>:clone:<id>`, Pocket prioritaire en voix automatique, échantillons (`record_sample`, `add_sample`
  avec consentement obligatoire, WAV 16 bits, stéréo ramenée en mono, 3 s minimum, 30 s gardées, `delete_sample`),
  jeton Hugging Face (`set_hf_token`, format `hf_…`, secret `huggingface`), déchargement de Kyutai après inactivité.
- `local_models.py` : une opération peut décrire son étape (`detail`), affichée dans Téléchargements.
  `security.py` : le secret `huggingface` est masqué comme les autres. `voice_audio.py` : fréquence de capture réglable.
- Interface (`voice.js`) : moteur de dictée, mots en direct et chargement dans la barre vocale, voix groupées par moteur,
  « Mes voix » (nom, durée, case d’accord, enregistrer au micro, importer un WAV, supprimer), jeton Hugging Face (saisi
  par l’utilisateur, jamais réaffiché), recommandations, tailles « ≈ » pour les environnements.
- Tests : `tests/test_voice_engines.py` (8 : mots pendant la dictée et audio du chargement transmis dans l’ordre,
  voix Pocket d’abord et copie avec consentement, import contrôlé, jeton secret et masqué par le vrai coffre, installation
  dans le dossier de données avec PyTorch processeur pour Pocket et CUDA automatique pour Kyutai, protocoles des deux
  programmes avec des bibliothèques simulées). Suite complète : 424 tests, aucun échec (2 ignorés). Navigateur :
  onglet Voix (10 sections, moteurs, catalogue, « Mes voix » désactivé tant que Pocket TTS manque, jeton).
- Non vérifié : aucun téléchargement fait, donc ni Pocket TTS, ni Kyutai, ni Whisper réels ; le premier essai confirmera
  l’API réelle.

**Paquet 0.2.28** (169,7 Mo) : 356 fichiers (`pocket.worker`, `kyutai.worker` en plus), aucun modèle ni donnée
utilisateur, SHA-256 conforme. Application empaquetée : contrôle `voice` conforme (20 éléments, 2 voix Windows, micro
fermé) ; un premier essai avait échoué parce que des processus WebView de l’essai précédent, interrompu, tenaient encore
le profil de test : arrêtés par numéro (commande contenant `scratchpad\ui-test`), puis contrôle refait.


## Codex et le bac à sable Windows, accès réglable ; discussion vocale directe (0.2.29)

Signalement : une discussion libre avec Codex échoue (« elevated Windows sandbox requires effective `:root` read
access »). Demande : que les discussions libres marchent simplement, et que l’on puisse augmenter les droits dans CyAI
au lieu d’être bloqué. Choix de l’utilisateur : « tester, garder le plus sûr ». Et, pour la voix : deux boutons côte à
côte, dictée à valider et discussion directe sans clavier.

- Cause : Codex 0.155 (`[windows] sandbox = "elevated"` chez l’utilisateur) exige la lecture de `:root` ; le profil
  `cyai-project` de CyAI met `":root": "deny"`. Essais réels (thread/start seulement, aucun message) : strict refusé,
  `windows.sandbox = "unelevated"` refusé (« cannot enforce split filesystem read restrictions »), lecture + interdictions
  accepté, réseau accepté, écriture de `:root` refusée (« setup refresh had errors »), `sandbox: danger-full-access`
  accepté. Schéma du protocole généré depuis le CLI installé (`codex app-server generate-json-schema`).
- `connectors.py` : `widen_reads` (lecture de `:root`, interdiction des emplacements de secrets et des données CyAI —
  seulement ses fichiers quand le projet est une discussion libre située dans le dossier de données), repli automatique
  unique dans `open_thread` sur ce refus précis (événement `sandbox_adjusted`) ; niveaux `ACCESS_LEVELS`
  (`project`, `read`, `read_network`, `full` = `danger-full-access`), événement `sandbox_access`, ignorés pour un plan ;
  `item/permissions/requestApproval` passe par l’autorisation de CyAI avec `permission_summary`, accordé pour la session
  (`scope: session`) ou rien.
- `engine.py` : `control.protected_roots` (données CyAI) et `control.access` (conversation, sinon défaut) ;
  `service.py` : action `access_settings`, `access_default` dans l’état, config `agent_access_default`.
- Interface : sélecteur « Accès Codex » dans la barre de conversation (confirmation pour « complet »), défaut dans la
  fenêtre Autorisations, carte d’autorisation lisible pour les droits (« Accorder pour cette conversation ») ; 🗣 à côté
  de 🎙 (discussion directe), 🎙 = dictée à relire.
- Tests : `tests/test_codex_sandbox.py` (7 : règle stricte gardée si acceptée, repli avec secrets fermés et écriture au
  projet, discussion libre dans le dossier de données, autres erreurs non rejouées, niveaux d’accès, demande de droits
  refusée ou accordée, réglage par conversation et par défaut transmis au connecteur). Suite complète : 431 tests, aucun
  échec (2 ignorés).

**Paquet 0.2.29** (169,7 Mo) : 356 fichiers, aucun modèle ni donnée utilisateur, SHA-256 conforme. Application
empaquetée revérifiée (voix conforme, micro fermé, autres contrôles inchangés) ; processus WebView de l’essai arrêtés
par numéro ensuite.


## Dictée Kyutai sous Windows (0.2.30)

Signalement : « Transcription : Cannot find a working triton installation… » avec Kyutai STT installé par l’utilisateur.
Cause : `moshi` décore son modèle par `torch_compile_lazy` (`moshi/utils/compile.py`), qui appelle `torch.compile` sauf si
`NO_TORCH_COMPILE` est défini ; Inductor demande Triton, absent sous Windows.

- `cyai/voice_workers/kyutai.worker` : `NO_TORCH_COMPILE=1` posé avant l’import de `moshi` ; une seule réponse par
  énoncé (erreur gardée jusqu’à `end`) ; `cyai/voice_python.py` : `NO_TORCH_COMPILE` dans l’environnement des moteurs,
  `HF_HUB_OFFLINE=1` pour Kyutai en service (ses poids sont téléchargés à l’installation).
- Tests : `test_voice_engines.py` (+2 : erreur rapportée une fois puis dictée suivante correcte ; démarrage hors ligne),
  la simulation de `LMGen` repart de zéro à chaque énoncé comme la vraie. Suite complète : 433 tests, aucun échec
  (2 ignorés).
- Essai réel avec les environnements installés par l’utilisateur (`<dossier-données-CyAI>\runtimes\voice-kyutai`,
  `voice-pocket`, poids dans `<dossier-modèles>\voice\huggingface`), sans micro ni son : audio de la voix Windows
  Hortense rééchantillonné à 24 kHz → texte exact, 26 mots en direct, sur CUDA ; Pocket TTS « anna » → WAV 24 kHz 16 bits.
  Constat : la connexion de cette machine vers huggingface.co présente un certificat auto-signé refusé par Python
  (inspection HTTPS probable) ; sans effet une fois les poids sur le disque.

**Paquet 0.2.30** (169,7 Mo) : 356 fichiers, aucun modèle ni donnée utilisateur, SHA-256 conforme ; application empaquetée
revérifiée, processus WebView de l’essai arrêtés par numéro.
