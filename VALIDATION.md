# Validation de livraison — 14 septembre 2026

## Environnement

- Windows, Python 3.11.5, Node 22.17.1.
- Codex CLI 0.153.4, authentification ChatGPT déjà présente.
- Claude Agent SDK 0.2.152 installé dans `.data/deps` pour les essais. Le package propose la même version via l’option d’installation `[claude]`.
- Service testé à `http://127.0.0.1:8766`. Le port 8765 était indisponible sur cette machine ; 8766 est le défaut livré.

## Tests automatisés sans fournisseur

`python -m unittest discover -s tests -v` : **47 tests, 46 réussis, 1 ignoré** après ajout des modes de conversation et des plugins.

## Projet et orchestration assistée par IA

- Migration SQLite ajoutant le type de conversation, conservation des historiques, compatibilité de restauration des anciennes conversations sans type.
- Tests du plan structuré : aucun agent de travail appelé avant autorisation, refus de cycle/agent inconnu, refus d’exécution sans acquittement, idempotence de l’autorisation.
- Essai Codex réel dans « Validation du mode orchestrateur » : proposition à deux tâches produite et rendue comme graphe ; laissée en attente d’autorisation. Les deux tâches de ce plan n’ont pas été lancées.
- Création réelle de `CyProjectCodex` depuis l’interface avec le chemin fourni par l’utilisateur, hors de l’ancienne racine.
- Page projet, conversations sous chaque projet, absence de bouton global de nouvelle conversation et masquage du suivi inspectés dans l’interface.
- La révision d’un plan est demandée par message ; pas de réaffectation autonome après échec. Les graphes restent exécutés séquentiellement. Les catalogues non accessibles et les coûts non transmis restent indiqués comme inconnus.

## Corrections d’interface et de connexion

- Projets créés dans tout dossier existant choisi ou saisi : ajout et persistance automatiques de la racine ; aucune édition manuelle du JSON.
- Bouton Parcourir utilisant le sélecteur Windows ; annulation sans création de projet.
- Conversations regroupées sous leur projet, projets repliables, bouton de création par projet ; entrées Espace de travail, Missions et Historique retirées de la navigation latérale.
- Panneau de suivi masquable ; préférence enregistrée dans le profil WebView2 local.
- Claude Code : bouton ouvrant le CLI natif interactif sans lancer automatiquement `auth login` et vérification séparée (`auth status`). Statut local réellement vérifié : non connecté. Le parcours de connexion reste à terminer par l’utilisateur.
- Initialisation réelle de Codex réussie dans `C:\Projects\CyProjectCodex`, sans génération ni exécution d’outil. L’échec dans le dépôt de l’application est identifié dans le journal Windows : `SetNamedSecurityInfoW failed` sur son dossier `.data`. Aucune suppression de protection ou modification des ACL n’a été effectuée.

## Version de bureau Windows

- Exécutable construit avec PyInstaller 6.22.3, pywebview 6.2.1 et SDK Claude embarqué, dans `dist/CyAIOrchestrator`.
- Raccourci `CyAI Orchestrator.lnk` généré à la racine : configuration et données existantes conservées.
- Fenêtre WebView2 réellement lancée ; diagnostic interne du `.exe` confirmant le chargement HTML et JavaScript.
- Démarrage autonome, accès API authentifié, arrêt et libération du verrou testés sur une base temporaire avec DPAPI Windows.
- Tests spécifiques : réutilisation du service sans le fermer, nettoyage après échec de port, refus de réutiliser un service sans jeton.
- Capture Windows indisponible sur cet environnement (`SetIsBorderRequired`, interface non prise en charge) ; vérification du chargement réalisée par diagnostic interne du composant WebView2. L’arbre d’accessibilité Windows seul n’exposait pas le contenu Web complet.
- L’exécutable n’est pas signé ; une installation sur un autre ordinateur reste à tester. WebView2 est un prérequis système. Les limites d’authentification et de sandbox des connecteurs décrites ci-dessous restent applicables.

Le test ignoré concerne la création d’un lien symbolique : le contexte Windows de test ne l’autorise pas. Le code résout néanmoins les chemins réels ; ce scénario reste à exécuter dans un Windows autorisant les liens.

Couverture vérifiée :

