"""Global agent profiles and per-project teams.

Lot 1 of the team/board specification: a reusable library of agent definitions, hierarchical
per-project teams built from frozen profile revisions, and reusable team templates.

Nothing here starts an execution. A profile is a saved configuration, never a provider session,
and a team declared "ready" means its composition is valid, not that an agent is working.
"""
import json

from .store import now, uid

UNHANDLED = object()

ROLES = {"chief", "lead", "member", "consultant"}
MANAGER_ROLES = {"chief", "lead"}
# A consultant is solicited on a task for what it does better (search, images, a specialised model).
# It sits outside the chain of command: it directs nobody and owes no report to a manager.
HIERARCHY_ROLES = {"chief", "lead", "member"}
ROLE_LABELS = {"chief": "Chef de projet", "lead": "Lead / chef d’équipe", "member": "Membre",
               "consultant": "Consultant · sollicité à la tâche"}
SETTING_KEYS = {"effort", "service_tier"}
DEFINITION_FIELDS = ("name", "description", "icon", "role", "skills", "connector", "model", "prompt", "settings", "helpers", "tools")
DEFINITION_DEFAULTS = {"name": "", "description": "", "icon": "", "role": "member", "skills": [],
                       "connector": "", "model": "", "prompt": "", "settings": {}, "helpers": [], "tools": []}
# What an assignment may change locally without touching the global profile. The role is not here:
# it is already a column of the assignment, and the suggested role belongs to the profile.
OVERRIDE_FIELDS = ("name", "description", "icon", "skills", "connector", "model", "prompt", "settings", "helpers", "tools")
FIELD_LABELS = {"name": "Nom", "description": "Description", "icon": "Icône", "role": "Rôle conseillé", "skills": "Compétences",
                "connector": "Connecteur", "model": "Modèle", "prompt": "Consignes initiales", "settings": "Réglages",
                "helpers": "Spécialistes appelables", "tools": "Outils (plugins)"}
BOARD_NOTICE = ("Composez les membres de l’équipe, puis utilisez le board ou leurs conversations. "
                "La création et la configuration de l’équipe ne lancent aucune tâche.")


def _text(value, limit, label, required=False):
    text = str(value if value is not None else "").strip()
    if required and not text:
        raise ValueError(label + " requis.")
    if len(text) > limit:
        raise ValueError(label + " limité à " + str(limit) + " caractères.")
    return text


def _skills(value):
    if isinstance(value, str):
        value = [part for chunk in value.split("\n") for part in chunk.split(",")]
    if not isinstance(value, list):
        raise ValueError("Les compétences doivent être une liste de textes.")
    skills = []
    for item in value:
        skill = _text(item, 80, "Compétence")
        if skill and skill not in skills:
            skills.append(skill)
    if len(skills) > 40:
        raise ValueError("40 compétences déclarées au maximum.")
    return skills


def _settings(value, connector):
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("Les réglages de modèle doivent être un objet.")
    settings = {}
    for key, item in value.items():
        if key not in SETTING_KEYS:
            raise ValueError("Réglage inconnu : " + str(key)[:40] + ". Réglages acceptés : " + ", ".join(sorted(SETTING_KEYS)) + ".")
        text = _text(item, 60, "Réglage " + key)
        if not text:
            continue
        if key == "service_tier" and connector != "codex":
            raise ValueError("La vitesse de service n’est proposée que par le connecteur Codex. Laissez ce réglage vide pour " + (connector or "ce connecteur") + ".")
        settings[key] = text
    return settings


def _helpers(service, value, own_id=None):
    """Other profiles this one may call as a tool. Kept short on purpose: a long list is a plan, not a helper."""
    if value is None:
        value = []
    if not isinstance(value, list):
        raise ValueError("Les spécialistes appelables sont une liste d’objets {profile_id, purpose}.")
    from .specialists import MAX_HELPERS
    if len(value) > MAX_HELPERS:
        raise ValueError("Au plus " + str(MAX_HELPERS) + " spécialistes appelables. Au-delà, écrivez une méthode.")
    helpers, seen = [], set()
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("Chaque spécialiste appelable est un objet {profile_id, purpose}.")
        id = _text(entry.get("profile_id"), 64, "Profil du spécialiste", required=True)
        if id == own_id:
            raise ValueError("Un profil ne peut pas se déclarer lui-même comme spécialiste appelable.")
        if id in seen:
            continue
        if service is not None and not service.store.rows("SELECT id FROM agent_profiles WHERE id=?", (id,)):
            raise ValueError("Spécialiste introuvable dans la bibliothèque : « " + id[:40] + " ».")
        seen.add(id)
        helpers.append({"profile_id": id, "purpose": _text(entry.get("purpose", ""), 300, "Rôle du spécialiste")})
    return helpers


def _tools(service, value):
    from .toolpacks import validate
    return validate(service, value)


