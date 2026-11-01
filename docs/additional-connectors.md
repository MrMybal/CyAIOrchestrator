# Connecteurs supplémentaires — 15 septembre 2026

Intégrations présentes dans les sources et le paquet dist-next, désactivées par défaut. Aucun CLI ni compte tiers installé automatiquement. Aucun redémarrage de l’application active.

| Connecteur | Transport | Configuration |
| --- | --- | --- |
| OpenRouter | API Chat Completions SSE, catalogue /models, outils CyAI, images | Clé dans le stockage secret CyAI et ID exact du modèle requis. Le catalogue public ne prouve pas la validité de la clé. Pas de session distante persistante. |
| Command Code | command-code / cmdc, JSON par ligne | CLI installé et connecté. Reprise par sessionId ; poursuite dans la même session si max_turns. Catalogue texte non interprété : saisie du modèle possible. |
| Tencent CodeBuddy | codebuddy / cbc, stream-json | CLI installé et connecté. MCP temporaire CyAI transmis, images et reprise de session. Modèle saisi dans les paramètres. |
| Google Antigravity | agy, stream-json | CLI installé et connecté. Reprise par conversation_id. Tchat/exécution seulement ; préparer le plan avec un autre connecteur. Images non prises en charge par cet adaptateur. |
| Cognition Devin | devin, mode print et export ATIF | CLI installé et connecté. Texte transmis en direct. Reprise si l’export fournit session_id. Tchat/exécution seulement. Images non prises en charge par cet adaptateur. |

Devin CLI ne désigne pas l’interface graphique Windsurf. CodeBuddy appartient à Tencent, pas à Alibaba ; le CLI Alibaba s’appelle Qwen Code et ne fait pas partie de cette modification.

## Permissions et MCP

Les nouveaux CLI utilisent leur politique native. L’option explicite « Autoriser automatiquement les outils natifs » active leur mode automatique pour les écritures et commandes ; elle est désactivée par défaut. CyAI demande l’autorisation globale d’invoquer l’agent selon la politique de la conversation, sans prétendre relayer chaque dialogue natif. Les refus et résultats incomplets doivent remonter en erreur.

Command Code, Antigravity et Devin utilisent leur propre configuration MCP : cette version ne leur injecte pas automatiquement le MCP temporaire CyAI. Leur contexte ne prétend donc pas disposer de ce MCP. CodeBuddy reçoit une configuration temporaire supprimée en fin d’exécution. OpenRouter appelle les outils via la passerelle CyAI.

Pas de limite de tours ajoutée par ces adaptateurs. Les limites, quotas et délais du fournisseur restent applicables. Aucun réglage de vitesse Codex n’est passé à ces CLI.

## Validation

159 tests Python réussis (2 ignorés), dont 8 nouveaux tests : désactivation initiale, parsing des flux, reprise, erreurs, EOF sans résultat, sous-processus, annulation avant lancement, images OpenRouter et résolution npm Windows sans shell. Syntaxe JavaScript validée. Les CLI tiers sont absents de cette machine : validation réelle authentifiée et compatibilité avec leurs versions installées restent à effectuer. Les tests de flux sont des fixtures, pas des sessions fournisseur réelles.

## Références officielles

- https://openrouter.ai/docs/quickstart
- https://commandcode.ai/docs/headless
- https://commandcode.ai/docs/reference/cli
- https://www.codebuddy.ai/docs/cli/headless
- https://www.codebuddy.ai/docs/cli/cli-reference
- https://antigravity.google/docs/cli/headless/
- https://docs.devin.ai/cli/reference/commands
