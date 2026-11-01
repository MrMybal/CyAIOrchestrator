# Audit des limites d’exécution — 14 septembre 2026

## Plafonds supprimés

- Claude Code : max_turns=30 retiré ; le SDK ne reçoit plus de plafond de tours.
- API Anthropic et outils locaux : suppression de la boucle limitée à 12 tours. Annulation et durée explicitement choisie restent contrôlées à chaque tour.
- Réponses locales : retrait des max_tokens imposés à 2048/4096 par CyAI. Le moteur conserve ses propres contraintes de contexte et génération.
- API Anthropic : max_tokens reste un paramètre requis par requête (4096 par segment). Une sortie textuelle tronquée est conservée et poursuivie, sans plafond de segments. Un appel d’outil incomplet ne doit pas être exécuté ; un message propose de fractionner l’action.
- Chargement llama.cpp : plus d’arrêt après 120 secondes. Attente de disponibilité, arrêt explicite ou erreur du processus ; annulation de mission contrôlée pendant le chargement.
- Mission : durée par défaut 0 (sans limite) ; retrait de la borne supérieure de deux heures et du minimum de dix secondes pour une durée explicitement choisie.
- Tentatives : la reprise explicite n’est plus plafonnée ; ancien paramètre max_attempts ignoré, champ supprimé de l’interface. Aucune relance automatique sur erreur.
- Plan : retrait des plafonds 20/64 étapes dans l’éditeur, le parseur et le moteur.
- Contexte : retrait de la borne supérieure de 500000 caractères. La cible locale s’agrandit pour conserver le contenu requis. Une session native disponible est réutilisée avec les messages nouveaux lorsque leur transmission précédente est confirmée.

## Limites conservées et leur rôle

- 32 agents simultanés : capacité demandée par l’utilisateur ; file d’attente pour les étapes suivantes, pas de plafond sur le travail total.
- Délais de découverte/connexion, requêtes HTTP, contrôle de santé, terminaison de processus : bornent une opération technique pour détecter une connexion indisponible. Ce ne sont pas des délais globaux de mission. Une panne réseau peut encore nécessiter une reprise.
- Contraintes de taille HTTP, pièces jointes, archives décompressées, chemins et permissions : validation des entrées et protection des ressources ; pas de suppression aveugle de ces contrôles.
- Pagination des événements/catalogues et rétention des journaux : limites d’affichage/stockage distinctes de l’exécution.
- Capacités GPU, contexte du modèle, quotas et maximum de sortie du fournisseur : CyAI ne peut pas les supprimer.
- Bornes des petits champs de métadonnées, notes et choix : contrôles de formulaire conservés ; cet audit cible les interruptions d’exécution.

## Déploiement

Modifications du moteur préparées sans arrêt de la mission en cours. Le processus déjà lancé garde son code précédent jusqu’au prochain redémarrage. Ne pas présenter les corrections comme actives dans la mission courante.
