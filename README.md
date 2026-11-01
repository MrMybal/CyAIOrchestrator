# CyAI Orchestrator

Application locale Windows pour réunir des conversations, des sessions natives d’agents et des missions organisées par dépendances. Interface française, thème sombre, SQLite et serveur MCP stdio. Aucun contenu de démonstration dans l’application.

## Application de bureau Windows

### Organisation par projet

Cliquez sur un projet pour ouvrir sa page : conversations, actions récentes, utilisation des IA, historique, mémoire partagée et configuration du dossier. Le « + » à côté du projet et le bouton de sa page créent une conversation dans ce projet. Il n’y a pas de conversation libre hors projet.

Deux types sont disponibles : **Normal**, pour échanger avec un seul agent et modèle dans la conversation, avec la mémoire validée du projet ; **Orchestrateur**, pour discuter de l’objectif et obtenir un plan de tâches réparties entre agents/modèles. Le bouton **Voir les IA disponibles** consulte leurs catalogues quand les connecteurs le permettent et les communique aux propositions suivantes. Les états non vérifiés ne garantissent pas une connexion fournisseur.

Un plan d’orchestrateur apparaît comme un graphe avec ses dépendances, agents, modèles et contrôles. Ouvrez les tâches pour lire leurs instructions, puis **Autoriser l’exécution** et confirmez le plan complet. La discussion de planification utilise des permissions sans écriture et ne lance pas les tâches proposées. Les plans autorisés peuvent exécuter leurs branches indépendantes en parallèle (3 agents par défaut, de 1 à 32 au lancement). Une tâche attend la réussite de toutes ses dépendances ; les branches disposent de sessions natives distinctes. Le moteur local intégré conserve une seule exécution à la fois. La limite de durée est facultative : 0 signifie sans limite.

**Demander une révision** prépare un message que vous pouvez compléter avec vos critères de qualité puis envoyer. L’orchestrateur reçoit les résultats/erreurs récents et peut proposer un autre agent ou modèle ; le nouveau graphe doit être autorisé à nouveau. Il n’existe pas encore de boucle autonome de changement de modèle ni de juge sémantique universel : prévoyez une tâche de vérification dans le plan et contrôlez les résultats.

Le bouton **Masquer le suivi / Afficher le suivi** contrôle le panneau droit. L’état des projets repliés et du panneau est conservé dans le profil local de la fenêtre.

Double-cliquez sur **CyAI Orchestrator.lnk** à la racine du projet. Ce raccourci ouvre une fenêtre Windows autonome et retrouve le `config.json` et les conversations existantes. Aucun terminal ni navigateur séparé à ouvrir. Le lanceur PowerShell équivalent est `Start-CyAI-Desktop.ps1`.

L’exécutable est dans `dist-next/CyAIOrchestrator/CyAIOrchestrator.exe`, avec Python et le SDK Claude embarqués. Conservez le dossier `_internal` à côté du `.exe`. Le moteur Microsoft Edge WebView2 doit être installé sur Windows. Les outils externes Codex/OpenCode et leurs authentifications restent nécessaires.

La fenêtre réutilise le service local s’il est déjà actif. Sinon, elle le démarre et l’arrête à sa fermeture, en interrompant ses missions en cours. Pour laisser les missions continuer après fermeture de la fenêtre, démarrez préalablement le service avec `Start-CyAI.ps1`.

Pour reconstruire : `Build-Desktop.ps1` (Python 3.11+, accès Internet pour les dépendances). Pour développer sans compiler : `python -m pip install -e ".[desktop,claude]"`, puis `python -m cyai.desktop`.

Sur une autre machine, copiez le dossier complet `dist-next/CyAIOrchestrator` dans un emplacement accessible en écriture. Un lancement direct du `.exe` crée une configuration et des données neuves à côté du programme ; `--config "chemin/config.json"` permet de choisir une configuration existante. La configuration et les données se trouvent dans le dossier utilisateur, séparé des fichiers du programme. Le binaire n’est pas signé.

