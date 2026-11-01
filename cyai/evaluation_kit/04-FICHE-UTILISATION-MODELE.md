# Fiche de transmission — Comment utiliser ce modèle

Cette fiche fait obligatoirement partie du rapport. Elle est destinée à l’IA qui délègue une tâche au modèle évalué, même dans une autre conversation ou un autre projet. C’est un mode d’emploi fondé sur les essais, pas seulement une note de performance.

Aucun test de modèle n’a encore été exécuté avec ce kit : les champs ci-dessous sont à renseigner, et ne constituent pas des capacités ou faiblesses constatées.

## Identité et validité

- Modèle réellement résolu, fournisseur, version du profil, préprompt, outils et paramètres testés : […]
- Rapport source, date et version de cette fiche : […]
- Conditions auxquelles les observations s’appliquent : […]
- Conditions différentes ou non testées nécessitant une nouvelle vérification : […]

Ne pas transférer automatiquement une observation à tous les agents utilisant le même nom de modèle. Distinguer le modèle de base du spécialiste configuré, de la mémoire injectée et du connecteur.

## Instructions pour l’IA qui délègue

Pour chacune des rubriques, renseigner les faits observés ou « non testé ». Une recommandation doit contenir : situation, consigne concrète, raison, identifiants des preuves, statut et limite de validité.

| Rubrique | Ce que la fiche doit indiquer |
|---|---|
| Tâches adaptées | Travaux à confier, granularité qui a fonctionné et cas demandant une supervision. |
| Formulation | Structure de consigne efficace, niveau de détail, séparation objectif / contraintes / données / livrable. |
| Contexte | Informations indispensables, références à joindre, ordre utile si testé, volume réellement vérifié et limites observées. |
| Décomposition | Quand envoyer une tâche unique, découper ou prévoir un point de contrôle ; dépendances à expliciter. |
| Format de sortie | Format à demander, exemple de structure sans réponse du benchmark, contrôle syntaxique ou sémantique nécessaire. |
| Vérification | Preuves, tests, fichiers ou références exigés avant d’accepter le résultat. |
| Ambiguïtés | Informations à faire clarifier ; hypothèses permises et décisions qui doivent remonter au responsable ou à l’utilisateur. |
| Outils et autorisations | Outils réellement testés, périmètre autorisé et preuves d’exécution ; ne pas inventer une capacité. |
| Échec et reprise | Symptôme observable, correction ciblée, état à préserver et solution de repli ; aucun bouclage sans borne convenue. |
| À éviter | Formulations ou usages ayant échoué, avec cas source et conditions, sans généralisation abusive. |

Statuts à employer : `observed` (comportement constaté), `hypothesis` (conseil à tester), `validated_comparison` (amélioration vérifiée sur cas non exposés). Mentionner le nombre d’essais et les résultats contradictoires. Une bonne intuition de l’évaluateur ne devient pas une recommandation validée.

## Préprompt et message de délégation réutilisables

Fournir deux blocs dans chaque rapport :

1. **Préprompt proposé au modèle** : consignes générales issues des observations, sans contenu ni réponse du benchmark ; adoption à valider séparément.
2. **Message de délégation pour l’IA appelante** : modèle de demande avec champs à remplir selon la tâche.

Gabarit de délégation général, à adapter après évaluation (pas une recette déjà validée pour ce modèle) :

```text
Objectif : [résultat attendu et périmètre].
Contexte utile : [faits, interfaces et sources nécessaires].
Données à traiter : [données clairement séparées des instructions].
Contraintes et actions autorisées : [règles concrètes].
Livrable : [format, fichiers ou réponse attendus].
Critères d’acceptation : [vérifications observables].
Si une information déterminante manque : [question à poser / destinataire].
Compte rendu : [résultat, preuves de vérification, limites et blocages].
```

Le rapport doit proposer au moins un exemple concret de consigne et sa reformulation conseillée, construit sur un nouveau cas métier sans révéler les réponses de test. Indiquer ce que la reformulation cherche à corriger et si son efficacité a été vérifiée.

## Lecture de la fiche par une future IA

Avant de déléguer : vérifier l’identité et les conditions, lire les recommandations pertinentes, adapter le message à l’objectif actuel, puis prévoir les contrôles recommandés. La fiche est une aide fondée sur des observations ; elle ne remplace pas les instructions actuelles de l’utilisateur ni les permissions des outils.

Ne transmettre au modèle que les consignes utiles à sa tâche. Garder références privées, corrigés et traces sensibles hors de son contexte. Si les conditions diffèrent, signaler l’incertitude et proposer une vérification ciblée ; ne pas déclarer le modèle inutilisable par défaut.

## Auteurs et dates de la fiche

Afficher obligatoirement :

- Tests conduits par : [nom d’agent, fournisseur, modèle résolu ou identité non vérifiée].
- Fiche rédigée par : [identité de l’IA et identifiant de contributeur].
- Revue par : [identité, ou non revue ; préciser si le même agent].
- Tests réalisés du […] au […] ; fiche créée le […] ; dernière modification le […], avec fuseau.
- Rapport source et révision : […] ; historique des changements : [qui, quand, quoi].

Conserver ces informations dans toute copie autonome. Ne pas confondre l’IA qui a évalué avec le modèle évalué. Ne jamais inventer un nom de modèle, une date ou une revue manquante.
