"""What the chief and the leads hold: an assessment of the agents they manage, and the cursors of the work.

**Scorecard.** For each assignment of the project: its cards (done, failed, in review), its executions, the average
of the evaluations of its work, and the latest assessment written by a superior. An assessment is a verdict with its
reasons — reliable, to watch, to reassign, to adapt, to replace — written by the chief, by a lead about the agents
under them, or by you. The agent assessed reads it at the start of its context; its superiors read the scorecard of
their team. What follows a verdict is explicit: reassign its open cards, replace it by another profile in the same
place, or propose an adaptation of its instructions (an improvement proposal you adopt).

**Cursors.** Autonomy, rigour, creativity, reasoning effort, detail of the report: five levels each, set for the project
by the chief (or by you), for a card by whoever frames it, and at the moment a task is launched. The most specific wins.
They become explicit lines of the task's instruction, and the reasoning effort of the model where the connector has one.

None of this proves anything about an agent: it is the judgement of its superiors, with the facts beside it.
"""
import json

from .model_capabilities import top as model_top
from .store import now, uid

UNHANDLED = object()

VERDICTS = {"reliable": "Fiable", "watch": "À surveiller", "reassign": "À réaffecter", "adapt": "À adapter", "replace": "À remplacer"}
CURSORS = {
    "autonomy": ("Autonomie", ["Demandez avant chaque décision qui engage la suite.",
                               "Demandez avant les décisions importantes ; les détails, décidez-les.",
                               "Décidez seul de ce qui est réversible ; demandez pour le reste.",
                               "Avancez seul ; ne demandez que pour ce qui est irréversible ou coûteux.",
                               "Avancez seul, sans attendre ; signalez clairement ce que vous avez décidé et pourquoi."]),
    "rigor": ("Rigueur", ["Allez au plus vite : vérifications minimales, et dites ce qui n’a pas été vérifié.",
                          "Vérifiez le principal, sans aller dans le détail.",
                          "Vérifiez l’essentiel avant de rendre.",
                          "Vérifiez soigneusement : relisez et testez ce que vous livrez.",
                          "Vérifiez tout : relisez, testez, contrôlez chaque livrable et chaque critère avant de rendre."]),
    "creativity": ("Créativité", ["Tenez-vous strictement à ce qui est demandé, sans initiative.",
                                  "Restez proche de la demande ; une amélioration seulement si elle est évidente.",
                                  "Proposez des améliorations mesurées, signalées comme telles.",
                                  "Cherchez de meilleures solutions et proposez-les, argumentées.",
                                  "Explorez des solutions nouvelles ; proposez des alternatives argumentées."]),
    "effort": ("Effort de raisonnement", ["Répondez vite, sans long raisonnement.",
                                          "Réfléchissez brièvement avant d’agir.",
                                          "Réfléchissez normalement avant d’agir.",
                                          "Réfléchissez en profondeur avant d’agir.",
                                          "Réfléchissez aussi loin que nécessaire : c’est une tâche difficile."]),
    "detail": ("Détail du compte rendu", ["Compte rendu très bref : l’essentiel en quelques lignes.",
                                          "Compte rendu court.",
                                          "Compte rendu normal.",
                                          "Compte rendu détaillé.",
                                          "Compte rendu très détaillé, avec les raisons de chaque choix."]),
}
EFFORT = {1: "low", 2: "low", 3: "medium", 4: "high", 5: "xhigh"}
EFFORT_CONNECTORS = {"codex": {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}, "claude-code": {"low", "medium", "high", "xhigh", "max"}}
ORIGINS = {"project": "projet", "task": "carte", "run": "lancement"}


def _text(value, limit, label, required=False):
    text = str(value if value is not None else "").strip()
    if required and not text:
        raise ValueError(label + " requis.")
    if len(text) > limit:
        raise ValueError(label + " limité à " + str(limit) + " caractères.")
    return text


def _context(service, data):
    from .tasks import _context as task_context
    return task_context(service, data)