def _definition(data, fallback=None, service=None, own_id=None):
    fallback = fallback or {}
    connector = _text(data.get("connector", fallback.get("connector", "")), 80, "Connecteur", required=True)
    role = str(data.get("role", fallback.get("role", "member")) or "member")
    if role not in ROLES:
        raise ValueError("Rôle conseillé inconnu. Valeurs acceptées : " + ", ".join(sorted(ROLES)) + ".")
    return {"name": _text(data.get("name", fallback.get("name", "")), 120, "Nom du profil", required=True),
            "description": _text(data.get("description", fallback.get("description", "")), 2000, "Description"),
            "icon": _text(data.get("icon", fallback.get("icon", "")), 8, "Icône"),
            "role": role,
            "skills": _skills(data.get("skills", fallback.get("skills", []))),
            "connector": connector,
            "model": _text(data.get("model", fallback.get("model", "")), 200, "Modèle"),
            "prompt": _text(data.get("prompt", fallback.get("prompt", "")), 20000, "Consignes initiales"),
            "settings": _settings(data.get("settings", fallback.get("settings", {})), connector),
            "helpers": _helpers(service, data.get("helpers", fallback.get("helpers", [])), own_id),
            "tools": _tools(service, data.get("tools", fallback.get("tools", [])))}


def _loaded(row):
    profile = dict(row)
    profile["skills"] = json.loads(profile["skills"])
    profile["settings"] = json.loads(profile["settings"])
    profile["helpers"] = json.loads(profile.get("helpers_json") or "[]")
    profile["tools"] = json.loads(profile.get("tools_json") or "[]")
    profile["archived"] = bool(profile["archived"])
    return profile


def normalised(definition):
    return {field: definition.get(field, DEFINITION_DEFAULTS[field]) for field in DEFINITION_FIELDS}


def effective_definition(frozen, overrides):
    """What this assignment actually is: its frozen revision, plus the edits made locally on it."""
    merged = normalised(frozen)
    merged.update({k: v for k, v in (overrides or {}).items() if k in OVERRIDE_FIELDS})
    return merged


def load_member(row):
    member = dict(row)
    member["frozen"] = normalised(json.loads(member["definition"]))
    member["overrides"] = json.loads(member["overrides"] or "{}") if "overrides" in member else {}
    member["definition"] = effective_definition(member["frozen"], member["overrides"])
    member["active"] = bool(member["active"])
    return member


def overrides_from(data, frozen, service=None):
    """Only what really differs from the frozen revision is stored as an override."""
    proposed = dict(data or {})
    unknown = set(proposed) - set(OVERRIDE_FIELDS)
    if unknown:
        raise ValueError("Champ non modifiable localement : " + ", ".join(sorted(unknown)) +
                         ". Modifiables : " + ", ".join(OVERRIDE_FIELDS) + ".")
    connector = _text(proposed.get("connector", frozen.get("connector", "")), 80, "Connecteur", required=True)
    candidate = {"name": _text(proposed.get("name", frozen["name"]), 120, "Nom", required=True),
                 "description": _text(proposed.get("description", frozen["description"]), 2000, "Description"),
                 "icon": _text(proposed.get("icon", frozen["icon"]), 8, "Icône"),
                 "skills": _skills(proposed.get("skills", frozen["skills"])),
                 "connector": connector,
                 "model": _text(proposed.get("model", frozen["model"]), 200, "Modèle"),
                 "prompt": _text(proposed.get("prompt", frozen["prompt"]), 20000, "Consignes"),
                 "settings": _settings(proposed.get("settings", frozen["settings"]), connector),
                 "helpers": _helpers(service, proposed.get("helpers", frozen.get("helpers", []))),
                 "tools": _tools(service, proposed.get("tools", frozen.get("tools", [])))}
    return {field: value for field, value in candidate.items() if value != frozen.get(field, DEFINITION_DEFAULTS[field])}


def current_definition(profile):
    current = {field: profile[field] for field in DEFINITION_FIELDS if field in profile}
    if "helpers" not in current:
        rows = profile.get("helpers_json")
        current["helpers"] = json.loads(rows) if rows else []
    if "tools" not in current:
        rows = profile.get("tools_json")
        current["tools"] = json.loads(rows) if rows else []
    return normalised(current)


def definition_status(service, definition):
    """What is actually known about the connector and model of a saved definition.

    A saved profile is never announced as ready to execute: an enabled connector is a configuration,
    not a verified run, and a model absent from the catalogue stays usable but unconfirmed.
    """
    connector_id = definition.get("connector", "")
    connector = service.engine.connectors.get(connector_id)
    status = {"connector_id": connector_id}
    if connector is None:
        status |= {"connector": "missing", "connector_detail": "Connecteur « " + (connector_id or "non renseigné") + " » absent de cette installation."}
    elif not connector.config.get("enabled", False):
        status |= {"connector": "disabled", "connector_detail": "Connecteur désactivé : activez-le dans Connecteurs avant toute exécution."}
    else:
        status |= {"connector": "enabled", "connector_detail": "Connecteur activé. Une activation n’est pas une exécution vérifiée."}
    model = definition.get("model", "")
    catalog = service.catalogs.get(connector_id) or []
    known = {m.get("id") if isinstance(m, dict) else str(m) for m in catalog}
    if not model:
        status |= {"model": "default", "model_detail": "Modèle par défaut du connecteur, résolu à l’exécution."}
    elif not catalog:
        status |= {"model": "catalogue_indisponible", "model_detail": "Catalogue du connecteur indisponible : le modèle saisi n’a pas pu être vérifié."}
    elif model in known:
        status |= {"model": "confirmed", "model_detail": "Modèle présent dans le catalogue du connecteur."}
    else:
        status |= {"model": "unconfirmed", "model_detail": "Modèle non confirmé : absent du catalogue connu du connecteur."}
    return status


