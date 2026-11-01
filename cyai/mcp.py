"""MCP stdio bridge. The running UI service owns the engine and database."""
import json
import sys
import urllib.parse
import urllib.request

from .connectors import request_json
from .security import SecretStore


def tool(name, description, properties, required=()):
    return {"name": name, "description": description, "inputSchema": {"type": "object", "properties": properties,
            "required": list(required), "additionalProperties": False}}


STRING = {"type": "string"}
TOOLS = [
    tool("list_projects", "Lister les projets autorisés et leurs conversations.", {}),
    tool("create_mission", "Créer une mission durable ; ne la lance pas. Retourne mission_id.",
         {"conversation_id": STRING, "title": STRING, "request_key": STRING,
          "steps": {"type": "array", "minItems": 1, "maxItems": 20, "items": {"type": "object", "properties": {
              "name": STRING, "connector": STRING, "model": STRING, "instruction": STRING,
              "depends_on": {"type": "array", "items": {"type": "integer"}}}, "required": ["connector", "instruction"], "additionalProperties": False}}}, ["conversation_id", "steps", "request_key"]),
    tool("launch_mission", "Lancer une mission créée. Idempotent ; suivi par mission_status.", {"mission_id": STRING}, ["mission_id"]),
    tool("mission_status", "Consulter les étapes, erreurs et nouveaux événements.", {"mission_id": STRING, "after": {"type": "integer", "minimum": 0}}, ["mission_id"]),
    tool("mission_result", "Récupérer les résultats enregistrés d’une mission.", {"mission_id": STRING}, ["mission_id"]),
    tool("continue_conversation", "Continuer une conversation autorisée ; retourne immédiatement mission_id.",
         {"conversation_id": STRING, "connector": STRING, "model": STRING, "instruction": STRING, "request_key": STRING}, ["conversation_id", "connector", "instruction", "request_key"]),
    tool("cancel_mission", "Propager l’annulation ; les fichiers déjà modifiés ne sont pas restaurés.", {"mission_id": STRING}, ["mission_id"]),
    tool("search_history", "Rechercher uniquement dans les projets autorisés au client MCP.",
         {"text": STRING, "project_id": STRING, "connector": STRING, "date_from": STRING, "date_to": STRING, "status": STRING}, ["text"]),
]


def call_tool(service, name, args, project_ids, allow_write=False, allow_global=False):
    if name in {'cyai_actions','cyai_call'}:
        from .app_mcp import call
        return call(service,name,args,project_ids,allow_write=allow_write,allow_global=allow_global)
    definition = next((t for t in TOOLS if t["name"] == name), None)
    if not definition:
        raise ValueError("Outil MCP inconnu.")
    if name in {"create_mission","launch_mission","continue_conversation","cancel_mission"} and not allow_write:
        raise ValueError("Client MCP en lecture seule. Configurez --allow-write pour autoriser les modifications.")
    schema = definition["inputSchema"]
    if not set(schema["required"]).issubset(args) or not set(args).issubset(schema["properties"]):
        raise ValueError("Arguments MCP invalides.")
    allowed = set(project_ids)
    if not allowed:
        raise ValueError("Aucun projet autorisé. Configurez --project PROJECT_ID pour ce client MCP.")
    if name == "list_projects":
        state = service.state()
        return {"projects": [p for p in state["projects"] if p["id"] in allowed],
                "conversations": [c for c in state["conversations"] if c["project_id"] in allowed]}
    if name == "search_history":
        if args.get("project_id") and args["project_id"] not in allowed:
            raise ValueError("Projet non autorisé pour ce client.")
        return [r for r in service.search(args) if r["project_id"] in allowed]
    conversation_id = args.get("conversation_id")
    if "mission_id" in args:
        conversation_id = service.store.one("SELECT conversation_id FROM missions WHERE id=?", (args["mission_id"],))["conversation_id"]
    project = service.project_for_conversation(conversation_id)
    if project["id"] not in allowed:
        raise ValueError("Projet non autorisé pour ce client MCP.")
    if name in {"create_mission", "launch_mission", "continue_conversation"}:
        with service.engine.lock:
            # A running agent cannot recursively fill a delegation queue through MCP.
            if service.store.rows("SELECT id FROM missions WHERE status IN ('running','awaiting_approval')"):
                raise ValueError("Délégation MCP bloquée pendant une exécution ; prévention des boucles.")
            return service.action(name, {**args, **({"launch": False} if name == "create_mission" else {})})
    if name == "mission_status":
        return service.mission(args["mission_id"], args.get("after", 0))
    if name == "mission_result":
        mission = service.mission(args["mission_id"])
        return {"mission_id": mission["id"], "status": mission["status"], "steps": [{k: s[k] for k in ("name", "status", "result", "error", "usage")} for s in mission["steps"]]}
    return service.action(name, args)


def serve_stdio(data_dir, url, projects, allow_write=False, allow_global=False):
    if urllib.parse.urlparse(url).hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("Le pont MCP doit joindre le service local.")
    token = SecretStore(data_dir).get("local_token")
    if not token:
        raise ValueError("Démarrez CyAI Orchestrator avant de connecter MCP.")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line)
            if "id" not in request:
                continue
            method = request.get("method")
            if method == "initialize":
                requested = request.get("params", {}).get("protocolVersion")
                result = {"protocolVersion": requested if requested in {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"} else "2025-06-18",
                          "capabilities": {"tools": {}, "resources": {}}, "serverInfo": {"name": "CyAIOrchestrator", "version": "0.1.0"}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                from .app_mcp import TOOLS as APP_TOOLS
                result = {'tools':APP_TOOLS+TOOLS}
            elif method in {'resources/list','resources/read'}:
                result=request_json(url.rstrip('/')+'/api/mcp',{'method':method,'params':request.get('params',{}),'project_ids':projects},{'Authorization':'Bearer '+token})
            elif method == "tools/call":
                try:
                    params = request.get("params", {})
                    value = request_json(url.rstrip("/") + "/api/mcp", {"name": params["name"], "arguments": params.get("arguments", {}), "project_ids": projects,"allow_write":allow_write,"allow_global":allow_global}, {"Authorization": "Bearer " + token})
                    result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "isError": False}
                except Exception as e:
                    detail = str(e)
                    if isinstance(e, urllib.error.HTTPError):
                        detail = json.loads(e.read()).get("error", detail)
                    result = {"content": [{"type": "text", "text": detail}], "isError": True}
            else:
                print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32601, "message": "Method not found"}}), flush=True)
                continue
            response = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except Exception:
            response = {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None, "error": {"code": -32700, "message": "Invalid JSON-RPC request"}}
        print(json.dumps(response, ensure_ascii=False), flush=True)
