"""Channels you create in a project, beside the ones CyAI derives from its data.

The first kind is a whiteboard: notes you place and link, like a Miro board kept small on purpose — text, a
colour, a position, and arrows between notes. An AI can read it and draw on it through the MCP, under the
same authorisation as any write. Each save carries the version it started from: a board changed elsewhere
in the meantime is never overwritten silently.

The second kind is a graph, computed from the project each time it is read — the tasks and their
dependencies, or the hierarchy of the team. Only its source is stored, so it can never be out of date.

The third is a plugin console: the read tools a plugin declares, called by hand, with the history of the
calls kept in the channel. Only declared read tools can be called, under the plugin's rules for the project.
"""
import json

from .store import now, uid

UNHANDLED = object()

TYPES = {"whiteboard": "Tableau blanc", "graph": "Graphe", "plugin": "Console de plugin"}
GRAPH_SOURCES = {"tasks": "Tâches et dépendances", "team": "Hiérarchie de l’équipe"}
COLORS = {"yellow", "blue", "green", "pink", "violet", "grey"}
MAX_SPACES = 40
MAX_NOTES = 300
MAX_LINKS = 600
MAX_CALLS = 50
MAX_RESULT = 20000


def _text(value, limit, label, required=False):
    text = str(value if value is not None else "").strip()
    if required and not text:
        raise ValueError(label + " requis.")
    if len(text) > limit:
        raise ValueError(label + " limité à " + str(limit) + " caractères.")
    return text


def _project(service, project_id):
    project = service.store.one("SELECT * FROM projects WHERE id=?", (project_id,))
    service.engine.policy.project(project["root"])
    return project


def _space(service, data):
    project = _project(service, data["project_id"])
    rows = service.store.rows("SELECT * FROM project_spaces WHERE id=? AND project_id=?", (data["id"], project["id"]))
    if not rows:
        raise ValueError("Salon introuvable dans ce projet.")
    space = dict(rows[0])
    space["data"] = json.loads(space["data"])
    return space


