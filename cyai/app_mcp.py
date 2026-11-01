"""CyAI application MCP: discovered schemas, scoped reads and approved mutations."""
import json
import threading
from pathlib import Path
from jsonschema import Draft202012Validator
from .store import uid, now

S={'type':'string'}; B={'type':'boolean'}; N={'type':'integer'}; O={'type':'object'}; A={'type':'array','items':S}
ACTIONS={}
def register(name, domain, description, fields='', scope=None, write=False, deferred=False):
    props={};required=[]
    for field in fields.split():
        key,_,kind=field.partition(':');optional=key.endswith('?');key=key.rstrip('?')
        props[key]={'s':S,'b':B,'n':N,'o':O,'a':A,'l':{'type':'array','items':O}}.get(kind or 's',S)
        if not optional:required.append(key)
    ACTIONS[name]={'name':name,'domain':domain,'description':description,'write':write,'deferred':deferred,'scope':scope,
                   'inputSchema':{'type':'object','properties':props,'required':required,'additionalProperties':False}}

# A schema for each operation; never forward arbitrary names into Service.action.
register('get_state','application','Projets autorisés, conversations, connecteurs, réglages non secrets.')
register('get_project','projects','Lire le tableau de bord, historique, mémoire et configuration.','project_id', 'project_id')
register('get_conversation','conversations','Lire messages, pièces jointes, sessions, mémoire et plans.','conversation_id','conversation_id')
register('get_memory','memory','Lire les catégories et notes du projet.','project_id','project_id')
register('get_settings','application','Lire les réglages globaux publics, stockage et catégories.')
register('get_logs','application','Événements des missions du projet.','project_id','project_id')
register('analytics','analytics','Statistiques et stockage du projet ou de la conversation.','project_id conversation_id?','project_id')
register('context_preview','conversations','Inspecter le contexte envoyé à un agent.','conversation_id instruction? context?:o','conversation_id')
register('create_project','projects','Créer un projet dans un dossier existant après autorisation.','name root',None,True)
register('update_project','projects','Renommer le projet ou changer son dossier.','id name? root?','project:id',True,True)
register('create_free_conversation','conversations','Créer une discussion libre indépendante des projets.','title?',None,True)
register('create_conversation','conversations','Créer un chat normal ou orchestrator dans un projet.','project_id title mode?','project_id',True)
for name,fields in [('rename_conversation','id title'),('archive_conversation','id archived:b'),('delete_conversation','id')]:
    register(name,'conversations',name,fields,'conversation:id',True,True)
register('branch','conversations','Créer une branche à partir d’un message.','conversation_id message_id','conversation_id',True)
register('organize','projects','Favori, archivage, suppression, catégorie, couleur ou logo du projet/conversation.','kind id favorite?:b archived?:b delete?:b category? color? icon?','organize',True,True)
register('category','projects','Créer ou renommer une catégorie globale.','name old?',None,True)
register('reorder','projects','Réordonner les projets autorisés ou les conversations du projet. kind=project ou conversation.','kind project_id? ids:a','project_id',True)
register('conversation_workdirs','conversations','Modifier les dossiers de travail de la conversation.','id workdirs:a','conversation:id',True,True)
register('git_init','projects','Initialiser Git dans le dossier du projet.','project_id','project_id',True,True)
register('agent_settings','skills','Consignes, skills, mémoire automatique et budget de contexte par projet ou conversation.','scope id settings:o','settings',True,True)
register('conversation_summary','conversations','Enregistrer le résumé de reprise et compacter la session.','id summary','conversation:id',True,True)
register('runtime_settings','models','Effort et vitesse pour une conversation.','id effort? service_tier?','conversation:id',True,True)
register('save_memory','memory','Créer/modifier une note catégorisée, avec sources et validation.','project_id id? content category? validated?:b source_ids?:a','project_id',True)
register('delete_memory','memory','Supprimer une note du projet.','project_id id','project_id',True)
register('attach_file','files','Joindre une copie d’un fichier texte du dossier de travail.','conversation_id path','conversation_id',True)
register('delete_file','files','Retirer une pièce jointe de cette conversation.','conversation_id id','conversation_id',True)
register('annotation_list','files','Lister les documents CyAnnota.','conversation_id','conversation_id')
register('annotation_open','files','Lire le document CyAnnota et son image.','conversation_id id','conversation_id')
register('annotation_save','files','Créer ou modifier un document CyAnnota avec image data URL et annotations.','conversation_id id? name? image document:o','conversation_id',True)
register('export','files','Exporter une conversation et ses missions.','conversation_id','conversation_id')
register('mcp_local_register','plugins','GLOBAL · Enregistrer un MCP local découvert : config contient un seul mcpServers avec command/args/cwd/env ou url. Ne lance aucun processus. project_id expose le MCP dans ce projet. Appeler ensuite mcp_local_test, plugin_catalog et plugin_call : disponibles dans la conversation actuelle.','config:o name? project_id? instructions?','global',True)
register('mcp_local_test','plugins','Tester initialize et tools/list du MCP enregistré. Peut démarrer son processus local ; suit les autorisations de la conversation. Renvoie les outils ou une erreur explicite.','project_id id','project_id',True)
register('plugins_list','plugins','Lister les plugins activés pour le projet.','project_id','project_id')
register('plugin_catalog','plugins','Découvrir les outils et ressources du plugin dans le projet.','project_id id','project_id')
register('plugin_read','plugins','Consulter une ressource ou un outil de lecture borné au projet.','project_id id tool? arguments?:o resource?','project_id')
register('plugin_call','plugins','Appeler un outil du plugin, avec autorisation et rattachement au projet.','project_id id tool arguments?:o','project_id',True)
register('plugin_bind','plugins','Activer/configurer le plugin pour ce projet.','project_id id enabled?:b external_project_id? auto_memory?:b','project_id',True,True)
register('plugin_create_project','plugins','Créer et associer un projet CyProjectCodex.','project_id id name','project_id',True,True)
register('plugin_attach','plugins','Joindre une référence du plugin dans la conversation.','conversation_id id tool? arguments?:o resource?','conversation_id',True)
register('model_catalog','models','Catalogues, préférences, notes et benchmarks.','refresh?:b connector?')
register('list_models','models','Lister les modèles proposés par un connecteur.','id')
register('test_connector','connectors','Vérifier la connexion sans générer une réponse.','id')
register('save_connector','connectors','Activer un connecteur ou régler son modèle/exécutable, sans clés secrètes.','id enabled?:b model? executable?',None,True,True)
register('model_rating','models','Évaluer un modèle par domaine et enregistrer des observations.','connector model scores?:o preference? notes? benchmark_score?:n benchmark_source? benchmark_name?',None,True)
register('model_capabilities','models','Capacités estimées des modèles par domaine (code, interface, debug, raisonnement, tests, documentation, automation, general), sur 10, avec leurs sources : notes de l’utilisateur (prioritaires), évaluations des projets, benchmarks publics, estimation d’une IA ; et l’ordre de préférence de l’utilisateur par domaine. Avec connector (et model) : un seul modèle.','connector? model?')
register('model_preferences','models','Choix de qualité, vitesse, coût et préférences de sélection.','priority instructions?',None,True)
register('refresh_benchmarks','models','Actualiser les résultats publiés en cache.',write=True)
register('local_catalog','local_models','Catalogue de modèles GGUF disponibles au téléchargement.')
register('local_state','local_models','Modèles installés, paramètres CPU/GPU, téléchargements, erreurs et progression.')
register('local_model_files','local_models','Lister les fichiers GGUF et tailles d’un dépôt Hugging Face.','repo')
register('local_runtime_install','local_models','Installer llama.cpp (backend cpu, vulkan, cuda) ou PrismML pour Bonsai 2 (prism-cpu, prism-vulkan, prism-cuda), sans remplacer le moteur standard. Retourne job_id, suivre local_state.','backend',None,True)
register('local_model_install','local_models','Télécharger un GGUF dans le dossier configuré et l’enregistrer dans CyAI. Retourne job_id, suivre local_state.','repo filename',None,True)
register('local_model_import_path','local_models','Importer un GGUF existant du dossier de travail dans CyAI.','project_id path','project_id',True)
register('local_settings','local_models','Réglages globaux : cpu/gpu/hybrid, couches, threads, contexte et dossier.','device? gpu_layers?:n threads?:n context?:n models_dir?',None,True)
register('local_model_settings','local_models','Exceptions par modèle ; settings accepte device, gpu_layers, threads, context et runtime_family (standard ou prism). Objet vide pour hériter des valeurs globales et détecter automatiquement le moteur.','id settings:o',None,True)
register('local_start','local_models','Charger un modèle installé ; suivre local_state.','id',None,True)
register('local_stop','local_models','Arrêter le moteur local et libérer sa mémoire.',write=True)
register('save_settings','application','Thème, budget de contexte, dossier des sauvegardes.','theme? context_chars?:n backup_dir?',None,True)
register('save_theme','application','Créer un thème personnalisé.','name bg panel text muted accent line',None,True)
register('set_storage','application','Programmer la migration du stockage au prochain redémarrage.','path',None,True,True)
register('job_cancel','application','Annuler une opération différée non exécutée.','id',None,True)
register('job_resume','application','Reprendre une opération interrompue ou en échec, après une nouvelle autorisation.','id',None,False)
register('job_status','application','Lire une opération différée autorisée.','id')

