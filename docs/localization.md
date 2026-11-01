# Interface localization

CyAI starts in English independently of the operating-system language. French is available from Settings → Appearance → Interface language. The setting is stored as `settings.language` in the application configuration. Missing or unsupported saved values fall back to English; unsupported new values are rejected.

The local service injects the selected language and shared catalogue before `i18n.js` executes. Static HTML, JavaScript labels and Windows tray text use the same catalogue. Date and number formatting uses the selected locale. Language changes save the draft before reloading the interface; the service and background missions keep running.

## Adding interface text

French source strings are stable catalogue keys; `cyai/locales/en.json` provides their English translations. Both `ui('Enregistrer')` and tagged templates are supported. For example:

```javascript
ui`<p>${count} tâche(s)</p>`
```

The catalogue entry is `"{0} tâche(s)": "{0} task(s)"`. Within each text segment, template slots are numbered by occurrence and may be reordered in translations. Preserve all slots and their multiplicity.

Only static application markup is translated. Dynamic template values are inserted afterward, without recursive processing. Keep message bodies, project names, paths, editable documents and user-entered labels opaque. Continue escaping values with `esc` when inserting into HTML; localization does not provide HTML escaping. Do not translate DOM selectors, protocol identifiers, option values, parsing markers or file formats.

Server errors with an exact known translation are localized at the HTTP boundary. Raw diagnostic records retain their original contents. Native Windows system-dialog buttons follow the operating system. The bundled CyMD and CyAnnota editors already support both languages. CyAI sets their documented same-origin preference keys before they open. External web plugins may implement their own localization and are not rewritten by CyAI.

Run `node tests/i18n.cjs` and the Python localization tests after editing the catalogue. No translation service or network connection is needed at runtime.
