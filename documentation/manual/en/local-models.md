---
id: local-models
title: Local models & memory
description: Install a runtime, choose a GGUF and configure its context.
section: Models & speech
order: 19
revision: 1
---


1. Open Settings → Local models. Choose the llama.cpp runtime appropriate to the CPU/GPU, or configure a separate Ollama connector.
2. Download a compatible GGUF from the catalogue/Hugging Face repository or import an existing model. Wait for installation to complete.
3. Configure CPU/GPU/hybrid execution, GPU layers, threads and context. Per-model overrides can replace global defaults.
4. Start the installed model, follow its loading state, then select CyAI local and the model in the composer. Stop/unload it to release memory when finished.

Context is a configured local token capacity, distinct from generated output length. The model’s architecture and runtime still constrain usable context. A larger context can need substantially more KV-cache memory. Check actual load/generation errors rather than assuming a file size equals required RAM or VRAM.

```callout
{"type": "info", "title": "Keep in mind", "body": "Resource estimates are guidance. Orange indicates limited available margin; it is not by itself a ban on trying to load. Red indicates that total VRAM is below the stated estimate, not proof of every runtime’s behaviour. Actual loading can still fail. The integrated engine serves one request at a time."}
```


[Open local models](doc:local-models?app-settings=local)

## Related chapters {#related}

- [Downloads & optional components](doc:downloads)
- [Context, memory & usage](doc:context)
- [Logs, resources & usage](doc:diagnostics)