register('create_mission','missions','Préparer une mission sans la lancer ; steps contient connector, model, instruction, depends_on, ou profile_id pour appeler un profil de la bibliothèque.','conversation_id title? steps:l request_key? concurrency?:n timeout_seconds?:n','conversation_id',True)
register('mission_status','missions','Lire les étapes et événements de la mission.','mission_id after?:n','mission_id')
register('mission_result','missions','Lire le résultat complet de la mission.','mission_id','mission_id')
register('launch_mission','missions','Lancer une mission préparée, après la mission courante pour éviter une délégation récursive.','mission_id','mission_id',True,True)
register('continue_conversation','missions','Envoyer une instruction à un agent ; différé jusqu’à la fin de l’exécution courante.','conversation_id connector model? instruction request_key?','conversation_id',True,True)
register('pause_mission','missions','Mettre la chaîne en pause après les étapes actives.','mission_id','mission_id',True)
register('resume_mission','missions','Reprendre une chaîne en pause.','mission_id','mission_id',True,True)
register('cancel_mission','missions','Annuler une mission du projet.','mission_id','mission_id',True)
register('retry_mission','missions','Relancer une mission en échec après confirmation.','mission_id acknowledged:b timeout_seconds?:n concurrency?:n','mission_id',True,True)
register('search_history','conversations','Rechercher les messages et résultats dans les projets autorisés.','text project_id? connector? date_from? date_to? status?')

