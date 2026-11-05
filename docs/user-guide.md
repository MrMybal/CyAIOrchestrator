# CyDoc documentation

CyAI's help is a **local CyDoc reader** bundled in `cyai/help`. Open the permanent **? Documentation** rail button, Settings → Documentation, or **F1** for the current panel. It opens a dedicated window, keeping the application workspace and draft intact. Browser mode launches the same local reader process; installations without the optional desktop extra use the system browser with a `file://` URL.

English is the default; French is available in the reader header. The 27 guide chapters have matching page IDs, explicit section anchors and revision tracking. The full repository documentation, code examples, evaluation resources and historical notes are also preserved in the reader. Reference text that has not been translated is clearly marked with its original language; it is not counted as a completed translation. The **Migration inventory** lists source files, historical notices, literal repository paths and translation work.

## Authoring and generation

Sources are in `documentation/manual/en` and `documentation/manual/fr`. Use the frontmatter and Markdown contracts in the pinned CyDoc AI guides. Keep `id` and explicit `{#anchor}` values identical between languages. Increase English `revision` after a semantic change, then French `sourceRevision` after updating its translation. Do not duplicate IDs generated from source annotations.

```powershell
# Node.js 22+, npm, Python 3.11+; generation only.
python scripts/build_documentation.py --install
# Rebuild using installed, pinned dependencies.
python scripts/build_documentation.py
# Check packaged output and source freshness; no Node.js required.
python scripts/build_documentation.py --check
```

Equivalent npm commands are `npm ci --prefix documentation` and `npm run build --prefix documentation`. `npm run check --prefix documentation` also compiles and checks CyDoc links. The pinned MIT package is vendored under `documentation/vendor`; no access to the private upstream repository is needed to rebuild this application. `Build-Desktop.ps1` generates the export, PyInstaller refuses stale documentation, and the installer validates its staged resources. Python wheels include the generated reader, images and licenses. Node.js is not a reader dependency.

`prepare.py` preserves the root README, validation notes, `docs/*.md` and evaluation-kit Markdown/JSON. It converts local document links to stable `doc:` links, copies referenced images and keeps non-distributed repository references as visible literal paths. Historical documents remain historical, with notices about their original context. Their contents are not a guarantee of current application behaviour.

## Modules and local assets

Only **image** is enabled: the guides contain localized screenshots that benefit from zoom and enlargement inside the window. Workflow diagrams compile to accessible static SVG. There are no documentation video/GIF/3D/gallery/node-graph assets, so these modules are omitted. The application still has its own 3D viewer; that does not add Three.js to the help reader.

The CyDoc exporter produces `data.js`, the selected classic media script, CSS and local assets. The host bootstrap uses the public `mountViewer` API and retains the exporter's packed-resource provider contract. CyDoc's image reader resolves bundled `assets/` files directly through local file URLs; it does not need a fetch-based provider. All reader resources are distributed locally; CSP disables network connections. No HTTP server, CDN, remote font or runtime package download is needed. Outbound reference links remain optional links to external sites.

The host uses the midnight theme by default, mapped from CyAI's appearance preferences. Media have minimal controls and in-window enlargement. CyDoc supplies keyboard navigation, touch pan/pinch, search, bookmarks, notes and reading-position restoration during navigation in the current reader session. Reading positions are not promised to survive closing the reader.

## Help routes and compatibility

`cyai.documentation.documentation_url(page_id, locale, anchor, state, theme)` checks pages, anchors and media against the bundled manifest. A typical local route is:

```text
file:///…/cyai/help/index.html#/fr/start/help-part-1?theme=midnight
file:///…/cyai/help/index.html#/en/start?media=conversation&theme=midnight&zoom=1.5
```

The theme is in the fragment because Windows .NET treats an outer query on a file URL as part of its filename. Other media state uses CyDoc's route contract. Unknown locales fall back to English and unknown pages to `start`. Invalid explicit anchors/media are rejected. Aliases are configured in `cydoc.config.json`.

Existing application links `?help=CHAPTER_ID` still work, including `section`, `anchor`, `#help-part-N`, `media` and image state. F1 and the top-bar help button map the current panel to a guide. Settings links return to the corresponding application panel in desktop mode; a standalone reader instead opens the matching help page.

## Code documentation and translation reports

CyDoc's actual Python/JavaScript source support is lexical. `prepare.py` has an explicit seven-file allowlist: the help API, context builder, connector interface, store, MCP bridge, help adapter and evaluation reference. Only these distributable sources enter the reader; no user workspace, local configuration, credentials, environment or test output is indexed. They are copied into a generated staging directory before indexing.

The help API has bilingual `@doc`, `@locale`, `@title`, `@section` and `@symbol` annotations, with common `parameters` and `native` anchors. Source pages support stable line links. CyDoc 0.1.0 does not track `sourceRevision` on extracted annotations; the bilingual API text and preserved original-language references are intentionally reported as **untracked**. Inspect `cyai/help/translation-report.json` or its reader page. The authored guides must have no missing or outdated translations.

## Verification and platform scope

```powershell
python -m unittest discover -s tests -p test_help.py -v
node tests/help.cjs
node tests/i18n.cjs
node tests/ui-async-regressions.cjs
```

Check all pages, translated anchors, source/API links, local asset decoding, search, reader language changes, keyboard and touch media controls, in-window enlargement, reading positions and old application links. `tests/documentation-browser.mjs` can run the reader integration checks against an isolated Chromium DevTools endpoint, including HTTP/HTTPS request blocking. The application native integration is tested with Windows WebView2; Linux/macOS native embedding remains unverified. The standalone exported reader is platform-neutral HTML/JavaScript.
