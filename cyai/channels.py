"""The channels of a project, and what its agents are really doing.

The interface shows a project the way Discord shows a server: typed channels on the left, the team on
the right. The structure is computed here, once, so the interface and the MCP see the same thing.

A channel is typed. Today the types are the existing views; new types — a graph, a whiteboard, a plugin —
are added to `TYPES` and get their own view, without reshaping the rest.

Presence never pretends. An agent is "running" only when a mission of its conversations is actually
active, "awaiting" only when an approval is pending, and "unavailable" when its connector cannot run.
Nothing here says "online".
"""
import json

UNHANDLED = object()

TYPES = {
    "assistant": {"label": "Assistant du projet", "icon": "sparkles"},
    "conversation": {"label": "Conversation", "icon": "hash"},
    "agent": {"label": "Conversation d’agent", "icon": "user"},
    "board": {"label": "Board", "icon": "layout-kanban"},
    "team": {"label": "Équipe", "icon": "users"},
    "overview": {"label": "Vue d’ensemble", "icon": "layout-dashboard"},
    "memory": {"label": "Mémoire", "icon": "brain"},
    "pins": {"label": "Épinglés", "icon": "pin"},
    "media": {"label": "Médias", "icon": "photo"},
    "skills": {"label": "Skills & contexte", "icon": "sparkles"},
    "plugins": {"label": "Plugins", "icon": "puzzle"},
    "settings": {"label": "Réglages", "icon": "settings"},
    "whiteboard": {"label": "Tableau blanc", "icon": "sticky-note"},
    "graph": {"label": "Graphe", "icon": "git-fork"},
    "plugin": {"label": "Console de plugin", "icon": "plug"},
}
CATEGORIES = ["Assistant", "Conversations", "Agents", "Espaces", "Équipe", "Projet"]
PRESENCE = {"running": "Exécution en cours", "awaiting": "Attend votre autorisation",
            "idle": "Au repos", "unavailable": "Connecteur indisponible"}


def _project(service, project_id):
    project = service.store.one("SELECT * FROM projects WHERE id=?", (project_id,))
    service.engine.policy.project(project["root"])
    return project


def _count(service, sql, params):
    return service.store.rows(sql, params)[0]["n"]


def presence(service, project_id):
    """What each agent of the team is doing, from recorded facts only.

    The source is the missions of its own conversations: a task execution row may still say "running"
    until it is reconciled, a mission status is what the engine is actually doing now.
    """
    from .teams import load_member, definition_status, ROLE_LABELS
    teams = service.store.rows("SELECT id FROM teams WHERE project_id=?", (project_id,))
    if not teams:
        return []
    members = [load_member(r) for r in service.store.rows(
        "SELECT * FROM team_members WHERE team_id=? AND active=1 ORDER BY position,created_at", (teams[0]["id"],))]
    conversations = {}
    for row in service.store.rows("SELECT id,member_id FROM conversations WHERE project_id=? AND member_id IS NOT NULL", (project_id,)):
        conversations.setdefault(row["member_id"], []).append(row["id"])
    with service.engine.lock:
        waiting = {a.get("mission_id") for a in service.engine.approvals.values()}
    result = []
    for member in members:
        ids = conversations.get(member["id"], [])
        missions = service.store.rows(
            "SELECT id,status,updated_at FROM missions WHERE conversation_id IN (" + ",".join("?" for _ in ids) + ") AND status IN ('queued','running','awaiting_approval','pausing')",
            tuple(ids)) if ids else []
        connector = definition_status(service, member["definition"])["connector"]
        if any(m["id"] in waiting or m["status"] == "awaiting_approval" for m in missions):
            state = "awaiting"
        elif missions:
            state = "running"
        elif connector != "enabled":
            state = "unavailable"
        else:
            state = "idle"
        last = None
        if missions:
            marks = ",".join("?" for _ in missions)
            last = service.store.rows("SELECT MAX(created_at) AS at FROM events WHERE mission_id IN (" + marks + ")",
                                      tuple(m["id"] for m in missions))[0]["at"]
        result.append({"id": member["id"], "name": member["definition"]["name"], "icon": member["definition"].get("icon", ""),
                       "role": member["role"], "role_label": ROLE_LABELS[member["role"]],
                       "connector": member["definition"]["connector"], "model": member["definition"]["model"],
                       "state": state, "state_label": PRESENCE[state], "last_signal": last,
                       "overridden": bool(member["overrides"])})
    return result