# Global agent library and per-project teams. Writes marked 'global' leave the project perimeter and need an explicit grant.
register('agent_profile_list','teams','GLOBAL · Lister la bibliothèque de profils d’agents, leurs révisions et leurs affectations.','','global')
register('agent_profile_get','teams','GLOBAL · Lire un profil, l’historique de ses révisions et ses affectations.','id','global')
register('agent_profile_save','teams','GLOBAL · Créer un profil ou enregistrer une nouvelle révision. helpers déclare les spécialistes qu’il pourra appeler pendant son travail, tools les plugins MCP qu’il pourra utiliser. Les équipes gardent leur révision figée.','id? name role? description? icon? skills?:a connector model? prompt? settings?:o helpers?:l tools?:a note?','global',True)
register('agent_profile_duplicate','teams','GLOBAL · Dupliquer un profil en profil indépendant.','id name?','global',True)
register('agent_profile_category','teams','GLOBAL · Ranger un profil dans une catégorie de la bibliothèque (vide pour le retirer). Sans effet sur ses révisions ni ses affectations.','id category','global',True)
register('agent_direct_message','conversations','Ouvrir une discussion privée avec un profil de la bibliothèque, hors de tout projet : espace de travail isolé, révision figée.','profile_id title?',None,True)
register('agent_profile_archive','teams','GLOBAL · Archiver ou réactiver un profil sans toucher aux affectations existantes.','id archived?:b','global',True)
register('team_get','teams','Lire l’équipe du projet : hiérarchie, révisions figées, problèmes bloquants et avertissements d’exécution.','project_id','project_id')
register('team_save','teams','Créer l’équipe du projet, la renommer ou déclarer sa composition prête. Ne lance aucune exécution.','project_id name? status?','project_id',True)
register('team_add_member','teams','Affecter un profil à l’équipe du projet avec un rôle et un responsable de la même équipe.','project_id profile_id role? responsibility? manager_id? revision?:n','project_id',True)
register('team_update_member','teams','Changer rôle, responsabilité, responsable, état actif, et surcharger localement nom, icône, description, compétences, connecteur, modèle, consignes ou réglages (overrides vide = retour à la révision figée).','project_id id role? responsibility? manager_id? active?:b overrides?:o reassign_to? acknowledged?:b','project_id',True)
register('team_remove_member','teams','Retirer ou supprimer une affectation, avec réaffectation explicite des subordonnés.','project_id id reassign_to? acknowledged?:b delete?:b','project_id',True)
register('team_revision_preview','teams','Comparer la révision figée d’une affectation avec une révision du profil global.','project_id id revision?:n','project_id')
register('team_adopt_revision','teams','Adopter explicitement une révision de profil pour une affectation de ce projet.','project_id id revision?:n','project_id',True)
register('team_template_list','teams','GLOBAL · Lister les modèles d’équipe réutilisables.','','global')
register('team_save_template','teams','GLOBAL · Enregistrer la composition de l’équipe du projet comme modèle réutilisable.','project_id name description? template_id?','global',True)
register('team_apply_template','teams','Appliquer un modèle d’équipe au projet : nouvelles affectations, sans tâches ni sessions du projet d’origine.','project_id template_id name? replace?:b','project_id',True)
register('team_template_delete','teams','GLOBAL · Supprimer un modèle d’équipe.','id','global',True)

# Task cards and reports of a project team. Project-scoped; none of them starts an agent.
register('task_list','tasks','Lister les cartes de tâches de l’équipe du projet, avec les statuts et les membres.','project_id','project_id')
register('task_get','tasks','Lire une carte : historique, dépendances bloquantes, sous-tâches, rapports et validateurs habilités.','project_id id','project_id')
register('task_create','tasks','Créer une carte de tâche « à préparer » ou « prête ». L’auteur est une affectation de l’équipe, ou l’utilisateur (by_user).','project_id objective author_id? by_user?:b assignee_id? parent_id? dependencies?:a file_scope? acceptance_criteria? deliverables? status?','project_id',True)
register('task_update','tasks','Modifier objectif, responsable, parent, dépendances, périmètre, critères ou livrables.','project_id id objective? assignee_id? parent_id? dependencies?:a file_scope? acceptance_criteria? deliverables?','project_id',True)
register('task_delete','tasks','Supprimer une carte ; confirmation requise si des sous-tâches ou dépendances y sont rattachées.','project_id id acknowledged?:b','project_id',True)
register('task_status','tasks','Changer le statut d’une carte. « Terminée » et « à corriger » passent par l’acceptation ou la demande de correction.','project_id id status author_id? by_user?:b reason?','project_id',True)
register('task_report','tasks','Rendre un rapport : résultat, fichiers modifiés, tests réellement exécutés, limites, risques, décisions demandées. Ne termine pas la tâche.','project_id id author_id result modified_files? executed_tests? limits? risks? requested_decisions?','project_id',True)
register('task_accept','tasks','Accepter une tâche en revue, avec les preuves examinées. Réservé à un responsable hiérarchique du responsable.','project_id id proofs author_id? by_user?:b','project_id',True)
register('task_correction','tasks','Renvoyer une tâche en revue vers une correction, avec le motif.','project_id id reason author_id? by_user?:b','project_id',True)
register('task_consult','tasks','Demander l’avis d’un agent de l’équipe sur une carte. Un avis ne déplace pas la tâche et ne transfère pas sa responsabilité.','project_id id consultant_id question author_id? by_user?:b','project_id',True)
register('task_consult_answer','tasks','Enregistrer l’avis rendu, ou son refus motivé. source=agent uniquement si l’agent a réellement répondu.','project_id id answer declined?:b source?','project_id',True)
register('team_conversation','teams','Ouvrir ou retrouver la conversation d’une affectation, éventuellement à propos d’une carte.','project_id member_id task_id?','project_id',True)
register('team_conversations','teams','Lister les conversations d’équipe du projet et désigner le chef de projet.','project_id','project_id')
register('profile_conversation','teams','Solliciter un profil directement dans une conversation ordinaire, sans composer d’équipe : un spécialiste appelé à la demande.','project_id profile_id title?','project_id',True)
register('task_execute','tasks','Lancer l’agent responsable sur une carte prête ou à corriger. Son compte rendu devra être examiné avant acceptation. Une carte qui tourne sans progresser exige acknowledged. cursors : réglages pour ce lancement, de 1 à 5 (autonomy, rigor, creativity, effort, detail), qui priment sur ceux de la carte et du projet.','project_id id acknowledged?:b cursors?:o','project_id',True,True)
register('team_autopilot_plan','tasks','Voir ce que ferait un tour de l’automate de délégation : cartes lançables, comptes rendus à faire relire, ce qui attend l’utilisateur. Rien n’est lancé.','project_id','project_id')
register('task_execution_cancel','tasks','Annuler une exécution en cours. Les effets déjà produits dans le projet ne sont pas annulés.','project_id id','project_id',True)
register('task_execution_pause','tasks','Mettre en pause une exécution en cours, ou la reprendre avec resume=true.','project_id id resume?:b','project_id',True)

