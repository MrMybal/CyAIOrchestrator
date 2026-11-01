# CyAI — Projets, continuité et choix des modèles

## Accès
- Paramètres → Plugins : importer directement le JSON `mcpServers`, instructions de consultation, URL web et dossier de données CyAICodex. Le jeton MCP est conservé dans le coffre Windows.
- Projet → CyAICodex / CyProjectCodex : ouvrir le site dans CyAI ou séparément. CyProjectCodex : associer un projet existant ou créer et associer une nouvelle bible.
- Les deux sites locaux ont été adaptés pour autoriser uniquement CyAI sur localhost:8766 comme parent. CyAICodex utilise son flux de session web existant ; ce secret reste hors du contexte IA et des journaux. Un port d’application personnalisé exige d’adapter l’origine autorisée des sites.

## Mémoire et skills
- Mémoire partagée : catégories libres, notes actives ou propositions, sources consultables.
- Skills & contexte : instructions Markdown, résumé du projet, import / rédaction de skills, budget du contexte, mémoire automatique, compaction et sessions neuves. Les conversations héritent du projet et peuvent remplacer ses réglages.
- Mes skills : consulter, activer / désactiver, exporter Markdown ou préparer un appel dans la conversation.
- Une IA peut proposer une recette de test ou automation via le bloc de continuité. Les skills proposés sont enregistrés inactifs avec le message source. Ils ne lancent rien automatiquement.
- Mémoire et résumé automatiques sont optionnels. Le modèle doit fournir le bloc structuré ; s’il ne le fournit pas, CyAI ne prétend pas avoir créé de mémoire. Les messages complets sont conservés. Le budget est en caractères, pas une garantie sur les tokens internes ou de sortie du fournisseur.

## Modèles et statistiques
- Paramètres → Modèles & préférences : catalogue annoncé par les fournisseurs, notes personnelles sur 10 par usage, préférer / éviter, priorité qualité / rapidité / économie / équilibre. Ces préférences sont transmises à l’orchestrateur.
- Benchmarks externes : champs facultatifs avec nom, source, date et score sur 100. Aucun score public inventé ni comparaison automatique de benchmarks différents.
- Les descriptions, efforts et vitesses Codex proviennent de `model/list` du CLI installé. Le schéma App Server local a été vérifié ; `turn/start.effort` et `serviceTier` sont effectivement transmis. Les niveaux non annoncés sont refusés. Claude Code accepte le champ effort du SDK ; les autres fournisseurs restent sur leurs réglages par défaut.
- Référence du protocole : https://learn.chatgpt.com/docs/app-server
- Projet → Projet → Statistiques & stockage, ou bouton dans la conversation : messages, missions, tentatives, états, tokens et coûts fournis, cache, événements d’outils et d’approbation, activité quotidienne, stockage UTF-8 et fichiers référencés dédupliqués, export JSON.
- La taille physique SQLite (avec WAL / SHM) est globale. Les valeurs par conversation sont des tailles logiques ; les fichiers du dossier de travail ne sont pas scannés. Les vidéos sont comptées lorsqu’elles sont référencées par l’application. Les coûts absents sont affichés comme non fournis. Un succès technique ne constitue pas une évaluation qualitative.

## Apparence
- Sombre violet, clair doux lin, océan, forêt, système Windows, création de thèmes personnalisés.
- Interface condensée. L’onglet Projet regroupe Vue d’ensemble, Utilisation IA, Historique, Statistiques & stockage, Configuration. Les actions globales Local / Nouvelle mission ont été retirées de l’en-tête conformément aux annotations.
