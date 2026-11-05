---
id: voice
title: Dictation, speech & voices
description: Configure speech engines and choose when the microphone is active.
section: Models & speech
order: 20
revision: 1
---


1. Open Settings → Voice. Choose a transcription engine, language and optional microphone/device settings. Install only the runtime and model you need.
2. For speech output, choose Windows voices or a local synthesis engine such as Piper. Install a voice, choose its speaker where supported and test it.
3. Use the microphone button for dictation: review the recognized text before sending.
4. Direct discussion sends recognized phrases, reads replies and reopens the microphone for the next phrase. Click again to stop this mode. Reading responses aloud can be toggled independently.

| Option | Use |
| --- | --- |
| Whisper / Phonon | Optional speech-to-text engines. Phonon-2 is English; Phonon-2.5 supports French and other languages. Runtime and weights are separate downloads. |
| Piper | Lightweight local synthesis. The catalogue lists languages, quality levels and speaker variants; multi-speaker models share model files. |
| Other voice engines | Hardware, languages, voice cloning and resource needs depend on the chosen engine. Check its card and actual loading state. |

```callout
{"type": "info", "title": "Keep in mind", "body": "The microphone and automatic reading start disabled. Browser/Windows device permission is still required. Test with a short phrase before relying on hands-free mode. Transcription can be imperfect; recording permission does not guarantee a model is installed."}
```


[Open voice settings](doc:voice?app-settings=voice)

## Related chapters {#related}

- [Downloads & optional components](doc:downloads)
- [Local models & memory](doc:local-models)
- [Troubleshooting](doc:troubleshooting)
