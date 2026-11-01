# MCP de CyAI Orchestrator

Les agents lancés par CyAI reçoivent automatiquement le serveur `cyai_plugins`. `cyai_actions` découvre les opérations et leurs schémas ; `cyai_call` les exécute. Il ne faut pas piloter le navigateur pour gérer CyAI.

Codex et Claude Code ont été vérifiés par une exécution réelle créant puis relisant une note dans un projet de test. OpenCode reçoit la configuration MCP mais nécessite son installation pour une validation réelle. Claude API utilise le même routeur. Ollama et llama.cpp utilisent les appels de fonctions : le modèle et son template doivent prendre en charge les outils. Un modèle de conversation sans cette capacité ne devient pas un agent par la seule présence de MCP.

## Connexion externe

Dans Paramètres > MCP, choisir le projet, le client et les droits, puis générer la configuration. Le programme console `dist/CyAI-MCP/CyAI-MCP.exe` communique avec le service CyAI en cours. Il accepte `--config CHEMIN --project IDENTIFIANT`, répétable pour plusieurs projets. Sans `--allow-write`, les appels sont en lecture seule. Les autorisations globales d’écriture ne donnent pas accès aux autres projets.

Les jetons de connexion internes sont temporaires et révoqués en fin de mission. Les ressources `cyai://project/ID/overview`, `/memory` et `/conversations` suivent le même périmètre.

## Autorisations et suivi

Les écritures des agents utilisent l’approbation de la conversation, y compris le mode automatique choisi par l’utilisateur. La planification ne modifie pas l’application. Une action qui nécessite l’arrêt des missions retourne un `job_id` : terminer la réponse, puis consulter `job_status`. Elle s’exécute après les missions en cours. Après redémarrage une opération interrompue nécessite `job_resume`, sans réexécution silencieuse.

Les téléchargements retournent leur propre identifiant et se suivent avec `local_state`. Leurs erreurs et leur progression sont exposées. Les réglages du moteur local peuvent être globaux ou propres à chaque modèle.

## Opérations disponibles

### analytics

- `analytics` : Statistiques et stockage du projet ou de la conversation.

### application

- `get_state` : Projets autorisés, conversations, connecteurs, réglages non secrets.
- `get_settings` : Lire les réglages globaux publics, stockage et catégories.
- `get_logs` : Événements des missions du projet.
- `save_settings` : Thème, budget de contexte, dossier des sauvegardes.
- `save_theme` : Créer un thème personnalisé.
- `set_storage` : Programmer la migration du stockage au prochain redémarrage.
- `job_cancel` : Annuler une opération différée non exécutée.
- `job_resume` : Reprendre une opération interrompue ou en échec, après une nouvelle autorisation.
- `job_status` : Lire une opération différée autorisée.

### connectors

- `test_connector` : Vérifier la connexion sans générer une réponse.
- `save_connector` : Activer un connecteur ou régler son modèle/exécutable, sans clés secrètes.

### conversations

- `get_conversation` : Lire messages, pièces jointes, sessions, mémoire et plans.
- `context_preview` : Inspecter le contexte envoyé à un agent.
- `create_conversation` : Créer un chat normal ou orchestrator dans un projet.
- `rename_conversation` : rename_conversation
- `archive_conversation` : archive_conversation
- `delete_conversation` : delete_conversation
- `branch` : Créer une branche à partir d’un message.
- `conversation_workdirs` : Modifier les dossiers de travail de la conversation.
- `conversation_summary` : Enregistrer le résumé de reprise et compacter la session.
- `search_history` : Rechercher les messages et résultats dans les projets autorisés.

### files

- `attach_file` : Joindre une copie d’un fichier texte du dossier de travail.
- `delete_file` : Retirer une pièce jointe de cette conversation.
- `annotation_list` : Lister les documents CyAnnota.
- `annotation_open` : Lire le document CyAnnota et son image.
- `annotation_save` : Créer ou modifier un document CyAnnota avec image data URL et annotations.
- `export` : Exporter une conversation et ses missions.

### local_models

