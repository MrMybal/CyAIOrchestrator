"""Scoped memory, evaluations and improvement proposals.

Three memory scopes that must never be merged:

1. project  — already carried by the `memory` table and `project_memory.project_foundation()`.
2. member   — what an assignment learned inside one project. Never transferred anywhere on its own.
3. profile  — general methods explicitly declared transferable, with their sources and the revision
              they were observed on.

A member memory becomes a profile memory only through a proposal the user adopts. Adopting a prompt
improvement creates a **new profile revision**; the teams then adopt that revision explicitly, exactly as
for any other edit. Nothing changes under an existing team by itself, and every adoption is reversible by
adopting the previous revision.

None of this trains a model. It changes the context and the instructions an agent receives, nothing else.
An evaluation records an opinion with its evidence; it never feeds an automatic model ranking.
"""
import json

from .store import now, uid
from .tasks import _context, _project, _task, _name

UNHANDLED = object()

SCOPES = {"member": "Agent dans ce projet", "profile": "Profil global"}
SCORES = {"quality": "Qualité du travail", "scope": "Respect du périmètre", "integration": "Intégration",
          "tests": "Tests réellement fournis", "corrections": "Corrections nécessaires"}
KINDS = {"prompt": "Consignes initiales", "memory": "Mémoire transférable"}
DECISIONS = {"proposed": "À décider", "adopted": "Adoptée", "rejected": "Écartée"}
LEARNING_NOTICE = ("Ces éléments modifient le contexte et les consignes transmis aux agents. "
                   "Ils n’entraînent aucun modèle et ne modifient aucune équipe sans adoption explicite.")


def _text(value, limit, label, required=False):
    text = str(value if value is not None else "").strip()
    if required and not text:
        raise ValueError(label + " requis.")
    if len(text) > limit:
        raise ValueError(label + " limité à " + str(limit) + " caractères.")
    return text


def _sources(service, value, project_id=None):
    """A note without evidence proves nothing: sources point at cards, reports or evaluations."""
    if isinstance(value, str):
        value = [value] if value.strip() else []
    if not isinstance(value, list):
        raise ValueError("Les sources doivent être une liste d’identifiants de tâches, de rapports ou d’évaluations.")
    sources = []
    for item in value:
        id = _text(item, 64, "Source")
        if not id or id in sources:
            continue
        found = any(service.store.rows("SELECT id FROM " + table + " WHERE id=?", (id,))
                    for table in ("tasks", "task_reports", "task_evaluations", "messages"))
        if not found:
            raise ValueError("Source introuvable : « " + id[:40] + " ». Référencez une carte, un rapport, une évaluation ou un message.")
        sources.append(id)
    return sources


def _member(service, project_id, id):
    member = service.store.one("SELECT * FROM team_members WHERE id=?", (id,))
    if member["project_id"] != project_id:
        raise ValueError("Cette affectation appartient à un autre projet.")
    return dict(member)


# --- memory ---------------------------------------------------------------------------------

def save_memory(service, data):
    scope = str(data.get("scope", ""))
    if scope not in SCOPES:
        raise ValueError("Portée inconnue. Valeurs acceptées : " + ", ".join(sorted(SCOPES)) + ".")
    content = service.engine.secrets.redact(_text(data.get("content"), 20000, "Contenu de la mémoire", required=True))
    category = _text(data.get("category", ""), 80, "Catégorie")
    id = data.get("id") or uid()
    existing = service.store.rows("SELECT * FROM agent_memory WHERE id=?", (id,))
    if existing and existing[0]["scope"] != scope:
        raise ValueError("Une mémoire ne change pas de portée. Créez une proposition pour la rendre transférable.")
    timestamp = now()
    if scope == "member":
        project, team, members = _context(service, data)
        member = _member(service, project["id"], data["member_id"])
        if existing and existing[0]["member_id"] != member["id"]:
            raise ValueError("Cette mémoire appartient à une autre affectation.")
        sources = _sources(service, data.get("source_ids", []))
        service.store.execute(
            "INSERT INTO agent_memory(id,scope,project_id,member_id,profile_id,content,category,source_ids,transferable,origin,created_at,updated_at)"
            " VALUES(?,?,?,?,NULL,?,?,?,0,?,?,?) ON CONFLICT(id) DO UPDATE SET content=excluded.content,category=excluded.category,"
            "source_ids=excluded.source_ids,updated_at=excluded.updated_at",
            (id, scope, project["id"], member["id"], content, category, json.dumps(sources),
             _text(data.get("origin", "Observation locale"), 200, "Origine"), timestamp, timestamp))
        return {"id": id, "scope": scope, "notice": "Mémoire locale enregistrée pour cette affectation. Elle ne quittera ce projet "
                                                    "que par une proposition que vous adopterez."}
    profile = service.store.one("SELECT * FROM agent_profiles WHERE id=?", (data["profile_id"],))
    if not data.get("transferable"):
        raise ValueError("Une mémoire de profil global doit être explicitement déclarée transférable (transferable), "
                         "avec ses sources : sans cela, gardez-la dans la portée de l’agent dans son projet.")
    sources = _sources(service, data.get("source_ids", []))
    if not sources:
        raise ValueError("Une mémoire transférable doit citer au moins une source vérifiable.")
    service.store.execute(
        "INSERT INTO agent_memory(id,scope,project_id,member_id,profile_id,content,category,source_ids,transferable,origin,created_at,updated_at)"
        " VALUES(?,?,NULL,NULL,?,?,?,?,1,?,?,?) ON CONFLICT(id) DO UPDATE SET content=excluded.content,category=excluded.category,"
        "source_ids=excluded.source_ids,updated_at=excluded.updated_at",
        (id, scope, profile["id"], content, category, json.dumps(sources),
         _text(data.get("origin", "Adoptée par l’utilisateur"), 200, "Origine") + " · révision " + str(profile["revision"]),
         timestamp, timestamp))
    return {"id": id, "scope": scope, "notice": "Mémoire transférable enregistrée sur le profil global, avec ses sources. "
                                                "Les projets qui utilisent ce profil la verront ; leurs équipes ne changent pas pour autant."}


