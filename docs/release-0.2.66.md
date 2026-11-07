# 0.2.66 — Updated CyDoc reader

- Update the bundled CyDoc reader with header search, nested topic navigation, quick title/description tooltips and six themes.
- Publish 30 pages in each of English and French, including localized screenshots, static workflow diagrams and concise public integration APIs.
- Separate authoring inputs in `.CyDocBuild/` from the distributed `Documentation/Documentation.html`, `DocAI.md` and `DocData/` resources.
- Keep engineering archives, audits, migration records and full source implementations outside the human reader.
- Preserve contextual F1 help, native settings links and legacy page aliases; open the reader directly through `file://`.
- Include the complete generated manual in Windows and Python distributions. Use only the image media module for the manual's screenshots.

The Windows installer updates the application while retaining the existing configuration and previous installed version. Reading the bundled manual requires no documentation server or Internet connection.

## Status

**CyAI Orchestrator 0.2.66 · Alpha.** This release is intended for testing and feedback. Features may be incomplete and workflows may change before a stable release.

## Documented limitations

- The published installer targets Windows x64 and is not digitally signed. Microsoft Edge WebView2 Runtime must be available. No Linux or macOS installer is published for this release.
- Provider capabilities, native tool permissions, context limits and subscription usage depend on the selected connector. A limit or quota is displayed only when the connector supplies it; an unavailable value is not a measured zero.
- Independent missions may run concurrently, but the integrated local inference engine processes one model request at a time. Model and voice requirements depend on the downloaded engine and weights.
- Large model weights, optional native engines, the Claude Code CLI and CyAnnota's optional FFmpeg component are separate downloads. Native providers require their own authentication; app subscriptions do not automatically include API credit.
- Portable application backups do not include credentials, project working files or provider-native sessions. Back up those files separately. Stopping an agent does not undo changes it has already made to project files.

These are product limitations, not a list of confirmed bug tickets. The release does not publish a bug-by-bug inventory; consult the [issue tracker](https://github.com/MrMybal/CyAIOrchestrator/issues) for reports and feedback.

## Links

- [Published release and Windows installer](https://github.com/MrMybal/CyAIOrchestrator/releases/tag/v0.2.66)
- [English manual](https://mrmybal.github.io/CyAIOrchestrator/Documentation.html#/en/start)
- [Notes en français](release-0.2.66.fr.md)
- [README](../README.md)
