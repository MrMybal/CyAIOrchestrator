# Bundled user guide

Open the permanent **? Documentation** rail button or the Documentation entry in Settings. `?help=CHAPTER_ID` also opens a specific chapter. Leaving the guide preserves the workspace; the rail stays available.

The 27 chapters cover setup, projects, connectors, conversations, context, permissions, orchestration, teams, task review, methods, isolated evaluations, whiteboards, files, 3D, CyAnnota, CyMD, plugins, CyTools, MCP, local models, speech, downloads, preferences, diagnostics, backup and troubleshooting.

## Maintaining content

- `cyai/web/help/en.json` and `fr.json` contain complete English/French content with matching chapter IDs, groups and block types. English is the application default. Runtime translation services are not used.
- Text, steps, tables, notes, settings links and related chapters use structured blocks. The renderer escapes text and builds its own HTML. Do not put executable markup in content.
- `image` blocks reference bundled PNGs under `cyai/web/help/images`, with a localized filename, alt text and caption. Use a disposable demonstration workspace; inspect images and metadata before publishing.
- `diagram` blocks render accessible inline SVG. A pipeline has five labels; a parallel workflow has six. Supply translated titles and explanatory captions.
- The guide search includes all chapter content and ignores accents/case. Images have an enlarged preview with zoom. Print styling selects the current article.
- `help.js`, `help.css` and the JSON/images are included in Python packages and collected by the Windows build. Static routes accept the two supported catalogues and local PNG images only.

## Verification

```powershell
python -m unittest discover -s tests -p test_help.py -v
node tests/help.cjs
node tests/i18n.cjs
node tests/ui-async-regressions.cjs
```

For a UI change, open all chapters in both languages in an isolated workspace. Check search, stale navigation, retry, settings links, image zoom, dark/light themes and constrained windows. Confirm the guide uses bundled assets while remote application resources are unavailable.