def _number(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(label + " invalide.")
    return max(-100000.0, min(100000.0, number))


def _board(value):
    if not isinstance(value, dict):
        raise ValueError("Un tableau blanc est un objet {notes, links}.")
    notes, links, ids = [], [], set()
    raw_notes = value.get("notes", [])
    if not isinstance(raw_notes, list) or len(raw_notes) > MAX_NOTES:
        raise ValueError("Au plus " + str(MAX_NOTES) + " notes par tableau.")
    for raw in raw_notes:
        if not isinstance(raw, dict):
            raise ValueError("Chaque note est un objet {id, x, y, text}.")
        id = _text(raw.get("id") or uid(), 40, "Identifiant de note")
        if id in ids:
            raise ValueError("Note en double : « " + id + " ».")
        ids.add(id)
        color = str(raw.get("color") or "yellow")
        if color not in COLORS:
            raise ValueError("Couleur de note inconnue : " + ", ".join(sorted(COLORS)) + ".")
        notes.append({"id": id, "x": _number(raw.get("x", 0), "Position"), "y": _number(raw.get("y", 0), "Position"),
                      "text": _text(raw.get("text", ""), 4000, "Texte de note"), "color": color})
    raw_links = value.get("links", [])
    if not isinstance(raw_links, list) or len(raw_links) > MAX_LINKS:
        raise ValueError("Au plus " + str(MAX_LINKS) + " liens par tableau.")
    seen = set()
    for raw in raw_links:
        if not isinstance(raw, dict):
            raise ValueError("Chaque lien est un objet {from, to}.")
        source, target = str(raw.get("from", "")), str(raw.get("to", ""))
        if source not in ids or target not in ids or source == target:
            raise ValueError("Un lien relie deux notes distinctes du tableau.")
        if (source, target) in seen:
            continue
        seen.add((source, target))
        links.append({"from": source, "to": target, "label": _text(raw.get("label", ""), 120, "Libellé de lien")})
    return {"notes": notes, "links": links}


def list_spaces(service, project_id):
    return [{"id": r["id"], "type": r["type"], "name": r["name"], "updated_at": r["updated_at"],
             "notes": len(json.loads(r["data"]).get("notes", []))}
            for r in service.store.rows("SELECT * FROM project_spaces WHERE project_id=? ORDER BY position,created_at", (project_id,))]


def create_space(service, data):
    project = _project(service, data["project_id"])
    kind = str(data.get("type") or "whiteboard")
    if kind not in TYPES:
        raise ValueError("Type de salon inconnu. Types disponibles : " + ", ".join(TYPES) + ".")
    if len(service.store.rows("SELECT id FROM project_spaces WHERE project_id=?", (project["id"],))) >= MAX_SPACES:
        raise ValueError("Au plus " + str(MAX_SPACES) + " salons créés par projet.")
    name = _text(data.get("name"), 80, "Nom du salon") or TYPES[kind].lower()
    content = {"notes": [], "links": []}
    if kind == "graph":
        source = str(data.get("source") or "tasks")
        if source not in GRAPH_SOURCES:
            raise ValueError("Source de graphe inconnue : " + ", ".join(GRAPH_SOURCES) + ".")
        content = {"source": source}
    if kind == "plugin":
        plugin = service.plugins.plugin(_text(data.get("plugin"), 80, "Plugin", required=True), project["id"])
        if not plugin.get("read_tools"):
            raise ValueError("Ce plugin ne déclare aucun outil de lecture : une console n’aurait rien à appeler.")
        content = {"plugin_id": plugin["id"], "calls": []}
        name = name if data.get("name") else plugin.get("name", plugin["id"])
    id, timestamp = uid(), now()
    position = len(service.store.rows("SELECT id FROM project_spaces WHERE project_id=?", (project["id"],)))
    service.store.execute("INSERT INTO project_spaces(id,project_id,type,name,position,data,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                          (id, project["id"], kind, name, position, json.dumps(content), timestamp, timestamp))
    return {"id": id, "type": kind, "name": name, "notice": TYPES[kind] + " « " + name + " » créé."}


def get_space(service, data):
    space = _space(service, data)
    return {"space": space}


def rename_space(service, data):
    space = _space(service, data)
    name = _text(data.get("name"), 80, "Nom du salon", required=True)
    service.store.execute("UPDATE project_spaces SET name=?,updated_at=? WHERE id=?", (name, now(), space["id"]))
    return {"id": space["id"], "name": name, "notice": "Salon renommé."}


def delete_space(service, data):
    space = _space(service, data)
    service.store.execute("DELETE FROM project_spaces WHERE id=?", (space["id"],))
    return {"id": space["id"], "notice": "Salon « " + space["name"] + " » supprimé avec son contenu."}


def save_whiteboard(service, data):
    space = _space(service, data)
    if space["type"] != "whiteboard":
        raise ValueError("Ce salon n’est pas un tableau blanc.")
    board = _board(data.get("data"))
    base = data.get("base")
    # A save starts from a version: if someone — you in another window, or an AI — saved since, refuse.
    if base and base != space["updated_at"]:
        raise ValueError("Ce tableau a été modifié ailleurs depuis votre ouverture. Rechargez-le pour ne rien écraser.")
    timestamp = now()
    service.store.execute("UPDATE project_spaces SET data=?,updated_at=? WHERE id=?",
                          (json.dumps(board, ensure_ascii=False), timestamp, space["id"]))
    return {"id": space["id"], "updated_at": timestamp, "notes": len(board["notes"]), "links": len(board["links"])}


def graph_data(service, data):
    """A graph computed from the project now: nothing is stored but its source, so it is never stale."""
    space = _space(service, data)
    if space["type"] != "graph":
        raise ValueError("Ce salon n’est pas un graphe.")
    source, project_id = space["data"].get("source", "tasks"), space["project_id"]
    nodes, edges = [], []
    teams = service.store.rows("SELECT id FROM teams WHERE project_id=?", (project_id,))
    if source == "tasks" and teams:
        from .tasks import STATUSES
        from .teams import load_member
        names = {m["id"]: load_member(m)["definition"]["name"] for m in
                 service.store.rows("SELECT * FROM team_members WHERE team_id=?", (teams[0]["id"],))}
        for row in service.store.rows("SELECT * FROM tasks WHERE team_id=? ORDER BY created_at", (teams[0]["id"],)):
            nodes.append({"id": row["id"], "label": row["objective"][:120], "kind": "task", "status": row["status"],
                          "status_label": STATUSES.get(row["status"], row["status"]), "detail": names.get(row["assignee_id"], "sans responsable")})
            for dependency in json.loads(row["dependencies"]):
                edges.append({"from": dependency, "to": row["id"], "kind": "dependency"})
            if row["parent_id"]:
                edges.append({"from": row["parent_id"], "to": row["id"], "kind": "parent"})
    elif source == "team" and teams:
        from .teams import load_member, ROLE_LABELS
        for row in service.store.rows("SELECT * FROM team_members WHERE team_id=? AND active=1 ORDER BY position,created_at", (teams[0]["id"],)):
            member = load_member(row)
            nodes.append({"id": member["id"], "label": member["definition"]["name"], "kind": "member", "status": member["role"],
                          "status_label": ROLE_LABELS[member["role"]], "detail": member["definition"]["connector"]})
            if member["manager_id"]:
                edges.append({"from": member["manager_id"], "to": member["id"], "kind": "manager"})
    known = {n["id"] for n in nodes}
    edges = [e for e in edges if e["from"] in known and e["to"] in known]
    return {"id": space["id"], "name": space["name"], "source": source, "source_label": GRAPH_SOURCES[source],
            "nodes": nodes, "edges": edges, "team": bool(teams)}


def _plugin_space(service, data):
    space = _space(service, data)
    if space["type"] != "plugin":
        raise ValueError("Ce salon n’est pas une console de plugin.")
    return space


def plugin_console(service, data):
    """The read tools the plugin offers now, and the calls already made from this channel."""
    space = _plugin_space(service, data)
    plugin_id = space["data"]["plugin_id"]
    try:
        plugin = service.plugins.plugin(plugin_id, space["project_id"])
        tools, problem = service.plugins.catalog(plugin_id)["tools"], ""
    except Exception as exc:  # a stopped server or a plugin disabled since: say it, keep the history readable
        plugin, tools, problem = {"name": plugin_id}, [], str(exc)
    return {"id": space["id"], "name": space["name"], "plugin_id": plugin_id, "plugin": plugin.get("name", plugin_id),
            "tools": [{"name": t["name"], "description": t.get("description", ""), "inputSchema": t.get("inputSchema", {})} for t in tools],
            "problem": problem, "calls": space["data"].get("calls", [])}


def plugin_console_call(service, data):
    space = _plugin_space(service, data)
    tool = _text(data.get("tool"), 120, "Outil", required=True)
    arguments = data.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("Les arguments d’un outil sont un objet.")
    entry = {"at": now(), "tool": tool, "arguments": arguments, "ok": True, "result": "", "error": ""}
    try:
        # plugins.read refuses any tool the plugin does not declare as a read tool.
        result = service.plugins.read(space["data"]["plugin_id"], space["project_id"], tool, arguments)
        blocks = [b.get("text", "") for b in result.get("content", []) if b.get("type") == "text"] if isinstance(result, dict) else []
        entry["result"] = ("\n\n".join(blocks) if blocks else json.dumps(result, ensure_ascii=False, indent=2))[:MAX_RESULT]
        entry["ok"] = not (isinstance(result, dict) and result.get("isError"))
    except Exception as exc:
        entry.update(ok=False, error=str(exc)[:2000])
    calls = ([entry] + space["data"].get("calls", []))[:MAX_CALLS]
    service.store.execute("UPDATE project_spaces SET data=?,updated_at=? WHERE id=?",
                          (json.dumps({**space["data"], "calls": calls}, ensure_ascii=False), now(), space["id"]))
    return {"call": entry}


def spaces_action(service, action, data):
    if action == "plugin_console":
        return plugin_console(service, data)
    if action == "plugin_console_call":
        return plugin_console_call(service, data)
    if action == "graph_data":
        return graph_data(service, data)
    if action == "space_create":
        return create_space(service, data)
    if action == "space_get":
        return get_space(service, data)
    if action == "space_rename":
        return rename_space(service, data)
    if action == "space_delete":
        return delete_space(service, data)
    if action == "whiteboard_save":
        return save_whiteboard(service, data)
    return UNHANDLED