def delete_memory(service, data):
    row = service.store.one("SELECT * FROM agent_memory WHERE id=?", (data["id"],))
    if row["scope"] == "member":
        _project(service, row["project_id"])
    service.store.execute("DELETE FROM agent_memory WHERE id=?", (row["id"],))
    return {"id": row["id"], "notice": "Mémoire supprimée. Les sources qu’elle citait ne sont pas touchées."}


def member_memory(store, member_id):
    return [dict(r) | {"source_ids": json.loads(r["source_ids"])}
            for r in store.rows("SELECT * FROM agent_memory WHERE scope='member' AND member_id=? ORDER BY created_at", (member_id,))]


def profile_memory(store, profile_id):
    return [dict(r) | {"source_ids": json.loads(r["source_ids"])}
            for r in store.rows("SELECT * FROM agent_memory WHERE scope='profile' AND profile_id=? AND transferable=1 ORDER BY created_at", (profile_id,))]


def list_memory(service, data):
    scope = str(data.get("scope", "member"))
    if scope == "profile":
        profile = service.store.one("SELECT * FROM agent_profiles WHERE id=?", (data["profile_id"],))
        return {"scope": scope, "profile": profile["name"], "entries": profile_memory(service.store, profile["id"]),
                "notice": LEARNING_NOTICE}
    project, team, members = _context(service, data)
    entries = []
    for member in members:
        for entry in member_memory(service.store, member["id"]):
            entries.append({**entry, "member": member["definition"]["name"], "role": member["role"]})
    return {"scope": "member", "project_id": project["id"], "entries": entries, "notice": LEARNING_NOTICE}


# --- evaluations ----------------------------------------------------------------------------

