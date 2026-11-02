# Plugins, CyTools and MCP

Configure integrations in **Settings → Plugins** and enable them for each project. **Settings → CyTools** contains standalone tools rather than project tabs. Only enabled plugins declaring a project view appear in the project navigation.

## Current integrations

- [CyAnnota](https://github.com/MrMybal/CyAnnota): embedded image, video and 3D annotation editor, version 0.4.4. Its `cyannota.integration` version 2 protocol delivers an archive to the originating conversation. The bundled source archive identifies the upstream commit and web build recipe. FFmpeg WASM remains an optional download.
- [CyMD](https://github.com/MrMybal/CyMD): official embedded plugin 0.1.4, using `cymd.integration` version 1. Save creates a new conversation attachment and keeps the original. Both editors follow the CyAI interface language and include their licences and source archives.
- [CyAICodex](https://github.com/MrMybal/CyAICodex): `get_context`, `search_skills`, `get_skill`, `search_images`, `get_image` and `view_image`, plus compatibility method names. Create a scoped connection in CyAICodex and paste its token or generated MCP configuration. Streamable HTTP defaults to `http://127.0.0.1:8765/mcp`; stdio configurations are supported. Opening its Web application uses its own session flow rather than reading its database.
- [CyTask](https://github.com/MrMybal/CyTask): the official dependency-free MCP bridge for Node.js 22 or later and JavaScript SDK are bundled with their source and licence. Set the CyTask server URL and an agent/API token. Read tools browse projects, tasks, agents and notifications; task creation, updates and agent calls follow the conversation approval policy when assigned to an agent. Server-side token permissions still apply. This connects to an existing CyTask server; downloading its desktop application does not configure a server or create an account.

## Official CyTools

| Tool | Repository | Purpose |
| --- | --- | --- |
| AudioStudio | [CyTools_AudioStudio](https://github.com/MrMybal/CyTools_AudioStudio) | Audio editing, effects, music, voices and transcription |
| AudioLibrary | [CyTools_AudioLibrary](https://github.com/MrMybal/CyTools_AudioLibrary) | Local sound libraries, analysis and semantic search |
| AIChat | [CyTools_AIChat](https://github.com/MrMybal/CyTools_AIChat) | Local/cloud chat engines and speech |
| PersonaRP | [CyTools_PersonaRP](https://github.com/MrMybal/CyTools_PersonaRP) | Persistent roleplay characters and voices |
| Storyboard | [CyTools_Storyboard](https://github.com/MrMybal/CyTools_Storyboard) | Storyboards, previs and image generation |
| MeshStudio | [CyTools_MeshStudio](https://github.com/MrMybal/CyTools_MeshStudio) | Mesh reconstruction, remeshing, UVs, textures and workflows |

Settings reads are offline. **Check GitHub releases** queries stable releases; **Download and connect** verifies the published SHA-256 and installs a Windows portable package in the user's CyAI data directory. It does not launch the GUI, run an operation, install engines or download model weights. Updates keep previous tool directories, project bindings and enabled/disabled state. Configure any required permissions or credentials in the tool itself.

**Add installed folder** detects `app/CyTool.json` or `CyTool.json`, explicit `mcp.json` configurations, and portable or virtual-environment Python runtimes. Detection never executes the manifest's `executable` text. Inferred MCP commands use a separate `data/jobs-cyai` store. An explicit MCP configuration can instead connect to the tool's shared service.

Operations use `op_<operationId>` and return jobs. Keep the MCP session alive and poll `cy_get_job` until `Completed`, `Failed` or `Cancelled`; a successful poll is not proof that the job succeeded. Assign a tool pack to an agent before expecting its operation tools to be available. Read tools can run directly; other operations use the conversation's approval policy.

## Previous registrations

Older split tools and CyProjectCodex are no longer added as defaults. Existing configurations are preserved under **Previous registrations · compatibility**, with replacements indicated where known. Custom MCP integrations are kept. Connect the replacement and update agent tool assignments before retiring an older registration; operation identifiers are not silently renamed.

## Custom MCP integrations

Use **Settings → MCP** to register a local server or **Plugins → Install manifest** for a declarative CyAI manifest. The configuration declares transport, command/arguments or a local HTTP endpoint, allowed read tools and optional project tabs. Importing MCP configuration does not itself run a process. Imported CyTask/CyTools token variables are stored in the Windows vault and injected only when their process starts. No third-party JavaScript is injected into the CyAI interface.