- `local_catalog` : Catalogue de modèles GGUF disponibles au téléchargement.
- `local_state` : Modèles installés, paramètres CPU/GPU, téléchargements, erreurs et progression.
- `local_model_files` : Lister les fichiers GGUF et tailles d’un dépôt Hugging Face.
- `local_runtime_install` : Installer llama.cpp CPU, Vulkan ou CUDA. Retourne job_id, suivre local_state.
- `local_model_install` : Télécharger un GGUF dans le dossier configuré et l’enregistrer dans CyAI. Retourne job_id, suivre local_state.
- `local_model_import_path` : Importer un GGUF existant du dossier de travail dans CyAI.
- `local_settings` : Réglages globaux : cpu/gpu/hybrid, couches, threads, contexte et dossier.
- `local_model_settings` : Exceptions par modèle ; objet settings vide pour hériter des valeurs globales.
- `local_start` : Charger un modèle installé ; suivre local_state.
- `local_stop` : Arrêter le moteur local et libérer sa mémoire.

### memory

- `get_memory` : Lire les catégories et notes du projet.
- `save_memory` : Créer/modifier une note catégorisée, avec sources et validation.
- `delete_memory` : Supprimer une note du projet.

### missions

- `create_mission` : Préparer une mission sans la lancer ; steps contient connector, model, instruction, depends_on.
- `mission_status` : Lire les étapes et événements de la mission.
- `mission_result` : Lire le résultat complet de la mission.
- `launch_mission` : Lancer une mission préparée, après la mission courante pour éviter une délégation récursive.
- `continue_conversation` : Envoyer une instruction à un agent ; différé jusqu’à la fin de l’exécution courante.
- `cancel_mission` : Annuler une mission du projet.
- `retry_mission` : Relancer une mission en échec après confirmation.

### models

- `runtime_settings` : Effort et vitesse pour une conversation.
- `model_catalog` : Catalogues, préférences, notes et benchmarks.
- `list_models` : Lister les modèles proposés par un connecteur.
- `model_rating` : Évaluer un modèle par domaine et enregistrer des observations.
- `model_preferences` : Choix de qualité, vitesse, coût et préférences de sélection.
- `refresh_benchmarks` : Actualiser les résultats publiés en cache.

### plugins

- `plugins_list` : Lister les plugins activés pour le projet.
- `plugin_catalog` : Découvrir les outils et ressources du plugin dans le projet.
- `plugin_read` : Consulter une ressource ou un outil de lecture borné au projet.
- `plugin_call` : Appeler un outil du plugin, avec autorisation et rattachement au projet.
- `plugin_bind` : Activer/configurer le plugin pour ce projet.
- `plugin_create_project` : Créer et associer un projet CyProjectCodex.
- `plugin_attach` : Joindre une référence du plugin dans la conversation.

### projects

- `get_project` : Lire le tableau de bord, historique, mémoire et configuration.
- `create_project` : Créer un projet dans un dossier existant après autorisation.
- `update_project` : Renommer le projet ou changer son dossier.
- `organize` : Favori, archivage, suppression, catégorie, couleur ou logo du projet/conversation.
- `category` : Créer ou renommer une catégorie globale.
- `reorder` : Réordonner les projets autorisés ou les conversations du projet. kind=project ou conversation.
- `git_init` : Initialiser Git dans le dossier du projet.

### skills

- `agent_settings` : Consignes, skills, mémoire automatique et budget de contexte par projet ou conversation.

## Actions réservées à l’utilisateur

- `approve` : Décisions d’autorisation : seul l’utilisateur peut approuver.
- `approval_settings` : L’agent ne peut pas modifier ses propres autorisations.
- `approve_plan` : Lancement d’un plan réservé à l’utilisateur.
- `restore` : Restauration globale remplaçant les données : interface utilisateur.
- `plugin_save` : Installation de nouveaux plugins et clés : interface utilisateur.
- `connect_claude` : Authentification personnelle : interface utilisateur.
- `choose_project_folder` : Dialogue Windows : fournir un chemin dans les outils de configuration.
- `backup` : Export global hors périmètre : interface utilisateur. Utiliser export par conversation.