def save_evaluation(service, data):
    project, team, members = _context(service, data)
    task = _task(service, project["id"], data["id"])
    reports = service.store.rows("SELECT * FROM task_reports WHERE task_id=? ORDER BY created_at", (task["id"],))
    if not reports:
        raise ValueError("Rien à évaluer : cette carte n’a aucun rapport. Une note sans travail rendu ne démontre rien.")
    comment = _text(data.get("comment"), 4000, "Commentaire explicatif", required=True)
    scores = data.get("scores") or {}
    if not isinstance(scores, dict) or not scores:
        raise ValueError("Fournissez au moins une note parmi : " + ", ".join(sorted(SCORES)) + ".")
    clean = {}
    for key, value in scores.items():
        if key not in SCORES:
            raise ValueError("Critère inconnu : " + str(key)[:40] + ". Critères acceptés : " + ", ".join(sorted(SCORES)) + ".")
        if not isinstance(value, int) or not 1 <= value <= 5:
            raise ValueError("La note de « " + SCORES[key] + " » doit être un entier de 1 à 5.")
        clean[key] = value
    author_id = None if data.get("by_user") else _member(service, project["id"], data["author_id"])["id"]
    if author_id and author_id == task["assignee_id"]:
        raise ValueError("Un agent n’évalue pas son propre travail. Cette note revient à son responsable, ou à vous.")
    if author_id and task["assignee_id"]:
        # The chief and the superiors of the agent judge its work; a peer does not.
        from .tasks import _superiors
        author = next(m for m in members if m["id"] == author_id)
        if author["role"] != "chief" and author_id not in _superiors(members, task["assignee_id"]):
            raise ValueError(author["definition"]["name"] + " n’encadre pas cet agent : cette note revient à son responsable, au chef de projet, ou à vous.")
    member = _member(service, project["id"], task["assignee_id"]) if task["assignee_id"] else None
    definition = json.loads(member["definition"]) if member else {}
    execution = service.store.rows("SELECT * FROM task_executions WHERE task_id=? AND status='succeeded' ORDER BY created_at DESC LIMIT 1", (task["id"],))
    duration = 0
    if execution and execution[0]["settled_at"]:
        from datetime import datetime
        try:
            duration = int((datetime.fromisoformat(execution[0]["settled_at"]) - datetime.fromisoformat(execution[0]["created_at"])).total_seconds())
        except ValueError:
            duration = 0
    usage = ""
    if execution:
        rows = service.store.rows("SELECT usage FROM steps WHERE mission_id=? AND usage IS NOT NULL", (execution[0]["mission_id"],))
        usage = rows[0]["usage"] if rows and rows[0]["usage"] else ""
    id = uid()
    service.store.execute(
        "INSERT INTO task_evaluations(id,task_id,project_id,member_id,author_id,scores,duration_seconds,usage,comment,profile_revision,connector,model,created_at)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (id, task["id"], project["id"], task["assignee_id"], author_id, json.dumps(clean), duration, usage, comment,
         member["profile_revision"] if member else 0, definition.get("connector", ""), definition.get("model", ""), now()))
    return {"id": id, "duration_seconds": duration, "usage_recorded": bool(usage),
            "notice": "Évaluation enregistrée avec l’auteur, la date, la carte, la révision du préprompt et le modèle effectivement "
                      "utilisé. Elle n’alimente aucun classement automatique de modèles : une note ne démontre pas une supériorité."}


def evaluations(service, members, task_id):
    rows = []
    for row in service.store.rows("SELECT * FROM task_evaluations WHERE task_id=? ORDER BY created_at DESC", (task_id,)):
        entry = dict(row)
        entry["scores"] = json.loads(entry["scores"])
        entry["labels"] = {SCORES[k]: v for k, v in entry["scores"].items() if k in SCORES}
        entry["author"] = _name(members, entry["author_id"]) if entry["author_id"] else "Utilisateur"
        entry["member"] = _name(members, entry["member_id"]) if entry["member_id"] else ""
        entry["usage"] = json.loads(entry["usage"]) if entry["usage"] else None
        rows.append(entry)
    return rows


# --- improvement proposals ------------------------------------------------------------------

def create_proposal(service, data):
    project, team, members = _context(service, data)
    member = _member(service, project["id"], data["member_id"])
    if member["role"] not in {"chief", "lead"}:
        raise ValueError("Seul un chef de projet ou un lead propose une amélioration : c’est une observation de responsable, "
                         "pas une auto-évaluation.")
    profile = service.store.one("SELECT * FROM agent_profiles WHERE id=?", (data["profile_id"],))
    kind = str(data.get("kind", ""))
    if kind not in KINDS:
        raise ValueError("Type de proposition inconnu : " + ", ".join(sorted(KINDS)) + ".")
    proposed = service.engine.secrets.redact(_text(data.get("proposed_value"), 20000, "Valeur proposée", required=True))
    rationale = _text(data.get("rationale"), 4000, "Motif de la proposition", required=True)
    sources = _sources(service, data.get("source_ids", []))
    if not sources:
        raise ValueError("Une proposition doit citer ses sources : une seule impression ne justifie pas de réécrire un profil global.")
    current = profile["prompt"] if kind == "prompt" else ""
    if kind == "prompt" and proposed.strip() == current.strip():
        raise ValueError("La valeur proposée est identique aux consignes actuelles.")
    id = uid()
    service.store.execute(
        "INSERT INTO improvement_proposals(id,project_id,member_id,profile_id,kind,current_value,proposed_value,rationale,source_ids,status,created_at)"
        " VALUES(?,?,?,?,?,?,?,?,?,'proposed',?)",
        (id, project["id"], member["id"], profile["id"], kind, current, proposed, rationale, json.dumps(sources), now()))
    warning = " Une seule source : vérifiez qu’il ne s’agit pas d’un incident isolé avant d’adopter." if len(sources) == 1 else ""
    return {"id": id, "sources": len(sources),
            "notice": "Proposition enregistrée et visible. Rien ne change tant que vous ne l’adoptez pas." + warning}