La fenêtre utilise [pywebview et son conditionnement Windows](https://pywebview.flowrl.com/guide/freezing).

## Modèles et composants téléchargés séparément

Le paquet Windows contient l’interface, Python et les adaptateurs. Les modèles GGUF, voix, PyTorch et moteurs GPU s’installent à la demande depuis **Paramètres > Modèles locaux**, **Voix** et **Téléchargements**. Ils sont conservés dans le stockage utilisateur.

Le CLI natif **Claude Code** est réutilisé s’il est déjà installé ; sinon, **Téléchargements > Composants à la demande** le récupère depuis le serveur officiel, avec vérification SHA-256, puis **Connecteurs** permet de se connecter. Le SDK Python est inclus dans le paquet de bureau, son gros exécutable ne l’est pas.

**FFmpeg vidéo CyAnnota** (environ 31 Mo) se télécharge dans le même panneau. Les images et modèles 3D restent utilisables sans ce composant. La vidéo l’utilise ensuite depuis le cache local, sans nouvelle connexion pour charger le codec.

Les fichiers `releases/` sont des produits de compilation destinés aux assets de release GitHub, pas à l’historique Git. Les sources de CyMD/CyAnnota et leurs licences restent fournies avec les plugins.

Pour vérifier les fichiers candidats et tout l’historique Git disponible avant un envoi :

```powershell
python scripts/check_repository.py --download-gitleaks
```

Les rapports masqués sont écrits dans `test-results/repository-check`, exclu de Git. Le workflow GitHub effectue le même contrôle sur les pushes et pull requests. Pour compiler : `Build-Desktop.ps1`, puis `python scripts/build_release.py` produit l’installateur.

## Lancer le service sous Windows

Prérequis : Python 3.11 ou ultérieur. Installez le projet pour obtenir les dépendances du cœur (`jsonschema`).

```powershell
cd C:\Projects\CyAIOrchestrator
python -m cyai
```

Ouvrir **http://127.0.0.1:8766**. La commande ouvre normalement le navigateur. Pour garder le lancement manuel :

```powershell
python -m cyai serve --no-browser
```

Le script `Start-CyAI.ps1` utilise le Python du dossier `.venv` s’il existe, sinon celui du PATH. Arrêt propre : `Ctrl+C` dans le terminal du serveur. Fermer seulement l’onglet laisse les missions continuer tant que le serveur reste ouvert.

Pour installer également le SDK officiel Claude Code :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[claude]"
.\.venv\Scripts\python.exe -m cyai
```

Alternative : `Install-CyAI.ps1`. Pas de compilation JavaScript, Node n’est nécessaire que pour certaines installations des agents.

## Configuration

Pour ajouter un projet, cliquez sur **＋** près de Projets, puis **Parcourir…** pour sélectionner un dossier avec Windows, ou saisissez son chemin. Tout dossier existant peut être choisi ; CyAI enregistre automatiquement cette autorisation lors de la création. Aucune modification manuelle du JSON ni redémarrage n’est nécessaire. Le dossier interne de données CyAI reste exclu.

Pour Claude Code, ouvrez **Connecteurs → Utiliser le CLI local**. CyAI réutilise une authentification valide ou ouvre le CLI interactif ; utilisez `/login` dedans si nécessaire, puis **Vérifier la connexion**. Le même exécutable natif sert aux échanges. La session de l’application Claude n’est pas importée.

`config.example.json` ne contient aucun secret. Copier ce fichier vers `config.json` **seulement si ce dernier n’existe pas**, si vous souhaitez personnaliser les paramètres avancés. Les dossiers de projets sont ajoutés automatiquement depuis l’interface.

```powershell
if (!(Test-Path config.json)) { Copy-Item config.example.json config.json }
```

Un projet ajouté depuis l’interface doit être un dossier existant sous une racine autorisée. Les chemins sont résolus, y compris les liens, avant les accès de l’application. Les dossiers de contrôle et fichiers connus de secrets ne peuvent pas être joints. Les outils natifs des agents sont aussi soumis à leurs mécanismes de permissions ; voir les limites ci-dessous.

Configuration principale :

- `port` : 8766, écoute sur **127.0.0.1 uniquement**.
- `data_dir` : `.data`, relatif à `config.json`, ou un chemin absolu.
- `allowed_roots` : liste de dossiers explicitement autorisés.
- `context_chars` : budget conservateur en caractères, 48 000 par défaut. Il ne prétend pas mesurer les tokens ni connaître la fenêtre de tous les modèles.
- `connectors.<id>.executable` : exécutable natif ou nom sur le PATH pour Codex et OpenCode. Les shims npm reconnus passent directement par Node, sans construire une commande shell avec le prompt.
- `connectors.<id>.model` : identifiant exact du modèle ; vide pour utiliser le défaut d’un agent. Obligatoire pour Anthropic et Ollama.
- `connectors.<id>.enabled` : activer/désactiver un connecteur.

Modifier manuellement les paramètres avancés dans le JSON nécessite un redémarrage. La création de projet et le changement de dossier depuis la page projet sont appliqués immédiatement. Les modèles et l’activation sont modifiables dans **Connecteurs** quand aucune mission n’est active.

## Connexion des fournisseurs

| Connecteur | Interface utilisée | Configuration nécessaire | Capacités actuelles |
|---|---|---|---|
| Codex | App Server officiel, JSON-RPC sur stdio | `codex login`, CLI sur le PATH | Streaming, sessions/reprise, outils natifs, commandes sous sandbox, approbation des commandes et modifications, usage, catalogue de modèles |
| Claude Code | `claude-agent-sdk` Python 0.2.152 | Installer l’option `[claude]`, lancer `claude`, puis `/login` | Streaming, sessions/reprise, outils Read/Write/Edit/Glob/Grep, contrôle de chemin et approbations ; shell et sous-agents désactivés |
| OpenCode | Serveur HTTP officiel lancé localement pour chaque exécution | Installer OpenCode, lancer `opencode auth login` | Sessions/reprise, suivi des messages, permissions, fichiers ; shell, outils externes et délégation désactivés dans la configuration de lancement |
| Claude API | API Anthropic Messages, streaming SSE | Clé API et modèle dans Connecteurs | Catalogue, streaming, usage ; boucle de 12 tours maximum avec lecture/écriture de texte et approbation avant écriture |
| Ollama | API HTTP locale `/api/chat` et `/api/tags` | Installer/lancer Ollama et télécharger un modèle | Catalogue, streaming, usage lorsqu’il est fourni ; conversation texte sans outils de fichiers |

Le SDK Claude Code peut employer sa CLI embarquée ; la présence d’une autre CLI `claude` sur le PATH ne prouve pas que le SDK est connecté. **Un abonnement ChatGPT/Claude n’accorde pas automatiquement un crédit d’API.** CyAI n’extrait pas les jetons des applications.

**API Anthropic** : saisir la clé uniquement dans le champ dédié. Windows DPAPI chiffre la clé pour l’utilisateur Windows courant, dans `secrets.dpapi`. Elle n’est pas placée dans `config.json`, les exports ou les journaux HTTP. `ANTHROPIC_API_KEY` est également accepté et prend priorité sur le coffre. La suppression de cette variable doit se faire dans l’environnement qui lance CyAI.

**Ollama** : l’adresse configurée doit rester en boucle locale, par défaut `http://127.0.0.1:11434`. Choisir le nom exact d’un modèle installé. CyAI n’installe ni ne télécharge automatiquement de modèles.

Les badges distinguent *non configuré*, *installé/configuré à vérifier*, *opérationnel* et *erreur*. Pour les agents, une exécution réussie constitue la preuve opérationnelle ; la présence d’un exécutable ne suffit pas. Pour les API de modèles, **Tester** vérifie le catalogue. Les coûts ne sont jamais calculés à partir de tarifs supposés.

## Parcours principal

1. Ajouter un projet, puis une conversation.
2. Choisir l’agent et éventuellement un modèle. Envoyer une instruction (`Ctrl+Entrée` est disponible).
3. Consulter les étapes, événements, outils, résultats et contrôles à droite.
4. Changer d’agent pour passer le relais. CyAI construit un contexte explicite à partir des messages et de la mémoire validée. Il ne transfère aucun état interne privé entre modèles.
5. Fermer et relancer le serveur : les messages et résultats restent présents. Le même agent reprend son identifiant natif si disponible.

Les connexions **API Anthropic et Ollama sont sans session native** : leur contexte est reconstruit à partir de l’historique sélectionné. Les agents conservent leurs sessions dans leur propre stockage. Une sélection manuelle de messages ouvre une nouvelle session native pour éviter qu’un message exclu demeure implicitement dans la session précédente. Les anciennes correspondances restent enregistrées.

**Contexte automatique** : messages les plus récents qui tiennent dans le budget, plus mémoire validée et pièces jointes choisies. Les identifiants des messages omis sont conservés. Une sélection manuelle trop volumineuse est refusée, pas tronquée silencieusement. Les résultats des étapes précédentes sont ajoutés au contexte d’une mission. Le contexte exact envoyé à chaque étape reste consultable dans son suivi, avec références et empreinte SHA-256.

**Mémoire** : proposer un message depuis la conversation ou écrire une instruction/décision/résumé dans Mémoire partagée. Une proposition reste exclue des envois jusqu’à validation explicite. Modification et suppression sont possibles. Les références aux messages sources sont conservées. Les résumés sont rédigés par l’utilisateur ou demandés à un agent puis validés ; aucun résumé automatique présenté comme vérité permanente.

**Pièces jointes** : fichiers texte UTF-8 de 100 Ko maximum, sous le projet. L’historique conserve une copie. Les fichiers produits par les outils de fichiers reconnus sont copiés dans le panneau lorsqu’ils sont textuels et suffisamment petits ; les suppressions, fichiers binaires et fichiers créés par des commandes shell restent visibles via les événements natifs, sans copie automatique exhaustive.

## Missions et reprises

Une mission contient 1 à 20 étapes. Dans l’interface, chaque étape dépend des précédentes ; le moteur accepte des dépendances explicites vers des indices antérieurs. Tout cycle est rejeté. Chaque rôle, agent, modèle, instruction et contrôle est configurable.

- Un seul worker pour toutes les missions : aucune édition concurrente de dépôt.
- Durée globale : 10–7200 secondes ; tentatives : 1–5, **sans réessai automatique d’une action pouvant avoir produit des effets**.
- Contrôles disponibles : réponse non vide, texte attendu, JSON valide, existence d’un fichier autorisé. Une réponse non vide n’est pas une certification du travail. Les commandes de test peuvent être demandées à Codex, leur sortie apparaît dans les événements.
- États : en attente, en file, en cours, approbation requise, réussie, échouée, annulée, interrompue.
- Une clé d’idempotence interdit la double création/exécution de la même requête.
- Les missions qui étaient actives au redémarrage deviennent interrompues ; les missions en file ne sont pas relancées aveuglément.
- **Examiner et reprendre** exige de vérifier les effets déjà produits. Les étapes réussies ne sont pas répétées.
- Une annulation interrompt le connecteur, mais ne restaure pas les fichiers. Une API HTTP silencieuse peut retarder l’observation de l’annulation jusqu’au délai de lecture réseau (20 secondes).

Les demandes de permissions natives prises en charge sont présentées avec leurs détails. Une autorisation s’applique à la demande courante. Les extensions de permissions Codex génériques non prises en charge sont refusées ; les autres requêtes interactives inconnues sont signalées, jamais auto-approuvées.

## MCP depuis Codex

Le serveur MCP est un **pont stdio** vers le service local déjà lancé. Il ne crée pas un second moteur. Copier l’identifiant du projet dans **Données & paramètres**. Chaque `--project` autorise un projet ; aucun projet n’est autorisé par défaut.

Exemple de commande à adapter :

```powershell
codex mcp add cyai -- python C:\Projects\CyAIOrchestrator\scripts\mcp_bridge.py --project PROJECT_ID
```

Avec environnement virtuel, utiliser son Python absolu à la place de `python` :

```powershell
codex mcp add cyai -- C:\Projects\CyAIOrchestrator\.venv\Scripts\python.exe C:\Projects\CyAIOrchestrator\scripts\mcp_bridge.py --project PROJECT_ID
```

Le script trouve `config.json` relativement au projet, quel que soit le répertoire du client MCP. Sous Windows, le pont lit le jeton local chiffré par DPAPI pour le même utilisateur. Le service doit être démarré. Après son redémarrage, reconnecter le client MCP pour renouveler le jeton en mémoire.

Outils : `list_projects`, `create_mission`, `launch_mission`, `mission_status`, `mission_result`, `continue_conversation`, `cancel_mission`, `search_history`.

Les outils de lancement rendent immédiatement `mission_id`. Utiliser `mission_status` avec le dernier numéro d’événement `after` pour suivre les exécutions longues. `create_mission` crée sans lancer. Les écritures mémoire et réponses d’approbation ne sont pas exposées aux agents MCP. Une délégation MCP pendant une exécution est bloquée pour empêcher les boucles. Le parallélisme n’est pas disponible.

## Historique, branches et sauvegardes

- Recherche plein texte par sous-chaîne avec projet, agent, dates et statut ; 100 résultats par recherche.
- Renommage, archivage/désarchivage et suppression des conversations.
- Branche à partir d’un message : copie seulement les messages jusqu’à ce point et garde la filiation. **Aucun retour arrière des fichiers.**
- Export JSON d’une conversation : messages, missions, contexte, événements et fichiers conservés.
- Sauvegarde JSON globale et restauration transactionnelle depuis l’interface (24 Mo maximum pour l’import). Une copie `before-restore-*.json` est créée avant remplacement.
- Les secrets, paramètres machine, fichiers des projets et stockages natifs des agents sont exclus de la sauvegarde portable. Après restauration, CyAI redémarre de nouvelles sessions à partir du contexte restauré.
- Supprimer dans CyAI ne supprime pas les sessions chez les agents. Les sauvegardes précédentes conservent les données qu’elles contenaient.

Pour une sauvegarde locale de grande taille, arrêter le serveur et copier le dossier de données complet. Le coffre DPAPI est lié au compte Windows et ne constitue pas une sauvegarde portable des identifiants.

## Tests et état de validation

```powershell
python -m unittest discover -s tests -v
node --check cyai/web/app.js
```

Tests réels optionnels (utilisent les connexions existantes et peuvent consommer du quota) :

```powershell
python scripts/smoke_codex.py
python scripts/smoke_claude.py
python scripts/smoke_mcp.py
```

Consulter [VALIDATION.md](VALIDATION.md) pour distinguer résultats réels, simulations de protocole et limites restantes. Les connecteurs de test ne sont jamais enregistrés dans l’application.

## Limites connues

- Sur la machine de livraison, Codex fonctionne dans `test-results/live-project`, mais l’initialisation du dossier racine de l’application échoue sur `apply deny-read ACLs`. Le refus du sandbox Windows est conservé. Choisir un projet de travail distinct ; vérifier le fonctionnement du sandbox avec la CLI officielle avant de traiter un dossier concerné. Ne pas utiliser un mode sans sandbox pour contourner cette erreur.
- Les profils Codex et leurs protections dépendent de la version et de la politique d’installation de Codex. Une ancienne configuration `sandbox_mode` peut prendre priorité sur les profils de permissions ; CyAI refuse cette configuration lorsqu’elle est détectée. Il ne remplace pas une isolation OS contre un agent ou plugin malveillant exécuté par le même utilisateur.
- L’authentification Claude Code manque sur la machine de livraison. OpenCode n’est pas installé ; ses appels restent à valider avec la version installée. Aucune clé Anthropic ni serveur Ollama utilisable n’a été fourni.
- Pas de paral­lélisme/worktrees, de retour arrière des fichiers, de sélection automatique sémantique, de comptage exact des tokens ni de budget monétaire automatique.
- Pas de support complet de toutes les demandes interactives natives (questions utilisateur, authentification interactive, extensions de permissions). Elles ne sont pas contournées.
- Pas de rendu Markdown riche ni de pièces jointes image/PDF/binaires. Les réponses sont affichées comme texte échappé pour éviter l’exécution de HTML fourni par un modèle.
- Interface prévue pour un poste de travail ; le volet d’inspection est masqué sous 850 px. La navigation mobile complète n’est pas un objectif de cette version.

## Architecture et références

Voir [docs/architecture.md](docs/architecture.md) et [docs/connectors.md](docs/connectors.md).

Interfaces officielles consultées pendant l’implémentation (14 septembre 2026) :

- [Codex App Server](https://developers.openai.com/codex/app-server/), [permissions](https://developers.openai.com/codex/permissions/) et [MCP](https://developers.openai.com/codex/mcp/).
- [Claude Agent SDK Python](https://platform.claude.com/docs/en/agent-sdk/python), [permissions](https://platform.claude.com/docs/en/agent-sdk/permissions) et [streaming API](https://platform.claude.com/docs/en/build-with-claude/streaming).
- [OpenCode Server](https://opencode.ai/docs/server/), [CLI](https://opencode.ai/docs/cli/) et [permissions](https://opencode.ai/docs/permissions/).
- [Ollama Chat API](https://docs.ollama.com/api/chat) et [MCP stdio](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).

## Extensions

La page **Plugins** permet de configurer CyAnnota, CyAICodex et CyProjectCodex, ou d’installer un manifeste local. Les associations et la mémoire structurée facultative se règlent dans **Projet → Plugins**. Voir le [guide des plugins](docs/plugins.md) pour les transports MCP, les boutons et l’import des annotations.

### Zone de notification Windows

Fermer la fenêtre avec la croix masque CyAI dans la zone de notification et conserve le service et les missions. Double-cliquez sur son icône, ou utilisez **Ouvrir CyAI Orchestrator**, pour la réafficher. **Quitter** arrête le service démarré par cette application et demande confirmation si des missions sont actives. Un service déjà lancé séparément reste indépendant. Windows peut placer l’icône dans son menu d’icônes masquées.

## Organisation du travail

Clic droit (ou bouton ⋯) sur un projet ou une conversation : renommer, archiver, supprimer l’historique, favoris et ordre. Le glisser-déposer change l’ordre ; les favoris restent regroupés en premier. Les catégories regroupent les projets. La configuration du projet permet de choisir un logo ou emoji, une couleur et une catégorie, et de détecter ou initialiser Git sans créer de commit.

Dans une conversation, **Dossiers de travail** ajoute jusqu’à 12 dossiers supplémentaires. Les sessions sont réinitialisées quand ce périmètre change, les messages sont conservés. Codex reçoit les permissions de ces dossiers ; Claude Code utilise `add_dirs` et les contrôles de chemins ; l’API Anthropic utilise les mêmes contrôles de fichiers. OpenCode reste limité au dossier principal dans cette version ; Ollama ne dispose pas d’outils de fichiers.

Les paramètres utilisent des catégories verticales : Apparence, MCP, Sauvegarde, Dossiers, Contexte et IA, Application Windows. Le dossier de sauvegarde est choisi depuis Windows ; une sauvegarde locale peut y être écrite directement. Les images des projets doivent être sauvegardées avec leurs dossiers.

La pause de chaîne est progressive : les étapes déjà actives se terminent, puis les étapes restantes restent en attente. Le statut « En pause » persiste après un redémarrage ; Reprendre conserve les étapes réussies. « Pause demandée » signifie que des agents travaillent encore : attendre « En pause » avant de mettre à jour. Une fermeture avant cet état constitue une interruption, pas une pause sûre.
