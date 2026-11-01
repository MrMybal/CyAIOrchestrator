# Audit vocal et méthode d’évaluation — CyAI 0.2.31

Date : 19 septembre 2026, Europe/Paris. Réalisé par l’assistant Codex de cette conversation (identité exacte du modèle évaluateur non exposée à ce travail). Matériel observé : Ryzen 9 7900X, 12 cœurs / 24 threads, RTX 3090, 24 576 Mio de VRAM. Instantané au démarrage : 1 702 Mio utilisés, GPU à 9 % ; ce n’est pas une mesure de contention pendant une mission lourde.

## Verdict Codex avec abonnement

**Indisponible par les interfaces testées avec la connexion ChatGPT actuelle.** Il ne s’agit pas d’une conclusion sur toutes les interfaces futures ni sur l’implémentation privée du bouton vocal de Codex Desktop.

La [documentation officielle App Server](https://learn.chatgpt.com/docs/app-server) présente l’intégration de l’authentification, des conversations et des événements de Codex. Son schéma généré par la version installée expose des méthodes expérimentales `thread/realtime/start`, `appendAudio` et des événements audio. Une commande présente n’est pas une autorisation d’accès.

Essais minimaux sans micro, sans clé API, sans extraction de jeton et sans modification des projets :

| Binaire | Authentification confirmée par account/read | Essai | Résultat |
|---|---|---|---|
| CLI 0.155.0 | chatgpt | protocole par défaut, sortie audio, WebSocket | événement `thread/realtime/error` : `realtime conversation requires API key auth` |
| CLI 0.155.0 | chatgpt | version v3 | même refus |
| Codex Desktop 0.154.0-alpha.6.2 | chatgpt | version v3 | même refus |

L’accusé de réception du démarrage était vide et sans erreur JSON-RPC, mais l’événement suivant refuse la session : ce n’est **pas** un succès vocal. Aucun audio bidirectionnel ou interruption distante n’a donc pu être testé. Une simple transcription locale envoyée à Codex reste possible et distincte de cette fonctionnalité. Pas d’option Codex audio prétendument opérationnelle ajoutée, pas de nouvel abonnement, pas de facturation API. Réexaminer à une future version si un chemin officiellement pris en charge devient accessible.

Preuves : `experiments/voice-audit/codex-probe*.json`, scripts `probe_codex*.py`, schéma public dans `experiments/codex-voice-schema`. Les sondes ne lisent pas les fichiers d’authentification ; le binaire Codex gère sa connexion existante. Les fils de test sont éphémères.

## État conservé et causes identifiées

Configuration réellement enregistrée : Kyutai STT 1B sur GPU, français ; Pocket TTS français, voix anna sur CPU ; silence 1 200 ms ; fermeture après 120 s sans parole ; déchargement après 300 s ; lecture limitée à 2 500 caractères. Ces réglages existants sont conservés. La vitesse 2.0 configurée ne s’applique pas à Pocket : l’interface le précise désormais.

1. **Coupure pendant la parole, reproduite.** Le plancher de bruit montait pendant une voix constante, qui finissait par être classée comme silence. Il n’est plus mis à jour sur les blocs classés comme parole.
2. **Coupure fixe à deux minutes.** Le code terminait toute capture à 120 000 ms, même pendant la parole. Retirée. Le délai sans parole reste un réglage utilisateur ; zéro permet l’écoute continue. Nouvelles configurations : zéro et pause de 1 800 ms. Aucun changement silencieux de vos valeurs existantes.
3. **Synthèse bloquante par segment.** Le texte était déjà découpé et transmis pendant la génération de l’IA, mais Pocket rendait un WAV complet. Il transmet maintenant les blocs PCM dès leur production. Un seul périphérique de sortie reste ouvert pendant le segment, avec trois buffers maximum déjà soumis au pilote et une file de huit blocs entre synthèse et lecteur.
4. **Micro fermé pendant la réponse.** Ajout d’une écoute avec interruption parlée, activable explicitement en mode casque. Détection après 150 ms de blocs vocaux consécutifs. Elle arrête la lecture, pas la mission de l’agent. La phrase suivante est conservée ; l’interface permet d’attendre la fin de la réponse ou de l’annuler. Bouton « Reprendre la parole » disponible sans activer l’écoute simultanée.
5. **Une synthèse en cours était invisible à l’état “parle”.** Le micro pouvait se rouvrir avant l’arrivée du premier WAV. Corrigé en comptant la synthèse dans l’activité vocale.
6. **Sondages d’interface concurrents.** La boucle de lecture d’état ne superpose plus plusieurs requêtes lentes, évitant les doubles consommations de transcription et les états périmés.
7. **Capture périmée.** Une transcription terminée après fermeture/changement de conversation ne doit plus être livrée à la nouvelle conversation. Une nouvelle écoute est refusée clairement pendant la finalisation de la précédente.

Les modèles sont inchangés. Kyutai et Pocket étaient déjà conservés chargés entre deux utilisations ; ce comportement reste. Whisper charge encore son processus/modèle à chaque dictée, mais ce n’est pas le moteur actuellement utilisé. Une copie complète du PCM n’est plus conservée pour le STT en continu ; avant parole, seul un pré-début d’une seconde est conservé pour Whisper.

## Mesures et comparaison

Essais synthétiques locaux, sans capturer le micro. Pocket a produit les mêmes textes avant/après, une exécution par condition. La génération est stochastique : durées de voix différentes, pas une moyenne ni une preuve de qualité équivalente. Le cas long ci-dessous est **une requête TTS de 260 caractères**, pas le délai complet d’une réponse CyAI : l’application découpait déjà ses réponses en segments.

| Mesure | Avant | Après |
|---|---:|---:|
| Premier audio, phrase courte, moteur froid | 7,060 s | 4,626 s |
| Premier audio, phrase courte, moteur chaud | 2,289 s | 0,235 s |
| Premier audio, texte long, moteur chaud | 12,033 s | 0,453 s |
| Génération totale de la phrase courte à chaud | 2,289 s | 3,417 s |
| Génération totale du texte long | 12,033 s | 13,723 s |
| Parole continue simulée, seuil de silence identique | arrêt erroné à 8,05 s | pas de coupure sur 125 s |
| Phrase de 600 ms puis silence, seuil 1 200 ms | fin à 1,80 s | fin à 1,80 s |
| Pause intermédiaire de 800 ms | phrase conservée | phrase conservée |
| Silence seul, dans le callback de capture | coupure fixe à 120 s | aucune coupure fixe ; délai utilisateur géré séparément |
| Interruption par parole | pas de micro pendant la réponse | logique testée ; validation humaine au casque restante |

Après modification, le pilote Windows rend la main **49,3 ms** après le signal d’arrêt (un essai, sortie à volume nul, sans microphone). Ce n’est ni une mesure acoustique ni le délai depuis le début réel de votre parole. La détection ajoute 150 ms, les blocs micro font 50 ms et le moniteur tourne toutes les 150 ms. Les variations de pilotes restent à mesurer.

**Reconnaissance Kyutai :** chargement froid 3,52 s avant, 3,51 s après. Après injection des blocs en temps réel : finalisation 0,106 s avant, 0,156 s après ; audio source 2,80 s puis 4,32 s, donc pas une comparaison de débit strictement identique. Transcriptions synthétiques : « Bonjour, je suis prêt à vous aider. » puis « Bonjour, je suis prête à vous aider. ». Aucun jugement de qualité du français sur ce seul exemple. Le silence de fin configuré (1,2 s ici) s’ajoute avant la finalisation ; réduire aveuglément ce seuil couperait les hésitations.

**Génération Codex, abonnement existant :** deux essais indépendants sans outils, modèle résolu `gpt-6-astra`. Court : premier texte 6,173 s, fin 7,056 s. Long (~70 mots demandés) : premier texte 4,549 s, fin 7,768 s. Mesuré après `turn/start`, inclut l’attente fournisseur ; l’accès ne permet pas de séparer sa file interne de son calcul. Ces essais ne reproduisent pas tout le contexte d’une de vos missions. Aucun changement de modèle effectué.

**Interface :** récupération de transcription par sondage toutes les 300 ms (attente théorique 0–300 ms, hors requête). Les journaux ajoutés permettent de relever `end_of_speech`, `transcription_start/complete`, `transcript_taken`, premier événement de mission, premier texte, fin du texte, début de synthèse, premier audio, fin de synthèse, début et fin/arrêt de lecture. Accès par « Mesures vocales » dans la barre. Timestamps UTC et temps monotones ; pas d’audio ni de texte privé dans ces diagnostics. Les événements récents sont conservés en mémoire, pas dans un enregistrement permanent. Le début de lecture signifie remise au chemin de lecture, pas son audible physiquement.

**Pas de mesure bout en bout d’une conversation humaine dans cette livraison.** Ne pas additionner naïvement les valeurs : transcription et parole se chevauchent, génération texte et audio aussi. L’essai au casque, la qualité perçue et le comportement dans une longue mission avec contention restent à mesurer.

## Priorités restantes

| Action | Impact attendu | Effort / statut |
|---|---|---|
| Détecteur stable et absence de coupure fixe | Élevé sur les interruptions intempestives | Réalisé, reproduit avant/après |
| Pocket en flux et modèles chauds | Élevé sur le premier son | Réalisé ; écoute humaine restante |
| Reprise de parole au casque + bouton | Élevé sur le dialogue | Réalisé ; faux déclenchements à mesurer au casque |
| Ajuster le silence à votre rythme (ex. 1 800 ms) | Élevé sur les hésitations, augmente le délai d’envoi | Réglage disponible, valeur existante conservée |
| Tester un effort de raisonnement plus léger pour la discussion seule | Potentiellement élevé, vu les 4,5–6,2 s avant texte | Faible, à comparer avec vos attentes ; pas modifié sans preuve |
| Annulation d’écho acoustique et VAD plus robuste | Élevé pour mains libres sur haut-parleurs | Élevé ; non implémenté. Le mode casque n’est pas une AEC |
| Arrêter le calcul TTS devenu inutile | Moyen sur reprise rapide d’une longue phrase | À étudier : actuellement la lecture est coupée immédiatement mais le worker termine et ses anciens blocs sont jetés pour garder le protocole aligné |
| Vérifier sous forte occupation CPU/GPU, buffers et débit irrégulier | Élevé sur stabilité selon charge | Essais matériels supplémentaires ; aucun goulet de VRAM démontré au repos |

Le détecteur local reste un seuil de niveau, pas une reconnaissance sémantique de fin de phrase. Bruit permanent, clavier et écho peuvent le tromper. Le comportement au casque est présenté comme une option, désactivée par défaut.

## Méthode d’évaluation intégrée

Bibliothèque d’agents → Méthodes → **Ajouter la méthode d’évaluation**. L’ajout ne lance aucune IA et ne remplace pas une méthode déjà éditée. La méthode embarque protocole, prompts, batterie A/B, corrigés et utilitaires dans `cyai/evaluation_kit`.

Fiche d’agent → Méthodes → **Évaluations et mode d’emploi de cet agent** : import JSON avec agent.id correspondant, auteur(s), rôles, date avec fuseau et fiche handoff_guide ; export et historique conservés. La nouvelle table `agent_benchmarks` fait partie des sauvegardes. Les identités de rapports importés sont déclaratives, pas des signatures cryptographiques. Le MCP `evaluation_guides` expose uniquement identité, provenance et guide aux prochaines IA ; `evaluation_report_save` est une écriture globale soumise aux autorisations MCP existantes. Les spécialistes ayant des rapports sont signalés à leur appelant.

Il s’agit d’une méthode guidée, pas d’un exécuteur de benchmarks automatique avec isolation garantie. L’évaluateur doit disposer d’un accès au candidat isolé des références ; sinon il prépare l’expérience et annonce la limite. Aucun test candidat ou saturation n’a été lancé ici. L’accord pour les tests coûteux reste explicite dans le protocole ; aucun préprompt ni mémoire n’est modifié à l’import d’un rapport.

## Vérification et reproduction

- 443 tests du projet : succès, 2 ignorés. Une instabilité préexistante de classement de conversations créées à la même milliseconde a été corrigée avec un second critère de tri stable.
- Tests ciblés : 36 vocaux, 3 intégration des rapports ; le correcteur autonome a ses propres tests.
- Interface sur base temporaire distincte : méthode ajoutée, nouvel ajout idempotent, dialogue des rapports et réglages vocaux contrôlés ; aucun micro activé.
- Syntaxe JavaScript vérifiée. Version 0.2.31 construite séparément de l’installation ouverte.

Depuis la racine du dépôt :

```powershell
.desktop-venv\Scripts\python.exe -m unittest discover -s tests -p 'test_voice*.py'
.desktop-venv\Scripts\python.exe -m unittest discover -s tests -p test_agent_evaluation.py
.desktop-venv\Scripts\python.exe experiments\voice-audit\benchmark_local.py experiments\voice-audit\reproduction-stream.json --stream
.desktop-venv\Scripts\python.exe experiments\voice-audit\benchmark_flow.py
```

Les scripts de moteurs sont adaptés aux chemins de cette machine, n’utilisent pas le micro et ne jouent pas de son audible. `benchmark_flow.py` emploie le pilote à volume nul. Les sondes Codex nécessitent la connexion existante et peuvent consommer le quota de l’abonnement ; ne pas les relancer implicitement. `benchmark_llm.py` envoie deux prompts courts. Les résultats bruts avant/après sont dans `experiments/voice-audit/`.

Validation utilisateur recommandée après mise à jour : activer 🗣, prononcer une phrase de 15 s avec des pauses naturelles, une réponse courte puis une longue, reprendre la parole au casque, rester silencieux avec délai zéro, et vérifier qu’un changement de conversation coupe bien le micro. Relever les mesures vocales. Aucun engagement de fluidité identique à Codex avant cette validation.