def _authority(members, data, target_id, label):
    """Who may judge or frame the work of an assignment: you, the chief, or one of its superiors."""
    from .tasks import _member, _superiors
    if data.get("by_user"):
        return None, "Utilisateur"
    author = _member(members, data.get("author_id"), label)
    if author["role"] != "chief" and author["id"] not in _superiors(members, target_id):
        raise ValueError(author["definition"]["name"] + " n’encadre pas cet agent : ce rôle revient à son responsable, "
                         "au chef de projet, ou à vous.")
    return author["id"], author["definition"]["name"]


def clean_cursors(value):
    value = value if isinstance(value, dict) else {}
    result = {}
    for key, level in value.items():
        if key not in CURSORS:
            raise ValueError("Curseur inconnu : " + str(key)[:30] + ". Curseurs : " + ", ".join(CURSORS) + ".")
        if level in (None, "", 0):
            continue
        if not isinstance(level, int) or not 1 <= level <= 5:
            raise ValueError("« " + CURSORS[key][0] + " » se règle de 1 à 5.")
        result[key] = level
    return result


# --- cursors -------------------------------------------------------------------------------------------------

def set_project_cursors(service, data):
    project, team, members = _context(service, data)
    if not data.get("by_user"):
        from .tasks import _member
        author = _member(members, data.get("author_id"), "auteur")
        if author["role"] != "chief":
            raise ValueError("Les curseurs du projet se règlent par le chef de projet, ou par vous.")
    cursors = clean_cursors(data.get("cursors"))
    service.store.execute("UPDATE teams SET cursors=? WHERE id=?", (json.dumps(cursors), team["id"]))
    return {"cursors": cursors, "notice": "Curseurs du projet enregistrés : ils s’appliquent aux prochaines exécutions, "
                                         "sauf réglage plus précis sur une carte ou au lancement."}


def set_task_cursors(service, data):
    from .tasks import _task
    project, team, members = _context(service, data)
    task = _task(service, project["id"], data["id"])
    if not data.get("by_user"):
        from .tasks import _member
        _member(members, data.get("author_id"), "auteur")
        # The card's author frames it; otherwise a superior of the agent who holds it.
        if task["assignee_id"] and data.get("author_id") != task["author_id"]:
            _authority(members, data, task["assignee_id"], "auteur")
    cursors = clean_cursors(data.get("cursors"))
    service.store.execute("UPDATE tasks SET cursors=?, updated_at=? WHERE id=?", (json.dumps(cursors), now(), task["id"]))
    return {"id": task["id"], "cursors": cursors, "notice": "Curseurs de la carte enregistrés."}


def effective(service, project_id, task, runtime=None):
    """Project, then card, then launch: the most specific setting wins, and says where it comes from."""
    team = service.store.rows("SELECT cursors FROM teams WHERE project_id=?", (project_id,))
    layers = [("project", json.loads(team[0]["cursors"] or "{}") if team else {}),
              ("task", json.loads(task.get("cursors") or "{}") if isinstance(task.get("cursors"), str) else task.get("cursors") or {}),
              ("run", clean_cursors(runtime) if runtime else {})]
    result = {}
    for origin, values in layers:
        for key, level in values.items():
            if key in CURSORS and level:
                result[key] = {"level": int(level), "origin": origin}
    return result


def cursor_lines(cursors):
    if not cursors:
        return ""
    lines = ["Réglages de cette mission (fixés par votre encadrement ; niveau sur 5) :"]
    for key, value in cursors.items():
        label, texts = CURSORS[key]
        lines.append("- " + label + " " + str(value["level"]) + "/5 (" + ORIGINS[value["origin"]] + ") : " + texts[value["level"] - 1])
    return "\n".join(lines)


def effort_for(cursors, connector):
    level = cursors.get("effort", {}).get("level")
    value = EFFORT.get(level)
    return value if value and value in EFFORT_CONNECTORS.get(connector, set()) else ""


# --- assessments and scorecard --------------------------------------------------------------------------------

