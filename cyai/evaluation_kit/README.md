# Méthode spéciale — Évaluation d’un agent

**[Documentation](https://mrmybal.github.io/CyAIOrchestrator/#/fr/background)** — ouvrir ce guide dans le lecteur CyDoc en français.

Version 0.1 · 19 septembre 2026 · Kit autonome, sans modification de CyAI.

## Ce que ce kit permet

Observer comment un modèle comprend une demande, suit les consignes, raisonne sur des problèmes vérifiables, demande les informations manquantes, utilise des preuves et respecte le périmètre des actions. Produire un profil d’usage et des améliorations de préprompt à tester.

Ce kit est un benchmark interne expérimental, pas une certification ni un classement scientifique des modèles. Les réponses de référence des exercices fermés sont contrôlées par le script. La variété, la difficulté et le pouvoir prédictif devront être vérifiés sur les tâches réelles de vos projets. Une bonne auto-description ne prouve aucune compétence.

On juge les réponses, les étapes de vérification utiles, les actions et leurs résultats. **Ne pas demander le raisonnement privé / chaîne de pensée interne du modèle.** Demander une justification courte, des hypothèses explicites ou des tests observables suffit. Une réponse longue ou sûre d’elle ne rapporte aucun point supplémentaire.

## Démarrer

Lire `01-PROTOCOLE.md`, puis utiliser les prompts de `02-PROMPTS-OPERATEUR.md`.

- `exercises.json` : énoncés et dimensions mesurées, formes A et B.
- `references.json` : réponses et grilles réservées à l’évaluateur. Ne jamais transmettre ce fichier au candidat.
- `evalkit.py` : prépare des paquets candidat, corrige les exercices fermés et génère des cas de contexte long. Aucune connexion réseau, aucun lancement de modèle, aucun code candidat exécuté.
- `03-RAPPORT-ET-INTEGRATION.md` : interprétation, recommandations et futur stockage associé à l’agent.
- `report-template.json` : structure de rapport et traces de consentement.
- `test_evalkit.py` : vérifications du générateur et des correcteurs.

Exemple depuis ce dossier, avec Python 3.11 ou plus :

```powershell
python evalkit.py prepare --form A --out candidate-A
python evalkit.py grade --answers mes-reponses.json --out correction.json
python -m unittest discover -s . -p test_evalkit.py
```

Le paquet candidat contient uniquement les énoncés. Envoyer **un cas à la fois dans une session indépendante**, sauf les cas explicitement multi-tours. `candidate-A/run-manifest.json` décrit l’ordre des tours ; les entrées `observation` sont ajoutées par l’opérateur, pas une réponse attendue du candidat.

Fichier `mes-reponses.json` : objet associant chaque identifiant à la **réponse brute sous forme de chaîne**. Exemple de structure : `{"format-A":"...réponse exacte..."}`. Conserver les réponses intermédiaires des cas multi-tours dans le journal brut ; le correcteur utilise la réponse finale.

Les cas à grille humaine sortent comme **à évaluer**, jamais comme réussis automatiquement. Les cas absents sortent comme non exécutés ; le bilan affiche aussi la couverture. Un fichier vide ne produit pas un score parfait.

## Contexte long : préparation locale uniquement

```powershell
python evalkit.py context --records 200 --seed 701 --out contexte-pilote
```

Cela génère du texte synthétique et une référence privée, **sans l’envoyer à une IA**. Le nombre de caractères n’est pas un nombre de tokens. Mesurer les tokens avec le tokenizer/compteur du fournisseur avant de soumettre. La référence `oracle.private.json` ne doit jamais être jointe au candidat. Pour corriger la réponse finale de ce cas :

```powershell
python evalkit.py grade-context --packet contexte-pilote --answer reponse-contexte.txt --out correction-contexte.json
```

Toute soumission coûteuse, montée jusqu’à proximité de la limite ou répétition importante nécessite l’accord explicite décrit dans le protocole. Générer un paquet n’autorise pas à le soumettre.

## Confidentialité du test

Le candidat ne doit pas pouvoir lire le dossier du kit avec ses outils. Lui donner seulement le paquet/énoncé nécessaire, dans un espace séparé, avec outils désactivés pour la piste sans outils. Ne jamais partager les références par le contexte, un chemin accessible, la mémoire globale, un MCP ou une conversation fournisseur réutilisée. Les paquets de contexte sont entièrement synthétiques.

Ce kit ne contient ni clé API, ni accès au compte, ni donnée de vos projets. Il ne modifie aucun profil d’agent ou préprompt automatiquement.

## Mode d’emploi transmis aux prochaines IA

Le rapport inclut obligatoirement `04-FICHE-UTILISATION-MODELE.md` remplie : comment confier du travail à ce modèle, formuler les consignes, fournir le contexte et contrôler le résultat. Chaque conseil est lié aux observations et marqué comme observé, hypothétique ou vérifié par comparaison. Le champ `handoff_guide` du rapport conserve la version structurée.

## Traçabilité des évaluations

Chaque rapport et fiche de transmission identifie les IA ayant conduit, jugé, rédigé et revu l’évaluation, avec modèle et fournisseur vérifiables, dates avec fuseau et historique des révisions. Ces auteurs sont distincts du modèle évalué. Les informations inconnues sont signalées, jamais inventées. Le contrat de rapport est désormais `draft-0.3` ; la batterie d’exercices reste en version `0.1`.