# Scoped memory, evaluations and improvement proposals. Nothing here trains a model.
register('agent_memory_list','learning','Lire la mémoire des agents du projet, ou celle d’un profil global (scope=profile).','scope? project_id? profile_id?','project_id')
register('agent_memory_save','learning','Enregistrer une observation locale d’une affectation, ou une mémoire transférable d’un profil (avec sources).','scope content id? project_id? member_id? profile_id? category? source_ids?:a transferable?:b origin?','project_id',True)
register('agent_memory_delete','learning','Supprimer une mémoire d’agent.','id','project_id',True)
register('team_scorecard','teams','Bilan de l’équipe du projet : pour chaque agent, cartes (acceptées, échouées, en revue), exécutions, moyennes des évaluations et derniers bilans de ses supérieurs ; curseurs du projet. Des faits et des jugements, pas un classement.','project_id','project_id')
register('member_assess','teams','Rédiger le bilan d’un agent que vous encadrez (chef : tous) : verdict reliable|watch|reassign|adapt|replace, points forts, points faibles, recommandation, sources. L’agent le lira dans son contexte.','project_id member_id verdict author_id? by_user?:b strengths? weaknesses? recommendation? source_ids?:a','project_id',True)
register('task_reassign','teams','Réaffecter les cartes ouvertes d’un agent que vous encadrez à un autre agent de l’équipe (toutes, ou task_ids), avec le motif inscrit sur chaque carte.','project_id member_id to_member_id author_id? by_user?:b task_ids?:a reason?','project_id',True)
register('team_replace_member','teams','Remplacer un agent que vous encadrez par un autre profil de la bibliothèque, à la même place : même rôle, même responsable, mêmes agents encadrés, cartes ouvertes reprises. L’ancienne affectation est retirée, pas supprimée.','project_id member_id profile_id author_id? by_user?:b reason?','project_id',True)
register('team_cursors_set','teams','Régler les curseurs du projet (chef de projet ou utilisateur) : autonomy, rigor, creativity, effort, detail, de 1 à 5 ; absent ou 0 = non réglé.','project_id cursors:o author_id? by_user?:b','project_id',True)
register('task_cursors_set','teams','Régler les curseurs d’une carte (son auteur, un supérieur de son responsable ou l’utilisateur) : autonomy, rigor, creativity, effort, detail, de 1 à 5.','project_id id cursors:o author_id? by_user?:b','project_id',True)
register('task_evaluate','learning','Noter le travail rendu sur une carte : critères de 1 à 5 et commentaire obligatoire. Un agent n’évalue pas son propre travail.','project_id id scores:o comment author_id? by_user?:b','project_id',True)
register('improvement_propose','learning','Proposer une amélioration des consignes ou une mémoire transférable d’un profil, avec motif et sources.','project_id member_id profile_id kind proposed_value rationale source_ids:a','project_id',True)
register('improvement_decide','learning','Adopter ou écarter une proposition. L’adoption crée une révision ; les équipes l’adoptent ensuite explicitement.','id adopt?:b decision?','project_id',True)
register('improvement_list','learning','Lister les propositions d’amélioration d’un projet ou d’un profil.','project_id? profile_id?','project_id')
register('profile_track_record','learning','GLOBAL · Bilan enregistré du travail d’un profil : tâches, acceptations, exécutions, moyennes d’évaluation et compétences attestées. Agrégats seulement.','profile_id','global')
register('skill_attest','learning','GLOBAL · Attester une compétence déclarée d’un profil, en citant des tâches acceptées ou des évaluations de son travail.','profile_id skill source_ids:a note?','global',True)
register('skill_withdraw','learning','GLOBAL · Retirer une attestation de compétence.','profile_id skill','global',True)

