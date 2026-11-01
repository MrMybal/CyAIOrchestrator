# Améliorations UI/UX CyAI 0.2.59 — 31 octobre 2026

Cette passe poursuit l’audit 0.2.58 en ciblant les pertes de brouillons et les réponses asynchrones tardives. Les modifications concernent le client web intégré ; aucun fournisseur IA réel n’a été appelé pendant cette vérification.

## Comportements corrigés

- L’envoi capture sa conversation, son projet, ses réglages et son contexte au clic. L’accusé de réception ne supprime que le texte resté identique et les pièces jointes effectivement soumises. Une saisie plus récente ou le brouillon d’une autre discussion restent en place.
- Le bouton affiche « Envoi en cours… » via son nom accessible et une ellipse. Les doubles soumissions d’une même discussion sont ignorées pendant cet accusé de réception. Une autre discussion reste utilisable et peut envoyer son propre message.
- Le texte et les pièces jointes sélectionnées sont mémorisés ensemble par conversation dans sessionStorage. Ils survivent à la navigation et au rechargement de cette fenêtre ; aucune garantie nouvelle de récupération après fermeture de l’application n’est annoncée. Un JSON invalide ou un échec d’écriture des brouillons ne bloque plus ces opérations.
- Les transferts portent leur conversation d’origine. Leur progression et l’attente avant envoi concernent uniquement cette conversation. Un fichier reçu après navigation, y compris depuis CyMD/CyAnnota, reste sélectionné dans son brouillon d’origine.
- Sélection de conversation et actualisation des missions : les réponses anciennes sont ignorées après une nouvelle sélection. La lecture indique son attente, une erreur peut être retentée. Le modèle de l’agent de la conversation est rétabli au démarrage lorsqu’il est enregistré.
- Les sections projet capturent leur onglet et leur projet avant les lectures. Les données Équipe, scorecard, Board, épinglés et médias ne sont plus récupérées pour un projet modifié entre deux attentes. Un chargement apparaît immédiatement en conservant les commandes de navigation ; un échec propose Réessayer.
- Logs : la navigation est affichée avant la lecture et reste utilisable. Un ancien Journal ne peint plus au-dessus du RAW ou d’une autre vue ; les erreurs restent dans le panneau concerné avec reprise.
- Une actualisation forcée demandée pendant un poll est rejouée ensuite. Les erreurs de rendu ou de service ne sont plus systématiquement présentées comme une déconnexion.

## Validation

- `node tests/ui-async-regressions.cjs` : **18 scénarios passent**, avec les fonctions et gestionnaires réels du client, services différés et DOM minimal. Couverture : stockage invalide, brouillons et pièces jointes par discussion, accusé de réception après nouvelle saisie/navigation, deux envois indépendants, échec et double soumission, transfert terminé ailleurs, création capturant les réglages, sélections inversées, navigation vers les Logs, détails/missions tardifs, actualisation forcée, classification des erreurs, RAW concurrent, sections projet et cache, erreur et reprise.
- Autres tests JavaScript : réglages vocaux, rendu sûr des médias, retour des actions locales, ainsi que contrôle de syntaxe des onze scripts modifiés : **réussis**.
- Python : `test_inference_controls.py` (4), `test_background_work.py` (7), `test_media.py` (3), `test_cymd_media.py` (3), `test_annotation_delivery.py` (3) : **20 tests réussis**.
- Navigateur : instance jetable sur localhost, projet temporaire, connecteur simulé avec accusé de réception retardé de 4 secondes et réponse de 15 secondes ; statistiques retardées de 3 secondes. Saisie suivante conservée pendant l’envoi, deux brouillons indépendants, fichier OBJ sélectionné retrouvé après navigation puis rechargement, Journaux/RAW/Ressources et bascule Statistiques vers Utilisation IA vérifiés. Aucun message d’erreur/warning dans la console sur ces parcours.
- Capture : [envoi pendant la saisie suivante](../test-results/audit059-pending-send.jpg).

Les sessions et processus de l’application utilisée par l’utilisateur n’ont pas été modifiés. Les mesures CPU/GPU de l’instance de test sont des lectures de la machine ; les inférences et messages proviennent du connecteur simulé. Les moteurs vocaux et l’ensemble des formats 3D ne font pas l’objet d’une nouvelle campagne dans cette version.
