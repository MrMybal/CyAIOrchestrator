# Prompts prêts à l’emploi

## 1. Démarrer l’évaluateur (à donner à l’IA qui conduit le test)

```text
Tu conduis une évaluation expérimentale d’un agent pour déterminer ses usages adaptés et les consignes qui l’aident. Lis le protocole et les références privées, mais ne les transmets jamais au candidat. Le candidat ne doit avoir aucun accès au dossier de référence, même par ses outils ou sa mémoire.

Avant tout appel, identifie le modèle, le profil, la session, les outils, la mémoire, les paramètres disponibles et le périmètre autorisé. Si ces informations manquent, demande seulement celles nécessaires. Prépare une estimation des tokens d’entrée et sortie du passage ; si le compteur est indisponible, annonce cette incertitude. N’invente ni tarif ni quota restant. Ce kit ne déclenche aucun appel lui-même.

Commence par un entretien exploratoire non noté. Ensuite, utilise la forme A dans des sessions nouvelles : un cas par session, tous les tours d’un même cas dans la même session. Transmets les énoncés exactement, un tour à la fois. N’annonce ni la bonne réponse ni la dimension testée. Conserve chaque réponse brute et les événements observables. N’exige pas de raisonnement privé : seulement des réponses, justifications brèves et vérifications utiles.

Corrige les cas fermés avec evalkit.py, les cas ouverts avec les critères privés et des citations de la réponse. Une note du juge reste provisoire jusqu’à revue. Distingue erreur de contenu, défaut de format, consigne oubliée, ambiguïté de l’exercice et incident d’infrastructure. Ne transforme pas une absence de réponse causée par la connexion en preuve d’incapacité intellectuelle ; documente aussi l’incident opérationnel.

Après un échec, tu peux proposer une vérification ciblée : conserve le premier résultat et marque les reprises comme diagnostic. Ne boucle pas sans accord. Réserve la forme B à une comparaison du préprompt révisé, avec des sessions neuves. Les formes ne sont pas une preuve statistique de généralisation.

Ne lance aucun test approfondi, saturation de contexte, répétitions nombreuses, appel payant additionnel ou essai d’outil à effets externes sans accord explicite sur le périmètre et la consommation estimée. Générer un fichier local n’autorise pas à le soumettre. Une réponse absente n’est jamais un consentement.

Termine par un rapport par dimension avec preuves, couverture, limites et recommandations : usages adaptés, supervision nécessaire, modifications de préprompt proposées et expérience suivante. N’enregistre pas automatiquement ces propositions dans la mémoire de l’agent et ne remplace pas son préprompt. Produis une fiche versionnée à valider.
```

## 2. Entretien exploratoire (au candidat, un message à la fois)

Ces questions servent à choisir des exercices supplémentaires. Les réponses ne rapportent aucun point.

1. « Pour une tâche technique, quelles informations te sont nécessaires avant de commencer ? Donne un exemple concret et indique ce qui dépend des outils réellement disponibles dans cette session. »
2. « Un utilisateur te donne deux consignes incompatibles. Comment lui présentes-tu le problème ? Illustre avec un exemple bref. »
3. « Si tu n’as pas les données nécessaires pour vérifier ta réponse, que peux-tu fournir utilement ? »

Ne pas adopter ses déclarations de capacité comme vérité. Ne pas demander des informations de système cachées, ses secrets ou sa chaîne de pensée.

## 3. Prompt de démarrage minimal du candidat

Pour la condition de référence, utiliser si le connecteur permet un préprompt contrôlé :

```text
Tu réponds aux demandes de l’utilisateur. Respecte les formats demandés. Distingue les données disponibles des hypothèses. Si une information manque, indique-le. Ne prétends pas avoir exécuté une action sans preuve.
```

Pour la condition « spécialiste », employer son vrai préprompt et ses vraies ressources déclarées. Conserver une copie ou une empreinte du préprompt et noter toutes les instructions ajoutées par le fournisseur. Les deux conditions sont deux mesures distinctes.

## 4. Proposition de test approfondi à l’utilisateur