# Reusable methods: a named chain of specialists with the artefacts that pass between them.
register('evaluation_method_install','methods','GLOBAL · Installer le protocole fourni d’évaluation des agents dans la bibliothèque. Préserve les modifications existantes. Ne lance aucun test ; le contexte long exige un accord explicite.','','global',True)
register('evaluation_prepare','methods','Préparer un benchmark en arrière-plan, invisible dans la liste des discussions : 12 exercices par candidat, sessions neuves et contexte sans mémoire CyAI ni réponses des autres candidats. candidates contient connector, model, name facultatif. Utiliser launch_mission puis evaluation_results. Jamais de contexte long.','conversation_id candidates:l form? concurrency?:n request_key?','conversation_id',True)
register('method_test_run','methods','Lancer un test de méthode déjà préparé, dans une session interne rattachée à conversation_id. Respecte les autorisations de cette conversation ; la fin réveille automatiquement l’agent appelant. Pour un benchmark indépendant de modèles, préférer evaluation_prepare puis launch_mission.','test_id conversation_id connector? model? concurrency?:n','conversation_id',True)
register('method_run_evaluate','methods','Faire évaluer un test terminé par le connecteur et modèle choisis ; les résultats reviennent automatiquement. La note reste identifiée comme un jugement IA.','run_id connector model?','run_id',True)
register('evaluation_results','methods','Lire les réponses brutes d’un benchmark et leurs notes automatiques ; needs_review exige le jugement de l’évaluateur.','mission_id','mission_id')
register('evaluation_guides','methods','GLOBAL · Lire les modes d’emploi issus des évaluations d’un profil, auteurs et dates, sans les corrigés. Vérifier les conditions avant délégation.','profile_id','global')
register('evaluation_report_save','methods','GLOBAL · Associer un rapport JSON signé par son auteur déclaré et daté à un profil. Ne modifie pas ses consignes.','profile_id report:o','global',True)
register('method_list','methods','GLOBAL · Lister les méthodes réutilisables et l’état des profils qu’elles emploient. Avec profile_id : les méthodes que ce profil doit utiliser, puis celles qu’il préfère, viennent en premier (champ preference).','profile_id?','global')
register('method_get','methods','GLOBAL · Lire une méthode complète (tâches, positions dans l’éditeur, prompt de base, prérequis) et ses avertissements pour cette machine.','id','global')
register('method_check','methods','GLOBAL · Avertissements d’une méthode sur cette machine : profils, connecteurs, plugins et logiciels manquants. N’empêche rien.','id','global')
register('method_save','methods','GLOBAL · Créer ou modifier une méthode (graphe de nœuds, comme un blueprint). Chaque élément de steps : {key, name, description?, kind: "task"|"method", depends_on: [clés] (ordre seul), position: {x, y}}. Une tâche (kind task) : instruction (peut contenir {objectif}), executor: "profile"|"any"|"connector", profile_id si profile, connector et model si connector, helpers: [profile_id appelables], receives: "inputs" (ses entrées branchées seules, recommandé) ou "chain" (toute la conversation de la chaîne), inputs: [{key, name, kind: text|context|file, source: {step: clé de tâche ou "@entrees", port: clé de broche}}], outputs: [{key, name, kind: text|context|file, description?, path si file (relatif au projet)}], attachments: [identifiants des fichiers joints à la méthode], adaptations: {"connecteur:modèle": précisions ajoutées quand ce modèle exécute la tâche}. Plusieurs sorties texte sont rédigées sous « ### Sortie : nom » et chaque entrée ne reçoit que sa section. Une sous-méthode (kind method) : method_id, et inputs [{key, source}] pour brancher ses entrées. Méthode : inputs [{key, name, kind, description, required, prepare (comment préparer ce contexte)}] — objectif est toujours présent —, outputs [{key, name, kind, source}], usage (mode d’emploi pour l’IA qui applique la méthode), preprompt (placé devant chaque tâche de cette méthode), requirements [{kind: software|plugin|connector|note, name, executable?, detail?}], layout {in: {x,y}, out: {x,y}}, options {proposals: true pour inviter les agents à finir leurs réponses par « ### Proposition d’amélioration »}, note (note de version). Pas de boucle ; chaque enregistrement est gardé comme version.','name steps:l id? description? usage? preprompt? category? requirements?:l inputs?:l outputs?:l layout?:o options?:o note?','global',True)
register('method_export','methods','GLOBAL · Exporter une méthode en fichier autonome, avec la définition des profils qu’elle utilise. Aucun secret n’y figure.','id','global')
register('method_as_skill','methods','Ajouter une méthode comme skill d’un projet (project_id) ou d’une conversation (conversation_id) : n’importe quelle IA de ce périmètre la reçoit comme recette à suivre. La réajouter la remplace.','id project_id? conversation_id?',None,True)
register('method_import','methods','GLOBAL · Importer un export de méthode. Ce qui manque ici devient un avertissement ; create_profiles=false confie à n’importe quelle IA les tâches dont le profil est absent.','data:o create_profiles?:b','global',True)
register('method_delete','methods','GLOBAL · Supprimer une méthode.','id','global',True)
register('method_from_mission','methods','GLOBAL · Transformer une chaîne qui a fonctionné en méthode réutilisable ; profiles associe chaque étape à un profil.','mission_id name? description? profiles:o','global',True)
register('method_apply','methods','Préparer une méthode dans sa propre conversation, pour un objectif donné. La chaîne n’est pas lancée. inputs : {clé: texte} pour ses autres entrées (contextes, textes) ou {clé: chemin relatif au projet} pour une entrée fichier — lisez son mode d’emploi (usage) et la préparation de chaque entrée avec method_get. connector et model : l’IA des tâches confiées à n’importe quelle IA.','project_id id objective inputs?:o concurrency?:n connector? model?','project_id',True)
register('profile_methods','methods','GLOBAL · Méthodes liées à un profil : préférées, à utiliser, et la note d’usage de l’agent pour chacune, avec les logiciels requis et leur présence sur cette machine.','profile_id','global')
register('method_agents','methods','GLOBAL · Profils liés à une méthode (préférée ou à utiliser) et leurs notes d’usage.','id','global')
register('profile_method_set','methods','GLOBAL · Lier une méthode à un profil : mode preferred (préférée, proposée en premier), always (à utiliser pour ce type de travail) ou none (retirer ; la note est gardée).','profile_id method_id mode','global',True)
register('method_note_save','methods','GLOBAL · Écrire votre propre note d’usage d’une méthode (Markdown) : ce qui marche, les pièges, ce que vous vérifiez. Un agent n’écrit que la note de son propre profil ; l’utilisateur la voit depuis la méthode et depuis la fiche. Contenu vide = effacer.','profile_id method_id content','global',True)
register('method_tests','methods','GLOBAL · Tests d’une méthode (objectif, entrées, attendu) et leurs dernières exécutions avec leurs notes.','id','global')
register('method_test_save','methods','GLOBAL · Créer ou modifier un test d’une méthode : name, objective, inputs {clé: texte}, expected (critères de réussite). Enregistré avec la méthode, hors du contexte des agents. Le lancer reste réservé à l’utilisateur.','method_id name objective id? inputs?:o expected?','global',True)
register('method_runs','methods','GLOBAL · Exécutions de tests, évaluations, vérifications de compréhension, affinages et propositions d’amélioration d’une méthode, avec leurs résultats.','id kind?','global')
register('method_proposals','methods','GLOBAL · Propositions d’amélioration écrites par les agents à la fin de leurs tâches dans les chaînes d’une méthode, avec leurs examens.','id','global')
register('method_history','methods','GLOBAL · Versions enregistrées d’une méthode (numéro, origine, note, date).','id','global')
register('method_restore','methods','GLOBAL · Rétablir une version antérieure d’une méthode ; elle devient une nouvelle version, rien n’est effacé.','id revision:n','global',True)