def assess(service, data):
    """A superior's verdict on an assignment, with its reasons. The agent reads it; the history stays."""
    from .tasks import _member
    project, team, members = _context(service, data)
    target = _member(members, data.get("member_id"), "agent évalué")
    if data.get("author_id") == target["id"]:
        raise ValueError("Un agent ne se juge pas lui-même : ce bilan revient à son responsable, au chef de projet ou à vous.")
    author_id, author = _authority(members, data, target["id"], "auteur")
    verdict = str(data.get("verdict") or "")
    if verdict not in VERDICTS:
        raise ValueError("Verdict : " + ", ".join(k + " (" + v + ")" for k, v in VERDICTS.items()) + ".")
    fields = {k: _text(data.get(k, ""), 2000, label) for k, label in
              (("strengths", "Points forts"), ("weaknesses", "Points faibles"), ("recommendation", "Recommandation"))}
    if not (fields["strengths"] or fields["weaknesses"] or fields["recommendation"]):
        raise ValueError("Un bilan donne ses raisons : points forts, points faibles ou recommandation.")
    sources = [str(s) for s in (data.get("source_ids") or []) if str(s).strip()][:20]
    id = uid()
    service.store.execute("INSERT INTO member_assessments(id,project_id,member_id,author_id,verdict,strengths,weaknesses,recommendation,source_ids,created_at) "
                          "VALUES(?,?,?,?,?,?,?,?,?,?)", (id, project["id"], target["id"], author_id, verdict, fields["strengths"],
                                                         fields["weaknesses"], fields["recommendation"], json.dumps(sources), now()))
    follow = {"reassign": " Réaffectez ses cartes ouvertes depuis le bilan de l’équipe.", "replace": " Remplacez-le depuis le bilan de l’équipe.",
              "adapt": " Proposez une adaptation de ses consignes : elle ne change rien sans votre adoption."}.get(verdict, "")
    return {"id": id, "notice": "Bilan de " + target["definition"]["name"] + " par " + author + " : " + VERDICTS[verdict] + "." + follow}


def _assessments(service, member_id, limit=5):
    rows = service.store.rows("SELECT * FROM member_assessments WHERE member_id=? ORDER BY created_at DESC LIMIT ?", (member_id, limit))
    return [{**r, "verdict_label": VERDICTS.get(r["verdict"], r["verdict"]), "source_ids": json.loads(r["source_ids"] or "[]")} for r in rows]


def scorecard(service, data):
    """Facts and judgements, per assignment of the project. No ranking is computed: you read and decide."""
    from .learning import SCORES
    from .tasks import _name
    project, team, members = _context(service, data)
    rows = []
    for member in members:
        tasks = service.store.rows("SELECT status FROM tasks WHERE assignee_id=?", (member["id"],))
        runs = service.store.rows("SELECT status FROM task_executions WHERE member_id=?", (member["id"],))
        scores = {}
        for evaluation in service.store.rows("SELECT scores FROM task_evaluations WHERE member_id=?", (member["id"],)):
            for key, value in json.loads(evaluation["scores"]).items():
                scores.setdefault(key, []).append(value)
        averages = {SCORES[k]: round(sum(v) / len(v), 1) for k, v in scores.items() if k in SCORES}
        values = [x for v in scores.values() for x in v]
        latest = _assessments(service, member["id"], 3)
        for entry in latest:
            entry["author"] = _name(members, entry["author_id"]) if entry["author_id"] else "Utilisateur"
        rows.append({"member_id": member["id"], "name": member["definition"]["name"], "role": member["role"], "active": bool(member["active"]),
                     "manager_id": member.get("manager_id"), "connector": member["definition"].get("connector", ""),
                     "model": member["definition"].get("model", ""),
                     "tasks": {"total": len(tasks), "done": sum(t["status"] == "done" for t in tasks),
                               "in_review": sum(t["status"] == "in_review" for t in tasks),
                               "to_correct": sum(t["status"] == "to_correct" for t in tasks),
                               "failed": sum(t["status"] in {"failed", "cancelled"} for t in tasks),
                               "open": sum(t["status"] not in {"done", "failed", "cancelled"} for t in tasks)},
                     "executions": {"total": len(runs), "failed": sum(r["status"] == "failed" for r in runs)},
                     "evaluations": {"count": len(values), "average": round(sum(values) / len(values), 1) if values else None, "by_criterion": averages},
                     "capabilities": [{"label": a["label"], "value": a["value"], "confidence": a["confidence"]} for a in
                                      model_top(service, member["definition"].get("connector", ""), member["definition"].get("model", ""))],
                     "assessments": latest, "verdict": latest[0]["verdict"] if latest else "",
                     "verdict_label": latest[0]["verdict_label"] if latest else ""})
    cursors = json.loads(service.store.one("SELECT cursors FROM teams WHERE id=?", (team["id"],))["cursors"] or "{}")
    return {"members": rows, "verdicts": VERDICTS, "cursors": cursors,
            "cursor_labels": {k: {"label": v[0], "levels": v[1]} for k, v in CURSORS.items()},
            "notice": "Des faits et des jugements, pas un classement : une moyenne sur peu d’évaluations ne démontre rien."}


