## 0.2.60

- Paquet Windows allégé : CLI Claude Code et codec FFmpeg installés séparément depuis Téléchargements, avec progression et vérification des empreintes. Réutilisation du CLI déjà installé et cache utilisateur pour la vidéo CyAnnota.
- Compilation portable depuis une recette versionnée ; contrôle du contenu du paquet pour garder modèles, environnements ML et données locales hors de l’installateur.
- Exemples et chemins par défaut portables ; dossiers de compilation, modèles téléchargés et traces de développement exclus de Git. Vérification reproductible des fichiers candidats et de l’historique disponible dans le workflow du dépôt.

## 0.2.59

- Envoi : la réponse du service ne vide plus le texte saisi entre-temps ni le brouillon d’une autre conversation. Paramètres et pièces jointes figés au clic, doubles envois empêchés pendant l’accusé de réception ; état « Envoi en cours » visible.
- Brouillons : les pièces jointes sélectionnées suivent désormais le texte de chaque conversation, dans la session de la fenêtre. Transferts et fichiers sauvegardés depuis CyMD/CyAnnota restent sélectionnés dans leur conversation d’origine, même après navigation.
- Navigation : une ancienne lecture de conversation, de mission ou de section projet ne remplace plus le choix récent. Les chargements et erreurs de conversation/projet sont indiqués avec reprise possible.
- Logs : les onglets restent utilisables pendant une lecture ; les réponses tardives ne réaffichent plus un ancien journal. Navigation et erreurs restent visibles pendant le chargement.
- Actualisation : les demandes forcées attendent la fin de la lecture en cours au lieu d’être perdues. Une erreur d’affichage n’est plus annoncée comme une déconnexion. Démarrage protégé contre des brouillons JSON invalides dans le navigateur.
- Validation : tests JavaScript avec réponses retardées, parcours dans une instance jetable et tests Python ciblés. Détails dans ui-ux-improvements-0.2.59.md.

## 0.2.58

- Audit UI/UX : navigation des paramètres commune à tous les catalogues, catégories Voix/Téléchargements/CyTools rétablies dans la liste des modèles, rail et panneaux adaptés aux petites fenêtres. Bouton Fermer ancré dans le panneau.
- Correction du parcours Équipe sans équipe créée ; retrait des anciennes mentions « lot 2 ». Cadrage initial des nouvelles méthodes.
- Compositeur : Inspecter le contexte ne soumet plus le message. Aucune limite de contexte attribuée au fournisseur quand il n’en annonce pas ; plafond HTML obsolète retiré des réglages locaux.
- Formulaires : état d’enregistrement visible, fermeture protégée contre les réponses asynchrones anciennes, reprise après erreur du chargement local. Menu des fichiers utilisable au clavier.
- Voix : détection Windows en arrière-plan, sélection conservée pendant la découverte, options de moteurs masquées sans bloquer la validation ni écraser leurs réglages. Clonage repliable et arrêt de lecture disponible dans les paramètres.
- Phonon ajouté : fermion-research 0.2.15 dans un Python/PyTorch CPU isolé ; Phonon-2 (anglais) et Phonon-2.5 (25 langues dont français). Cache et poids locaux, worker gardé chargé entre les dictées, libération à l’inactivité. Signalement explicite des transcriptions tronquées.
- Contraste des notifications, compteurs, jauges et graphiques en thème clair ; focus clavier visible. Lectures automatiques de suivi retirées du journal des actions, erreurs conservées.
- Validation : parcours dans une instance jetable, tests automatiques et transcriptions réelles de deux phrases synthétiques anglaise/française. Détails dans ui-ux-audit-0.2.58.md.

## 0.2.57

- Estimations vocales : orange pour une marge faible (chargement autorisé), rouge uniquement lorsque la VRAM totale est inférieure au minimum estimé. Aucun blocage de lancement fondé sur ces estimations.
- Boutons des voix : retour immédiat lors du téléchargement, de la vérification, de l’enregistrement et de l’essai. Progression et erreurs affichées dans la carte du modèle, même pendant la saisie des réglages.
- Suivi de la synthèse / lecture dans les paramètres jusqu’à sa fin ou son erreur.

## 0.2.56

- CyAnnota embarqué mis à jour vers la compilation locale 0.4.0 du 20 septembre : annotations image, vidéo et 3D. Sources, licences et provenance du bundle actualisées.
- Exports : conservation des modèles 3D comme pièces jointes en plus de l’archive, des captures et des consignes. Le protocole d’ouverture directe reste image/vidéo/projet ; importer un mesh dans l’éditeur ou rouvrir un projet CyAnnota.
- Bouton Fermer/Échap retiré des vues Logs et Agents ; correction CSS de `[hidden]` qui pouvait laisser le bouton visible. Rail permanent conservé.
- Validation : cinq tests CyAnnota (bundle, garde d’import CyAI, archives et octets des modèles). Éditeur vérifié en iframe : version 0.4.0, connexion CyAI et bouton d’import 3D présents. Pas d’exécution d’agent ni de redémarrage de l’application en cours.

## 0.2.55

- La capacité affichée indique sa provenance : contexte annoncé pour la session ou métadonnées du catalogue. Les 258 400 observés proviennent réellement de `thread/tokenUsage/updated.tokenUsage.modelContextWindow`, vérifié dans le journal local (entrée 187 338, sortie 202).
- Visualiseur : cinq fonds et quatre éclairages (studio PBR, doux, contrasté, jour), exposition et rotation. Réflexions procédurales PMREM, tone mapping ACES, matériaux GLB/glTF conservés. Les restrictions sur textures externes et Draco restent inchangées.
- Logs : onglets à la place des conversations, rail des projets toujours présent.
- Validation en navigateur isolé : nouveau panneau Logs, chargement du mesh, contrôles de scène et changement réel du fond. Tests médias et syntaxe JavaScript.

## 0.2.54

- Jauges de ressources rendues en SVG compatibles avec la politique CSP : anneaux et pourcentages verts, orange à 75 %, rouges à 90 %. Mesure absente en gris. Inclut les améliorations de la 0.2.53.

## 0.2.53

- Rail de navigation permanent dans les paramètres, la bibliothèque et les méthodes.
- CyTools séparés des plugins, dans une rubrique dédiée des paramètres et une section distincte du projet. Serveurs locaux dans MCP.
- Logs avec navigation verticale : journal, RAW JSON (secrets masqués), opérations MCP, connecteurs, courbes de ressources. Opérations MCP retirées des paramètres.
- Historique en mémoire des 720 derniers échantillons : CPU, RAM, GPU, VRAM, moteur local et CyAI ; environ une heure pendant l’utilisation, réinitialisé au démarrage.
- Menu clic droit sur les médias et liens de fichiers : Explorateur, application externe, copie du lien.
- Tokens plus contrastés et capacité de contexte issue des métadonnées ou événements du fournisseur ; non fournie si absente. Aucun quota ou contexte distant inventé.
- Vérification dans une instance isolée : rail visible dans les paramètres, onglets Logs, courbes et menu contextuel. Tests médias et contrôles d’inférence ; syntaxe JavaScript.

## 0.2.52