# The project seen as a server: typed channels and what each agent is really doing.
register('project_assistant','conversations','Ouvrir ou créer la conversation « Assistant du projet » : l’assistant qui aide à mettre le projet en place (présentation, consignes, équipe, premières cartes).','project_id','project_id',True)
register('project_channels','channels','Lister les salons typés du projet (conversations, board, équipe, mémoire, épinglés, médias) et la présence réelle des agents : exécution en cours, attente d’autorisation, au repos, connecteur indisponible.','project_id','project_id')
register('space_create','channels','Créer un salon dans le projet. type=whiteboard (tableau blanc : notes et liens) ou graph (graphe calculé ; source=tasks pour les tâches et leurs dépendances, team pour la hiérarchie) ou plugin (console des outils de lecture du plugin donné).','project_id name? type? source? plugin?','project_id',True)
register('plugin_console','channels','Lire une console de plugin : outils de lecture disponibles et historique des appels.','project_id id','project_id')
register('plugin_console_call','channels','Appeler un outil de lecture du plugin d’une console ; l’appel et son résultat rejoignent l’historique du salon.','project_id id tool arguments?:o','project_id',True)
register('graph_data','channels','Lire un salon graphe : nœuds et arêtes calculés maintenant à partir du board ou de l’équipe.','project_id id','project_id')
register('space_get','channels','Lire un salon créé : pour un tableau blanc, ses notes {id, x, y, text, color} et ses liens {from, to, label}, avec updated_at.','project_id id','project_id')
register('space_rename','channels','Renommer un salon créé.','project_id id name','project_id',True)
register('space_delete','channels','Supprimer un salon créé et son contenu.','project_id id','project_id',True)
register('whiteboard_save','channels','Enregistrer le contenu complet d’un tableau blanc. data={notes:[{id, x, y, text, color: yellow|blue|green|pink|violet|grey}], links:[{from, to, label?}]}. base : le updated_at lu avec space_get ; si le tableau a changé depuis, rien n’est écrasé.','project_id id data:o base?','project_id',True)
register('project_pins','channels','Lister les notes proposées en mémoire depuis un message, avec leur conversation d’origine.','project_id','project_id')
register('project_media','channels','Lister les médias joints aux conversations du projet.','project_id','project_id')

USER_ONLY={'approve':'Décisions d’autorisation : seul l’utilisateur peut approuver.', 'team_autopilot_step':'Lancer un tour de l’automate de délégation engage des dépenses : réservé à l’utilisateur.', 'team_autopilot_set':'Activer l’automate de délégation et fixer son budget : réservé à l’utilisateur.', 'team_autopilot_options':'Inviter ou non les relecteurs à proposer des améliorations : réservé à l’utilisateur.', 'software_path_set':'Indiquer où se trouve un logiciel sur cette machine modifie la configuration : réservé à l’utilisateur.', 'method_check_understanding':'Une vérification de compréhension appelle un modèle : réservée à l’utilisateur.', 'method_refine_for_model':'Un affinage fait dialoguer deux modèles : réservé à l’utilisateur.', 'method_improve':'Demander une amélioration à une IA engage des dépenses : réservé à l’utilisateur.', 'method_improvement_adopt':'Adopter une proposition est une décision de l’utilisateur.', 'method_adaptation_set':'Garder des précisions pour un modèle est une décision de l’utilisateur.', 'method_run_rate':'Noter un test est le jugement de l’utilisateur.', 'method_loop_start':'Une boucle d’affinage engage des dépenses répétées : réservée à l’utilisateur.', 'method_loop_stop':'Arrêter une boucle est une décision de l’utilisateur.', 'method_proposal_review':'Faire examiner une proposition par un modèle engage des dépenses : réservé à l’utilisateur.', 'method_proposal_adopt':'Adopter une proposition est une décision de l’utilisateur.', 'method_proposal_dismiss':'Écarter une proposition est une décision de l’utilisateur.', 'model_preference_order':'L’ordre de préférence des modèles est un choix de l’utilisateur.', 'model_estimate':'Demander une estimation à une IA engage une dépense : réservé à l’utilisateur.', 'approval_settings':'L’agent ne peut pas modifier ses propres autorisations.',
 'approve_plan':'Lancement d’un plan réservé à l’utilisateur.', 'restore':'Restauration globale remplaçant les données : interface utilisateur.',
 'plugin_save':'Installation de nouveaux plugins et clés : interface utilisateur.', 'connect_claude':'Authentification personnelle : interface utilisateur.',
 'choose_project_folder':'Dialogue Windows : fournir un chemin dans les outils de configuration.', 'backup':'Export global hors périmètre : interface utilisateur. Utiliser export par conversation.'}
TOOLS=[{'name':'cyai_actions','description':'Découvrir les actions CyAI et leurs schémas par domaine. Commencer ici pour gérer le logiciel, les modèles locaux, la mémoire ou les skills sans navigateur.',
        'inputSchema':{'type':'object','properties':{'domain':S},'additionalProperties':False},'annotations':{'readOnlyHint':True}},
       {'name':'cyai_call','description':'Exécuter une action annoncée par cyai_actions. Les écritures demandent une autorisation dans CyAI ; les opérations différées retournent un job_id. Ne jamais piloter le navigateur pour une action CyAI disponible ici.',
        'inputSchema':{'type':'object','properties':{'action':{'type':'string','enum':list(ACTIONS)},'arguments':O},'required':['action'],'additionalProperties':False},'annotations':{'readOnlyHint':False,'destructiveHint':True}}]

def validate(schema,args):
    errors=list(Draft202012Validator(schema).iter_errors(args))
    if errors:raise ValueError('Arguments invalides : '+errors[0].message)

GLOBAL_REFUSAL=('Opération sur la bibliothèque globale d’agents : ce client MCP est limité à ses projets. '
                'Ajoutez --allow-global à sa configuration pour autoriser les écritures globales ; la portée n’est jamais élargie implicitement.')