def member_context(store, member_id):
    """What an agent reads about itself — its latest assessment — and, for a chief or a lead, about its team."""
    rows = store.rows("SELECT * FROM team_members WHERE id=?", (member_id,))
    if not rows:
        return ""
    member = rows[0]
    parts = []
    mine = store.rows("SELECT * FROM member_assessments WHERE member_id=? ORDER BY created_at DESC LIMIT 1", (member_id,))
    if mine:
        a = mine[0]
        parts.append("Dernier bilan de votre travail dans ce projet (" + VERDICTS.get(a["verdict"], a["verdict"]) + ", " + a["created_at"][:10] + ") :" +
                     ("\n  Points forts : " + a["strengths"] if a["strengths"] else "") +
                     ("\n  Points faibles : " + a["weaknesses"] if a["weaknesses"] else "") +
                     ("\n  Recommandation : " + a["recommendation"] if a["recommendation"] else ""))
    if member["role"] in {"chief", "lead"}:
        team = store.rows("SELECT * FROM team_members WHERE team_id=? AND active=1", (member["team_id"],))
        index = {m["id"]: m for m in team}

        def under(candidate):
            seen, current = set(), index.get(candidate)
            while current and current["manager_id"] and current["manager_id"] not in seen:
                if current["manager_id"] == member_id:
                    return True
                seen.add(current["manager_id"])
                current = index.get(current["manager_id"])
            return False

        lines = []
        for other in team:
            if other["id"] == member_id or not (member["role"] == "chief" or under(other["id"])):
                continue
            name = json.loads(other["definition"]).get("name", "?")
            tasks = store.rows("SELECT status FROM tasks WHERE assignee_id=?", (other["id"],))
            scores = [v for e in store.rows("SELECT scores FROM task_evaluations WHERE member_id=?", (other["id"],)) for v in json.loads(e["scores"]).values()]
            verdict = store.rows("SELECT verdict FROM member_assessments WHERE member_id=? ORDER BY created_at DESC LIMIT 1", (other["id"],))
            lines.append("- " + name + " [" + other["id"] + "] : " + str(sum(t["status"] == "done" for t in tasks)) + " carte(s) acceptée(s), " +
                         str(sum(t["status"] in {"failed", "cancelled"} for t in tasks)) + " échouée(s)" +
                         (", moyenne des évaluations " + str(round(sum(scores) / len(scores), 1)) + "/5 sur " + str(len(scores)) + " note(s)" if scores else ", pas encore évalué") +
                         (", bilan : " + VERDICTS.get(verdict[0]["verdict"], "") if verdict else ""))
        if lines:
            parts.append("Les agents que vous encadrez (faits enregistrés, pas un classement) :\n" + "\n".join(lines) +
                         "\nVous pouvez rédiger leur bilan (member_assess), réaffecter leurs cartes (task_reassign), proposer de les remplacer "
                         "(team_replace_member) ou d’adapter leurs consignes (improvement_propose), et régler les curseurs d’une carte "
                         "(task_cursors_set)" + (" ou du projet (team_cursors_set)" if member["role"] == "chief" else "") + ".")
        cursors = store.rows("SELECT cursors FROM teams WHERE id=?", (member["team_id"],))
        current = json.loads(cursors[0]["cursors"] or "{}") if cursors else {}
        if current:
            parts.append("Curseurs du projet : " + ", ".join(CURSORS[k][0] + " " + str(v) + "/5" for k, v in current.items() if k in CURSORS) + ".")
    return "\n".join(parts)