- Persistance SQLite après fermeture/réouverture et reprise du bon identifiant natif.
- Conversation regroupant deux connecteurs et transmission du résultat du premier au second.
- Séparation mémoire proposée/validée ; sélection manuelle et références hors conversation refusées.
- Budget de contexte, omission automatique tracée et sélection manuelle trop grande refusée.
- Idempotence de création/lancement, réemploi invalide d’une clé et prévention des cycles/délégations.
- Erreurs, annulation coopérative, interruption au redémarrage et absence de relance automatique.
- Réessai explicite conservant les étapes réussies et respect du maximum de tentatives.
- Approbation acceptée/refusée et nettoyage des demandes en attente.
- Échec de validation avec conservation du résultat.
- Branches, provenance, horodatages, archives, filtres de recherche et copies de pièces jointes.
- Sauvegarde/restauration et annulation transactionnelle d’une restauration invalide.
- Traversées de chemins et fichiers sensibles exclus.
- Authentification HTTP, contrôle d’origine/hôte et périmètre MCP.
- Décodage SSE Anthropic et JSONL Ollama, absence de fin de flux traitée comme erreur, usage sans coût inventé.
- Boucle d’outil Anthropic avec refus d’écriture et réponse d’approbation Codex via un protocole simulé.

Ces tests emploient des adaptateurs de test et des flux synthétiques, **pas de fausses connexions présentées dans l’application**.

Autres contrôles : compilation Python, vérification de syntaxe JavaScript et construction du wheel Python réussies. Le wheel comprend l’interface web.

## Essais réels

| Parcours | Résultat observé |
|---|---|
| Codex App Server | Connexion réelle, événements de session/modèle/texte/usage reçus |
| Reprise Codex par script | Première requête `OK`, seconde requête retrouvant `CYAI-REPRISE-742` dans la même session native |
| Conversation depuis l’UI | Message envoyé à Codex et réponse `Connexion vérifiée` enregistrée |
| Redémarrage réel du serveur | Historique toujours présent ; une nouvelle requête reprend la session et retrouve `CYAI-INTERFACE-218` |
| Mission de deux étapes depuis l’UI | `PLAN-CYAI`, puis `VERIF-CYAI` ; deux contrôles de texte attendu réussis et mission réussie |
| MCP stdio | Initialisation JSON-RPC, liste de 8 outils, liste de projets bornée et recherche d’historique via le service local |
| DPAPI Windows | Création/lecture du jeton local chiffré, utilisé par le pont MCP sans exposition dans stdout |
| Claude Agent SDK | Démarre et crée une session ; retourne `Not logged in — Please run /login`. Aucune génération réussie revendiquée |

Les rapports techniques des scripts sont dans `test-results/codex-smoke.json` et `test-results/mcp-smoke.json`. Les traces des essais d’interface sont dans l’historique local, projet **Validation locale**. Il s’agit de vrais résultats de tests, pas de données fictives préchargées.

## Vérification visuelle

Application ouverte et inspectée dans le navigateur intégré, en disposition bureau 1280 × 720 :

- Accueil vide et création d’un projet/conversation.
- Envoi, progression, réponse finale et historique retrouvé après redémarrage.
- Renommage et inspection du contexte effectivement envoyé.
- Page des connecteurs et distinction de leurs états.
- Proposition de mémoire conservée comme *non transmise* avec référence source.
- Recherche d’un mot présent dans un message et une réponse.
- Branche avec messages copiés et absence de session native héritée.
- Formulaire de mission à deux étapes, sélection des contrôles et exécution réelle.
- Résultat et validations de chaque étape dans le volet latéral.

La vérification visuelle a permis de corriger un sélecteur de validation mal formé, la reconnexion du cookie après redémarrage, la mémorisation de la conversation sélectionnée et le rafraîchissement trop fréquent des contrôles.

Les dialogues destructifs et la restauration de l’historique utilisateur n’ont pas été exercés dans le navigateur ; leur logique est testée sur des bases temporaires isolées.

## Points non validés ou limités

