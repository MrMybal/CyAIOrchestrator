# 0.2.38 — Discussion, délégation et évaluations en arrière-plan

## Comportement

- Les messages envoyés pendant une réponse restent dans une file SQLite. Ils sont visibles, retirables et partent un par un au prochain tour disponible.
- « Envoyer maintenant » annule la réponse active, attend son arrêt et transmet le message dans la même discussion avec reprise native si le connecteur la prend en charge. Ce mécanisme est une interruption/reprise, pas une injection pendant le raisonnement natif. Les effets déjà produits ne sont pas annulés.
- Les délégations MCP attendent la fin de leur conversation d’origine plutôt que toutes les missions de l’application. Leur fin génère un message de retour automatique au demandeur, une seule fois par lot terminé. Les échecs sont rapportés sans relance aveugle.
- Une nouvelle conversation créée par le demandeur conserve son mode d’autorisation. Les opérations internes d’évaluation utilisent le mode courant de leur discussion principale. Les permissions natives ne sont pas élargies.

## Méthode d’évaluation

L’évaluateur appelle evaluation_prepare avec conversation_id, candidates [{connector,model,name?}], form A/B, concurrency (32 par défaut, les modèles locaux restent sérialisés) et request_key facultatif. La préparation retourne une mission à lancer avec launch_mission. Aucun appel candidat n’a lieu pendant la préparation.

Un lot contient 12 exercices par candidat. Il utilise une conversation interne absente de la liste des discussions. Chaque exercice a son propre répertoire de travail et démarre une session native neuve ; seul l’exercice à deux tours reprend sa propre session. Le contexte transmis est l’énoncé brut, sans mémoire, réponses précédentes, pièces jointes, instructions de continuité ou MCP CyAI. Un exercice nommé planning reste un exercice texte, jamais une demande de plan d’Orchestrator.

Les corrections privées sont lues côté serveur par evaluation_results, après la réponse. Les comparaisons JSON strictes ont un résultat pass/fail ; les critères humains restent needs_review. Une exécution réussie ne signifie pas une bonne réponse. Le résultat fournit les réponses brutes, erreurs, modèle demandé et modèle rapporté. L’évaluateur complète les critères humains et enregistre le rapport signé et daté, avec guide destiné aux futures IA, via evaluation_report_save.

Le lot et ses états sont visibles dans la discussion principale, avec arrêt et autorisations sur place. La fin réveille l’évaluateur, qui consulte les résultats et poursuit le protocole autorisé. La recette fournie est mise à jour seulement si elle n’a pas été modifiée. Aucun contexte long/saturation n’est inclus.

## Limites importantes

L’isolation du contexte et des sessions CyAI ne garantit pas une isolation système des CLI : leurs politiques natives et outils globaux peuvent encore s’appliquer. Aucun corrigé n’est placé dans le répertoire candidat ; aucun accès automatique aux outils natifs n’est ajouté pour un benchmark. Le rapport doit signaler cette limite. Les exercices ont une valeur diagnostique, pas celle d’un classement universel.

La file et les retours survivent à la fermeture. Un envoi dont le démarrage a été interrompu reste explicitement à reprendre, pour éviter une répétition invisible. Les missions interrompues au redémarrage conservent le parcours de récupération existant.

## Validation

Tests ciblés : file et déduplication, interruption/reprise, retour unique au demandeur, indépendance vis-à-vis d’une mission étrangère, 24 exercices parallèles à connecteurs simulés, absence de fuite du contexte précédent, conservation du second tour dans la seule session concernée, invisibilité des conversations internes, reprise après interruption, autorisations héritées.

Navigateur : saisie d’un message pendant le travail, carte en attente, action Envoyer maintenant, reprise dans la même discussion. Correction du bandeau qui restait auparavant sur l’ancienne mission.

Suite générale intermédiaire : 467 tests, 2 ignorés ; une erreur de nettoyage Windows WinError 145 après les assertions d’un test de spécialiste. Les 8 tests de spécialistes ont ensuite réussi. Les 7 tests ciblés finaux ont réussi, dont le cumul d’usage des deux tours sans double comptage. Les 7 tests de connecteurs et les 4 tests de contrôle d’inférence ont également réussi après les derniers changements.

Les 84 appels réels Gemini n’ont pas été relancés dans cette validation. Les entretiens antérieurs contenant les réponses des autres candidats restent invalides comme comparaison indépendante ; une nouvelle exécution isolée est nécessaire pour obtenir des résultats comparables. Aucune session utilisateur active n’a été arrêtée pour installer cette version.