def check_scope(s,op,args,projects,allow_global=False):
    allowed=set(projects)
    if not allowed:raise ValueError('Aucun projet autorisé.')
    if op['scope']=='global' and op['write'] and not allow_global:raise ValueError(GLOBAL_REFUSAL)
    def project(id):
        if id not in allowed:raise ValueError('Projet hors périmètre MCP.')
        s.store.one('SELECT id FROM projects WHERE id=?',(id,))
    def conversation(id):project(s.project_for_conversation(id)['id'])
    if 'project_id' in args:project(args['project_id'])
    if 'conversation_id' in args:conversation(args['conversation_id'])
    if 'mission_id' in args:conversation(s.store.one('SELECT conversation_id FROM missions WHERE id=?',(args['mission_id'],))['conversation_id'])
    if op['scope']=='run_id':conversation(s.store.one('SELECT conversation_id FROM method_runs WHERE id=?',(args['run_id'],))['conversation_id'])
    scope=op['scope']
    if scope=='project:id':project(args['id'])
    if scope=='conversation:id':conversation(args['id'])
    if scope in {'settings','organize'}:
        kind=args.get('scope',args.get('kind'))
        if kind=='project':project(args['id'])
        elif kind=='conversation':conversation(args['id'])
        else:raise ValueError('Portée invalide.')
    if op['name']=='reorder':
        if args['kind']=='project':
            if len(args['ids'])!=len(set(args['ids'])) or set(args['ids'])!=allowed:raise ValueError('Fournissez chaque projet autorisé une seule fois.')
        elif args['kind']!='conversation' or not args.get('project_id'):raise ValueError('Projet et type de réordonnancement requis.')
    if op['name']=='agent_settings' and 'approval_mode' in args['settings']:raise ValueError('Les autorisations sont réservées à l’utilisateur.')

def public_state(s,projects):
    state=s.state()
    conversations=[c for c in state['conversations'] if c['project_id'] in projects];ids={c['id'] for c in conversations}
    return {**{k:state[k] for k in ['connectors','settings','data_dir','pending_data_dir','context_chars','version']},
            'projects':[p for p in state['projects'] if p['id'] in projects], 'conversations':conversations,
            'missions':[m for m in state['missions'] if m['conversation_id'] in ids]}

def execute(s,name,args,projects):
    if name=='reorder' and args['kind']=='project':
        ordered=iter(args['ids'])
        ids=[next(ordered) if r['id'] in projects else r['id'] for r in s.store.rows('SELECT id FROM projects ORDER BY position,created_at')]
        return s.action(name,{**args,'ids':ids})
    if name=='search_history':return [r for r in s.search(args) if r['project_id'] in projects]
    if name in {'mission_status','mission_result'}:return s.mission(args['mission_id'],args.get('after',0))
    if name=='create_mission':return s.action(name,{**args,'launch':False})
    if name=='agent_settings' and args['scope']=='conversation':
        existing=json.loads(s.store.one('SELECT agent_settings FROM conversations WHERE id=?',(args['id'],))['agent_settings'])
        if 'approval_mode' in existing:args={**args,'settings':{**args['settings'],'approval_mode':existing['approval_mode']}}
    if name=='get_state':return public_state(s,projects)
    if name=='get_settings':return {k:public_state(s,projects)[k] for k in ['settings','data_dir','pending_data_dir','context_chars']}
    if name=='get_project':return s.project(args['project_id'])
    if name=='get_conversation':return s.conversation(args['conversation_id'])
    if name=='get_memory':return s.memory(args['project_id'])
    if name=='get_logs':
        rows=s.store.rows('SELECT e.* FROM events e JOIN missions m ON m.id=e.mission_id JOIN conversations c ON c.id=m.conversation_id WHERE c.project_id=? ORDER BY e.seq DESC LIMIT 200',(args['project_id'],))
        return rows
    if name in {'job_status','job_cancel'}:
        row=s.store.one('SELECT * FROM mcp_jobs WHERE id=?',(args['id'],))
        if not set(json.loads(row['projects'])).issubset(set(projects)):raise ValueError('Opération hors périmètre.')
        if name=='job_cancel':
            if row['status'] not in {'pending','interrupted','failed'}:raise ValueError('Opération déjà exécutée ou active.')
            s.store.execute("UPDATE mcp_jobs SET status='cancelled' WHERE id=?",(row['id'],));return {'ok':True}
        return {k:row[k] for k in ['id','action','status','result','created_at']}
    if name=='local_model_import_path':
        import shutil
        from .security import scoped_path
        source=scoped_path(s.project(args['project_id'])['root'],args['path'])
        if source.suffix.lower()!='.gguf':raise ValueError('Fichier GGUF requis.')
        with source.open('rb') as f:
            if f.read(4)!=b'GGUF':raise ValueError('GGUF invalide.')
        def copy(progress):
            target=s.local_models.folder()/source.name;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():raise ValueError('Un modèle de ce nom existe déjà.')
            shutil.copy2(source,target);s.local_models.add(target,source.stem)
        return s.local_models.job('Import '+source.name,copy)
    if name=='plugin_catalog':
        p=s.plugins.plugin(args['id'],args['project_id'])
        return {'tools':s.plugins.rpc(p,'tools/list',{}).get('tools',[]),'resources':s.plugins.catalog(args['id']).get('resources',[])}
    if name=='plugin_read':return s.plugins.read(args['id'],args['project_id'],args.get('tool'),args.get('arguments'),args.get('resource'))
    if name=='plugin_call':
        p=s.plugins.plugin(args['id'],args['project_id']);values=dict(args.get('arguments',{}))
        if p.get('project_parameter'):
            external=p.get('projects',{}).get(args['project_id'],{}).get('external_project_id')
            if not external:raise ValueError('Associez le projet au plugin avant cet appel.')
            values[p['project_parameter']]=external
        tools=s.plugins.rpc(p,'tools/list',{}).get('tools',[])
        definition=next((t for t in tools if t['name']==args['tool']),None)
        if not definition:raise ValueError('Outil absent du plugin.')
        validate(definition['inputSchema'],values)
        return s.plugins.rpc(p,'tools/call',{'name':args['tool'],'arguments':values})
    result=s.action(name,args)
    if name=='create_project':projects.append(result['id'])
    if name in ('create_free_conversation','agent_direct_message'):projects.append(result['project_id'])
    return result