# --- profiles -------------------------------------------------------------------------------

def list_profiles(service, include_archived=True):
    rows = [_loaded(r) for r in service.store.rows("SELECT * FROM agent_profiles ORDER BY archived,name")]
    profiles = []
    for profile in rows:
        if profile["archived"] and not include_archived:
            continue
        profile["status"] = definition_status(service, current_definition(profile))
        profile["attested"] = [r["skill"] for r in service.store.rows("SELECT skill FROM skill_attestations WHERE profile_id=?", (profile["id"],))]
        profile["assignments"] = service.store.rows(
            "SELECT m.id,m.project_id,m.role,m.active,m.profile_revision,p.name AS project FROM team_members m JOIN projects p ON p.id=m.project_id WHERE m.profile_id=? ORDER BY p.name",
            (profile["id"],))
        profiles.append(profile)
    return profiles


def get_profile(service, id):
    profile = _loaded(service.store.one("SELECT * FROM agent_profiles WHERE id=?", (id,)))
    profile["status"] = definition_status(service, current_definition(profile))
    profile["revisions"] = [{**r, "definition": json.loads(r["definition"])}
                            for r in service.store.rows("SELECT * FROM agent_profile_revisions WHERE profile_id=? ORDER BY revision DESC", (id,))]
    profile["assignments"] = service.store.rows(
        "SELECT m.id,m.project_id,m.team_id,m.role,m.active,m.profile_revision,p.name AS project FROM team_members m JOIN projects p ON p.id=m.project_id WHERE m.profile_id=? ORDER BY p.name",
        (id,))
    return profile


def save_profile(service, data):
    id = data.get("id")
    existing = _loaded(service.store.one("SELECT * FROM agent_profiles WHERE id=?", (id,))) if id else None
    definition = _definition(data, current_definition(existing) if existing else None, service, id)
    note = _text(data.get("note", ""), 400, "Note de révision")
    timestamp = now()
    if existing is None:
        id = uid()
        with service.store.transaction() as db:
            db.execute("INSERT INTO agent_profiles(id,name,description,icon,role,skills,connector,model,prompt,settings,helpers_json,tools_json,revision,archived,created_at,updated_at)"
                       " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,0,?,?)",
                       (id, definition["name"], definition["description"], definition["icon"], definition["role"],
                        json.dumps(definition["skills"], ensure_ascii=False), definition["connector"], definition["model"],
                        definition["prompt"], json.dumps(definition["settings"], ensure_ascii=False),
                        json.dumps(definition["helpers"], ensure_ascii=False), json.dumps(definition["tools"]), timestamp, timestamp))
            db.execute("INSERT INTO agent_profile_revisions(id,profile_id,revision,definition,note,created_at) VALUES(?,?,?,?,?,?)",
                       (uid(), id, 1, json.dumps(definition, ensure_ascii=False), note or "Création du profil.", timestamp))
        if data.get("category"):
            set_profile_category(service, {"id": id, "category": data["category"]})
        return {"id": id, "revision": 1, "created": True}
    if "category" in data and data["category"] != existing.get("category", ""):
        set_profile_category(service, {"id": id, "category": data["category"]})
    if definition == current_definition(existing):
        return {"id": id, "revision": existing["revision"], "created": False, "unchanged": True,
                "notice": "Aucune modification : la révision " + str(existing["revision"]) + " est conservée."}
    revision = existing["revision"] + 1
    with service.store.transaction() as db:
        db.execute("UPDATE agent_profiles SET name=?,description=?,icon=?,role=?,skills=?,connector=?,model=?,prompt=?,settings=?,helpers_json=?,tools_json=?,revision=?,updated_at=? WHERE id=?",
                   (definition["name"], definition["description"], definition["icon"], definition["role"],
                    json.dumps(definition["skills"], ensure_ascii=False), definition["connector"], definition["model"],
                    definition["prompt"], json.dumps(definition["settings"], ensure_ascii=False),
                    json.dumps(definition["helpers"], ensure_ascii=False), json.dumps(definition["tools"]), revision, timestamp, id))
        db.execute("INSERT INTO agent_profile_revisions(id,profile_id,revision,definition,note,created_at) VALUES(?,?,?,?,?,?)",
                   (uid(), id, revision, json.dumps(definition, ensure_ascii=False), note, timestamp))
    return {"id": id, "revision": revision, "created": False,
            "notice": "Révision " + str(revision) + " enregistrée. Les équipes existantes conservent leur révision jusqu’à adoption explicite."}


def set_profile_category(service, data):
    """File a profile in the library. Organisation only: no revision, no effect on assignments."""
    profile = service.store.one("SELECT id,name,category FROM agent_profiles WHERE id=?", (data["id"],))
    category = _text(data.get("category", ""), 60, "Catégorie")
    service.store.execute("UPDATE agent_profiles SET category=?,updated_at=? WHERE id=?", (category, now(), profile["id"]))
    return {"id": profile["id"], "category": category,
            "notice": (profile["name"] + " rangé dans « " + category + " ».") if category else (profile["name"] + " retiré de sa catégorie.")}


