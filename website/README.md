# CyAI Orchestrator showcase

Maintained static showcase sources. The generated site is separate from the desktop application and the existing documentation publication. English is the default; use `?lang=fr` for French. No framework, npm dependency, Git metadata or remote API is required to build this site.

## Build and preview

From the application checkout, with Node.js 22 or later:

```powershell
node website/build.mjs
node website/preview.mjs
```

The preview rebuilds first, binds only to `127.0.0.1`, prints its local address and serves only files listed in the generated artifact. Its default `/cyai/` subpath exercises project hosting. Stop it with Ctrl+C. To choose an address:

```powershell
node website/preview.mjs --port=8080 --base=/cyai/
```

The generated entry is `dist/website/index.html`. Copy the entire `dist/website/` folder to use it elsewhere. Open its `index.html` directly in a browser permitting local files; showcase interactions use a classic script, embedded translations and relative assets. The copied manual is `manual/Documentation.html`, with its complete `DocData/` and separate `DocAI.md`. Reading it needs no server or Internet connection. Optional GitHub and download links require a connection when followed.

The builder checks the existing application manual and refuses stale inputs, missing translations and unexpected output files. If the application's documentation changed, regenerate it with the project's existing toolchain before rebuilding the showcase:

```powershell
python scripts/build_documentation.py --install
python scripts/build_documentation.py --check
node website/build.mjs
```

## Maintained files

| File | Purpose |
| --- | --- |
| `site.json` | Explicit product stage, verified optional repository/release/download destinations and the application license |
| `source/en.json`, `source/fr.json` | Complete matching translation keys, including metadata, accessible names and captions |
| `source/screens.json` | Source-side screenshot catalog, dimensions and relevant manual pages |
| `source/template.mjs` | Prerendered English structure and semantic controls |
| `source/styles.css` | Graphite/violet styling and responsive layouts |
| `source/site.js` | Classic-script language, menu, tab and modal image-viewer interactions |
| `assets/screenshots/` | Selected real captures from an isolated demo instance and the actual manual |
| `build.mjs` | Dependency-free, bounded artifact generation and content revisions |
| `preview.mjs` | Read-only loopback preview under a configurable static subpath |

The version comes from `pyproject.toml`; release/download URLs interpolate that version. Verify a release's existence before changing these destinations. Optional external destinations may be omitted from `site.json`; building and viewing never performs a release lookup. Review stage-specific copy in both languages when the product stage changes.

Do not edit generated HTML, bundles or copied manual files. Do not commit `dist/website/`. CSS, script and screenshot URLs include content hashes. Each generation replaces only a previously owned, unmodified artifact; unknown or modified files are preserved and cause an error. HTML and the manual should be revalidated by a static host; hashed assets can use long-lived caching. The preview demonstrates these distinct cache policies.

## Capture catalog

All six views have English and French images, alt text and captions in `source/screens.json` and the translation catalogs:

- **Conversation:** existing application documentation captures of the Nebula Studio demo project, its conversation, composer and team.
- **Task board:** existing documentation captures of seven fictional assignments and review states.
- **CyTools:** existing documentation captures of the six official catalogue entries; no installed engines or model execution is implied.
- **Agent library:** captured from the real CyAI browser interface using an isolated test service, fictional profiles and connector fixtures.
- **Connectors:** captured from that same isolated service. Visible provider states are fixture data, not live account checks.
- **Manual:** captured from the actual published 0.2.66 CyDoc reader, with its language selector used for the French view. The build copies the corresponding verified application export.

Keep temporary originals, capture servers and QA evidence in ignored working folders. Do not capture a personal workspace or credentials. The selected source images retain full frames and proportions. The logo comes from `cyai/web/cyai-logo.png`; do not regenerate product UI or branding.

## Verification

```powershell
python -m unittest discover -s tests -p test_showcase.py -v
node website/build.mjs
```

The consumer tests build without Git metadata, verify the complete manual and classic-script resources, exercise asset cache renewal and reject incomplete translations, escaping sources and unknown output files. Browser checks must additionally cover both languages, the specified desktop/mobile sizes, keyboard tabs/menu/FAQ, image enlargement, zoom, modal focus and scroll restoration, direct local-file opening and manual search. Record evidence outside the public site and manual.

The showcase and its new sources use the application's AGPL-3.0-only license. The output includes `LICENSE`; copied CyDoc and component notices remain under `manual/DocData/`. No Three.js, external font or runtime CDN is added by this showcase.

## Publication

Building and previewing do not push, create releases, modify repository settings or deploy. The existing GitHub Pages workflow continues publishing the documentation artifact. Publishing this showcase requires a separate authorized integration of its generated artifact; preserve existing reader URLs and deep links when doing so.
