# 0.2.65 — Local CyDoc documentation

- Replace the HTTP-based help renderer with a bundled CyDoc file reader in a dedicated window. The project workspace and drafts remain available.
- Preserve the 27 English/French guide chapters, localized screenshots, static diagrams, technical references, evaluation resources and historical notes. Original-language references awaiting translation are labelled explicitly.
- Add contextual F1 help and stable page, section and media routes; keep existing `?help=` application links.
- Include the image module for zoom and enlargement within the reader window. No video, GIF, mesh, gallery or graph module is added.
- Generate a bounded lexical source index and bilingual annotated help API. Add translation and migration inventories.
- Normalize text-source checksums across Windows/Linux checkouts, including authoring ignore files.
- Integrate pinned documentation generation, resource copying and freshness validation with desktop, Python package, installer and repository checks.

Reading uses local `file://` resources and does not require Node.js or an Internet connection. Regeneration needs Node.js 22+ and Python 3.11+. See [the documentation maintenance guide](user-guide.md) for commands and translation/platform limitations.
