---
id: install
title: Installation & lifecycle
description: Install, start, update and close the application.
section: Getting started
order: 1
revision: 1
---


1. Download the Windows installer from the project’s GitHub Releases and run it. For portable versions, keep the entire directory including _internal.
2. Ensure Microsoft Edge WebView2 is available. Open CyAI from its shortcut. English is the default unless a language was already saved.
3. Configure a connector or install a local engine and model. Large model weights and optional runtimes are downloaded separately.

Closing the desktop window hides it in the Windows notification area. Double-click its tray icon to reopen it. Quit stops the service started by that instance, with confirmation when work is active. A separately started service remains independent. Closing a browser tab does not stop the service or its missions.

Application data is separate from program files. Stop work and create a backup before updating; back up project folders separately. Install the new version and check the sidebar version. The Windows executable is currently unsigned.

```callout
{"type": "info", "title": "Keep in mind", "body": "Source mode requires Python 3.11+. Start with python -m cyai, or python -m cyai.desktop for the desktop window. The default service address is http://127.0.0.1:8766. A changed port also changes client URLs."}
```


## Related chapters {#related}

- [Downloads & optional components](doc:downloads)
- [History, exports & backups](doc:backups)
- [Settings, language & folders](doc:settings)
