# Moteurs expressifs locaux — CyAI 0.2.34

Validation effectuée par l’assistant Codex le 19 septembre 2026, sur Windows, Ryzen 9 7900X et RTX 3090 24 Go. Identifiant précis du modèle évaluateur non attesté. Il s’agit d’une validation d’intégration, pas d’une évaluation perceptuelle complète de la qualité vocale.

## Utilisation

Après installation et redémarrage volontaire de CyAI : Paramètres > Voix > Voix. Les trois moteurs installés sont détectés depuis leurs manifestes locaux. Choisir la voix, ajuster les champs affichés, puis « Enregistrer et écouter la voix ». Le texte de préécoute est modifiable. Aucune nouvelle clé API ni facturation API ; les calculs et références audio restent locaux.

- Qwen : CustomVoice 1.7B pour une voix prédéfinie et une consigne de style ; VoiceDesign pour décrire une nouvelle voix ; Base pour une référence audio. La consigne ne s’applique pas au clonage Base. Français ou anglais selon la langue de dictée ; les consignes en anglais sont conseillées.
- Chatterbox Multilingual : intensité expressive, guidage CFG et température ; voix par défaut ou référence. Le filigrane natif est conservé.
- Fish S2 Pro : balise de style, température et top-p ; une référence demande sa transcription exacte. Sans référence, le timbre peut changer. Les balises ne garantissent pas une émotion parfaitement reproduite.
- Mes voix : importer un WAV ou enregistrer avec accord ; choisir le moteur dans la liste avant « Utiliser cette voix ». Le bouton « Transcription » renseigne les mots exacts de l’échantillon. Les paramètres sont communs aux voix du même moteur, pas des profils indépendants pour chaque agent.

## Ressources et comportement

Les environnements sont isolés sous `<dossier-données-CyAI>/runtimes/voice-{qwen,chatterbox,fish}`. Les modèles téléchargés et épinglés à une révision sont sous `<dossier-modèles>/voice/huggingface/models`. Ils ne sont pas contenus dans l’installateur. Les futures installations utilisent les dossiers de données et de modèles configurés dans CyAI.

Changer de moteur expressif ou de variante décharge le précédent. Les modèles sont conservés entre phrases puis libérés après le délai d’inactivité existant. Fish a rapporté 20,3 à 20,6 Go de mémoire GPU utilisée lors des essais ; le fournisseur recommande au moins 24 Go. Une IA locale déjà chargée peut donc empêcher son démarrage. Aucun modèle de conversation n’est déchargé automatiquement.

Qwen et Chatterbox produisent ici la phrase entière avant lecture. Fish utilise les segments audio de son moteur ; le très court exemple de test ne produisait qu’un segment. La lecture reste interruptible via le mécanisme vocal existant, mais l’inférence courante est drainée avant le prochain texte. Pas de promesse de mode vocal aussi réactif que Pocket ou Codex.

## Mesures réelles

Phrase : « Bonjour, je suis prêt à discuter avec vous. » Pas de microphone ni lecture sonore pendant les essais. Les premiers essais incluent le chargement, avec des caches disque déjà utilisés. Ce sont des observations individuelles, pas des moyennes. Les durées audio varient à cause de l’échantillonnage.

| Cas | Premier audio, chargement compris | Premier audio, modèle chargé |
|---|---:|---:|
| Qwen CustomVoice, Ryan | 10,14 s | 2,60 s |
| Chatterbox, voix native | 15,30 s | 1,67 s |
| Fish, référence synthétique | 47,50 s | 2,80 s |

Autres essais réussis : Qwen VoiceDesign, Qwen Base avec clonage, Chatterbox avec clonage, Fish sans référence. Les références utilisées sont des voix générées pour le test, pas la voix d’une personne. Les WAV, mesures JSON, scripts et journaux sont dans `experiments/voice-engines`.

La retranscription locale Kyutai retrouve la phrase exacte pour Qwen CustomVoice, Chatterbox avec référence et Fish avec/sans référence (hors casse). Elle relève des écarts pour Qwen VoiceDesign, Qwen Base et Chatterbox natif. Ce contrôle automatique ne permet pas de distinguer à lui seul une erreur de prononciation d’une erreur de reconnaissance. Prononciation, fidélité du timbre et émotions restent à écouter humainement. Une première génération Chatterbox a également déclenché la détection native de répétitions : les résultats varient selon voix et paramètres.

## Validation et compatibilité

Suite complète : 450 tests, 2 ignorés, aucun échec. Après les dernières corrections Windows : 43 tests vocaux réussis. Vérifications navigateur : affichage des paramètres par moteur et sauvegarde pour les trois moteurs. La génération, le clonage et la libération des processus ont été essayés sur le GPU réel. Les essais ne démontrent pas la qualité sur tous les textes, langues et styles.

Corrections nécessaires : certificats de confiance Windows via truststore (TLS toujours vérifié), téléchargements Hugging Face dans des dossiers ordinaires pour éviter les symlinks Windows, TensorBoard 2.18 pour les dépendances Fish, setuptools 80.9 pour le filigrane Chatterbox. Qwen utilise SDPA ; Fish fonctionne sans compilation Triton. Pas de désactivation des contrôles d’accès ou du filigrane.

## Versions et sources

- qwen-tts 0.1.1 ; trois modèles Qwen3-TTS-12Hz-1.7B, révisions fixées dans le worker. [Source officielle](https://github.com/QwenLM/Qwen3-TTS).
- chatterbox-tts 0.1.7, modèle multilingue v2 distribué avec cette API PyPI. La branche GitHub propose des évolutions non présumées disponibles dans ce paquet. [Source officielle](https://github.com/resemble-ai/chatterbox).
- Fish Speech commit `214da3cd841bda85da2496b96cd3c4d7edb1337e`, modèle `fishaudio/s2-pro`. Conditions Fish Audio Research License indiquées dans le catalogue, distinctes des licences Qwen/Chatterbox. [Source officielle](https://github.com/fishaudio/fish-speech), [recommandation GPU](https://github.com/fishaudio/fish-speech/blob/main/docs/en/inference.md).