def duplicate_profile(service, data):
    source = _loaded(service.store.one("SELECT * FROM agent_profiles WHERE id=?", (data["id"],)))
    definition = current_definition(source)
    definition["name"] = _text(data.get("name", "") or (source["name"] + " (copie)"), 120, "Nom du profil", required=True)
    result = save_profile(service, {**definition, "note": "Duplication de « " + source["name"] + " » (révision " + str(source["revision"]) + ")."})
    if source.get("category"):
        set_profile_category(service, {"id": result["id"], "category": source["category"]})
    return {**result, "notice": "Profil indépendant créé. Il ne partage ni révisions ni affectations avec le profil d’origine."}


def archive_profile(service, data):
    profile = service.store.one("SELECT * FROM agent_profiles WHERE id=?", (data["id"],))
    archived = bool(data.get("archived", True))
    service.store.execute("UPDATE agent_profiles SET archived=?,updated_at=? WHERE id=?", (int(archived), now(), profile["id"]))
    assignments = service.store.rows("SELECT id FROM team_members WHERE profile_id=? AND active=1", (profile["id"],))
    notice = ("Profil archivé : " + str(len(assignments)) + " affectation(s) active(s) conservée(s) avec leur révision figée ; "
              "l’historique des révisions reste intact. Le profil n’est plus proposé pour de nouvelles affectations.") if archived else \
             "Profil réactivé : il est de nouveau proposé pour de nouvelles affectations."
    return {"id": profile["id"], "archived": archived, "notice": notice}


# --- teams ----------------------------------------------------------------------------------

def _project(service, project_id):
    project = service.store.one("SELECT * FROM projects WHERE id=?", (project_id,))
    service.engine.policy.project(project["root"])
    return project


def _team_row(service, project_id, required=True):
    rows = service.store.rows("SELECT * FROM teams WHERE project_id=?", (project_id,))
    if not rows:
        if required:
            raise ValueError("Aucune équipe pour ce projet. Créez-la depuis l’onglet Équipe avant d’ajouter des agents.")
        return None
    return rows[0]


def _members(service, team_id):
    return [load_member(row) for row in service.store.rows("SELECT * FROM team_members WHERE team_id=? ORDER BY position,created_at", (team_id,))]


def _manager_chain(members, member_id):
    """Assignment ids from member to the top of its branch; a repeat means a cycle."""
    index = {m["id"]: m for m in members}
    chain, seen = [], set()
    current = index.get(member_id)
    while current and current.get("manager_id"):
        if current["manager_id"] in seen:
            return chain, True
        seen.add(current["manager_id"])
        chain.append(current["manager_id"])
        current = index.get(current["manager_id"])
    return chain, False


def _check_manager(members, member_id, manager_id):
    """Refused at the service level, not merely hidden in the interface."""
    if manager_id is None:
        return None
    if manager_id == member_id:
        raise ValueError("Un agent ne peut pas être son propre responsable.")
    manager = next((m for m in members if m["id"] == manager_id), None)
    if manager is None:
        raise ValueError("Responsable introuvable dans cette équipe. Un responsable doit être une affectation de la même équipe et du même projet.")
    if not manager["active"]:
        raise ValueError("Ce responsable est retiré de l’équipe : choisissez un agent actif.")
    if manager["role"] not in MANAGER_ROLES:
        raise ValueError("Seul un chef de projet ou un lead peut diriger des membres.")
    chain, cycle = _manager_chain(members, member_id)
    if cycle or member_id in chain:
        raise ValueError("Hiérarchie circulaire refusée : cette affectation se retrouverait sous elle-même.")
    return manager_id


def team_issues(team, members):
    """Blocking composition problems. Connector availability is reported separately as a warning.

    Consultants are deliberately exempt from the chain-of-command rules: they answer task requests,
    they do not own a branch.
    """
    issues = []
    if not team["name"].strip():
        issues.append({"code": "team_name", "field": "name", "message": "Nom de l’équipe requis."})
    active = [m for m in members if m["active"]]
    chiefs = [m for m in active if m["role"] == "chief"]
    if not chiefs:
        issues.append({"code": "no_chief", "field": "role", "message": "Aucun chef de projet actif : désignez l’interlocuteur principal."})
    if len(chiefs) > 1:
        for chief in chiefs[1:]:
            issues.append({"code": "multiple_chiefs", "member_id": chief["id"], "field": "role",
                           "message": chief["definition"]["name"] + " : une équipe prête ne comporte qu’un seul chef de projet."})
    index = {m["id"]: m for m in members}
    for member in active:
        name = member["definition"]["name"]
        if member["role"] == "consultant":
            # Outside the hierarchy on purpose: an optional referent, never a required manager.
            if member["manager_id"] and not index.get(member["manager_id"], {}).get("active"):
                issues.append({"code": "manager_inactive", "member_id": member["id"], "field": "manager_id",
                               "message": name + " a pour référent une affectation retirée : choisissez-en une autre ou retirez le lien."})
            continue
        if member["role"] == "chief":
            if member["manager_id"]:
                issues.append({"code": "chief_has_manager", "member_id": member["id"], "field": "manager_id",
                               "message": name + " est chef de projet : il ne doit pas avoir de responsable."})
            continue
        manager = index.get(member["manager_id"]) if member["manager_id"] else None
        if manager is None:
            issues.append({"code": "missing_manager", "member_id": member["id"], "field": "manager_id",
                           "message": name + " n’a pas de responsable : rattachez-le au chef ou à un lead."})
            continue
        if not manager["active"]:
            issues.append({"code": "manager_inactive", "member_id": member["id"], "field": "manager_id",
                           "message": name + " dépend de " + manager["definition"]["name"] + ", qui est retiré de l’équipe : réaffectez-le."})
            continue
        if manager["role"] not in MANAGER_ROLES:
            issues.append({"code": "manager_role", "member_id": member["id"], "field": "manager_id",
                           "message": name + " dépend de " + manager["definition"]["name"] + ", qui n’est ni chef ni lead."})
            continue
        chain, cycle = _manager_chain(members, member["id"])
        if cycle:
            issues.append({"code": "cycle", "member_id": member["id"], "field": "manager_id",
                           "message": name + " appartient à une boucle hiérarchique."})
        elif chiefs and chain and index.get(chain[-1], {}).get("role") != "chief":
            issues.append({"code": "detached", "member_id": member["id"], "field": "manager_id",
                           "message": name + " : sa branche ne remonte pas jusqu’au chef de projet."})
    return issues


