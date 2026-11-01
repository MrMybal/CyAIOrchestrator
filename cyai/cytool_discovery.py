"""Read installed CyTool metadata without starting its runtime."""
import json
import os
import shutil
from pathlib import Path


def discover(folder):
    root = Path(folder).expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("Choisissez un dossier CyTool existant.")
    root = root.resolve()
    candidates = [p for p in (root / "CyTool.json", root / "app" / "CyTool.json") if p.is_file()]
    if len(candidates) != 1:
        raise ValueError("Plusieurs manifestes trouvés : choisissez le dossier app." if candidates else "CyTool.json introuvable dans ce dossier ou son sous-dossier app.")
    path = candidates[0]
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    if manifest.get("schemaVersion") != 1 or manifest.get("protocolVersion") != "1.0" or "MCP" not in manifest.get("interfaces", []):
        raise ValueError("Ce manifeste ne déclare pas le protocole CyTools 1.0 avec MCP.")
    base = path.parent.parent if path.parent.name == "app" else root
    config = path.parent / "mcp.json"
    command, args, warnings, env = "", [], [], {}
    servers = None
    if config.is_file():
        try:
            servers = json.loads(config.read_text(encoding="utf-8-sig")).get("mcpServers", {})
        except ValueError:
            warnings.append("mcp.json invalide : commande déduite de la structure du dossier, à vérifier.")
    if servers is not None:
        matching = [v for k, v in servers.items() if k in (manifest.get("name"), manifest.get("id"))]
        if not matching and len(servers) == 1: matching = list(servers.values())
        if len(matching) != 1:
            warnings.append("Plusieurs serveurs MCP : précisez la commande dans les options avancées.")
        else:
            server = matching[0]
            command, args = server.get("command", ""), server.get("args", [])
            env = server.get("env", {})
            if not isinstance(env, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in env.items()):
                raise ValueError("Variables d’environnement MCP invalides.")
            if server.get("cwd"):
                cwd = Path(server["cwd"])
                base = cwd if cwd.is_absolute() else base / cwd
    elif (path.parent / "tool.py").is_file():
        relative = ["runtime/python/Scripts/python.exe", ".venv/Scripts/python.exe"] if os.name == "nt" else ["runtime/python/bin/python", ".venv/bin/python"]
        command = next((str(base / r) for r in relative if (base / r).is_file()), "")
        args = [str(path.parent / "tool.py"), "mcp"]
    if not isinstance(command, str) or not isinstance(args, list) or any(not isinstance(a, str) for a in args):
        raise ValueError("Commande MCP invalide dans mcp.json.")
    if command and not Path(command).is_absolute() and (base / command).is_file():
        command = str((base / command).resolve())
    if not isinstance(command, str) or not isinstance(args, list) or any(not isinstance(a, str) for a in args):
        raise ValueError("Commande MCP invalide dans mcp.json.")
    if not command or not (Path(command).is_file() or shutil.which(command)):
        warnings.append("Exécutable introuvable : installez le runtime du CyTool ou précisez son chemin dans les options avancées.")
    if not args or args[-1] != "mcp":
        warnings.append("Arguments MCP à compléter dans les options avancées (dernier argument : mcp).")
    return {"manifest": manifest, "manifest_path": str(path), "cwd": str(base), "command": command, "args": args, "warnings": warnings, "env": env}
