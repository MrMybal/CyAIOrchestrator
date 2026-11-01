# Architecture

```text
Navigateur local ── HTTP même origine ──┐
                                      ├─ Service ─ Engine (1 worker) ─ Connectors
Client MCP ─ stdio ─ pont HTTP local ──┘      │            │                │
                                             └─ SQLite ──┘          CLI / SDK / API
                                                  │
                                               Context
```

## Responsabilités

| Module | Responsabilité |
|---|---|
| `cyai/web/` | Présentation française, formulaires, état visible, suivi par polling incrémental ; aucun secret dans localStorage |
| `service.py` | Cas d’usage communs : projets, historique, mémoire, fichiers, recherche, sauvegardes |
| `engine.py` | Ordonnancement, machine à états, annulation, approbations, idempotence, validation et reprise |
| `store.py` | Schéma SQLite, transactions, horodatages UTC et récupération après arrêt |
| `context.py` | Construction d’un contexte inspectable avec références et budget explicite |
| `connectors.py` | Traduction des protocoles des fournisseurs, sessions natives, streaming, outils et usage |
| `security.py` | Résolution des chemins, fichiers sensibles exclus, coffre DPAPI et masquage des secrets connus |
| `server.py` | HTTP sur loopback, contrôle Host/Origin, cookie HttpOnly SameSite et authentification du pont |
| `mcp.py` | Protocole stdio et filtrage explicite par projet |
| `__main__.py` | Composition, configuration et verrou exclusif du dossier de données |

Python 3.11 et sa bibliothèque standard rendent le cœur facilement installable et débogable sur Windows. SQLite fournit transactions, clés étrangères et mode WAL. L’interface sans framework évite une chaîne de compilation supplémentaire. Le compromis est une UI moins riche et un serveur destiné à un seul utilisateur local, pas à un déploiement partagé.

## Données

`projects → conversations → messages / sessions / missions / files` ; `missions → steps / events` ; `projects → memory`.

- Les messages possèdent un identifiant stable et un numéro de séquence monotone.
- Plusieurs sessions natives peuvent correspondre au même couple conversation/connecteur/modèle. Une sélection manuelle en crée une nouvelle ; les anciennes restent consultables.
- `sessions.last_seq` indique le dernier message connu de la session après un résultat enregistré. Un passage de relais transmet les nouveaux messages au connecteur repris.
- Chaque étape conserve son contexte exact, résultat, usage fourni et erreur. Les événements conservent les deltas et informations d’outils, y compris si la réponse finale échoue.
- Le modèle demandé est enregistré sur l’étape. Le modèle effectivement déclaré par Codex/Claude Code est conservé dans l’événement `model` et sur le message final.
- Les fichiers joints/produits enregistrés sont des copies textuelles, pas des liens symboliques vers le disque.
- La mémoire proposée et la mémoire validée restent séparées par un statut. `source_ids` conserve la provenance d’une décision ou d’un résumé.

## Exécution durable

La création d’une mission, de ses étapes et du message utilisateur constitue une transaction. `request_key` est unique. Un second lancement du même identifiant ne remet jamais une étape réussie en file. Les statuts en cours sont écrits avant d’appeler le fournisseur ; les résultats et statuts réussis sont validés ensemble.

Après arrêt brutal, il n’existe aucune garantie universelle « exactement une fois » pour les effets externes d’un agent. CyAI marque donc l’exécution interrompue et demande une vérification avant tout réessai. Les journaux partiels et identifiants natifs restent disponibles pour cette vérification. Le verrou OS évite qu’un second service démarre un autre worker sur la même base.

L’exécution est strictement séquentielle, même entre projets. Une évolution parallèle devra ajouter un gestionnaire de worktrees isolés, des verrous par dépôt, un journal d’intégration et une politique de résolution des conflits. Aucun bouton actuel ne promet ce comportement.

## Sécurité et frontières

Le navigateur n’accède pas directement au système de fichiers ni aux clés. Le serveur rejette les origines/hôtes étrangers, exige une session et un en-tête personnalisé, applique une CSP sans script externe et échappe le texte des modèles. MCP requiert le jeton local et une liste de projets. Les outils MCP ne peuvent pas approuver leur propre travail.

DPAPI protège le secret au repos pour l’utilisateur Windows courant. Cela ne protège pas contre un programme malveillant ayant déjà les mêmes droits que cet utilisateur. Les exports contiennent les conversations et doivent être traités comme des données privées. Le masquage automatique couvre les secrets connus du coffre et certaines formes de clés ; ce n’est pas un outil universel de détection de secrets arbitraires.

Les API distantes reçoivent le contexte retenu. Les contrôles de chemin applicatifs ne remplacent pas les mécanismes de sandbox des agents natifs. CyAI ne relance jamais un agent en mode sans sandbox après un refus.

## Tests

Les tests unitaires utilisent des fournisseurs déterministes non exposés dans l’UI et des flux de protocole synthétiques. Les scripts `smoke_*` distinguent clairement les essais réseau réels. Les validations de référence figurent dans `VALIDATION.md`.
