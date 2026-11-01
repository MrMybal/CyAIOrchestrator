"""Methods and the agents that use them: preferred or imposed methods, the agent's own note, the programs they need.

A profile can prefer a method (it comes first when that agent looks for a method) or be told to use it for its kind
of work. Beside that link, the agent keeps its own note on how to use the method — written by the agent itself
through the MCP, or by you — readable from the method and from the agent. None of this is part of a profile
revision: it is how the library is organised, not what the agent is.

A method may need a program (LocalMesh, Blender…). Where it lives differs from one machine to another: the path you
give for this machine is kept in the configuration, used to check the requirement and written into the tasks that
need it. A missing program is a warning, never a refusal.
"""
import json
import re
import shutil
from pathlib import Path

from .store import now

UNHANDLED = object()

MODES = {"preferred": "préférée", "always": "à utiliser"}
MAX_NOTE = 20_000
NOTE_IN_CONTEXT = 1_500
NOTE_IN_TASK = 3_000


# --- programs on this machine -------------------------------------------------------------------------

def _key(name):
    return str(name or "").strip().lower()


def software_paths(service):
    paths = service.config.get("software_paths")
    return paths if isinstance(paths, dict) else {}


def software_status(service, requirement):
    """(found, where): the path given for this machine first, then the path or command of the method."""
    override = software_paths(service).get(_key(requirement["name"]))
    if override:
        return Path(override).exists(), str(override)
    target = requirement.get("executable") or requirement["name"]
    if re.search(r"[\\/]", target):
        path = Path(target).expanduser()
        return path.exists(), str(path)
    found = shutil.which(target)
    return bool(found), found or ""


