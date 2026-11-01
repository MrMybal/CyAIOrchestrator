# Rapport et intégration ultérieure

## Rapport lisible attendu

- Identité : agent, version du profil et du préprompt, modèle demandé et réellement résolu, fournisseur, paramètres, outils et mémoire présents.
- Périmètre autorisé et réellement exécuté ; dates ; forme et version de batterie ; entretien séparé des scores.
- Tableau par dimension : cas exécutés / prévus, résultat, preuves, incidents, interprétation limitée.
- Pour chaque cas fermé : réponse brute, verdict et défaut précis. Un échec de format n’efface pas un contenu éventuellement correct : conserver les deux observations sans modifier le verdict strict.
- Pour chaque cas ouvert : chacun des quatre critères vaut 0 ou 1, avec citation ou absence constatée ; total sur 4 pour ce cas seulement. Si un critère est ambigu, marquer à revoir sans inventer un score. Revue de la limite de mots : définir les mots comme segments séparés par espaces ; une violation reste une observation distincte du score sémantique.
- Temps : latence avant premier événement si disponible, durée totale observée, tokens d’entrée/sortie réels ou inconnus, tokens mis en cache et de raisonnement seulement si fournis. Ne pas les déduire de la longueur du texte.
- Résultat pratique : tâches auxquelles confier cet agent, garde-fous utiles, faiblesses observées, preuves insuffisantes, prochaine expérience.

Pas de classement universel ou de score unique d’intelligence. « Réussite 1/1 sur cet exercice » ne signifie pas « fiable à 100 % ». Un passage sert au dépistage. Une décision importante demande des cas réels supplémentaires et une validation humaine, avec accord de consommation.

## Fiche associée à l’agent

Utiliser `report-template.json` comme proposition de contrat de données (ce n’est pas un schéma JSON Schema validé). Les champs inconnus restent null. Conserver les traces brutes hors du contexte candidat et les référencer par identifiants. Une absence de réponse due au transport se marque `infrastructure_error`, pas `fail` de contenu. Le script produit des verdicts de contenu provisoires ; l’opérateur établit le statut final après vérification du transport.

Prévoir plus tard dans CyAI :

1. Une méthode spéciale qui choisit le profil, le modèle, la piste et les sessions d’essai.
2. Un écran de consentement pour le périmètre coûteux avec comptage disponible et estimation honnête.
3. Des espaces séparés pour le candidat et le juge : aucune lecture des références par les outils du candidat.
4. Un stockage versionné des rapports, traces, propositions et validations, rattaché à l’agent ; garder les versions antérieures.
5. Un onglet « Évaluations » avec forces observées, faiblesses et comparaisons à paramètres identiques.
6. Une proposition explicite d’amélioration du préprompt ; adoption distincte et réversible, suivie d’un test sur cas non exposés.

Cette version ne crée aucun de ces éléments dans CyAI. Elle fournit les documents et utilitaires préparatoires.

## Mémoire transférable

Stocker comme apprentissage proposé une règle générale étayée (« demander la définition du champ avant de mapper un CSV ambigu »), pas l’énoncé ni la réponse d’un test. Séparer observations liées au modèle, au préprompt, au projet et au connecteur. Un changement de modèle ou de paramètres rend une ancienne évaluation informative mais pas automatiquement valide pour le nouvel agent.

## Extensions nécessaires pour un vrai spécialiste

Ajouter des fixtures métier et critères externes : tests fonctionnels réels pour le code, fichiers et mesures pour Blender, références annotées pour la vision. La présente batterie est textuelle et sans outils ; elle ne certifie pas ces compétences. Les outils s’évaluent ensuite dans un environnement isolé avec vérification des effets réels. Le générateur de contexte livré mesure surtout extraction, mise à jour et provenance ; synthèse complexe et mémoire sur plusieurs tours demandent des exercices additionnels avant toute conclusion.

## Transmission obligatoire aux prochaines IA

Chaque rapport inclut la fiche `04-FICHE-UTILISATION-MODELE.md` remplie : instructions à l’IA appelante, formulation des demandes, contexte à transmettre, vérifications, reprise et escalade. Produire aussi un préprompt proposé et un gabarit de délégation. Relier chaque conseil aux essais, distinguer hypothèse et amélioration vérifiée, et préciser les conditions de validité. Le rapport structuré stocke cette transmission sous `handoff_guide`.

## Qui a évalué, rédigé et vérifié — traçabilité obligatoire

Afficher en tête du rapport : « Tests conduits par [agent, fournisseur, modèle réellement résolu], le [date et heure avec fuseau]. Rapport rédigé par […], le […]. Revu par […], le […], ou non revu. Dernière modification : […]. »

L’identité de l’IA évaluatrice est distincte de celle du modèle candidat. Identifier chaque contributeur : nom de l’agent, version de profil si disponible, fournisseur, application/connecteur, modèle demandé et modèle réellement résolu, source de cette identification et identifiant de session si disponible. Ne pas déduire le modèle de son style ou de sa propre déclaration : si l’identité technique n’est pas disponible, indiquer « non vérifiée » et conserver le champ résolu à null.

Distinguer les rôles : conduite des tests, jugement, rédaction, revue. Si une seule IA remplit tous ces rôles, l’indiquer ; ne pas présenter son auto-relecture comme une revue indépendante. Pour chaque cas, associer les contributeurs qui l’ont exécuté et jugé, ainsi que ses heures de début et de fin. Une correction automatique mentionne aussi l’outil et la version de batterie, sans lui inventer un auteur IA.

Enregistrer création, modification et contributions en ISO 8601 avec fuseau. Conserver l’historique des révisions (qui, quand, quoi), sans remplacer l’auteur initial par le dernier intervenant. Dates et identités inconnues restent null et sont affichées comme inconnues. La fiche destinée aux prochaines IA doit garder ses auteurs, relecteurs, dates et référence à la révision source même lorsqu’elle est exportée seule.

Le contrat de données `draft-0.3` ajoute `provenance` au rapport et à `handoff_guide`, ainsi que les identifiants d’exécutants et de juges dans les cas. Les contributeurs sont référencés par un identifiant stable dans ce rapport.