def decide_proposal(service, data):
    proposal = service.store.one("SELECT * FROM improvement_proposals WHERE id=?", (data["id"],))
    if proposal["project_id"]:
        _project(service, proposal["project_id"])
    if proposal["status"] != "proposed":
        raise ValueError("Cette proposition est déjà " + DECISIONS[proposal["status"]].lower() + ".")
    decision = _text(data.get("decision", ""), 2000, "Motif de la décision")
    if not data.get("adopt"):
        service.store.execute("UPDATE improvement_proposals SET status='rejected',decision=?,decided_at=? WHERE id=?",
                              (decision or "Écartée sans motif enregistré.", now(), proposal["id"]))
        return {"id": proposal["id"], "status": "rejected",
                "notice": "Proposition écartée. Elle reste consultable avec son motif ; rien n’a été modifié."}
    from .teams import save_profile, current_definition, _loaded
    profile = _loaded(service.store.one("SELECT * FROM agent_profiles WHERE id=?", (proposal["profile_id"],)))
    if proposal["kind"] == "prompt":
        definition = current_definition(profile)
        result = save_profile(service, {**definition, "id": profile["id"], "prompt": proposal["proposed_value"],
                                        "note": "Proposition adoptée : " + proposal["rationale"][:300]})
        revision = result["revision"]
        notice = ("Révision " + str(revision) + " créée sur le profil global. Aucune équipe ne change : chaque projet doit "
                  "adopter cette révision explicitement. Pour revenir en arrière, adoptez la révision précédente.")
    else:
        save_memory(service, {"scope": "profile", "profile_id": profile["id"], "content": proposal["proposed_value"],
                              "category": "Méthode transférable", "transferable": True,
                              "source_ids": json.loads(proposal["source_ids"]), "origin": "Proposition adoptée"})
        revision = profile["revision"]
        notice = "Mémoire transférable ajoutée au profil global, avec les sources de la proposition."
    service.store.execute("UPDATE improvement_proposals SET status='adopted',decision=?,revision=?,decided_at=? WHERE id=?",
                          (decision or "Adoptée.", revision, now(), proposal["id"]))
    return {"id": proposal["id"], "status": "adopted", "revision": revision, "notice": notice}


def list_proposals(service, data):
    rows = []
    where, params = "", ()
    if data.get("profile_id"):
        where, params = " WHERE profile_id=?", (data["profile_id"],)
    elif data.get("project_id"):
        _project(service, data["project_id"])
        where, params = " WHERE project_id=?", (data["project_id"],)
    for row in service.store.rows("SELECT * FROM improvement_proposals" + where + " ORDER BY created_at DESC", params):
        entry = dict(row)
        entry["source_ids"] = json.loads(entry["source_ids"])
        entry["status_label"] = DECISIONS.get(entry["status"], entry["status"])
        entry["kind_label"] = KINDS.get(entry["kind"], entry["kind"])
        profiles = service.store.rows("SELECT name,revision FROM agent_profiles WHERE id=?", (entry["profile_id"],))
        entry["profile"] = profiles[0]["name"] if profiles else "Profil supprimé"
        entry["profile_revision"] = profiles[0]["revision"] if profiles else 0
        rows.append(entry)
    return {"proposals": rows, "notice": LEARNING_NOTICE}


# --- verified skills ------------------------------------------------------------------------

def track_record(service, profile_id):
    """Facts recorded about the work of a profile, across its assignments. Counts and averages only:
    no task content and no project name leave their project through this global view."""
    members = [r["id"] for r in service.store.rows("SELECT id FROM team_members WHERE profile_id=?", (profile_id,))]
    if not members:
        return {"assignments": 0, "tasks": 0, "accepted": 0, "closed_without_acceptance": 0, "executions": 0,
                "failed_executions": 0, "evaluations": 0, "averages": {}}
    marks = ",".join("?" for _ in members)
    tasks = service.store.rows("SELECT status FROM tasks WHERE assignee_id IN (" + marks + ")", tuple(members))
    runs = service.store.rows("SELECT status FROM task_executions WHERE member_id IN (" + marks + ")", tuple(members))
    rows = service.store.rows("SELECT scores FROM task_evaluations WHERE member_id IN (" + marks + ")", tuple(members))
    totals = {}
    for row in rows:
        for key, value in json.loads(row["scores"]).items():
            totals.setdefault(key, []).append(value)
    return {"assignments": len(members), "tasks": len(tasks),
            "accepted": len([t for t in tasks if t["status"] == "done"]),
            "closed_without_acceptance": len([t for t in tasks if t["status"] in {"failed", "cancelled"}]),
            "executions": len(runs), "failed_executions": len([r for r in runs if r["status"] == "failed"]),
            "evaluations": len(rows),
            "averages": {SCORES[k]: {"average": round(sum(v) / len(v), 2), "count": len(v)} for k, v in totals.items() if k in SCORES}}