def set_software_path(service, data):
    """Where a program lives on this machine. An empty path forgets it."""
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 120:
        raise ValueError("Nom du logiciel requis (120 caractères au plus).")
    raw = str(data.get("path") or "").strip().strip('"')
    paths = dict(software_paths(service))
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            raise ValueError("Indiquez un chemin complet, par exemple C:\\Program Files\\LocalMesh\\LocalMesh.exe.")
        if not path.exists():
            raise ValueError("Rien à ce chemin sur cette machine : " + str(path) + ".")
        paths[_key(name)] = str(path)
    else:
        paths.pop(_key(name), None)
    service.config["software_paths"] = paths
    service.config_path.write_text(json.dumps(service.config, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"name": name, "path": paths.get(_key(name), ""),
            "notice": ("« " + name + " » : " + paths[_key(name)] + " sur cette machine." if raw else
                       "Chemin de « " + name + " » oublié : il sera cherché dans le PATH ou au chemin de la méthode.")}


def method_software(service, method):
    """The programs a method needs, and where they are on this machine."""
    result = []
    for requirement in method.get("requirements", []):
        if requirement["kind"] == "software":
            found, where = software_status(service, requirement)
            result.append({"name": requirement["name"], "found": found, "where": where if found else "",
                           "detail": requirement.get("detail", "")})
    return result


# --- a profile and its methods ---------------------------------------------------------------------------

def _profile(service, id):
    return dict(service.store.one("SELECT id,name,icon,archived FROM agent_profiles WHERE id=?", (id,)))


def _method(service, id):
    return dict(service.store.one("SELECT id,name,description,usage,requirements FROM method_templates WHERE id=?", (id,)))


def set_link(service, data):
    """Prefer a method, impose it for this kind of work, or drop the link. The note is kept either way."""
    profile, method = _profile(service, data["profile_id"]), _method(service, data["method_id"])
    mode = str(data.get("mode") or "none")
    if mode not in {*MODES, "none"}:
        raise ValueError("Mode : preferred (préférée), always (à utiliser) ou none (retirer).")
    row = service.store.rows("SELECT note FROM profile_methods WHERE profile_id=? AND method_id=?", (profile["id"], method["id"]))
    if mode == "none":
        if row and row[0]["note"]:
            service.store.execute("UPDATE profile_methods SET mode='' WHERE profile_id=? AND method_id=?", (profile["id"], method["id"]))
        else:
            service.store.execute("DELETE FROM profile_methods WHERE profile_id=? AND method_id=?", (profile["id"], method["id"]))
        return {"profile_id": profile["id"], "method_id": method["id"], "mode": "",
                "notice": "« " + method["name"] + " » n’est plus liée à " + profile["name"] + "." + (" Sa note est conservée." if row and row[0]["note"] else "")}
    service.store.execute("INSERT INTO profile_methods(profile_id,method_id,mode,created_at) VALUES(?,?,?,?) "
                          "ON CONFLICT(profile_id,method_id) DO UPDATE SET mode=excluded.mode", (profile["id"], method["id"], mode, now()))
    missing = [s["name"] for s in method_software(service, {"requirements": json.loads(method["requirements"] or "[]")}) if not s["found"]]
    return {"profile_id": profile["id"], "method_id": method["id"], "mode": mode,
            "notice": "« " + method["name"] + " » " + ("préférée" if mode == "preferred" else "à utiliser") + " par " + profile["name"] + "." +
                      (" Logiciel absent de cette machine : " + ", ".join(missing) + "." if missing else "")}


def save_note(service, data, author="user"):
    """The agent's own note on how to use a method. Written by the agent (MCP) or by you; always attributed."""
    profile, method = _profile(service, data["profile_id"]), _method(service, data["method_id"])
    content = str(data.get("content") or "").strip()
    if len(content) > MAX_NOTE:
        raise ValueError("Note limitée à " + str(MAX_NOTE) + " caractères.")
    service.store.execute("INSERT INTO profile_methods(profile_id,method_id,mode,note,note_author,note_updated_at,created_at) VALUES(?,?,?,?,?,?,?) "
                          "ON CONFLICT(profile_id,method_id) DO UPDATE SET note=excluded.note,note_author=excluded.note_author,"
                          "note_updated_at=excluded.note_updated_at", (profile["id"], method["id"], "", content, author, now(), now()))
    if not content:
        service.store.execute("DELETE FROM profile_methods WHERE profile_id=? AND method_id=? AND mode=''", (profile["id"], method["id"]))
    return {"profile_id": profile["id"], "method_id": method["id"],
            "notice": ("Note de " + profile["name"] + " sur « " + method["name"] + " » enregistrée." if content else "Note effacée.")}


def _row(service, row):
    method = _method(service, row["method_id"])
    return {"method_id": method["id"], "name": method["name"], "description": method["description"], "mode": row["mode"],
            "note": row["note"], "note_author": row["note_author"], "note_updated_at": row["note_updated_at"],
            "software": method_software(service, {"requirements": json.loads(method["requirements"] or "[]")})}


def profile_methods(service, data):
    profile = _profile(service, data["profile_id"])
    rows = service.store.rows("SELECT * FROM profile_methods WHERE profile_id=?", (profile["id"],))
    order = {"always": 0, "preferred": 1, "": 2}
    methods = sorted((_row(service, r) for r in rows), key=lambda m: (order.get(m["mode"], 3), m["name"].lower()))
    return {"profile_id": profile["id"], "methods": methods}


def method_agents(service, data):
    method = _method(service, data["id"])
    rows = service.store.rows("SELECT pm.*, p.name, p.icon, p.archived FROM profile_methods pm JOIN agent_profiles p ON p.id=pm.profile_id "
                              "WHERE pm.method_id=? ORDER BY p.name", (method["id"],))
    return {"method_id": method["id"], "agents": [{"profile_id": r["profile_id"], "name": r["name"], "icon": r["icon"], "archived": bool(r["archived"]),
                                                   "mode": r["mode"], "note": r["note"], "note_author": r["note_author"],
                                                   "note_updated_at": r["note_updated_at"]} for r in rows]}


def summary(service, data=None):
    """For the library cards: each profile's preferred and imposed methods, and the programs they need here."""
    result = {}
    for row in service.store.rows("SELECT pm.profile_id, pm.mode, m.id, m.name, m.requirements FROM profile_methods pm "
                                  "JOIN method_templates m ON m.id=pm.method_id WHERE pm.mode<>'' ORDER BY m.name"):
        entry = result.setdefault(row["profile_id"], {"methods": [], "software": []})
        entry["methods"].append({"id": row["id"], "name": row["name"], "mode": row["mode"]})
        for program in method_software(service, {"requirements": json.loads(row["requirements"] or "[]")}):
            if program["name"] not in [p["name"] for p in entry["software"]]:
                entry["software"].append({"name": program["name"], "found": program["found"]})
    return {"profiles": result}


def preferences(service, profile_id):
    return {r["method_id"]: r["mode"] for r in service.store.rows("SELECT method_id,mode FROM profile_methods WHERE profile_id=? AND mode<>''", (profile_id,))}


def note_for(store, profile_id, method_id):
    rows = store.rows("SELECT note FROM profile_methods WHERE profile_id=? AND method_id=?", (profile_id, method_id))
    return rows[0]["note"] if rows else ""


def context_block(store, profile_id):
    """What an agent reads about its methods at the start of its context: names, how to use them, its own notes."""
    rows = store.rows("SELECT pm.mode, pm.note, m.id, m.name, m.description, m.usage, m.requirements FROM profile_methods pm "
                      "JOIN method_templates m ON m.id=pm.method_id WHERE pm.profile_id=? AND pm.mode<>'' ORDER BY pm.mode='preferred', m.name",
                      (profile_id,))
    if not rows:
        return ""
    lines = ["Méthodes de votre profil, dans la bibliothèque CyAI (lisez-les avec method_get, appliquez-les avec method_apply) :"]
    for r in rows:
        programs = [q["name"] for q in json.loads(r["requirements"] or "[]") if q.get("kind") == "software"]
        lines.append("- « " + r["name"] + " » [" + r["id"] + "] — " + ("à utiliser pour ce type de travail" if r["mode"] == "always" else "préférée") +
                     (" : " + r["description"][:300] if r["description"] else "") +
                     ("\n  Mode d’emploi : " + r["usage"][:600] if r["usage"] else "") +
                     ("\n  Logiciels requis : " + ", ".join(programs) if programs else "") +
                     ("\n  Votre note d’usage : " + r["note"][:NOTE_IN_CONTEXT] + ("…" if len(r["note"]) > NOTE_IN_CONTEXT else "") if r["note"] else ""))
    lines.append("Vous pouvez tenir votre propre note d’usage d’une méthode avec method_note_save (profile_id " + profile_id +
                 ") : ce qui marche, les pièges, ce que vous vérifiez. L’utilisateur la voit depuis la méthode et depuis votre fiche.")
    return "\n".join(lines)


def method_agents_action(service, action, data):
    if action == "software_path_set":
        return set_software_path(service, data)
    if action == "profile_method_set":
        return set_link(service, data)
    if action == "method_note_save":
        return save_note(service, data, str(data.get("author") or "user") if data.get("author") in {"user", "agent"} else "user")
    if action == "profile_methods":
        return profile_methods(service, data)
    if action == "method_agents":
        return method_agents(service, data)
    if action == "profile_methods_summary":
        return summary(service, data)
    return UNHANDLED