def execution_warnings(service, members):
    """Never blocking: a disabled connector or an unconfirmed model must not prevent configuration."""
    warnings = []
    for member in members:
        if not member["active"]:
            continue
        status = member["status"]
        name = member["definition"]["name"]
        if status["connector"] != "enabled":
            warnings.append({"code": "connector_" + status["connector"], "member_id": member["id"], "message": name + " : " + status["connector_detail"]})
        if status["model"] in {"unconfirmed", "catalogue_indisponible"}:
            warnings.append({"code": "model_" + status["model"], "member_id": member["id"], "message": name + " : " + status["model_detail"]})
    return warnings


def _decorate(service, members):
    profiles = {p["id"]: p for p in (_loaded(r) for r in service.store.rows("SELECT * FROM agent_profiles"))}
    for member in members:
        profile = profiles.get(member["profile_id"])
        member["status"] = definition_status(service, member["definition"])
        member["role_label"] = ROLE_LABELS[member["role"]]
        member["profile_missing"] = profile is None
        member["profile_archived"] = bool(profile["archived"]) if profile else False
        member["profile_revision_current"] = profile["revision"] if profile else member["profile_revision"]
        member["update_available"] = bool(profile and profile["revision"] > member["profile_revision"])
        member["profile_name"] = profile["name"] if profile else member["frozen"]["name"]
        member["overridden"] = sorted(member["overrides"])
        member["override_labels"] = [FIELD_LABELS[f] for f in sorted(member["overrides"]) if f in FIELD_LABELS]
    return members


def get_team(service, project_id):
    project = _project(service, project_id)
    team = _team_row(service, project_id, required=False)
    if not team:
        return {"project_id": project_id, "project": project["name"], "team": None, "members": [], "issues": [], "warnings": [],
                "templates": list_templates(service), "library": [{"id": p["id"], "name": p["name"], "role": p["role"], "revision": p["revision"],
                                                                   "archived": p["archived"], "connector": p["connector"], "model": p["model"],
                                                                   "skills": p["skills"], "status": p["status"]} for p in list_profiles(service)],
                "notice": BOARD_NOTICE, "roles": ROLE_LABELS}
    members = _decorate(service, _members(service, team["id"]))
    issues = team_issues(team, members)
    return {"project_id": project_id, "project": project["name"], "team": dict(team), "members": members,
            "issues": issues, "warnings": execution_warnings(service, members),
            "ready": team["status"] == "ready" and not issues,
            "templates": list_templates(service),
            "library": [{"id": p["id"], "name": p["name"], "role": p["role"], "revision": p["revision"], "archived": p["archived"],
                         "connector": p["connector"], "model": p["model"], "skills": p["skills"], "status": p["status"]} for p in list_profiles(service)],
            "notice": BOARD_NOTICE, "roles": ROLE_LABELS}


def project_team_summary(store, project_id):
    """Small badge for the project dashboard; it never triggers an execution or a write."""
    rows = store.rows("SELECT * FROM teams WHERE project_id=?", (project_id,))
    if not rows:
        return {"exists": False, "status": "absent", "active_members": 0, "issues": 0}
    team = rows[0]
    members = [load_member(row) for row in store.rows("SELECT * FROM team_members WHERE team_id=? ORDER BY position,created_at", (team["id"],))]
    issues = team_issues(team, members)
    return {"exists": True, "id": team["id"], "name": team["name"], "status": team["status"],
            "active_members": len([m for m in members if m["active"]]), "issues": len(issues),
            "ready": team["status"] == "ready" and not issues}


