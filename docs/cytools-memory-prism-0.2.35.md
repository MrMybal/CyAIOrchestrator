# CyAI 0.2.35 — mémoire, CyTools et Bonsai 2

## Mémoire
Les voix affichent un ordre de grandeur RAM ou VRAM dans les menus, y compris les choix par connecteur. Le choix courant affiche le détail sous le menu. Un avertissement orange et le symbole ⚠ distinguent un modèle trop grand ou une marge faible. Aucune interdiction automatique.
La capacité et la mémoire libre NVIDIA sont lues avec nvidia-smi (cache 10 secondes, par GPU, jamais la somme des cartes). Affichage actualisé à l’ouverture/actualisation des réglages. Les estimations ne comprennent pas les autres modèles, jeux ou applications. Fish : environ 20–21 Gio constatés lors des essais courts précédents, fourchette de planification 20–24 Gio. Qwen 4–6 et Chatterbox 3–5 Gio sont des estimations, pas des mesures garanties ; leur RAM CPU n’a pas été mesurée. Les GGUF indiquent les poids et signalent si les poids seuls dépassent la VRAM libre en mode GPU ; contexte et buffers s’ajoutent et ne sont pas estimés exactement.

## CyTools
Paramètres → Plugins → Ajouter un CyTool : sélectionner CyTool.json, le dossier de l’outil, son Python ou CLI, et un tableau d’arguments se terminant par `mcp` (par exemple `["tool.py", "mcp"]`). Le champ executable du manifeste n’est jamais exécuté implicitement. Le SDK doit déjà être installé dans l’environnement de l’outil avec son extra MCP.
Ensuite attribuer le plugin dans la boîte à outils du profil d’agent. Les opérations op_* suivent la politique d’autorisation de la conversation ; seuls les contrôles de lecture du SDK sont déclarés en lecture. La limite arbitraire de huit plugins par profil est retirée.
La session MCP est persistante et les appels sont sérialisés par connexion. Les agents d’un même projet partagent une connexion au même CyTool ; un autre projet utilise une autre connexion. Le stockage et l’isolation d’identité sont gérés par le SDK CyTools. Le guide injecté demande de suivre jobId avec cy_get_job et le champ state, et de distinguer Completed, Failed et Cancelled. Il n’y a pas de répétition automatique d’une opération après une erreur.
La fermeture de CyAI ou la reconfiguration du plugin ferme le processus autonome et peut annuler ses jobs. La reprise durable après crash nécessite le mode service HTTP du SDK avec une identité persistante ; cet assistant d’import ne le configure pas encore. Un tableau de suivi graphique dédié aux jobs CyTools n’est pas inclus ; le suivi est fourni à l’agent par les outils MCP.
Validation réelle : discovery, op_echo, cy_get_job répété, résultat Completed avec Bonjour CyAI sur une seule session. SDK local <dossier-SDK-CyTools> ; aucune modification du SDK ni des outils Flux/SPAR3D.

## Bonsai 2
Source officielle : https://github.com/PrismML-Eng/Bonsai-demo/blob/main/README.md
Bonsai 2 PTQ1_0 nécessite le fork PrismML. Boutons d’installation CPU, Vulkan et CUDA, également accessibles aux agents par local_runtime_install avec backend prism-cpu/prism-vulkan/prism-cuda. Téléchargements officiels vérifiés avec les SHA-256 publiés.
Le moteur est séparé du llama.cpp standard et choisi automatiquement par le nom/chemin Bonsai-2, Bonsai 2 ou PTQ1_0. Ce repérage n’est pas un analyseur complet des types GGUF : pour un fichier renommé, Configuration du modèle → Moteur permet de choisir explicitement PrismML. Le même réglage est disponible aux agents via local_model_settings et settings.runtime_family.
Moteur installé : prism-b10709-9a9394a CUDA 12.4. Sidecar de découverte dans <dossier-données-CyAI>/runtimes/prism-runtime.json, lu au prochain démarrage sans modifier la configuration de l’instance active.
Essai réel RTX 3090 : GGUF déjà présent de 5 946 648 928 octets, contexte 4096, chargement 9,58 s, réponse Bonjour via /v1/chat/completions. Prompt 18 tokens en 238 ms et 2 tokens générés en 41 ms : validation fonctionnelle uniquement, échantillon trop court pour un benchmark de débit. Le processus de test a été arrêté et déchargé.

## Reproduction
- `.desktop-venv/Scripts/python.exe experiments/voice-engines/cytools-probe.py`
- `.desktop-venv/Scripts/python.exe experiments/voice-engines/prism-probe.py` (court essai GPU, ne décharge pas les autres modèles)
- `.desktop-venv/Scripts/python.exe experiments/voice-engines/run-tests-035.py`
Logs dans experiments/voice-engines. Les essais sont isolés ; l’application active n’a pas été redémarrée.
