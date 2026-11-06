# Documentation workspace

Author English originals in `manual/en`, translate them fully in `manual/fr`, and retain page IDs and explicit anchors. Use `parent` for topic relationships. Revision/sourceRevision records reviewed guide translations. The neutral `api/en.json` and `api/fr.json` imports contain reviewed public declarations only; recheck their prose together when a signature changes. Their signatures are checked against the shipped Python module; this is not a semantic source index.

From the application root:

```sh
python scripts/build_documentation.py --install
python scripts/build_documentation.py --check
python -m unittest discover -s tests -p test_help.py -v
```

The first command installs the pinned local archive and calls `cydoc check`, which compiles AND writes the export. Reading uses no Node.js or server. Ship the entire `Documentation/` tree. `.CyDocBuild/` is build material only. The stock CyDoc reader/module provider is retained; `host/adapter.mjs` handles CyAI routes and the whitelisted native settings bridge.

The former reference importer published audits, archives and untranslated engineering notes. It is retained here as a working record, but never scanned for public pages. Existing repository documents remain at their original paths for maintainers. Old public IDs are aliases to the relevant current guide or the home page. Historical section anchors cannot always be preserved when their page is excluded.

Only `image` is enabled: localized screenshots need zoom and annotations. Workflow diagrams compile to SVG. No distributed video, GIF, interactive graph or 3D demonstration justifies another module or Three.js. The application's own 3D viewer remains separate.

GitHub Pages staging preserves the reader and all DocData resources and adds an index redirect for existing README URLs. The repository publishes the staged reader through its Pages workflow after changes reach main. Verify the actual deployed reader before reporting a successful publication.