- Aperçu 3D local : GLB, glTF autonome, OBJ (géométrie), STL et PLY. Rotation, zoom, déplacement, recentrage et filaire ; libération des ressources à la fermeture. Three.js r180 intégré avec sa licence MIT (https://github.com/mrdoob/three.js/tree/r180).
- Liens médias locaux hors espace de conversation accessibles depuis l’interface, tout en conservant les exclusions de fichiers protégés. La politique des outils de fichiers des agents reste séparée.
- Ouverture avec l’association Windows et sélection dans l’Explorateur disponibles. Une absence d’association Windows est explicitée.
- Validation : tests médias 3, tests accès/Windows simulé/modules HTTP 2, chargement glTF réel dans Node et syntaxe JavaScript. Gestes WebGL dans WebView non vérifiés automatiquement. Textures externes, Draco et fichiers Blender/FBX : utiliser Windows ou exporter un GLB autonome non compressé.

## 0.2.51

- Onglets de projet : seuls les plugins déclarant `project_tab` et actifs dans le projet apparaissent. Migration des deux bibliothèques intégrées ; les CyTools restent disponibles comme outils sans encombrer la navigation.
- Pied de barre latérale : connexions compactes, mémoire sur plusieurs lignes et jauges CPU/RAM/GPU/VRAM/disque. Les jauges mesurent la machine (disque = volume des données CyAI), les détails indiquent la consommation CyAI. Valeurs absentes : n/d.
- CLI : les actions refusées sont affichées explicitement, sans erreur intitulée SUCCESS. Les erreurs d’écriture du prompt ne sont plus ignorées. Trace de taille et empreinte du prompt préparé, sans prétendre confirmer sa réception distante.
- Validation : tests connecteurs incluant transmission locale de plus de 490 000 caractères et intégrité Unicode, tests MCP et arrêt d’inférence, syntaxe JavaScript. CPU/RAM et GPU NVIDIA vérifiés sur la machine. Aucun benchmark distant relancé ; conservation du corpus dans le service Antigravity encore non confirmée.

## 0.2.50

- Ligne d’usage sous les réglages du modèle : tokens fournis en entrée/sortie, contexte local configuré et dernière requête, RAM moteur et RAM CyAI.
- Quota abonnement indiqué non fourni : la connexion actuelle ne collecte pas les compteurs de quota. Aucun pourcentage estimé.
- Inclut la réorganisation de la barre de saisie de 0.2.49.

## 0.2.49

- Barre de saisie réorganisée selon cyai9 : connecteur, modèle, effort et vitesse au-dessus du prompt, outils et voix alignés à droite avec retour à la ligne.
- Indications de contexte retirées de la barre, lecture réduite à une icône et arrêt sous forme de croix rouge accessible.

## 0.2.48

- Suppression du plafond de 100 000 caractères des instructions au lancement.
- Entrées textuelles des méthodes sans plafond local de 50 000 caractères ; suppression de la troncature des transferts entre étapes à 60 000 caractères.
- Suppression du plafond de 20 000 caractères des consignes de tâches dans les méthodes et leur éditeur.
- Validation : corpus de plus de 496 000 caractères conservé intégralement jusqu’au connecteur de test et entre étapes ; 9 tests méthodes et 12 tests laboratoire réussis.
- Ces changements ne modifient pas les fenêtres de contexte des fournisseurs ni les protections de transfert HTTP et des archives. Aucun appel de benchmark réel lancé.

## 0.2.47

- Travaux en arrière-plan repliés par défaut en une ligne compacte avec compteur de lots actifs et en échec. Bouton Afficher/Masquer ; choix conservé par conversation. Les messages en attente restent accessibles.

## 0.2.46

- CyMD ouvert avec son association Windows, en conservant le fichier original et son extension. Le plugin interne viendra plus tard. Aperçus images et vidéos conservés.

## 0.2.45

- Registre MCP locaux dans Paramètres → MCP : ajout d’une configuration mcpServers, test de connexion, configuration et exposition au projet.
- Actions mcp_local_register et mcp_local_test disponibles aux agents, avec les autorisations existantes ; plugin_catalog/plugin_call utilisables immédiatement, sans redémarrage.
- Commande, arguments, dossier de travail et environnement conservés pour les serveurs stdio ; HTTP local avec jeton Bearer dans le coffre existant.
- Nouveau MCP non exposé à tous les projets par défaut. Aucun lancement lors de l’enregistrement ; test explicite de initialize/tools/list, outils en écriture soumis aux autorisations.
- Validation : 3 tests registre, 8 tests MCP et 4 tests mémoire/CyTools. Inclut les aperçus internes de la 0.2.44.

## 0.2.44

- Images ouvertes en surimpression dans CyAI : zoom à la molette, déplacement, adapter et taille réelle, fermeture Échap.
- Vidéos agrandies dans le lecteur interne, avec arrêt et conservation de la position à la fermeture.
- Documents CyMD en lecture seule dans CyAI, texte et images intégrées. Aucun contrat de plugin éditeur CyMD intégré n’a été trouvé ; ce lecteur n’est pas l’éditeur CyMD complet.
- Contrôle de conversation sur la lecture des documents joints. Vérification de syntaxe JavaScript et régressions médias/CyMD ; gestes graphiques restant à valider dans la version installée.

## 0.2.43

- Envoi d’une image ou d’un fichier sans texte : suppression de la validation HTML qui bloquait le formulaire avant son traitement.
- Le traitement existant transmet les pièces jointes avec « Consulte les pièces jointes. » ; un envoi sans texte ni pièce jointe reste ignoré.

## 0.2.42

- Les pièces jointes .cymd sont lues comme archives CyMD : document Markdown et images intégrées transmis au modèle, au lieu du seul nom de fichier binaire.
- Tous les fichiers joints originaux sont copiés intégralement dans .cyai-attachments du dossier de travail et leurs chemins transmis à l’agent. Les outils locaux peuvent les lire même sans extraction automatique. Une archive CyMD illisible est signalée, sans empêcher l’accès à l’original. Les connecteurs dépourvus d’outils locaux ne peuvent pas lire ces chemins.
- Les limites d’images existantes s’appliquent à l’ensemble des pièces jointes. Contrôle de la taille décompressée et des entrées ambiguës.
- Validation : 3 tests CyMD et 3 tests des pièces jointes réussis. Pas de validation de la réponse d’un fournisseur réel.

## 0.2.41

- Ajout CyTool par sélection de dossier : lecture de CyTool.json à la racine ou dans app, commande/arguments/environnement depuis mcp.json.
- Structure autonome actuelle et anciens dossiers simples reconnus, sans exécuter le manifeste ni charger les modèles pendant la détection.
- Options manuelles repliées ; erreurs de manifeste, runtime absent et configuration ambiguë affichées. mcp.json invalide : proposition depuis tool.py et runtime privé si disponibles.
- Validation : 3 tests de détection et 4 tests de mémoire/import CyTools ; lecture des 19 dossiers locaux sans lancement des moteurs. ACE-Step possède un chemin obsolète ; TripoSR un JSON invalide, signalés dans le formulaire.

## 0.2.40

- `method_test_run` et `method_run_evaluate` accessibles aux agents MCP avec les autorisations habituelles, au lieu d’une interdiction réservant ces lancements aux clics utilisateur.
- Les tests lancés via MCP sont rattachés à une conversation autorisée, masqués dans la liste et héritent de ses autorisations. Fin des tests et des évaluations : retour automatique à l’agent appelant.
- Lecture seule et périmètre des projets toujours vérifiés. Les notes IA restent distinctes des notes utilisateur.
- Validation : 12 tests du laboratoire de méthodes, 8 tests MCP et 7 tests des travaux en arrière-plan réussis, sans appels aux modèles réels.
- Le benchmark isolé multi-modèles reste `evaluation_prepare` puis `launch_mission` ; un test de méthode exécute le graphe de cette méthode et ses dépendances.

## 0.2.39

- Correction du plantage des paramètres vocaux lorsqu’un échantillon de voix clonée existe : le rendu utilisait une variable hors portée.
- Échec de chargement ou de rendu signalé dans la page avec message rouge et bouton Réessayer.
- Régression JavaScript : zéro, une et plusieurs références vocales, échappement des noms, erreur et reprise.
- La détection matérielle reste synchrone ; cette correction résout le plantage du rendu, sans annoncer de gain de latence de détection.

## 0.2.38

- File de messages persistante avec envoi immédiat par interruption/reprise.
- Retour automatique après les délégations ; suppression de l’attente globale entre conversations.
- Benchmark parallèle en sessions internes invisibles, contexte séparé et corrections explicites.
- Suivi et autorisations des lots dans la conversation principale.
- [Validation et limites](background-evaluation-0.2.38.md).

## 0.2.37

- Catalogue officiel Piper complet, disponible hors ligne et actualisable : langues, qualités et locuteurs.
- Français : 7 modèles, dont MLS à 125 locuteurs et UPMC Jessica/Pierre.
- Méthode d’évaluation ajoutée au premier démarrage ; installation aussi accessible aux agents, sans lancer de tests.
- [Validation et limites](piper-evaluation-0.2.37.md).

## 0.2.36

- Arrêt visible près de la saisie et interruption locale même avant le premier token.
- Entrée pour envoyer, Maj+Entrée pour un saut de ligne, préférence configurable.
- Tokens locaux normalisés et cumulés ; compteurs VRAM Windows par application et moteur.
- [Mesures et validation](inference-controls-0.2.36.md).

## 0.2.35

- Mémoire indicative et avertissements orange dans les choix de voix et modèles locaux.
- Import CyTools et connexions MCP persistantes pour les outils attribués aux agents.
- Moteur PrismML séparé pour Bonsai 2, installation CUDA validée sur RTX 3090.
- Voir [détails et limites](cytools-memory-prism-0.2.35.md).

# CyAI Orchestrator 0.2.34 — Windows

## Installer ou mettre à jour

Lancer `releases/CyAIOrchestrator-Setup-0.2.34.exe`. L’installation ne nécessite pas de compte administrateur. Choisir la configuration existante lors de la première installation : dans cet environnement `C:\Projects\CyAIOrchestrator\config.json`, qui référence `<dossier-données-CyAI>` et les modèles sur J:.

Le lanceur stable est installé dans `%LOCALAPPDATA%\Programs\CyAIOrchestrator\CyAIOrchestrator.exe`. Les raccourcis Bureau et menu Démarrer pointent vers ce lanceur. L’application et ses dépendances restent ensemble sous `versions/`. Le lanceur passe toujours le chemin explicite de la configuration ; le répertoire courant du raccourci ne sélectionne plus une autre base.

Pour une prochaine mise à jour, lancer le nouvel installateur. Il réutilise l’installation et la configuration mémorisées, vérifie les tailles et SHA-256 du paquet, puis active le nouveau dossier de version. Il conserve la version précédente. Fermer CyAI avec **Quitter** dans l’icône de notification avant de relancer la nouvelle version : fermer simplement sa fenêtre peut la masquer. L’installateur ne tue pas les missions en cours.

L’option **Revenir à la version précédente** change la version utilisée par le lanceur sans toucher aux conversations, aux modèles ou à la configuration. Les copies de configuration sont conservées sous `%LOCALAPPDATA%\CyAIOrchestrator\config-backups`. Ce retour arrière du programme ne restaure pas une base de données après une migration incompatible ; les futures migrations devront être traitées avant publication.

Il s’agit d’une distribution locale hors ligne. Pas de vérification automatique sur Internet ni de téléchargement de mise à jour en arrière-plan. Aucun certificat de signature Windows n’est configuré ; la somme SHA-256 contrôle l’intégrité, pas l’identité de l’éditeur. L’installateur ne supprime ni versions précédentes ni données utilisateur.

## Construire une version

1. Mettre à jour `cyai.__version__` et `pyproject.toml`.
2. Construire l’application PyInstaller dans `dist-next` avec ses données et le SDK Claude.
3. Exécuter `.desktop-venv\Scripts\python.exe scripts/build_release.py`.
4. Le résultat est un EXE d’installation autonome et sa somme SHA-256 dans `releases`.

## Changements 0.2.30

- **La dictée Kyutai marche sous Windows.** Elle échouait avec « Cannot find a working triton installation » : la
  bibliothèque `moshi` compile le modèle avec `torch.compile`, qui demande Triton, absent de PyTorch sous Windows. Le
  moteur de dictée désactive maintenant cette compilation (`NO_TORCH_COMPILE`, prévu par `moshi`) ; le résultat est le
  même.
- **Démarrage de la dictée hors ligne** : tous ses poids sont installés, elle ne consulte plus Hugging Face à chaque
  démarrage (3,7 s au lieu de 7,5 s sur cette machine, où la connexion vers Hugging Face présente un certificat
  auto-signé que Python refuse).
- **Une réponse par phrase dictée** : une erreur pendant l’écoute est rapportée à la fin de la phrase, une seule fois ;
  la dictée suivante ne reçoit plus la réponse de la précédente.

Essai réel sur cette machine, sans micro ni son joué : une phrase dite par la voix Windows Hortense (5,7 s) est
retranscrite mot pour mot par Kyutai sur la RTX 3090, les mots arrivant pendant l’écoute (traitement 1,8 s) ; Pocket TTS
(voix « anna », modèle français) produit la phrase demandée sur le processeur à peu près en temps réel.

## Changements 0.2.29

- **Codex remarche, discussions libres comprises.** Depuis ses versions de septembre 2026 (CLI 0.155), le bac à sable
  Windows « élevé » de Codex refuse de démarrer une session qui interdit de lire le disque hors du projet (« elevated
  Windows sandbox requires effective `:root` read access », openai/codex#46312) ; le mode « non élevé » refuse aussi.
  CyAI essaie toujours la règle stricte d’abord ; si Codex la refuse pour cette raison, il rouvre la session en
  autorisant la lecture du disque, **sauf** les emplacements qui contiennent des secrets (clés SSH, AWS, Azure, GnuPG,
  Kubernetes, Docker, Claude, identifiants Git/npm/PyPI, jetons et historique de Codex — pas vos consignes
  `~/.codex/AGENTS.md` —, profils Chrome, Edge, Brave, Firefox, GitHub CLI, et les données de CyAI). L’écriture reste
  limitée au projet. Le changement est écrit dans le suivi de la réponse.
- **Accès de Codex, choisi dans CyAI** : dans la barre de chaque conversation (ou par défaut dans Autorisations) :
  projet seulement, lecture du disque (secrets fermés), disque + Internet, ou complet. « Complet » est le mode sans bac à
  sable de Codex : il peut tout lire et écrire, y compris les données de CyAI ; CyAI demande une confirmation. Un plan
  d’orchestrateur reste en lecture du projet.
- **Quand Codex demande un droit en cours de travail**, CyAI ne le refuse plus d’office : la carte d’autorisation dit ce
  qui est demandé (lecture, écriture, Internet) et « Accorder pour cette conversation » le donne pour la session. En
  autorisations automatiques, il est accordé comme les autres demandes.
- **Deux boutons de voix dans la saisie** : 🎙 dicte dans la zone de saisie (vous relisez, puis envoyez) ; 🗣 lance la
  discussion directe (votre phrase part seule à la fin, la réponse est lue, le micro se rouvre, sans toucher au
  clavier ; recliquez pour arrêter). Le bouton « Conversation vocale » de la barre est remplacé par 🗣.

Vérifié avec le vrai Codex 0.155 de cette machine, en ouvrant des sessions sans envoyer de message : règle stricte
refusée (erreur reproduite), mode non élevé refusé, lecture du disque + secrets fermés acceptée, disque + Internet
acceptée, complet (mode sans bac à sable) accepté.

## Changements 0.2.28

Voix, deuxième jalon : les meilleurs modèles locaux à essayer.

- **Dictée en direct avec Kyutai STT 1B** (français et anglais) : les mots s’affichent sous la barre vocale pendant que
  vous parlez. Choix du moteur dans Paramètres › Voix : Whisper (le texte arrive à la fin) ou Kyutai. Ce que vous dites
  pendant le chargement du modèle est gardé en mémoire et transcrit dans l’ordre. Carte graphique NVIDIA recommandée ;
  en mode automatique, la dictée passe sur le processeur si un modèle local occupe déjà la carte.
- **Voix naturelles avec Pocket TTS** (Kyutai) : en français, « estelle » et 21 autres timbres, et en anglais, sur le
  processeur. Elles deviennent la voix automatique en français dès que Pocket TTS est installé.
- **Mes voix : copie de voix** à partir d’un échantillon enregistré au micro (5 à 30 s, à votre demande) ou d’un fichier
  WAV, seulement après avoir coché que la voix est la vôtre ou que la personne a donné son accord. L’échantillon reste
  dans le dossier de données ; « Supprimer » l’efface. La copie demande l’accès au modèle kyutai/pocket-tts : acceptez
  ses conditions sur Hugging Face et indiquez un jeton de lecture. Le jeton est chiffré par Windows avec les autres
  secrets, masqué dans les journaux, et n’est donné qu’au moteur de voix.
- **Whisper Large v3 Turbo** (complet et q8_0) et **Large v3** ajoutés au catalogue ; avec une carte NVIDIA, le moteur
  CUDA et Large v3 Turbo sont recommandés.
- **Installation à part** : Pocket TTS et Kyutai s’installent chacun dans un Python 3.12 isolé, créé par uv (Astral,
  SHA-256 publiée par GitHub), dans le dossier de données, avec les paquets officiels (pocket-tts 3.1.0, moshi 0.2.13)
  et PyTorch (processeur pour Pocket TTS, CUDA adapté au pilote pour Kyutai). Les poids viennent de Hugging Face dans le
  dossier des modèles. Rien n’est ajouté à l’installateur ni au Python du système. La progression apparaît dans
  Téléchargements, avec l’étape en cours. Tailles approximatives : Pocket TTS ≈ 1 Go, Kyutai STT ≈ 5 Go.

### Limites

Aucun de ces moteurs n’a encore tourné sur cette machine : rien n’a été téléchargé. Leur intégration suit la
documentation et le code publiés, et a été testée avec des bibliothèques simulées. Le premier essai réel peut révéler
un écart ; l’erreur affichée dans Paramètres › Voix ou dans la barre vocale le dira. La vitesse de lecture ne s’applique
pas à Pocket TTS.

### Migration

Réglages `voice` : `stt.engine`, `samples`. Secret `huggingface` (optionnel). Pas de changement de base de données.

## Changements 0.2.27

Voix dans les conversations, premier jalon : dictée et lecture des réponses, sur cet ordinateur.

- **La voix ne s’allume que par votre clic.** Le micro s’ouvre avec 🎙 (cliquer pour parler, recliquer pour terminer,
  ou maintenir appuyé) ou avec « Conversation vocale ». Les réponses ne sont lues que si « Lire les réponses » est
  activé, ou quand vous cliquez 🔈 sur un message. Rien ne se rallume au démarrage, au changement de conversation
  (tout s’éteint), et aucun agent ne peut allumer la voix : il n’existe aucun outil MCP pour cela. Le son dicté est
  transcrit en mémoire puis oublié, jamais enregistré.
- **La voix ne choisit pas l’IA.** Une dictée revient dans la zone de saisie, à relire. En conversation vocale, elle part
  comme un message tapé : même connecteur, même modèle, même effort, même contexte que la barre du compositeur. Le
  message porte une petite marque « 🎙 voix » dans l’historique.
- **Une réponse à la fois.** Si l’agent travaille encore, la dictée attend la fin de sa réponse (« Annuler la réponse et
  envoyer » ou « Ne pas envoyer » restent possibles). Une autorisation demandée est annoncée, jamais accordée par la voix.
- **Seuls les mots de la réponse sont lus** : ni la réflexion, ni les outils, ni les événements, ni le code, les
  tableaux, les liens, les chemins, le bloc de continuité ou les propositions d’amélioration de méthode. Codex, Claude
  Code, Claude API, Ollama, le modèle local et OpenRouter sont lus au fil de l’écriture ; les autres connecteurs quand
  leur réponse est complète. Une réponse de l’orchestrateur est lue sans son plan JSON, avec l’annonce qu’un plan attend
  votre autorisation. Les réponses de plusieurs agents sont lues l’une après l’autre, jamais en même temps.
- **« Arrêter la voix » n’annule pas la réponse** : l’agent continue, seule la lecture s’arrête. Annuler la réponse la
  fait aussi taire.
- **Conversation vocale** : le micro s’ouvre, un silence après votre phrase l’envoie, la réponse est lue, puis le micro
  se rouvre. Il reste fermé pendant que l’agent travaille et pendant la lecture. Sans parole pendant 2 minutes (réglable),
  le micro se ferme et la conversation vocale s’arrête.
- **Paramètres › Voix** : micro et sortie audio (par leur nom, par exemple la RME Fireface), langue, modèle de dictée,
  calcul (automatique : sur le processeur quand un modèle local occupe la carte graphique), voix, vitesse, volume,
  longueur de lecture, voix par agent. « Écouter la voix » et « Tester le micro (3 s) » à la demande.
- **Moteurs et modèles à télécharger depuis leur source officielle**, jamais inclus dans l’installateur :
  whisper.cpp (processeur ou NVIDIA CUDA 12.4, empreinte SHA-256 publiée par GitHub), modèles Whisper Tiny à Large v3
  Turbo (Hugging Face, révision figée, SHA-256 vérifiée), moteur Piper 2023.11.14-2 (dépôt archivé, aucune empreinte
  publiée : celle du fichier reçu est calculée et affichée) et des voix Piper françaises et anglaises avec leur licence.
  Les voix déjà installées dans Windows (par exemple Hortense) marchent sans rien télécharger. Les téléchargements
  apparaissent dans « Téléchargements ». Vérifier et Supprimer sont disponibles.
- La vue en direct n’affiche plus le bloc de continuité, déjà masqué dans l’historique.

### Limites de ce jalon

Pas encore d’interruption en parlant pendant la lecture, de mot d’activation, de reprise ou de pause des
téléchargements, de clonage de voix, de Kyutai ni de Pocket TTS : ce sont les jalons suivants. La dictée n’a pas encore
été essayée avec un vrai modèle Whisper ni avec Piper sur cette machine (aucun téléchargement fait) ; la lecture par une
voix Windows a été vérifiée en synthèse, sans jouer de son.

### Migration

Colonne `input` de `messages` (vide, ou `voice` pour un message dicté). Réglages `voice` dans la configuration,
écrits seulement quand vous les enregistrez ou installez un élément. Vérifié sur une copie de la vraie base.

## Changements 0.2.26

Retours sur les agents (note « Agent.md »).

- **Bilan de l’équipe** (onglet Équipe) : pour chaque agent, ses cartes acceptées, échouées et en revue, ses exécutions
  en échec, la moyenne des évaluations de son travail, les capacités de son modèle et le dernier bilan de ses
  supérieurs. Des faits et des jugements, pas un classement.
- **Le chef et les leads jugent ceux qu’ils encadrent.** Un bilan donne un verdict — fiable, à surveiller, à réaffecter,
  à adapter, à remplacer — avec ses raisons. Le chef juge toute l’équipe, un lead les agents sous lui ; vous, tout le
  monde. L’agent lit son dernier bilan au début de son contexte ; le chef et les leads lisent les faits de leur équipe.
  Changement de règle : **un collègue ne note plus la carte d’un collègue** — la note d’une carte revient à un
  supérieur de l’agent, au chef ou à vous.
- **Ce qui suit un verdict** : « Réaffecter ses cartes » (ses cartes ouvertes passent à un autre agent, le motif est
  écrit sur chaque carte ; une carte en cours reste à son agent), « Remplacer » (un autre profil prend la même place :
  même rôle, même responsable, mêmes agents encadrés, cartes ouvertes ; l’ancien est retiré, pas supprimé), et
  « Proposer une amélioration » pour adapter ses consignes. Le chef et les leads peuvent le faire par le MCP, avec
  votre autorisation.
- **Curseurs** : autonomie, rigueur, créativité, effort de raisonnement, détail du compte rendu, de 1 à 5. Réglés
  pour le projet (par vous ou le chef), pour une carte (par qui la cadre), et au lancement d’une tâche ; le plus
  précis l’emporte. Ils deviennent des consignes explicites dans la tâche (avec leur origine : projet, carte,
  lancement), et l’effort de raisonnement du modèle quand le connecteur en a un (Codex, Claude Code).
- **Capacités des modèles** (Paramètres › Modèles) : pour chaque modèle et chaque domaine, une estimation sur 10 avec ses
  sources — vos notes (toujours prioritaires), les évaluations de vos projets, les benchmarks publics connus de CyAI,
  et, à votre demande, l’estimation d’une IA avec son incertitude. Le succès technique des appels est montré à part.
  « Noter à la main » corrige à tout moment.
- **Ordre de préférence par domaine** : réordonnez les modèles d’un domaine (code, interface, tests…) ; l’ordre suggéré
  suit vos préférences puis les estimations. Le chef, l’assistant et l’orchestrateur le lisent.
- **Fiches d’agents** : les capacités de base du modèle s’affichent ; « Compléter depuis les capacités du modèle »
  ajoute aux compétences les domaines estimés à 7/10 ou plus, que vous modifiez librement.

### Migration

Table `member_assessments` ; colonne `cursors` de `teams` et de `tasks`. Préférences : `order` dans
`model_preferences`, `model_estimates` dans la configuration (écrits seulement à l’usage). Vérifié sur une copie de la
vraie base.

## Changements 0.2.25

- **CyAnnota : coller une image fonctionne de nouveau.** Dans une session ouverte depuis CyAI, CyAnnota 0.3.10
  refusait toute image collée, déposée ou choisie (« Le média lié à CyAI ne peut pas être remplacé dans cette
  session ») — alors que les vidéos avaient déjà une exception pour CyAI. La copie de CyAnnota fournie avec CyAI accepte
  maintenant les images comme les vidéos : sur une planche vide, l’image la remplit ; sinon elle s’ouvre dans un nouvel
  onglet, sans remplacer le média lié. Le code source fourni (`cyannota/source.zip`, licence AGPL) porte la même
  modification, décrite dans son README. Un test vérifie que la version livrée garde ce comportement.
- À reporter dans le projet CyAnnota lui-même (`app/page.tsx`, `loadImageFile`) pour que la prochaine version de
  CyAnnota n’y revienne pas.

## Changements 0.2.24

Retours sur la création d’un projet (note « CerationDeprojet »).

- **Logo sans limite à respecter.** Toute image (PNG, JPEG, WebP, GIF, SVG…) est réduite automatiquement dans la page
  en une petite image WebP (PNG si besoin) sous la limite de stockage. Le message « Logo limité à 300 Ko » disparaît.
- **Apparence dès la création.** « Ajouter un projet » propose couleur, emoji ou initiales, logo et catégorie (une
  catégorie nouvelle est créée au passage), avec un **aperçu** de l’icône telle qu’elle apparaîtra dans la barre des
  projets et dans la liste, mis à jour à chaque changement. La fenêtre « Personnaliser » a le même aperçu ; vider
  l’emoji revient aux initiales.
- **Assistant du projet.** Une conversation « assistant du projet », en tête de la liste, au-dessus des conversations.
  À la création (case cochée par défaut), elle s’ouvre directement. Son premier écran propose des points de départ qui
  remplissent la zone de saisie — « Reprise d’un projet » (lire le dossier pour comprendre), « Nouveau projet »,
  « Composer l’équipe », « Configurer le projet » — ou vous écrivez directement. L’assistant sait, par un skill de la
  conversation, lire le dossier, proposer une présentation et des consignes, composer l’équipe, préparer des cartes, et
  qu’il doit proposer avant d’agir : chaque écriture passe par votre autorisation. Il répond avec l’IA que vous
  choisissez.
- **Mis en avant** tant que vous ne lui avez pas écrit : reflet animé et point pulsant (désactivés si le système
  demande moins d’animations). Les projets existants ont aussi l’entrée : l’assistant est créé au premier clic.

### Changement de contrat

`project_channels` renvoie une catégorie « Assistant » en tête. Le test des catégories a été mis à jour en conséquence.

### Migration

Colonne `purpose` de `conversations` (vide pour les conversations ordinaires).

## Changements 0.2.23

Cinquième et dernier lot de l’éditeur de méthode : les propositions faites pendant l’usage.

- **Inviter les agents à proposer.** Case « Inviter les agents à proposer des améliorations » dans les propriétés d’une
  méthode : chaque tâche peut finir sa réponse par une section « Proposition d’amélioration » — ce qui lui a gêné ou
  manqué dans sa consigne ou son contexte. Cette section **n’est jamais transmise** à la suite de la chaîne, ni aux
  sorties de la méthode, ni à l’évaluation d’un test. Désactivé par défaut : quelques lignes de plus par consigne.
- **Relevé des propositions** à la fin de chaque chaîne de la méthode (tests compris), une seule fois, avec la tâche,
  le modèle qui l’a écrite et la fin de sa réponse. Le bouton « 🧪 Tests & affinage » affiche le nombre à lire.
- **Examen par un meilleur modèle** : il juge la proposition (pertinente, en partie, non) et rédige soit une nouvelle
  consigne pour tous les modèles, soit des précisions pour le modèle auteur seulement. Option **« Discuter d’abord avec
  l’auteur »** : l’examinateur pose ses questions au modèle qui a proposé, lit ses réponses, puis tranche (trois appels).
- **Adoption** : « Adopter comme consigne » ou « Adopter comme précisions pour ce modèle » crée une nouvelle version ;
  « Écarter » garde la proposition lisible. Examiner, adopter et écarter restent réservés à l’utilisateur ; une IA peut
  lire les propositions (`method_proposals`).
- Vérifié sur une **copie** de la vraie base : tables et colonnes ajoutées, contextes construits sans erreur.

### Migration

Ajout de la colonne `options` de `method_templates` et des tables `method_chains` et `method_proposals`.

## Changements 0.2.22

Quatrième lot de l’éditeur de méthode : tester et affiner. Tout ce qui appelle une IA le dit et attend votre clic.

- **Tests enregistrés avec la méthode** (« 🧪 Tests & affinage ») : un objectif, des entrées, et vos critères de
  réussite. Ils n’entrent pas dans le contexte des agents. « ▶ Lancer » applique la version enregistrée et lance la
  chaîne dans un projet dédié, « Tests de méthodes » (vos projets ne se remplissent pas de tests). Les sorties de la
  méthode s’affichent sous chaque exécution, avec un lien vers sa conversation.
- **Notes.** Vous notez une exécution de 1 à 5 avec un commentaire, ou vous la faites **évaluer par une IA** contre vos
  critères : note, verdict, problèmes, suggestions. L’évaluatrice ne reçoit que les sorties, pas la conversation de la
  chaîne. Une évaluation sans note lisible est un échec, jamais une note inventée. Votre note prime sur celle de l’IA.
- **Amélioration par une IA.** Elle lit la méthode, les tests, les notes et les vérifications, et propose une méthode
  complète. Vous voyez ce qui change (tâches ajoutées, retirées, modifiées…), puis vous l’**adoptez comme nouvelle
  version** ou la **chargez dans l’éditeur** pour la retoucher. Une proposition invalide (boucle, broche absente…) est
  refusée avec sa raison. Les fichiers joints, précisions par modèle et positions des tâches conservées sont repris.
- **Vérification de compréhension** (inspecteur d’une tâche) : le modèle qui ferait la tâche — ou une autre IA — reçoit
  sa consigne exacte, avec ses fichiers, et rapporte ce qu’il comprend, ce qu’il voit dans les fichiers, les
  ambiguïtés et ses questions, **sans faire la tâche**.
- **Précisions par modèle.** « Affiner pour ce modèle » : un modèle plus fort lit le rapport, pose ses questions au
  modèle vérifié, puis écrit des précisions pour ce modèle seulement (trois appels). « Garder » les ajoute à la tâche ;
  elles ne s’ajoutent à la consigne que quand ce modèle l’exécute. Elles se modifient ou se retirent dans l’inspecteur.
- **Boucle d’affinage** : test → évaluation → amélioration, jusqu’à la note visée, dans un nombre de tours que vous
  fixez (1 à 10), après une confirmation explicite qui annonce le nombre maximal d’appels. Chaque tour est adopté comme
  nouvelle version ; toutes restent dans l’historique. Elle s’arrête à la note visée, à la limite de tours, au premier
  échec, sur une évaluation ou une proposition illisible, sur votre demande, et au redémarrage de CyAI.
- Lancer, évaluer, vérifier, affiner, adopter et boucler restent **réservés à l’utilisateur** : une IA peut lire les tests
  et leurs résultats, et écrire un test (`method_test_save`), pas dépenser.

### Migration

Ajout des tables `method_tests`, `method_runs` et `method_loops`. Précisions par modèle (`adaptations`) dans les tâches.

## Changements 0.2.21

Troisième lot de l’éditeur de méthode : les agents et les logiciels.

- **Méthodes d’un agent.** Bouton « Méthodes » sur la fiche d’un agent, section « Agents » dans l’éditeur de méthode :
  une méthode peut être **préférée** (proposée en premier quand cet agent cherche une méthode) ou **à utiliser**
  (celle qu’il doit appliquer pour ce type de travail). La fiche de l’agent l’affiche. Aucune révision n’est créée.
- **Note d’usage de l’agent.** Pour chaque méthode, une note en Markdown — ce qui marche, les pièges, ce qu’il
  vérifie — écrite par l’agent lui-même (action MCP `method_note_save`, sur sa propre fiche seulement, signée « écrite
  par l’agent ») ou par vous. Elle se lit depuis la méthode et depuis l’agent. L’agent la retrouve au début de son
  contexte, et dans les tâches de cette méthode qu’il exécute.
- **Contexte de l’agent.** Dans une équipe ou appelé directement, l’agent lit ses méthodes (nom, description, mode
  d’emploi, logiciels requis) et ses notes. Un agent qui cherche une méthode par le MCP (`method_list` avec son
  `profile_id`) voit d’abord celles qu’il doit utiliser, puis ses préférées.
- **Logiciels sur cette machine.** Un logiciel requis introuvable propose « Indiquer le chemin… » : le chemin est
  gardé dans la configuration de cette machine (pas dans l’export), vérifié, et écrit dans les tâches de la méthode
  pour que l’agent sache où le lancer. La précision du prérequis sert d’indication d’installation. La fiche d’un agent
  dont une méthode préférée demande un logiciel l’indique, avec sa présence ici (« LocalMesh ✓ » ou « ⚠ absent »).
  Indiquer un chemin reste réservé à l’utilisateur.

### Migration

Ajout de la table `profile_methods`. Clé `software_paths` dans la configuration, écrite seulement quand vous
indiquez un chemin.

## Changements 0.2.20

Deuxième lot de l’éditeur de méthode : écrire les consignes.

- **Consigne en grand.** « ⤢ Ouvrir en grand » (dans l’inspecteur, au clic droit sur une tâche, ou par double-clic sur
  la tâche) ouvre la consigne sur tout l’éditeur. Le prompt de base, le mode d’emploi et la description de la méthode
  s’ouvrent de la même façon.
- **Images et fichiers dans la consigne.** Jusqu’à 8 fichiers par tâche (50 Mo chacun, 20 par méthode), par bouton ou
  glisser-déposer, avec aperçu des images. Ils sont transmis **à cette tâche seulement** : les images au modèle, le
  contenu des fichiers texte dans son contexte. Un fichier encore joint ne peut pas être supprimé ; supprimer la
  méthode supprime ses fichiers. L’export les embarque (15 Mo au total ; au-delà, ils sont nommés dans l’avis et
  signalés à l’import, jamais passés sous silence).
- **Assistant de rédaction.** À côté du texte, une vraie conversation avec l’IA de votre choix : l’**atelier** de la
  méthode, une discussion libre hors de tout projet, retrouvable dans vos messages privés. Chaque demande part avec la
  méthode telle qu’elle est dans l’éditeur (renvoyée seulement si elle a changé) et le texte en cours. L’IA propose un
  texte complet ; « Adopter ce texte » le met dans l’éditeur, « Revenir au texte d’avant » l’annule. Rien n’est
  enregistré sans vous.
- **Entrées préparées par une IA.** Dans « Appliquer », « Préparer ces entrées avec une IA » : une IA lit le mode
  d’emploi et la préparation de chaque entrée, rédige les contextes à partir de l’objectif et de la matière collée,
  et remplit le formulaire. Vous relisez avant d’appliquer ; les entrées qu’elle n’a pas rédigées sont nommées.
- Une IA qui applique une méthode par le MCP lit ce même mode d’emploi (`method_get`) et fournit ses entrées
  (`method_apply`, champ `inputs`).

### Migration

Ajout de la table `method_assets` et de la colonne `workshop` de `method_templates`. Fichiers stockés sous
`method-assets` dans le dossier de données.

## Changements 0.2.19

L’éditeur de méthode devient un vrai éditeur de fonctions, comme un blueprint (premier des cinq lots demandés dans
« Éditeur de méthode »).

- **Entrées et sorties nommées.** Une tâche a des broches d’entrée à gauche et de sortie à droite, colorées par type :
  texte, contexte, fichier. Un fil d’une sortie vers une entrée transmet ce qui est produit, et ordonne les tâches. Les
  points de l’en-tête gardent l’ordre seul, sans rien transmettre.
- **Plusieurs sorties, séparées.** Avec plusieurs sorties texte, la tâche les rédige sous « ### Sortie : nom » ; chaque
  entrée branchée ne reçoit **que sa section**. Une sortie fichier est vérifiée à la fin de la tâche.
- **Contextes distribués.** La méthode a ses propres entrées — l’objectif, toujours, puis des contextes (complet,
  simplifié, spécial…), des textes, des fichiers — avec, pour chacune, « comment la préparer ». Une tâche « à entrées
  seules » (réglage par défaut des nouvelles tâches) ne reçoit que ce qui lui est branché, **pas la conversation de la
  chaîne** : le contexte complet va à qui en a besoin, le résumé à un autre, rien à un troisième.
- **Sous-méthodes.** Une méthode peut en contenir une autre, comme une fonction : ses entrées et sorties deviennent les
  broches du nœud ; elle est dépliée à l’application. Une méthode ne peut pas s’inclure elle-même, même indirectement ;
  une méthode utilisée ailleurs ne peut pas être supprimée. L’export embarque les sous-méthodes.
- **Clic droit** sur le fond (tâche, sous-méthode, entrée, sortie, ranger, cadrer), sur un nœud ou sur une broche
  (renommer, changer de type, débrancher, supprimer). Déposer un fil sur une tâche lui crée l’entrée ; le lâcher dans le
  vide propose d’y créer une tâche branchée.
- **Description, mode d’emploi** de la méthode (pour l’IA ou la personne qui l’applique) et description de chaque tâche.
  La fenêtre « Appliquer » affiche le mode d’emploi et un champ par entrée.
- **Versions** : chaque enregistrement est gardé ; on peut rétablir une version antérieure (elle devient une nouvelle
  version, rien n’est effacé).
- Corrections : un fil qui repart vers la gauche fait une boucle large au lieu de traverser les nœuds ; le bloc « Agents
  appelables » retrouve sa mise en forme ; Échap ferme le menu sans quitter l’éditeur.
- Fuite corrigée : le premier message d’une chaîne de méthode recopiait toutes les consignes, contextes compris. Dans un
  projet neuf, il devenait la « demande initiale » envoyée à chaque tâche. Il ne contient plus que le nom de la méthode,
  l’objectif et la liste des tâches.

### Migration

Ajout de colonnes à `method_templates` (mode d’emploi, entrées, sorties, disposition, version) et d’une table
`method_revisions`. Les méthodes existantes restent valables : leurs tâches gardent « toute la chaîne » comme avant.
Un export sans rien de nouveau reste au format 1, lisible par les versions précédentes.

## Changements 0.2.18

- Automate de délégation : le budget compte **les exécutions et les relectures** — chaque relecture est aussi un agent
  lancé, donc des crédits consommés. C’était déjà le cas ; l’interface le dit maintenant partout.
- Mise à jour vérifiée sur une **copie** d’une vraie base (4 projets) : migration appliquée, salons, plans de l’automate
  et contextes construits sans erreur.

### Migration

Aucune.

## Changements 0.2.17

Deux corrections anciennes.

- **Contexte moins redondant** : faute de présentation du projet configurée, CyAI reprend un extrait de la première
  demande du projet. Il n’est plus renvoyé à une conversation qui l’a déjà — dans la session native reprise du
  fournisseur, ou résumée par une compaction — : une mention courte le remplace. Les autres conversations du projet le
  reçoivent toujours. Moins de tokens envoyés pour rien.
- **Catalogue de modèles de la saisie** : trois lignes chargées trop tôt n’avaient jamais fonctionné (erreur au
  chargement de chaque page). Corrigé ; le catalogue d’un connecteur est désormais demandé au plus une fois par
  session, seulement s’il est activé et pas déjà en cache — le lister peut démarrer le connecteur et réécrit la
  configuration. L’actualisation à la demande reste dans Paramètres → Modèles.

La suite de tests passe désormais entièrement (335 tests).

### Migration

Aucune.

## Changements 0.2.16

- **Propositions spontanées, à la demande** : une case de la barre de l’automate, décochée par défaut. Cochée, le chef
  ou le lead qui relit un compte rendu est invité à proposer d’améliorer les consignes de l’agent si le travail révèle
  un manque — une proposition au plus, qui cite la carte et le rapport. Jamais l’agent sur son propre travail : c’est
  une observation de responsable. Rien ne change tant que vous n’adoptez pas la proposition (onglet Équipe).

### Migration

Aucune.

## Changements 0.2.15

- **Automate de délégation**, sur le board de chaque équipe. Un tour lance les cartes prêtes (dépendances terminées,
  responsable actif, connecteur activé, pas déjà en cours, pas signalées comme bloquées) et fait relire chaque nouveau
  compte rendu par le supérieur de l’agent, qui accepte ou demande une correction par le MCP CyAI.
  - **Avancer d’un pas** : le tour est affiché avant de partir — ce qui sera lancé, relu, et ce qui vous attend —, et
    ne part qu’après votre confirmation.
  - **Pilote automatique** : les tours s’enchaînent, dans un **budget de lancements** que vous fixez (50 au plus) et
    une limite d’exécutions simultanées. Il s’arrête seul quand le budget est épuisé, à la première exécution échouée
    ou interrompue, quand plus rien ne peut avancer sans vous, et à chaque redémarrage de CyAI.
  - Une carte bloquée n’est jamais relancée ; un compte rendu n’est envoyé qu’une fois en relecture ; une relecture
    d’agent sans décision laisse la carte en revue. Les écritures des agents restent soumises aux autorisations.
  - Les agents peuvent **lire** le plan par le MCP, mais ni lancer un tour ni activer le pilote : c’est réservé à vous.
- Le texte d’aide du board annonçait encore l’arrivée des agents « au lot 2 » : corrigé.

### Migration

Une colonne ajoutée à `teams` (`autopilot`).

## Changements 0.2.14

- **Console de plugin**, nouveau type de salon dans *Espaces* : on choisit un plugin MCP activé pour le projet, et le
  salon propose ses **outils de lecture** — et eux seuls. Les arguments sont un petit formulaire tiré de la
  description de l’outil (avec un champ JSON pour le reste). Chaque appel et sa réponse, ou son refus, restent dans
  l’historique du salon. Un plugin désactivé depuis le dit clairement, l’historique reste lisible. Une IA peut
  utiliser la console par le MCP (`plugin_console`, `plugin_console_call`).

### Migration

Aucune.

## Changements 0.2.13

- **Outils de conversation**, comme sur Discord : au survol d’un message, une barre d’actions — **Répondre** (cite le
  message dans la saisie), **Copier**, **Épingler** (en un clic, dans les épinglés du projet ; la note reste à valider
  avant d’être transmise aux agents), proposer en mémoire avec relecture, créer une branche, joindre au contexte.
  Un message joint au contexte est marqué d’un trait sur sa gauche.

### Migration

Aucune.

## Changements 0.2.12

Étape 2 de l’interface, suite.

- **La carte de tâche en tête de fil** : dans la conversation d’un agent lancé sur une carte, la carte reste affichée
  au-dessus des messages — statut, responsable, rapports, exécution en cours — avec « Ouvrir la carte ».
- **Salons graphe**, à créer dans *Espaces* : le graphe des **tâches et de leurs dépendances** (les sous-tâches en
  pointillés) ou l’**organigramme de l’équipe**. Calculé à chaque affichage, il suit le board ou l’équipe en direct.
  Un clic sur un nœud ouvre la carte ou la fiche du membre. Une IA peut le lire par le MCP (`graph_data`).
- Corrigé : ouvrir une carte ailleurs que depuis le board (graphe, fil) échouait tant que le board du projet n’avait
  pas été affiché.

### Migration

Aucune.

## Changements 0.2.11

Étape 2 de l’interface, première partie.

- **Messages groupés par auteur**, comme sur Discord : les messages consécutifs d’un même auteur, à moins de sept
  minutes d’écart, forment un bloc. Dans la conversation d’un membre ou d’un profil, l’auteur est l’agent lui-même —
  son nom, son icône — et sa couleur suit son rôle : chef de projet, lead, membre, consultant.
- **Salons créés par vous**, dans une nouvelle catégorie *Espaces* de chaque projet. Premier type : le **tableau
  blanc** — des notes que l’on place, colore et relie par des flèches (double-clic pour une note, le ● d’une note vers
  une autre pour un lien, double-clic sur un lien pour le nommer, Suppr pour retirer). Enregistrement automatique.
- **Une IA peut lire le tableau et y dessiner** par le MCP (`space_get`, `whiteboard_save`), avec votre autorisation.
  Chaque enregistrement part d’une version : si le tableau a changé entre-temps, rien n’est écrasé — vous êtes prévenu
  et vous rechargez. Un tableau ouvert suit les changements faits ailleurs tant que vous ne l’éditez pas.

### Migration

Une table ajoutée (`project_spaces`), incluse dans les sauvegardes. Les sauvegardes antérieures restent restaurables.

## Changements 0.2.10

- **Une méthode comme skill** : le bouton « Comme skill… » d’une méthode l’ajoute aux skills d’un projet. Toutes ses
  conversations la reçoivent dans leur contexte, comme une recette à suivre — cadre commun, tâches dans l’ordre avec
  leurs dépendances et livrables, prérequis —, quelle que soit l’IA. Rien n’est lancé. La réajouter la met à jour ;
  elle se retire dans Skills & contexte. Une IA peut faire de même par le MCP (`method_as_skill`), avec votre
  autorisation.

### Migration

Aucune.

## Changements 0.2.9

Des agents qu’on range et à qui l’on écrit, et un éditeur de méthodes en nœuds.

- **Éditeur de méthodes nodal**, comme un blueprint : chaque nœud est une tâche, un fil d’une sortie ● vers une
  entrée ● est une dépendance. Glisser pour déplacer, double-cliquer sur le fond pour ajouter une tâche, Suppr pour
  retirer une tâche ou un lien, molette pour zoomer, Ranger pour aligner par dépendances, Ctrl+S pour enregistrer.
  Une boucle est refusée au moment même où on la trace.
- **Une tâche est tenue par** un profil de la bibliothèque, par un connecteur et un modèle précis, ou par
  **n’importe quelle IA** choisie au moment d’appliquer : une méthode peut ainsi servir à n’importe qui. Chaque tâche
  peut déclarer des **agents appelables** pendant son travail (6 au plus), en plus de ceux de son profil.
- **Prompt de base** de la méthode, placé devant chaque tâche, et **prérequis** de la machine : logiciel (cherché
  dans le PATH ou au chemin donné), plugin, connecteur, ou point à vérifier soi-même.
- **Export / import** : un fichier `.cyai-method.json` autonome, avec la définition des profils utilisés et sans
  aucun secret. À l’import, les profils absents peuvent être recréés ; tout ce qui manque sur la machine (profil,
  connecteur, plugin, logiciel) devient un **avertissement**, jamais un refus. Les avertissements sont aussi affichés
  sur chaque nœud et en bas de l’éditeur.
- **Une IA peut créer et modifier des méthodes** par le MCP CyAI (`method_get`, `method_check`, `method_save`,
  `method_export`, `method_import`), avec votre autorisation pour toute écriture.
- **Bibliothèque en plein écran**, comme les paramètres, avec des **catégories** d’agents : glisser une fiche sur une
  catégorie pour la ranger (sans créer de révision), créer, renommer. Chaque fiche a un bouton **Écrire**.
- **Messages privés** : le logo CyAI ouvre les discussions hors projet, comme les MP de Discord — avec un agent de
  la bibliothèque, qui répond avec ses consignes et son modèle dans un espace isolé, ou avec l’IA de votre choix.
- **Membres et Détails au même endroit** : même colonne, même largeur, sous l’en-tête.
- Le nom du projet en haut de la liste des salons ouvre la vue d’ensemble.

### Changements de contrat, volontaires

- Une tâche peut dépendre d’une tâche placée plus loin : l’ordre vient des dépendances. Seule une boucle est refusée.
- Transformer en méthode une chaîne dont une étape n’a pas de profil conserve son connecteur et son modèle, au lieu
  de refuser.

### Migration

Trois colonnes ajoutées à `method_templates` (`preprompt`, `requirements`, `category`) et une à `agent_profiles`
(`category`). Les méthodes existantes restent valides : leurs étapes sont lues comme des tâches tenues par un profil.

## Changements 0.2.8

Une interface organisée comme Discord : les projets sont des serveurs, leurs vues des salons.

- **Rail des projets** à gauche : une icône par projet (logo et couleur du projet), l’Accueil en haut, ＋ pour ajouter
  un projet, et en bas la bibliothèque d’agents, les logs et les paramètres. Un point vert signale une exécution en
  cours dans le projet, un point ambré une autorisation qui vous attend. Les projets se réordonnent par glisser-déposer
  sur le rail.
- **Salons typés** pour le projet choisi : *Conversations* (discussions et orchestrateurs), *Agents* (conversations
  d’affectation et consultations directes), *Équipe* (board, équipe) et *Projet* (vue d’ensemble, mémoire, épinglés,
  médias, skills & contexte, plugins, réglages, et un salon par plugin de mémoire activé). Chaque salon ouvre la vue
  existante : rien n’a été réécrit. Le board affiche le nombre de cartes en revue ; l’équipe, ses problèmes bloquants.
- **Épinglés** et **Médias** sont nouveaux : les notes proposées en mémoire depuis un message, avec leur conversation
  d’origine ; les fichiers joints aux conversations du projet.
- **Liste des membres** à droite, groupée par rôle, avec une présence calculée sur les faits : *exécution en cours*,
  *attend votre autorisation*, *au repos*, *connecteur indisponible*. Il n’y a pas d’état « en ligne » : un agent
  n’existe que lorsqu’il travaille. Un clic sur un membre ouvre sa fiche et sa conversation. Dans une conversation, le
  bouton **Membres / Suivi d’exécution** fait alterner la liste des membres et le suivi.
- **＋ Agents** : discuter avec un membre de l’équipe, ou solliciter directement un profil de la bibliothèque sans
  l’ajouter à l’équipe ni passer par un lead.
- L’**Accueil** regroupe les discussions libres, l’arborescence complète des projets (catégories, archives,
  glisser-déposer) et la bibliothèque d’agents.
- MCP : `project_channels`, `project_pins` et `project_media`, en lecture, limités au projet.

- **En-tête épuré**, comme sur Discord : l’icône et le nom du salon à gauche ; à droite une recherche dans
  l’historique limitée au projet affiché, puis des icônes — épinglés, membres, détails de la conversation. L’état des
  connecteurs et la mémoire utilisée (RAM / VRAM) passent en bas de la liste des salons.
- **Plus d’onglets de conversation** : les salons les remplacent. Le bouton ⧉ du rail ouvre une nouvelle fenêtre de
  CyAI sur la conversation affichée.
- **Zone de saisie épurée** : une ligne pour l’agent, le modèle, l’effort et le contexte, puis un champ d’une ligne
  qui s’agrandit avec le message, ＋ pour joindre un fichier à gauche, CyAnnota en icône à côté de l’envoi. L’envoi
  reste sur Ctrl+Entrée.

- **Panneau de droite à trois états** : l’icône Membres affiche les membres, l’icône Détails le suivi de la
  conversation ; cliquer sur l’icône déjà sélectionnée ferme le panneau. Le choix est mémorisé.
- **Paramètres par-dessus tout**, comme sur Discord : plein écran, navigation compacte à gauche, ✕ ou Échap pour revenir
  exactement où vous étiez.

Sur téléphone, le rail devient une barre horizontale, la recherche est masquée et les onglets du projet restent
affichés.

### Migration

Aucune : la structure des salons est calculée à partir des données existantes. Aucune table n’est ajoutée ni modifiée.

## Changements 0.2.7

Des spécialistes équipés, et des compétences que l’on peut attester.

- **Boîte à outils d’un profil** : un profil déclare les plugins MCP qu’il peut utiliser directement — par exemple un
  serveur Blender pour un modeleur. Pendant son travail, leurs outils lui sont exposés, et à lui seul. Un outil en
  lecture s’utilise librement ; un outil qui agit passe par l’autorisation de la conversation, comme un outil natif.
  Chaque appel est enregistré. Un plugin désactivé pour le projet n’est ni proposé ni utilisable. Déclarer un outil
  est une permission : CyAI ne vérifie pas que le plugin fait ce que son nom annonce.
- **Bilan d’un profil** : tâches, acceptations, exécutions et moyennes d’évaluation, toujours avec l’effectif —
  « trop peu pour conclure » sous trois évaluations. Agrégats uniquement : aucun contenu de tâche ne sort de son
  projet par cette vue.
- **Compétences attestées** : vous attestez une compétence déclarée en citant une tâche **acceptée** de ce profil ou
  une évaluation de son travail. Les preuves irrecevables sont écartées et signalées. Une compétence attestée est
  marquée ✓ sur la fiche ; les autres restent « déclarées ». Une attestation dit ce qui a été constaté, pas ce que
  l’agent réussira la prochaine fois.

### Migration

Une table ajoutée (`skill_attestations`) et une colonne sur `agent_profiles` (`tools_json`). Aucune table existante
n’est modifiée.

## Changements 0.2.6

Des agents que l’on traite comme des personnes : entièrement modifiables, utilisables partout, et capables
de faire appel à des spécialistes.

- **Tout est modifiable sur un agent d’équipe** : nom, icône, description, compétences, connecteur, modèle,
  consignes, réglages. La révision du profil reste la base figée ; vos modifications sont enregistrées comme
  **surcharges locales à cette affectation** — ni le profil global, ni les autres projets ne changent. La carte
  indique ce qui a été modifié sur place, et une case efface tout pour revenir à la révision. Attention : une
  surcharge reste prioritaire même après l’adoption d’une nouvelle révision.
- **Icône d’agent**, versionnée avec le reste de sa définition, affichée sur les fiches et dans l’arbre d’équipe.
- **Un profil s’utilise partout** : dans une équipe, dans une **conversation ordinaire** sans composer d’équipe,
  et comme étape d’une **chaîne**. On peut lui confier une carte directement, sans passer par un lead. Les trois
  usages ne partagent aucune session.
- **Méthodes réutilisables** : une chaîne nommée de spécialistes que l’on rejoue sur un nouvel objectif — concept,
  silhouette, modélisation, revue, matériaux. Chaque étape est tenue par un profil et peut déclarer le fichier
  qu’elle doit laisser ; son absence fait échouer l’étape, sa présence ne prouve pas sa qualité. Appliquer une
  méthode prépare la chaîne dans sa propre conversation **sans la lancer**.
- **Appeler un spécialiste pendant son travail** : un profil peut déclarer d’autres profils qu’il a le droit de
  solliciter — faire produire des images de référence avant de modéliser, par exemple. Pendant son exécution,
  l’agent voit un outil pour les appeler. Chaque appel est **enregistré dans la chaîne** avec la demande et la
  réponse, un spécialiste **ne peut pas en appeler un autre**, le nombre d’appels par étape est **plafonné**, et
  un spécialiste n’hérite d’aucune autorisation. Sa réponse est un compte rendu, pas une preuve.

### Ce que cette version ne fait pas

CyAI ne juge pas la qualité de ce qui est produit : il contrôle l’ordre, les dépendances, les instructions envoyées
et l’existence des fichiers déclarés. Une méthode avance ; un retour en arrière se pilote sur le board. Aucun
automate n’enchaîne les tours du chef et des leads sans vous.

### Migration

Une table ajoutée (`method_templates`), deux colonnes sur `agent_profiles` (`icon`, `helpers_json`), une sur
`team_members` (`overrides`), deux sur `conversations` (`profile_id`, `profile_revision`). Aucune table existante
n’est modifiée.

## Changements 0.2.5

Mémoire par portée, évaluations et propositions d’amélioration.

- **Trois portées de mémoire qui ne se mélangent jamais** : le projet, l’**agent dans ce projet**, et le **profil
  global**. Une observation locale ne quitte jamais son projet d’elle-même. Une mémoire de profil doit être
  explicitement déclarée transférable et citer au moins une source vérifiable. Changer la portée d’une mémoire
  existante est refusé : on passe du local au global par une proposition que vous adoptez, jamais en place.
- **Contexte des agents** : dans sa conversation, un agent reçoit ses observations locales — avec la consigne de ne pas
  les transposer ailleurs — et les méthodes transférables de son profil. La mémoire d’un autre agent ne lui parvient
  pas, et les conversations normales ne sont pas touchées. Tout reste visible dans « Inspecter le contexte ».
- **Évaluations** d’une carte : qualité, respect du périmètre, intégration, tests réellement fournis, corrections
  nécessaires, de 1 à 5, avec commentaire obligatoire. Sont conservés l’auteur, la date, la carte, la révision du
  préprompt, le connecteur et le modèle effectivement utilisés, la durée mesurée et la consommation lorsque le
  fournisseur la donne. Un agent n’évalue pas son propre travail, et **aucune note n’alimente un classement automatique
  de modèles** : une note ne démontre pas une supériorité.
- **Propositions d’amélioration** : un chef ou un lead propose de nouvelles consignes ou une mémoire transférable, avec
  motif et sources obligatoires. Une proposition appuyée sur une seule source est signalée comme incident possiblement
  isolé. L’adoption crée une **nouvelle révision du profil global** ; aucune équipe ne change tant qu’elle ne l’adopte
  pas, et revenir en arrière consiste à réadopter la révision précédente. Une proposition écartée reste consultable
  avec son motif.
- 7 actions MCP supplémentaires dans le domaine `learning`, toutes en portée projet.

### Ce que cette version ne fait pas

Ce mécanisme améliore le contexte et les consignes ; **il n’entraîne aucun modèle**. Les agents ne génèrent pas de
propositions d’eux-mêmes : ils peuvent en créer par le MCP sous votre autorisation, mais rien ne les y pousse. Et rien
n’empêche d’adopter une proposition mal fondée : CyAI compte les sources, il ne juge pas à votre place.

### Migration

Trois tables ajoutées (`agent_memory`, `task_evaluations`, `improvement_proposals`). Aucune table existante n’est
modifiée.

## Changements 0.2.4

Garde-fous d’exécution.

- **Une carte qui tourne sans avancer est signalée**, quel que soit celui qui la relance — vous ou un agent. Trois cas :
  deux exécutions échouées de suite ; trois corrections demandées, qui désignent alors l’énoncé ou les critères
  plutôt que le travail rendu ; trois exécutions sans acceptation. Le board affiche l’alerte sur la carte, et un nouveau
  lancement est **refusé tant que vous ne confirmez pas**. CyAI signale le problème et ne décide pas à votre place :
  il n’annule rien de lui-même.
- **Pause et reprise** d’une exécution depuis la carte. La pause laisse l’agent terminer son tour en cours et n’annule
  pas ce qu’il a déjà écrit.
- Statuts d’exécution affichés en français.

## Changements 0.2.3

Suite du mode Équipe : les cartes de tâches, les conversations des membres et l’exécution d’une carte.

- **Onglet Board** par projet : colonnes par statut, filtre par responsable, cartes closes repliables. Une carte porte
  objectif, responsable, auteur, parent, dépendances, périmètre de fichiers, critères d’acceptation, livrables et
  historique complet. Les transitions proposées sont exactement celles que le service autorise depuis l’état courant.
- **Rendre un rapport et accepter une tâche sont deux actes distincts.** Un rapport met la carte « en revue » et ne la
  termine jamais. L’acceptation exige un rapport existant, des preuves non vides et un validateur habilité : un agent ne
  peut pas accepter sa propre tâche, ni celle d’un pair. Vous pouvez toujours décider vous-même.
- **Rôle consultant** : hors de la chaîne de commandement, sollicité sur une carte pour ce qu’il fait mieux. Un avis ne
  déplace pas la carte, ne transfère pas sa responsabilité et ne vaut jamais acceptation. Le responsable d’une tâche ne
  se consulte pas lui-même : il rend un rapport.
- **Conversations de membres** : chaque affectation a sa conversation persistante, avec le connecteur, le modèle et les
  consignes de sa révision figée. Aucun partage entre projets ni avec le profil global. Les modes normal et
  orchestrateur sont inchangés.
- **Exécution d’une carte** par son responsable, dans sa propre conversation. Le compte rendu revient marqué comme
  produit par l’agent et **non vérifié par CyAI** : aucun test n’est déduit de son texte. Deux membres travaillent en
  parallèle. Un échec n’invente aucun rapport et invite à vérifier les effets déjà produits. L’annulation est possible ;
  après un plantage, l’issue est retrouvée à la lecture suivante.
- **Délégation par le MCP CyAI** : un chef de projet peut créer et attribuer des cartes depuis sa conversation, sous
  votre autorisation. Un agent ne peut rien écrire hors du projet de sa conversation, et lancer un membre depuis une
  mission en cours est **différé** — jamais récursif.
- 24 actions MCP supplémentaires dans les domaines `tasks` et `teams`, toutes en portée projet.

### Ce que cette version ne fait pas

Aucun automate n’enchaîne les tours du chef et des leads sans vous : la délégation avance à votre rythme, chaque
écriture étant autorisée par vous. Il n’y a pas de détection de boucle sans progrès. Le périmètre de fichiers d’une
carte est transmis à l’agent comme **consigne**, il n’est pas imposé techniquement ; l’interface le dit au lancement.
La pause d’une exécution passe par le suivi de mission, pas encore par le board.

### Migration

Quatre tables ajoutées (`tasks`, `task_reports`, `task_consultations`, `task_executions`), deux colonnes sur
`conversations` (`member_id`, `task_id`) et une sur `task_reports` (`source`). Aucune table existante n’est modifiée.

## Changements 0.2.2

- **Bibliothèque globale d’agents** : entrée dédiée dans la navigation pour créer, modifier, dupliquer et archiver des
  profils réutilisables (nom, rôle conseillé, compétences, connecteur, modèle, préprompt, réglages). Chaque modification
  crée une révision numérotée, l’historique complet reste consultable et la duplication produit un profil indépendant.
- **Onglet Équipe par projet** : composition hiérarchisée chef de projet → leads → membres à partir de la bibliothèque,
  avec responsabilité locale, arbre lisible, liste des problèmes bloquants et actions de correction. Une équipe
  incomplète reste enregistrable en brouillon.
- **Révisions figées** : chaque affectation conserve une copie de la définition du profil au moment de l’affectation.
  Modifier un profil global ne change aucune équipe ; l’adoption d’une nouvelle révision est explicite et précédée d’un
  comparatif champ par champ.
- **Modèles d’équipe réutilisables** : enregistrer une composition et l’appliquer à un autre projet. De nouveaux
  identifiants d’affectation sont générés et la hiérarchie est reconstruite ; aucune tâche, conversation, session native
  ni mémoire du projet d’origine n’est importée.
- **Refus côté service** : cycles hiérarchiques, auto-rattachement, responsable d’un autre projet ou d’une autre équipe,
  responsable qui n’est ni chef ni lead. Retirer un responsable exige une réaffectation ou une confirmation explicite.
- **Actions MCP correspondantes** : l’interface et le MCP appellent les mêmes services. Les opérations de la bibliothèque
  globale sont identifiées comme globales ; leurs écritures exigent `--allow-global` pour un client externe, ou
  l’autorisation interactive de l’utilisateur pour un agent interne. Une écriture hors portée est refusée avec une
  explication, sans élargissement implicite.
- **Sauvegarde format 2** : l’export global inclut la bibliothèque, les équipes et les modèles. Les sauvegardes de
  format 1 restent restaurables ; la bibliothèque globale est alors conservée telle quelle.
- Le board d’exécution, les conversations des membres, les tâches et les rapports arrivent au lot suivant. L’interface
  le dit explicitement plutôt que d’afficher des contrôles inopérants : aucune exécution n’est déclenchée par ces écrans.

### Migration

Cinq tables sont ajoutées (`agent_profiles`, `agent_profile_revisions`, `teams`, `team_members`, `team_templates`).
Aucune table existante n’est modifiée. Migration vérifiée sur une base neuve, sur une base créée avant ce lot et sur une
copie de la base de production locale (31 Mo) : conversations, messages, missions, événements et mémoire inchangés.

## Changements 0.2.0

- Configuration stable entre double-clic, raccourci et installation ; réparation du lancement depuis un build de développement.
- Installateur / mise à jour par utilisateur, raccourcis, contrôle du paquet et version précédente conservée.
- Bouton global de déchargement du moteur local et confirmation d’arrêt.
- Rafraîchissement du catalogue local après ajout de modèles.
- Informations GPT-5.3-Codex-Spark et nouveaux connecteurs expérimentaux décrits dans `additional-connectors.md`.

## Changements 0.2.31

- Détecteur de fin de parole corrigé : il n’apprend plus la voix comme bruit de fond ; retrait de la coupure fixe après deux minutes. Le délai sans parole accepte zéro (écoute continue), réglages existants conservés.
- Pocket TTS lu en blocs audio progressifs ; sortie Windows conservée ouverte pendant le segment. Premiers blocs à chaud mesurés à 0,23–0,45 s sur deux exemples, qualité perçue à valider.
- Reprise de parole manuelle et interruption vocale optionnelle au casque. Pas d’annulation d’écho sur haut-parleurs. Le bouton interrompt la voix ; annuler le travail reste distinct.
- Mesures des étapes vocales disponibles dans la barre ; sondage non concurrent ; capture périmée écartée après fermeture.
- Méthode d’évaluation ajoutable depuis la bibliothèque. Rapports JSON associés à un profil, auteurs, dates, historique et mode d’emploi pour les prochaines IA, sans modification automatique des consignes.
- Le protocole audio expérimental des deux binaires Codex installés exige une clé API malgré la connexion ChatGPT reconnue : pas de branche vocale Codex activée. Rapport complet : `docs/voice-audit-0.2.31.md`.
- Migration additive : table `agent_benchmarks`, incluse dans les sauvegardes. Ne pas restaurer avec une ancienne version une sauvegarde contenant cette nouvelle table.


## Changements 0.2.32

Paramètres > Voix affiche les réglages applicables au moteur sélectionné : vitesse/volume Windows, vitesse/volume et variations sonore/rythmique Piper, volume/température Pocket. Les champs de variation vides utilisent la valeur native du modèle. Le choix automatique affiche les possibilités de chaque moteur. Les réglages sont communs aux voix du même moteur, y compris les affectations par agent ; ce ne sont pas des profils distincts par agent.

Le texte de préécoute est personnalisable ; « Enregistrer et écouter » applique les réglages avant le test. La section Cloner une voix propose l’enregistrement ou l’import WAV avec accord, puis la sélection de la voix enregistrée. L’import seul ne prouve pas la capacité à cloner. Une première préécoute peut télécharger les poids accessibles au compte Hugging Face ; le WAV reste local. Le travail hors ligne des voix publiées est conservé.

Aucun moteur intégré ne propose ici de consigne textuelle d’émotion (« sensuelle », « enjouée », etc.). La température fait varier la génération, pas une émotion précise. Un échantillon avec le ton souhaité peut être essayé sans garantie de restitution du style.

Validation : tests vocaux automatisés, contrôle navigateur du masquage des réglages incompatibles et sauvegarde, synthèse Pocket 3.1.0 réelle en streaming avec température 0.35 puis valeur native (sans micro ni lecture). Pas de test de clonage réel : aucun échantillon personnel ni droits supplémentaires fournis ; aucun téléchargement de poids de clonage lancé. Les paramètres Piper sont vérifiés contre le code de la version distribuée ; qualité sonore à écouter selon la voix.

Sources : [API Pocket](https://github.com/kyutai-labs/pocket-tts/blob/main/docs/API%20Reference/python-api.md), [CLI Piper 2023.11.14-2](https://github.com/rhasspy/piper/blob/2023.11.14-2/src/cpp/main.cpp).


## Changements 0.2.33

Les libellés d’échec des opérations, téléchargements, réponses et fenêtres d’erreur sont affichés en rouge, avec la couleur adaptée aux thèmes sombre et clair. Le titre et le message restent explicites en complément de la couleur. Aucun changement du comportement des opérations.


## Changements 0.2.34

Trois moteurs CUDA locaux supplémentaires dans Paramètres > Voix : Qwen3-TTS 1.7B (VoiceDesign, CustomVoice, Base), Chatterbox Multilingual et Fish Audio S2 Pro. Téléchargement, vérification, sélection générale/par connecteur, paramètres propres au moteur, références vocales partagées et transcription de référence modifiable. Les moteurs précédents et la sélection actuelle sont conservés.

Les modèles sont préparés sur cette machine ; les manifestes locaux permettent leur détection au prochain démarrage. La version ouverte n’a pas été arrêtée ni remplacée. Un seul nouveau moteur de synthèse GPU reste chargé à la fois ; les modèles de conversation ne sont pas arrêtés. Déchargement vocal après le délai d’inactivité existant (5 minutes par défaut).

Voir [la validation des moteurs](voice-expressive-0.2.34.md) pour les capacités, mesures, limites et sources.
