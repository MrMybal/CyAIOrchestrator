# Ollama sur J: avec une RTX 3090

Fermer CyAI et les conversations Ollama avant l'installation. Dans PowerShell,
sous le compte Windows qui utilise CyAI, depuis la racine du projet :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-ollama.ps1
```

Le script utilise ces dossiers sans supprimer les anciens modèles :

- Programme : `C:\Models\Ollama\app`
- Modèles Ollama : `C:\Models\Ollama\models`
- Installateur officiel : `C:\Models\Ollama\installers`

Les fichiers GGUF déjà présents dans `<dossier-modèles>` restent disponibles
pour le moteur local llama.cpp de CyAI ; ce moteur est distinct d'Ollama.

| Modèle | Téléchargement approximatif | Usage proposé |
|---|---:|---|
| `qwen3.5:4b` | 3,4 Go | Défaut, français, résumés et échanges pendant Unreal |
| `qwen3.5:9b` | 6,6 Go | Travail général plus exigeant si la VRAM le permet |
| `qwen2.5-coder:7b` | 4,7 Go | Explication et rédaction de code |
| `qwen3.5:27b` | 17 Go | Raisonnement et analyse, de préférence sans Unreal |

Ces tailles sont celles des poids, pas une garantie de consommation VRAM.
Le contexte et les buffers ajoutent de la mémoire. Le script limite le contexte
par défaut à 4096 tokens, à un modèle chargé et une requête parallèle ; il règle
le déchargement après 30 secondes d'inactivité, Flash Attention et le cache KV
Q8. Cela ne réserve pas une quantité fixe de VRAM à Unreal.

Après les quatre téléchargements, le script vérifie le catalogue et effectue
une génération sur le 4b. Il sauvegarde ensuite `config.json`, règle uniquement
le connecteur Ollama sur le 4b et demande de relancer CyAI. Le connecteur Ollama
actuel échange du texte ; il n'exécute pas d'outils de fichiers et n'envoie pas
d'images. Les modèles restent sélectionnables dans Connecteurs.

Un téléchargement interrompu peut être repris en relançant le même script.
L'installateur n'est exécuté que si l'exécutable cible est absent.

Vérifications sans installation :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-ollama.ps1 -ValidateOnly
```

Après installation :

```powershell
& 'C:\Models\Ollama\app\ollama.exe' list
& 'C:\Models\Ollama\app\ollama.exe' ps
& 'C:\Models\Ollama\app\ollama.exe' stop qwen3.5:27b
```

Le script télécharge Ollama et les modèles lorsque vous le lancez. Adaptez le dossier avec `-Root`.