def save_team(service, data):
    project = _project(service, data["project_id"])
    team = _team_row(service, project["id"], required=False)
    timestamp = now()
    if team is None:
        id = uid()
        name = _text(data.get("name", "") or ("Équipe · " + project["name"]), 120, "Nom de l’équipe", required=True)
        service.store.execute("INSERT INTO teams(id,project_id,name,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                              (id, project["id"], name, "draft", timestamp, timestamp))
        return {"id": id, "status": "draft", "created": True,
                "notice": "Équipe créée en brouillon. Ajoutez un chef de projet, puis des leads et des membres."}
    name = _text(data.get("name", team["name"]), 120, "Nom de l’équipe", required=True)
    status = str(data.get("status", team["status"]))
    if status not in {"draft", "ready"}:
        raise ValueError("État d’équipe inconnu : brouillon (draft) ou prête (ready).")
    if status == "ready":
        members = _decorate(service, _members(service, team["id"]))
        issues = team_issues({**dict(team), "name": name}, members)
        if issues:
            raise ValueError("Équipe incomplète : " + " ".join(i["message"] for i in issues))
    service.store.execute("UPDATE teams SET name=?,status=?,updated_at=? WHERE id=?", (name, status, timestamp, team["id"]))
    return {"id": team["id"], "status": status,
            "notice": "Composition déclarée prête. Vous pouvez maintenant préparer les tâches dans le board."
                      if status == "ready" else "Équipe enregistrée en brouillon."}


def _revision_definition(service, profile_id, revision):
    rows = service.store.rows("SELECT * FROM agent_profile_revisions WHERE profile_id=? AND revision=?", (profile_id, revision))
    if not rows:
        raise ValueError("Révision " + str(revision) + " introuvable pour ce profil.")
    return json.loads(rows[0]["definition"])


def add_member(service, data):
    project = _project(service, data["project_id"])
    team = _team_row(service, project["id"])
    profile = _loaded(service.store.one("SELECT * FROM agent_profiles WHERE id=?", (data["profile_id"],)))
    if profile["archived"]:
        raise ValueError("Profil archivé : réactivez-le avant de l’affecter. Les affectations existantes ne sont pas touchées.")
    revision = int(data.get("revision") or profile["revision"])
    definition = _revision_definition(service, profile["id"], revision)
    role = str(data.get("role") or definition["role"])
    if role not in ROLES:
        raise ValueError("Rôle d’équipe inconnu. Valeurs acceptées : " + ", ".join(sorted(ROLES)) + ".")
    members = _members(service, team["id"])
    id = uid()
    manager_id = data.get("manager_id") or None
    if role == "chief" and manager_id:
        raise ValueError("Le chef de projet n’a pas de responsable.")
    _check_manager(members + [{"id": id, "role": role, "manager_id": manager_id, "active": True, "definition": definition}], id, manager_id)
    position = max([m["position"] for m in members], default=-1) + 1
    timestamp = now()
    service.store.execute(
        "INSERT INTO team_members(id,team_id,project_id,profile_id,profile_revision,definition,role,responsibility,manager_id,active,position,created_at,updated_at)"
        " VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?)",
        (id, team["id"], project["id"], profile["id"], revision, json.dumps(definition, ensure_ascii=False), role,
         _text(data.get("responsibility", ""), 2000, "Responsabilité locale"), manager_id, position, timestamp, timestamp))
    return {"id": id, "revision": revision,
            "notice": "Agent affecté avec une copie figée de la révision " + str(revision) + ". Aucune exécution n’est lancée."}


def _member(service, project_id, id):
    member = service.store.one("SELECT * FROM team_members WHERE id=?", (id,))
    if member["project_id"] != project_id:
        raise ValueError("Cette affectation appartient à un autre projet.")
    return member


def _subordinates(members, id):
    return [m for m in members if m["active"] and m["manager_id"] == id]


def _detach(simulated, member, data):
    """Removing or demoting a manager: reassign explicitly, or accept an explicitly incomplete draft.

    Returns (updates, notice) where updates maps subordinate ids to their new manager.
    """
    subordinates = _subordinates(simulated, member["id"])
    subordinates = [s for s in subordinates if s["id"] != member["id"]]
    if not subordinates:
        return {}, None
    names = ", ".join(m["definition"]["name"] for m in subordinates)
    target = data.get("reassign_to") or None
    ids = {s["id"] for s in subordinates}
    if target:
        if target == member["id"]:
            raise ValueError("Choisissez un autre responsable que celui qui perd cette autorité.")
        moved = [{**m, "manager_id": target if m["id"] in ids else m["manager_id"]} for m in simulated]
        for sub in subordinates:
            _check_manager(moved, sub["id"], target)
        return {id: target for id in ids}, "Subordonnés réaffectés : " + names + "."
    if not data.get("acknowledged"):
        raise ValueError(member["definition"]["name"] + " dirige " + str(len(subordinates)) + " agent(s) : " + names +
                         ". Fournissez un nouveau responsable (reassign_to) ou confirmez (acknowledged) pour laisser l’équipe explicitement incomplète.")
    return {id: None for id in ids}, ("Équipe laissée incomplète : " + names + " sans responsable. "
                                      "Le brouillon reste enregistré et le problème est signalé dans l’onglet Équipe.")


def _apply_detach(db, updates):
    timestamp = now()
    for id, manager in updates.items():
        db.execute("UPDATE team_members SET manager_id=?,updated_at=? WHERE id=?", (manager, timestamp, id))


def update_member(service, data):
    project = _project(service, data["project_id"])
    member = _member(service, project["id"], data["id"])
    members = _members(service, member["team_id"])
    current = next(m for m in members if m["id"] == member["id"])
    role = str(data.get("role", member["role"]))
    if role not in ROLES:
        raise ValueError("Rôle d’équipe inconnu. Valeurs acceptées : " + ", ".join(sorted(ROLES)) + ".")
    active = bool(data.get("active", member["active"]))
    manager_id = (data["manager_id"] or None) if "manager_id" in data else member["manager_id"]
    if role == "chief":
        manager_id = None
    responsibility = _text(data.get("responsibility", member["responsibility"]), 2000, "Responsabilité locale")
    overrides = current["overrides"]
    if "overrides" in data:
        overrides = {} if data["overrides"] in (None, {}) else overrides_from(data["overrides"], current["frozen"], service)
    simulated = [{**m, **({"role": role, "manager_id": manager_id, "active": active} if m["id"] == member["id"] else {})} for m in members]
    _check_manager(simulated, member["id"], manager_id)
    notice = []
    updates = {}
    if (current["role"] in MANAGER_ROLES and role not in MANAGER_ROLES) or (current["active"] and not active):
        updates, detached = _detach(simulated, current, data)
        if detached:
            notice.append(detached)
    with service.store.transaction() as db:
        _apply_detach(db, updates)
        db.execute("UPDATE team_members SET role=?,responsibility=?,manager_id=?,active=?,overrides=?,updated_at=? WHERE id=?",
                   (role, responsibility, manager_id, int(active), json.dumps(overrides, ensure_ascii=False), now(), member["id"]))
    if overrides != current["overrides"]:
        notice.append(("Modifications locales enregistrées sur " + ", ".join(FIELD_LABELS[f] for f in sorted(overrides) if f in FIELD_LABELS) +
                       ". Elles appartiennent à cette affectation : le profil global et les autres projets ne changent pas.")
                      if overrides else "Retour à la définition figée de la révision : les modifications locales sont effacées.")
    return {"id": member["id"], "notice": " ".join(notice) or "Affectation mise à jour."}


def remove_member(service, data):
    project = _project(service, data["project_id"])
    member = _member(service, project["id"], data["id"])
    members = _members(service, member["team_id"])
    current = next(m for m in members if m["id"] == member["id"])
    simulated = [{**m, **({"active": False} if m["id"] == member["id"] else {})} for m in members]
    updates, detached = _detach(simulated, current, data)
    notice = [detached] if detached else []
    with service.store.transaction() as db:
        _apply_detach(db, updates)
        if data.get("delete"):
            db.execute("DELETE FROM team_members WHERE id=?", (member["id"],))
            notice.append("Affectation supprimée de la composition.")
        else:
            db.execute("UPDATE team_members SET active=0,updated_at=? WHERE id=?", (now(), member["id"]))
            notice.append("Agent retiré de l’équipe ; son affectation reste consultable et réactivable.")
    return {"id": member["id"], "notice": " ".join(notice)}


def revision_preview(service, data):
    project = _project(service, data["project_id"])
    member = _member(service, project["id"], data["id"])
    profile = _loaded(service.store.one("SELECT * FROM agent_profiles WHERE id=?", (member["profile_id"],)))
    revision = int(data.get("revision") or profile["revision"])
    target = normalised(_revision_definition(service, profile["id"], revision))
    loaded = load_member(member)
    current = loaded["frozen"]
    changes = []
    for field in DEFINITION_FIELDS:
        if current.get(field) != target.get(field):
            changes.append({"field": field, "label": FIELD_LABELS[field], "from": current.get(field), "to": target.get(field),
                            "overridden": field in loaded["overrides"]})
    overridden = [FIELD_LABELS[c["field"]] for c in changes if c["overridden"]]
    return {"id": member["id"], "from_revision": member["profile_revision"], "to_revision": revision,
            "changes": changes, "profile_archived": profile["archived"], "overridden": overridden,
            "notice": "Aperçu seulement : rien n’est modifié tant que l’adoption n’est pas demandée." +
                      (" Vos modifications locales sur " + ", ".join(overridden) + " resteront prioritaires après l’adoption."
                       if overridden else "")}


def adopt_revision(service, data):
    project = _project(service, data["project_id"])
    member = _member(service, project["id"], data["id"])
    profile = service.store.one("SELECT * FROM agent_profiles WHERE id=?", (member["profile_id"],))
    revision = int(data.get("revision") or profile["revision"])
    definition = _revision_definition(service, profile["id"], revision)
    service.store.execute("UPDATE team_members SET profile_revision=?,definition=?,updated_at=? WHERE id=?",
                          (revision, json.dumps(definition, ensure_ascii=False), now(), member["id"]))
    return {"id": member["id"], "revision": revision,
            "notice": "Révision " + str(revision) + " adoptée pour cette affectation. Les autres projets gardent la leur."}


# --- reusable team templates ----------------------------------------------------------------

def list_templates(service):
    return [{**row, "composition": json.loads(row["composition"])} for row in service.store.rows("SELECT * FROM team_templates ORDER BY name")]


def save_template(service, data):
    project = _project(service, data["project_id"])
    team = _team_row(service, project["id"])
    members = [m for m in _members(service, team["id"]) if m["active"]]
    if not members:
        raise ValueError("Aucun agent actif à enregistrer dans ce modèle.")
    keys = {m["id"]: "k" + str(i) for i, m in enumerate(members)}
    composition = {"team_name": team["name"], "members": [
        {"key": keys[m["id"]], "profile_id": m["profile_id"], "profile_revision": m["profile_revision"], "definition": m["frozen"],
         "overrides": m["overrides"], "role": m["role"], "responsibility": m["responsibility"],
         "manager_key": keys.get(m["manager_id"]), "position": m["position"]}
        for m in members]}
    id = data.get("template_id") or uid()
    name = _text(data.get("name", ""), 120, "Nom du modèle", required=True)
    description = _text(data.get("description", ""), 2000, "Description du modèle")
    timestamp = now()
    service.store.execute(
        "INSERT INTO team_templates(id,name,description,composition,created_at,updated_at) VALUES(?,?,?,?,?,?)"
        " ON CONFLICT(id) DO UPDATE SET name=excluded.name,description=excluded.description,composition=excluded.composition,updated_at=excluded.updated_at",
        (id, name, description, json.dumps(composition, ensure_ascii=False), timestamp, timestamp))
    return {"id": id, "members": len(members),
            "notice": "Modèle enregistré : profils, révisions, rôles et liens hiérarchiques. Ni tâches, ni discussions, ni sessions, ni mémoire du projet."}


def apply_template(service, data):
    project = _project(service, data["project_id"])
    template = service.store.one("SELECT * FROM team_templates WHERE id=?", (data["template_id"],))
    composition = json.loads(template["composition"])
    missing = [m["definition"]["name"] for m in composition["members"]
               if not service.store.rows("SELECT id FROM agent_profiles WHERE id=?", (m["profile_id"],))]
    if missing:
        raise ValueError("Profils absents de cette installation : " + ", ".join(missing) + ". Recréez-les avant d’appliquer ce modèle.")
    team = _team_row(service, project["id"], required=False)
    if team is None:
        save_team(service, {"project_id": project["id"], "name": data.get("name") or composition.get("team_name") or ("Équipe · " + project["name"])})
        team = _team_row(service, project["id"])
    existing = _members(service, team["id"])
    if existing and not data.get("replace"):
        raise ValueError("Cette équipe contient déjà " + str(len(existing)) + " affectation(s). Confirmez le remplacement (replace) pour appliquer le modèle.")
    ids = {m["key"]: uid() for m in composition["members"]}
    timestamp = now()
    with service.store.transaction() as db:
        if existing:
            db.execute("DELETE FROM team_members WHERE team_id=?", (team["id"],))
        for member in composition["members"]:
            db.execute("INSERT INTO team_members(id,team_id,project_id,profile_id,profile_revision,definition,role,responsibility,manager_id,active,position,created_at,updated_at)"
                       " VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?)",
                       (ids[member["key"]], team["id"], project["id"], member["profile_id"], member["profile_revision"],
                        json.dumps(member["definition"], ensure_ascii=False), member["role"], member.get("responsibility", ""),
                        ids.get(member.get("manager_key")), member.get("position", 0), timestamp, timestamp))
            db.execute("UPDATE team_members SET overrides=? WHERE id=?",
                       (json.dumps(member.get("overrides", {}), ensure_ascii=False), ids[member["key"]]))
        db.execute("UPDATE teams SET status='draft',updated_at=? WHERE id=?", (timestamp, team["id"]))
    return {"team_id": team["id"], "members": len(ids),
            "notice": "Modèle appliqué avec de nouvelles affectations. Aucune tâche, conversation, session native ni mémoire du projet d’origine n’est importée."}


def delete_template(service, data):
    template = service.store.one("SELECT * FROM team_templates WHERE id=?", (data["id"],))
    service.store.execute("DELETE FROM team_templates WHERE id=?", (template["id"],))
    return {"id": template["id"], "notice": "Modèle supprimé. Les équipes déjà créées à partir de ce modèle ne sont pas touchées."}


# --- dispatcher -----------------------------------------------------------------------------

def teams_action(service, action, data):
    if action == "agent_profile_list":
        return {"profiles": list_profiles(service),
                "connectors": [{"id": id, "enabled": bool(c.config.get("enabled", False)), "model": c.config.get("model", ""),
                                "models": service.catalogs.get(id) or []} for id, c in service.engine.connectors.items()],
                "roles": ROLE_LABELS, "notice": BOARD_NOTICE}
    if action == "agent_profile_get":
        return get_profile(service, data["id"])
    if action == "agent_profile_save":
        return save_profile(service, data)
    if action == "agent_profile_duplicate":
        return duplicate_profile(service, data)
    if action == "agent_profile_category":
        return set_profile_category(service, data)
    if action == "agent_profile_archive":
        return archive_profile(service, data)
    if action == "team_get":
        return get_team(service, data["project_id"])
    if action == "team_save":
        return save_team(service, data)
    if action == "team_add_member":
        return add_member(service, data)
    if action == "team_update_member":
        return update_member(service, data)
    if action == "team_remove_member":
        return remove_member(service, data)
    if action == "team_revision_preview":
        return revision_preview(service, data)
    if action == "team_adopt_revision":
        return adopt_revision(service, data)
    if action == "team_template_list":
        return {"templates": list_templates(service)}
    if action == "team_save_template":
        return save_template(service, data)
    if action == "team_apply_template":
        return apply_template(service, data)
    if action == "team_template_delete":
        return delete_template(service, data)
    return UNHANDLED
