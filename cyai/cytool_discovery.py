"""Read installed CyTools metadata without running code or loading models."""
import json
import os
import shutil
from pathlib import Path


def discover(folder):
    root=Path(folder).expanduser()
    if not root.is_absolute() or not root.is_dir():raise ValueError("Choisissez un dossier CyTool existant.")
    root=root.resolve()
    candidates=[p for p in (root/"CyTool.json",root/"app/CyTool.json") if p.is_file()]
    if len(candidates)!=1:raise ValueError("Plusieurs manifestes trouvés : choisissez le dossier app." if candidates else "CyTool.json introuvable dans ce dossier ou son sous-dossier app.")
    path=candidates[0]
    manifest=json.loads(path.read_text(encoding="utf-8-sig"))
    if manifest.get("schemaVersion")!=1 or manifest.get("protocolVersion")!="1.0" or "MCP" not in manifest.get("interfaces",[]):
        raise ValueError("Ce manifeste ne déclare pas le protocole CyTools 1.0 avec MCP.")
    base=path.parent.parent if path.parent.name=="app" else root
    command,args,warnings,env="",[],[],{}
    configs=list(dict.fromkeys([path.parent/"mcp.json",base/"mcp.json"]))
    config=next((p for p in configs if p.is_file()),None)
    servers=None
    if config:
        try:
            servers=json.loads(config.read_text(encoding="utf-8-sig")).get("mcpServers",{})
            if not isinstance(servers,dict):raise ValueError()
        except ValueError:warnings.append("mcp.json invalide : commande déduite de la structure du dossier, à vérifier.")
    if servers is not None:
        matching=[v for k,v in servers.items() if k in (manifest.get("name"),manifest.get("id"))]
        if not matching and len(servers)==1:matching=list(servers.values())
        if len(matching)!=1:warnings.append("Plusieurs serveurs MCP : précisez la commande dans les options avancées.")
        else:
            server=matching[0]
            if not isinstance(server,dict):raise ValueError("Configuration MCP invalide.")
            command,args=server.get("command",""),server.get("args",[])
            env=server.get("env",{})
            if not isinstance(env,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in env.items()):raise ValueError("Variables d’environnement MCP invalides.")
            if server.get("cwd"):
                cwd=Path(server["cwd"]);base=cwd if cwd.is_absolute() else base/cwd
    elif (path.parent/"tool.py").is_file():
        runtime_paths=["runtime/python/Scripts/python.exe","runtime/python/python.exe",".venv/Scripts/python.exe","runtime/python/bin/python",".venv/bin/python"]
        if os.name!="nt":runtime_paths=runtime_paths[3:]+runtime_paths[:3]
        command=next((str(base/p) for p in runtime_paths if (base/p).is_file()),"")
        # CyAI jobs have their own runtime store; detection itself creates nothing.
        args=[str(path.parent/"tool.py"),"--data-dir",str(base/"data/jobs-cyai"),"mcp"]
    if not isinstance(command,str) or not isinstance(args,list) or any(not isinstance(a,str) for a in args):raise ValueError("Commande MCP invalide dans mcp.json.")
    command=command.replace("<tool>",str(base))
    args=[arg.replace("<tool>",str(base)) for arg in args]
    if command and not Path(command).is_absolute() and (base/command).is_file():command=str((base/command).resolve())
    if not command or not (Path(command).is_file() or shutil.which(command)):
        warnings.append("Exécutable introuvable : installez le runtime du CyTool ou précisez son chemin dans les options avancées.")
    if not args or args[-1]!="mcp":warnings.append("Arguments MCP à compléter dans les options avancées (dernier argument : mcp).")
    from .extension_catalog import CATALOG
    known=next((entry for entry in CATALOG if entry.get('tool_id')==manifest.get('id')),None)
    return {"manifest":manifest,"manifest_path":str(path),"cwd":str(base),"command":command,"args":args,"warnings":warnings,"env":env,"source_repo":known['repo'] if known else ''}