def attest_skill(service, data):
    """The user attests a declared skill, pointing at the accepted work that shows it."""
    profile = service.store.one("SELECT * FROM agent_profiles WHERE id=?", (data["profile_id"],))
    skill = _text(data.get("skill"), 80, "Compétence", required=True)
    declared = json.loads(profile["skills"])
    if skill not in declared:
        raise ValueError("« " + skill + " » n’est pas une compétence déclarée de ce profil. Déclarez-la d’abord, puis attestez-la.")
    sources = _sources(service, data.get("source_ids", []))
    members = {r["id"] for r in service.store.rows("SELECT id FROM team_members WHERE profile_id=?", (profile["id"],))}
    evidence = []
    for id in sources:
        task = service.store.rows("SELECT assignee_id,status FROM tasks WHERE id=?", (id,))
        if task and task[0]["assignee_id"] in members and task[0]["status"] == "done":
            evidence.append(id)
            continue
        evaluation = service.store.rows("SELECT member_id FROM task_evaluations WHERE id=?", (id,))
        if evaluation and evaluation[0]["member_id"] in members:
            evidence.append(id)
    if not evidence:
        raise ValueError("Aucune preuve recevable : citez au moins une tâche **acceptée** confiée à ce profil, ou une évaluation "
                         "de son travail. Une compétence ne s’atteste pas sur une déclaration ni sur un travail d’un autre agent.")
    note = _text(data.get("note", ""), 2000, "Commentaire")
    service.store.execute(
        "INSERT INTO skill_attestations(id,profile_id,skill,source_ids,note,created_at) VALUES(?,?,?,?,?,?)"
        " ON CONFLICT(profile_id,skill) DO UPDATE SET source_ids=excluded.source_ids,note=excluded.note,created_at=excluded.created_at",
        (uid(), profile["id"], skill, json.dumps(evidence), note, now()))
    ignored = len(sources) - len(evidence)
    return {"skill": skill, "evidence": len(evidence),
            "notice": "Compétence « " + skill + " » attestée par vous, sur " + str(len(evidence)) + " preuve(s)." +
                      (" " + str(ignored) + " source(s) écartée(s) : ni tâche acceptée de ce profil, ni évaluation de son travail." if ignored else "") +
                      " Une attestation dit ce qui a été constaté, pas ce que l’agent réussira la prochaine fois."}


def withdraw_skill(service, data):
    row = service.store.one("SELECT * FROM skill_attestations WHERE profile_id=? AND skill=?", (data["profile_id"], data["skill"]))
    service.store.execute("DELETE FROM skill_attestations WHERE id=?", (row["id"],))
    return {"skill": row["skill"], "notice": "Attestation retirée. La compétence redevient simplement déclarée."}


def attestations(service, profile_id):
    return [{**dict(r), "source_ids": json.loads(r["source_ids"])}
            for r in service.store.rows("SELECT * FROM skill_attestations WHERE profile_id=? ORDER BY skill", (profile_id,))]


def learning_action(service, action, data):
    if action == "profile_track_record":
        service.store.one("SELECT id FROM agent_profiles WHERE id=?", (data["profile_id"],))
        return {"profile_id": data["profile_id"], "record": track_record(service, data["profile_id"]),
                "attestations": attestations(service, data["profile_id"]),
                "notice": "Faits enregistrés sur le travail de ce profil. Ce ne sont ni des benchmarks ni une garantie."}
    if action == "skill_attest":
        return attest_skill(service, data)
    if action == "skill_withdraw":
        return withdraw_skill(service, data)
    if action == "agent_memory_save":
        return save_memory(service, data)
    if action == "agent_memory_delete":
        return delete_memory(service, data)
    if action == "agent_memory_list":
        return list_memory(service, data)
    if action == "task_evaluate":
        return save_evaluation(service, data)
    if action == "improvement_propose":
        return create_proposal(service, data)
    if action == "improvement_decide":
        return decide_proposal(service, data)
    if action == "improvement_list":
        return list_proposals(service, data)
    return UNHANDLED