def call(s,name,args,projects,control=None,allow_write=False,allow_global=False):
    definition=next((t for t in TOOLS if t['name']==name),None)
    if not definition:raise ValueError('Outil MCP inconnu.')
    validate(definition['inputSchema'],args)
    # An in-app agent has no standing global grant: each global write is authorized interactively by the user.
    globals_allowed=bool(allow_global or control)
    if name=='cyai_actions':
        return {'actions':[v for v in ACTIONS.values() if not args.get('domain') or v['domain']==args['domain']],
                'user_only':USER_ONLY,'project_ids':projects,'writes':bool(control or allow_write),'global_writes':globals_allowed,
                'instruction':'Utiliser ces actions directement, sans navigateur. Une tâche différée doit être suivie avec job_status. Un téléchargement se suit avec local_state.'
                              +('' if globals_allowed else ' Les écritures de la bibliothèque globale d’agents (domaine teams, description GLOBAL) sont refusées pour ce client.')}
    action=args['action'];values=args.get('arguments',{});op=ACTIONS[action]
    validate(op['inputSchema'],values);check_scope(s,op,values,projects,globals_allowed)
    if action=='method_note_save':
        # An agent writes its own note only; the note says it was written by an agent.
        conversation=getattr(control,'conversation_id',None)
        if conversation:
            row=s.store.one('SELECT member_id,profile_id FROM conversations WHERE id=?',(conversation,))
            own=row['profile_id'] or (s.store.rows('SELECT profile_id FROM team_members WHERE id=?',(row['member_id'],)) or [{}])[0].get('profile_id') if row['member_id'] or row['profile_id'] else None
            if own and own!=values['profile_id']:raise ValueError('Un agent n’écrit que la note de son propre profil.')
            values={**values,'author':'agent'}
    if action=='job_resume':
        job=execute(s,'job_status',values,projects)
        if job['status'] not in {'failed','interrupted'}:raise ValueError('Seule une opération interrompue ou en échec peut être reprise.')
        row=s.store.one('SELECT args FROM mcp_jobs WHERE id=?',(values['id'],))
        return call(s,'cyai_call',{'action':job['action'],'arguments':json.loads(row['args'])},projects,control,allow_write,allow_global)
    if op['write']:
        if control:
            if getattr(control,'planning',False):raise ValueError('La planification ne peut pas modifier CyAI.')
            control.check()
            if not control.approve({'provider':'CyAI MCP','tool':action,'scope':'bibliothèque globale' if op['scope']=='global' else 'projet','request':{'reason':op['description'],'arguments':values}}):raise ValueError('Action refusée par l’utilisateur.')
        elif not allow_write:raise ValueError('Client MCP en lecture seule. Autorisez --allow-write lors de sa configuration pour modifier CyAI.')
        from .conversation_queue import busy
        source = getattr(control,'conversation_id',None)
        if op['deferred'] and (busy(s,source) if source else s.store.rows("SELECT id FROM missions WHERE status IN ('running','awaiting_approval','queued')")):
            id=uid()
            s.store.execute('INSERT INTO mcp_jobs(id,action,args,projects,status,result,created_at,conversation_id) VALUES(?,?,?,?,?,?,?,?)',(id,action,json.dumps(values),json.dumps(projects),'pending',None,now(),getattr(control,'conversation_id',None)))
            return {'job_id':id,'status':'pending','message':'Action autorisée, programmée après votre réponse. Un retour automatique dans cette conversation suivra la fin des missions déléguées.'}
    result=execute(s,action,values,projects)
    source=getattr(control,'conversation_id',None)
    if source and action in {'create_conversation','create_free_conversation'}:
        original=s.store.one('SELECT agent_settings FROM conversations WHERE id=?',(source,))
        mode=json.loads(original['agent_settings']).get('approval_mode',s.engine.approval_default)
        s.store.execute('UPDATE conversations SET agent_settings=? WHERE id=?',(json.dumps({'approval_mode':mode}),result['id']))
    if action in {'launch_mission','continue_conversation','method_test_run','method_run_evaluate'}:
        from .conversation_queue import track
        track(s,source,result)
    s.store.log('info','mcp.'+action,'Action MCP terminée.')
    return s.engine.secrets.redact(result)

def init_jobs(s):
    s.store.execute('CREATE TABLE IF NOT EXISTS mcp_jobs(id TEXT PRIMARY KEY,action TEXT,args TEXT,projects TEXT,status TEXT,result TEXT,created_at TEXT)')
    if 'conversation_id' not in {r['name'] for r in s.store.rows('PRAGMA table_info(mcp_jobs)')}:s.store.execute('ALTER TABLE mcp_jobs ADD COLUMN conversation_id TEXT')
    s.store.execute("UPDATE mcp_jobs SET status='interrupted' WHERE status IN ('running','pending')")

def drain(s):
    with s.engine.lock:
        from .conversation_queue import busy, track
        for job in s.store.rows("SELECT * FROM mcp_jobs WHERE status='pending' ORDER BY created_at"):
            if busy(s,job['conversation_id']) if job['conversation_id'] else s.store.rows("SELECT id FROM missions WHERE status IN ('running','awaiting_approval','queued')"):continue
            s.store.execute("UPDATE mcp_jobs SET status='running' WHERE id=?",(job['id'],))
            try:
                args=json.loads(job['args']);projects=json.loads(job['projects'])
                check_scope(s,ACTIONS[job['action']],args,projects)
                result=execute(s,job['action'],args,projects);status='succeeded'
            except Exception as exc:result={'error':str(exc)};status='failed'
            if job['action'] in {'launch_mission','continue_conversation','method_test_run','method_run_evaluate'}:
                track(s,job['conversation_id'],result,result.get('error') if status=='failed' else None)
            s.store.execute('UPDATE mcp_jobs SET status=?,result=? WHERE id=?',(status,json.dumps(s.engine.secrets.redact(result)),job['id']))


def resources(s,projects):
    return [{'uri':'cyai://project/'+p+'/'+kind,'name':kind+' · '+p,'mimeType':'application/json'} for p in projects for kind in ['overview','memory','conversations']]

def resource_read(s,projects,uri):
    known={r['uri'] for r in resources(s,projects)}
    if uri not in known:raise ValueError('Ressource hors périmètre.')
    _,project,kind=uri.removeprefix('cyai://').split('/')
    value=s.project(project) if kind=='overview' else s.memory(project) if kind=='memory' else s.project(project)['conversations']
    return {'contents':[{'uri':uri,'mimeType':'application/json','text':json.dumps(s.engine.secrets.redact(value),ensure_ascii=False)}]}