1. **Sandbox Codex dans le dossier de l’application** : échec réel `apply deny-read ACLs`. Le même connecteur fonctionne dans `test-results/live-project`. Aucun mode sans sandbox n’a été employé. Le dossier de l’application contient son runtime et ses données ; utiliser un dossier de travail séparé et diagnostiquer le sandbox Codex avant d’utiliser le dossier concerné.
2. **Relais entre deux fournisseurs réels** : testé par adaptateurs déterministes seulement, faute de deuxième connexion authentifiée. Le pipeline réel utilise Codex pour ses deux rôles.
3. **Claude Code** : authentification `/login` nécessaire. Reprise, outils de fichiers et approbations du SDK ne sont pas validés avec une génération authentifiée.
4. **OpenCode** : CLI absente. Adaptateur HTTP implémenté à partir de l’interface officielle ; compatibilité avec l’installation cible et demandes de permissions à valider avant usage régulier. Il ne faut pas assimiler sa présence dans le code à une intégration vérifiée.
5. **Anthropic API** : aucune clé fournie. Flux et boucle d’outils testés sur réponses simulées ; authentification, facturation et modèles réels non vérifiés.
6. **Ollama** : pas de serveur/modèle réel configuré. Décodage et restrictions de boucle locale testés sans génération réelle.
7. **Modifications natives du disque et commandes réelles** : les essais réseau demandaient explicitement de ne pas utiliser d’outils. Les politiques de fichiers des agents et toute escalade de permissions méritent une validation sur un dépôt jetable avant une tâche importante.
8. **Parallélisme, worktrees, instantanés des projets et support de toutes les interactions natives** : non implémentés. L’exécution actuelle est séquentielle ; aucune restauration de fichiers n’est promise.
9. **Contexte** : budget en caractères, pas de comptage exact des tokens ni de connaissance universelle des fenêtres des modèles. Une session native reprise possède également son historique côté fournisseur.

## Prochain essai conseillé après authentification

Dans un dépôt jetable autorisé : demander un plan à Claude Code, une modification limitée à OpenCode, puis une vérification à Codex avec un contrôle `file_exists` ou une commande de test. Vérifier une demande d’approbation, annuler une étape, redémarrer le serveur et reprendre explicitement. Cette validation de bout en bout à trois fournisseurs ne peut pas être déclarée réussie tant que ces connexions ne sont pas disponibles.

## Plugins

Le test `python scripts/smoke_plugins.py` a traversé le pont Node, le service HTTP local et le vrai serveur MCP CyProjectCodex : lecture réussie et argument de projet forcé sur l’association autorisée. Les tests unitaires vérifient les refus des outils non autorisés, des jetons invalides et des destinations distantes. Ces contrôles ne constituent pas un appel du plugin par un modèle réel.

CyAICodex attend un jeton de lecture fourni par l’utilisateur. Le passage CyAnnota utilise son contrat de lancement natif et l’import de son export IA ; aucun éditeur n’est intégré dans la fenêtre CyAI.

## Tray Windows

Six tests du cycle de vie desktop passent, dont masquage sans arrêt du service, fermeture explicite, arrêt Windows et suppression de l’icône. Le diagnostic natif vérifie NotifyIcon.Visible, la fermeture masquant réellement la fenêtre, puis sa réouverture. Rapport : test-results/desktop-tray-final.json.

## Organisation, multi-dossiers et CyAnnota intégré

Suite finale : **56 tests, 55 réussis, 1 ignoré** (lien symbolique Windows). Tests ajoutés pour l’organisation, l’ordre, la sauvegarde, le périmètre multi-dossiers, les activations de plugins, la reprise des annotations et l’initialisation Git sans commit.

Vérification réelle : Codex a lu un marqueur uniquement présent dans un dossier supplémentaire, avec permissions de lecture et sans modification demandée. Le CLI Claude a retourné `disconnected`, y compris hors sandbox ; l’application ouverte est Claude Microsoft Store. Aucune connexion à cette session graphique n’est revendiquée.

Interface : menu au clic droit, paramètres verticaux, configuration logo/couleur, statut Git et activation par projet vérifiés. CyAnnota embarqué a chargé la capture utilisateur, créé une zone, enregistré sa consigne dans la conversation de validation, puis rouvert le document avec sa correction conservée. Aucune demande IA n’a été envoyée pour cette annotation de test.

CyAnnota, ouverture directe : éditeur affiché sans écran intermédiaire, collage Ctrl+V d’une image depuis le presse-papiers puis sauvegarde dans la conversation vérifiés dans la version Windows servie. Le pont open-workspace et le média original envoyé lors de la sauvegarde sont inclus dans les sources embarquées.

Correction cyai2 : navigation condensée, mémoire déplacée en pied de barre, plugins dans Paramètres et nouvelle vue Logs. Journal application borné à 5 000 entrées, événements de missions consultables avec filtres et export. Test dédié du filtre et de la suppression des secrets réussi.
