# Piper et méthode d’évaluation — 0.2.37

Catalogue : https://huggingface.co/rhasspy/piper-voices/blob/main/voices.json
Instantané livré : révision c10ece1aade47bb51c153c893d14e5bf8e5b7117, 177 modèles.
La liste est lue depuis voices.json, sans liste française codée en dur. Le bouton d’actualisation obtient la révision courante puis télécharge son manifeste immuable. Une erreur laisse le cache précédent intact. Aucun téléchargement réseau au démarrage ni de modèle implicite.

Paramètres > Voix > Voix Piper : recherche, langue (fr_FR par défaut), qualité, téléchargement par modèle. Les locuteurs installés deviennent disponibles dans le choix global et les voix des agents. Un modèle multivoix ne se télécharge qu’une fois. L’identifiant numérique réel de chaque locuteur est passé au moteur. Un seul moteur Piper est conservé en cache pour éviter de charger une copie pour chaque locuteur.

Piper utilise le processeur. Les fichiers ONNX et leur configuration sont vérifiés avec le MD5 publié ; leur provenance est le dépôt officiel via HTTPS, avec révision figée. Une SHA-256 est calculée localement mais n’est pas présentée comme publiée. La fiche de chaque modèle indique sa licence. Le moteur Piper Windows existant est conservé.

## Évaluation

La méthode cyai-agent-evaluation-v1 était uniquement installable manuellement. Elle est maintenant ajoutée au démarrage desktop/serveur une seule fois par bibliothèque. Les modifications et suppressions volontaires sont préservées. L’action evaluation_method_install est aussi exposée aux agents, avec les permissions globales d’écriture existantes. Aucun candidat n’est lancé à l’installation ; les essais de saturation du contexte restent soumis au choix explicite de l’utilisateur.

La bibliothèque de l’application actuellement ouverte a été réparée par cette action locale, sans redémarrer ni lancer d’évaluation.

## Validation

- Tests ciblés : les 7 variantes françaises, les 125 identifiants MLS, Jessica/Pierre, cache conservé après échec, rejet d’un fichier altéré, visibilité des locuteurs après une seule installation ; démarrage idempotent et conservation des éditions/suppressions de méthode.
- Navigateur, instance isolée : 7 modèles français affichés ; recherche mls : 2 résultats.
- Installation réelle MLS medium, empreintes modèle et configuration conformes. Synthèse française, locuteur 0 : 0,734 s pour 3,718 s d’audio ; locuteur 124 : 0,625 s pour 4,066 s d’audio. Mesures uniques, incluant le lancement du moteur, sur la machine locale ; qualité perceptive de toutes les voix non évaluée.
- Suite générale : 463 tests, 2 ignorés. Une erreur intermittente de nettoyage de dossier temporaire Windows (WinError 145) après le test de restauration ; assertions de restauration réussies et reprise isolée du test réussie. Aucun autre échec.
- Traces : experiments/voice-engines/full-tests-037.txt et piper-probe-037.txt.

Les 177 modèles n’ont pas tous été synthétisés. L’actualisation future peut ajouter des modèles dont la compatibilité avec l’ancien moteur Windows reste à vérifier. Aucun modèle ni runtime de l’application active n’a été arrêté.
