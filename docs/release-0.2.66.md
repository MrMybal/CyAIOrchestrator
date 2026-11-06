# 0.2.66 — Updated CyDoc reader

- Update the bundled CyDoc reader with header search, nested topic navigation, quick title/description tooltips and six themes.
- Publish 30 pages in each of English and French, including localized screenshots, static workflow diagrams and concise public integration APIs.
- Separate authoring inputs in `.CyDocBuild/` from the distributed `Documentation/Documentation.html`, `DocAI.md` and `DocData/` resources.
- Keep engineering archives, audits, migration records and full source implementations outside the human reader.
- Preserve contextual F1 help, native settings links and legacy page aliases; open the reader directly through `file://`.
- Include the complete generated manual in Windows and Python distributions. Use only the image media module for the manual's screenshots.

The Windows installer updates the application while retaining the existing configuration and previous installed version. Reading the bundled manual requires no documentation server or Internet connection.