# --- what follows a verdict --------------------------------------------------------------------------------------

def reassign(service, data):
    """Move the open cards of an assignment to another, with the reason written on each card."""
    from .tasks import _member, _task, _history
    project, team, members = _context(service, data)
    source = _member(members, data.get("member_id"), "agent")
    target = _member(members, data.get("to_member_id"), "nouveau responsable")
    if not target["active"]:
        raise ValueError(target["definition"]["name"] + " est retiré de l’équipe.")
    if source["id"] == target["id"]:
        raise ValueError("Choisissez un autre agent.")
    author_id, author = _authority(members, data, source["id"], "auteur")
    reason = _text(data.get("reason", ""), 1000, "Motif")
    wanted = set(data.get("task_ids") or [])
    moved = []
    for row in service.store.rows("SELECT id FROM tasks WHERE assignee_id=? AND status NOT IN ('done','failed','cancelled','in_progress')", (source["id"],)):
        if wanted and row["id"] not in wanted:
            continue
        task = _task(service, project["id"], row["id"])
        detail = "Réaffectée de " + source["definition"]["name"] + " à " + target["definition"]["name"] + (" : " + reason if reason else ".")
        service.store.execute("UPDATE tasks SET assignee_id=?, history=?, updated_at=? WHERE id=?",
                              (target["id"], _history(task, task["status"], author_id, author, detail), now(), task["id"]))
        moved.append(task["objective"][:60])
    return {"moved": moved, "notice": (str(len(moved)) + " carte(s) réaffectée(s) à " + target["definition"]["name"] + "." if moved else
                                       "Aucune carte ouverte à réaffecter (une carte en cours d’exécution reste à son agent).")}


def replace(service, data):
    """Another profile in the same place: same role, same manager, same reports, the open cards. The old one is withdrawn."""
    from .tasks import _member
    from .teams import add_member, remove_member
    project, team, members = _context(service, data)
    old = _member(members, data.get("member_id"), "agent remplacé")
    _authority(members, data, old["id"], "auteur")
    if service.store.rows("SELECT id FROM task_executions WHERE member_id=? AND status='running'", (old["id"],)):
        raise ValueError(old["definition"]["name"] + " travaille en ce moment : attendez la fin de son exécution ou annulez-la.")
    added = add_member(service, {"project_id": project["id"], "profile_id": data["profile_id"], "role": old["role"],
                                 "manager_id": old.get("manager_id"), "responsibility": old.get("responsibility", "")})
    new_id = added["id"]
    with service.store.transaction() as db:
        db.execute("UPDATE team_members SET manager_id=?, updated_at=? WHERE manager_id=? AND id<>?", (new_id, now(), old["id"], new_id))
        db.execute("UPDATE tasks SET assignee_id=?, updated_at=? WHERE assignee_id=? AND status NOT IN ('done','failed','cancelled')", (new_id, now(), old["id"]))
    remove_member(service, {"project_id": project["id"], "id": old["id"], "acknowledged": True})
    reason = _text(data.get("reason", ""), 1000, "Motif")
    newcomer = service.store.one("SELECT definition FROM team_members WHERE id=?", (new_id,))
    return {"id": new_id, "notice": old["definition"]["name"] + " remplacé par " + json.loads(newcomer["definition"])["name"] +
                                   " : même rôle, même responsable, mêmes agents encadrés et cartes ouvertes." + (" Motif : " + reason if reason else "") +
                                   " L’ancienne affectation reste consultable et réactivable."}


def team_lead_action(service, action, data):
    handlers = {"team_scorecard": scorecard, "member_assess": assess, "team_cursors_set": set_project_cursors,
                "task_cursors_set": set_task_cursors, "task_reassign": reassign, "team_replace_member": replace}
    handler = handlers.get(action)
    return handler(service, data) if handler else UNHANDLED