def project_channels(service, data):
    project = _project(service, data["project_id"])
    pid = project["id"]
    rows = service.store.rows(
        "SELECT id,title,mode,member_id,profile_id,favorite,purpose FROM conversations WHERE project_id=? AND archived=0 AND internal_parent_id IS NULL "
        "ORDER BY favorite DESC,position,created_at DESC", (pid,))
    activity = {r["conversation_id"]: r["status"] for r in service.store.rows(
        "SELECT conversation_id,status FROM missions WHERE status IN ('queued','running','awaiting_approval','pausing') "
        "AND conversation_id IN (SELECT id FROM conversations WHERE project_id=?)", (pid,))}
    channels = []

    def add(type, id, name, category, badge=0, tone="", **extra):
        channels.append({"type": type, "id": id, "name": name, "category": category, "icon": TYPES.get(type, {"icon": "square"})["icon"],
                         "badge": badge, "tone": tone, **extra})

    # The project's assistant comes first, above the conversations; highlighted until you have written to it.
    from .project_assistant import find, fresh
    assistant = find(service, pid)
    add("assistant", assistant or "", "assistant du projet", "Assistant", activity=activity.get(assistant, "") if assistant else "",
        fresh=bool(not assistant or fresh(service, assistant)), exists=bool(assistant))
    for row in rows:
        if row["purpose"] == "assistant":
            continue
        kind = "agent" if row["member_id"] or row["profile_id"] else "conversation"
        add(kind, row["id"], row["title"], "Agents" if kind == "agent" else "Conversations",
            activity=activity.get(row["id"], ""), mode=row["mode"], favorite=bool(row["favorite"]))
    from .teams import project_team_summary
    team = project_team_summary(service.store, pid)
    review = _count(service, "SELECT COUNT(*) AS n FROM tasks WHERE project_id=? AND status='in_review'", (pid,))
    from .spaces import list_spaces
    for space in list_spaces(service, pid):
        add(space["type"], space["id"], space["name"], "Espaces", space=True)
    add("board", "board", "board", "Équipe", review, "warning")
    add("team", "team", "équipe", "Équipe", team.get("issues", 0), "danger")
    add("overview", "overview", "vue d’ensemble", "Projet")
    add("memory", "memory", "mémoire", "Projet", _count(service, "SELECT COUNT(*) AS n FROM memory WHERE project_id=?", (pid,)))
    add("pins", "pins", "épinglés", "Projet",
        _count(service, "SELECT COUNT(*) AS n FROM memory WHERE project_id=? AND source_ids NOT IN ('[]','')", (pid,)))
    add("media", "media", "médias", "Projet", _count(service,
        "SELECT COUNT(*) AS n FROM files f JOIN conversations c ON c.id=f.conversation_id WHERE c.project_id=? AND f.kind='media'", (pid,)))
    add("skills", "skills", "skills & contexte", "Projet")
    add("plugins", "plugins", "plugins", "Projet")
    add("settings", "settings", "réglages", "Projet")
    return {"project_id": pid, "name": project["name"], "icon": project["icon"], "color": project["color"],
            "categories": CATEGORIES, "channels": channels, "members": presence(service, pid),
            "team": {"exists": team.get("exists", False), "ready": team.get("ready", False)}}


def project_pins(service, data):
    """Memory notes pinned from a message, with the conversation they came from."""
    project = _project(service, data["project_id"])
    pins = []
    for row in service.store.rows("SELECT * FROM memory WHERE project_id=? AND source_ids NOT IN ('[]','') ORDER BY created_at DESC", (project["id"],)):
        sources = json.loads(row["source_ids"])
        origin = service.store.rows(
            "SELECT m.conversation_id,c.title FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.id=?",
            (sources[0],)) if sources else []
        pins.append({**dict(row), "source_ids": sources,
                     "conversation_id": origin[0]["conversation_id"] if origin else None,
                     "conversation": origin[0]["title"] if origin else ""})
    return {"project_id": project["id"], "pins": pins}


def project_media(service, data):
    project = _project(service, data["project_id"])
    media = []
    for row in service.store.rows(
            "SELECT f.id,f.name,f.content,f.created_at,f.conversation_id,c.title FROM files f JOIN conversations c ON c.id=f.conversation_id "
            "WHERE c.project_id=? AND f.kind='media' ORDER BY f.created_at DESC", (project["id"],)):
        try:
            meta = json.loads(row["content"])
        except ValueError:
            meta = {}
        media.append({"id": row["id"], "name": row["name"], "content": row["content"], "kind": "media",
                      "mime": meta.get("mime", ""), "bytes": meta.get("bytes", 0),
                      "created_at": row["created_at"], "conversation_id": row["conversation_id"], "conversation": row["title"]})
    return {"project_id": project["id"], "media": media}


def channels_action(service, action, data):
    if action == "project_channels":
        return project_channels(service, data)
    if action == "project_pins":
        return project_pins(service, data)
    if action == "project_media":
        return project_media(service, data)
    return UNHANDLED
