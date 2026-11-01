# Audit UI/UX CyAI 0.2.58 — 31 octobre 2026

L’audit a utilisé un service jetable, un projet temporaire et des connecteurs de test, ainsi que les moteurs Windows et Phonon pour les essais audio synthétiques. Les conversations et processus de l’application utilisée par l’utilisateur n’ont pas été modifiés. Les catalogues et le code des plugins intégrés n’ont pas été remplacés pendant cet audit.

## Périmètre vérifié

- Les 13 catégories de paramètres : modèles et préférences, modèles locaux, voix, téléchargements, connecteurs, apparence, MCP, plugins, CyTools, sauvegarde, dossiers, contexte et IA, application Windows.
- Projet : vue d’ensemble, utilisation, historique, statistiques, configuration, mémoire (création et conservation d’une note), épinglés, skills et contexte, plugins, équipe vide et board vide.
- Journaux : Journal, RAW, opérations MCP, connecteurs et graphiques de ressources.
- Bibliothèque d’agents, liste des méthodes et ouverture de l’éditeur de graphe.
- Conversation : saisie, Maj+Entrée sans envoi, Entrée avec réponse du connecteur simulé et retour du bouton à son état disponible.
- Médias : ouverture d’un OBJ dans le viewer, changement de fond et filaire, fermeture. Les matériaux PBR et autres formats sont couverts par les tests existants, pas par une nouvelle campagne visuelle de tous les formats.
- CyMD : création, modification et enregistrement d’un document de test comme pièce jointe. CyAnnota : chargement de l’éditeur et présence des outils image/vidéo/3D et de la liaison CyAI.
- Affichage sombre et clair, fenêtres de 1365 × 900, 614 × 760 et 520 × 760 ; aucun débordement horizontal de document sur les deux petites tailles. Les composants natifs Windows et les connexions aux fournisseurs réels restent soumis à leurs propres comportements.

## Défauts corrigés

| Constat | Correction |
|---|---|
| Voix, téléchargements et CyTools disparaissaient depuis la liste des modèles | Une navigation de paramètres partagée, avec catégorie courante signalée |
| Équipe vide déclenchait des appels réservés à une équipe existante et laissait l’ancien écran affiché | Chargement de la mémoire/score seulement si leurs panneaux existent ; bouton de création visible |
| Le message « board au lot 2 » était encore affiché | Texte décrivant le parcours actuel |
| Nouvelle méthode ouverte avec son nœud d’entrée hors cadre | Cadrage automatique à la création aussi |
| Inspecter le contexte avait le type submit implicite | Bouton explicitement de type button |
| Mention d’une capacité fournisseur alors qu’aucune valeur n’était connue | Limite non communiquée affichée explicitement |
| Champs de contexte locaux encore plafonnés à 131 072 dans le HTML | Retrait de ce plafond obsolète ; le moteur et le modèle restent responsables de la capacité réellement utilisable |
| Réponse ancienne d’un formulaire pouvant fermer un nouveau dialogue | Identification du dialogue à l’envoi et vérification avant fermeture |
| Gestionnaire local pouvant rester sur le chargement après erreur | Message sur place et bouton Réessayer |
| Détection des voix Windows bloquant l’ouverture des réglages | Découverte en arrière-plan et actualisation des listes sans effacer les champs |
| Voix sélectionnée susceptible de disparaître pendant la découverte | Conservation explicite de la sélection enregistrée |
| Options de tous les moteurs visibles en mode automatique | Seulement les options du moteur choisi ; valeurs cachées préservées et exclues de la validation |
| Clonage et détails vocaux envahissant la page | Section repliable, formulaires élargis, cases à cocher alignées, arrêt de lecture dans les paramètres |
| Processus vocaux et flux non fermés après certaines erreurs | Fermeture lors d’un délai d’initialisation et fermeture des pipes après arrêt |
| Menu de fichiers au clavier incomplet | Flèches, Début/Fin et Échap |
| Bouton flottant recouvrant le rail, navigation étroite encombrante | Ancrage dans l’application, catégories défilantes et rail vertical préservé |
| Texte des notifications et graphiques presque invisible en clair | Couleurs adaptées au thème et focus visible |
| Journal noyé par les lectures périodiques | Suppression des traces de succès de cinq lectures de suivi ; les erreurs et modifications restent journalisées |

## Phonon

Intégration du paquet officiel `fermion-research==0.2.15`, avec ses modèles préparés dans le cache CyAI. Python/PyTorch CPU et les modèles se téléchargent sur demande ; aucun poids n’entre dans l’installateur. Les poids font environ 156–158 Mo par modèle ; cette taille ne représente ni le téléchargement complet des dépendances ni la RAM d’exécution.

- Phonon-2 : anglais uniquement.
- Phonon-2.5 : 25 langues, dont le français. Sélection proposée par défaut dans l’option Phonon.
- Sous Windows : CPU, phrase transcrite après capture ; le modèle reste dans son worker pour les dictées suivantes, puis est libéré après l’inactivité configurée.
- Un résultat signalé tronqué par le moteur est présenté comme incomplet, jamais accepté silencieusement.

Sources primaires : [dépôt officiel](https://github.com/fermionresearch/phonon), [documentation de transcription](https://www.fermionresearch.com/docs/speech/), [paquet PyPI](https://pypi.org/project/fermion-research/0.2.15/). Code Apache-2.0, modèles Phonon-2/2.5 CC-BY-4.0.

### Essai réel local

Deux phrases générées avec les voix Windows, converties en WAV mono 16 kHz, puis transcrites deux fois par le nouvel adaptateur. Aucun microphone enregistré, aucun audio transmis à un service distant.

| Modèle | Audio | Premier appel avec chargement | Appel modèle déjà chargé | Résultat |
|---|---:|---:|---:|---|
| Phonon-2, anglais | 3,42 s | 1,907 s | 0,062 s | Phrase attendue restituée |
| Phonon-2.5, français | 4,94 s | 1,985 s | 0,140 s | Phrase attendue restituée |

Ces deux exemples valident le chemin technique, pas un taux d’erreur représentatif ni la précision avec un microphone réel. Résultats conservés dans `test-results/audit058-phonon-real.json`.

## Validation et limites

La suite complète initiale comportait 489 tests. Les fixtures obsolètes de mémoire et de contrôle MCP ont été mises à jour ; le coffre DPAPI passe avec les droits Windows normaux. Un second passage a rencontré quatre erreurs de nettoyage de répertoires temporaires Windows, sans assertion fonctionnelle en échec ; les quatre tests concernés passent en reprise isolée. Les trois nouveaux tests Phonon passent, de même que les tests ciblés voix, équipes, contrôles d’inférence, modèles locaux et scripts de rendu JavaScript.

Les appels payants et authentifications des fournisseurs, la capture de la voix de l’utilisateur et une campagne exhaustive de modèles/VRAM n’ont pas été exécutés. Les tests de mission, annulation, file d’attente et évaluation utilisent les connecteurs simulés de la suite. Le module vocal ne télécharge ses modèles que lors de son installation explicite.

Installateur final : version 0.2.58, empreinte SHA-256 et manifeste vérifiés ; les dix fichiers UI modifiés comparés aux sources correspondent au bundle livré. Les trois serveurs jetables et l’onglet d’audit ont été fermés.