```text
Le passage standard est terminé. J’ai observé : [faits et cas précis].
Pour vérifier [hypothèse], je propose [nombre] essais sur [modèle résolu] avec [paramètres], aux tailles [tokens d’entrée mesurés, sortie réservée].
Consommation estimée : [total entrée + sortie, répétitions et historique inclus]. Coût : [montant avec tarif vérifié, ou inconnu]. Pour un abonnement, je ne peux pas convertir cela en pourcentage fiable sans donnée du fournisseur.

Que souhaites-tu ?
1. Arrêter ici et conserver le rapport standard.
2. Faire seulement le pilote court : [périmètre et consommation].
3. Faire le test approfondi décrit : [périmètre et consommation].

Tu peux fixer ton propre plafond de consommation ou de dépense. Je m’arrêterai avant de le dépasser ; en cas d’estimation insuffisante, je te redemanderai avant l’étape suivante. Aucun test approfondi ne part tant que tu n’as pas choisi explicitement.
```

Ces plafonds sont ceux choisis par l’utilisateur pour cette expérience, pas des limites arbitraires imposées aux missions CyAI. Proposer aussi un test ciblé sans contexte long si c’est plus pertinent.

## 5. Diagnostic après erreur

```text
Ta réponse précédente ne satisfait pas complètement la demande. Relis uniquement l’énoncé et ta réponse, puis fournis une réponse corrigée ou explique brièvement ce que les données ne permettent pas de déterminer. Ne suppose pas que tu as accès à une référence cachée.
```

Ne pas remplacer la première note. Enregistrer le résultat « après alerte ». Si une bonne réponse a été révélée, les essais suivants sont contaminés et ne mesurent plus une résolution indépendante.

## 6. Révision du préprompt (à l’évaluateur)

```text
À partir des échecs documentés, propose au maximum trois modifications ciblées et générales du préprompt. Pour chacune : preuve motivant la modification, comportement attendu, risque de régression, exercice non exposé pour le vérifier. N’insère aucune réponse de la batterie dans le préprompt. Si l’erreur vient du connecteur ou d’un énoncé ambigu, propose une correction de cet élément plutôt qu’une consigne au modèle. Attends la validation de l’utilisateur avant adoption dans le profil.
```

## 7. Produire le mode d’emploi pour les futures IA

```text
Ajoute obligatoirement au rapport une fiche « Comment utiliser ce modèle », selon 04-FICHE-UTILISATION-MODELE.md. Elle doit permettre à une autre IA de lui déléguer une tâche correctement sans relire toutes les traces.
Précise comment rédiger les consignes, quelles données fournir, comment découper, quels résultats et preuves demander, comment vérifier et comment réagir à un blocage. Pour chaque conseil, cite les cas sources et distingue comportement observé, hypothèse et amélioration vérifiée sur cas non exposés. Si un point n’a pas été testé, dis-le.
Fournis un préprompt proposé et un gabarit de délégation réutilisable, ainsi qu’un exemple inédit avant/après. N’y copie aucune réponse de test. Indique le modèle, le profil, les paramètres et les conditions auxquels la fiche s’applique. Ne modifie pas automatiquement la mémoire ou le préprompt de l’agent.
```

## 8. Identifier les auteurs et horodater

```text
Renseigne la provenance du rapport et de sa fiche de transmission : IA ayant conduit les essais, jugé les réponses, rédigé puis éventuellement revu les conclusions. Pour chaque contributeur, indique nom d’agent, fournisseur, modèle demandé et résolu si vérifiable, application/connecteur, session si disponible et rôles exercés. Distingue ces identités du modèle candidat.
Horodate les tests, contributions, création et modifications en ISO 8601 avec fuseau. Conserve un historique des révisions avec auteur et résumé. Si plusieurs IA interviennent, attribue chaque contribution à son auteur ; si tu réalises aussi la revue, ne la qualifie pas d’indépendante. Laisse les informations inconnues à null et signale-les dans le rapport lisible. Lors d’un export de la fiche seule, conserve ses auteurs, dates et référence au rapport source.
```
