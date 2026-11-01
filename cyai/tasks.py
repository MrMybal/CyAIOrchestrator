"""Task cards and reports for a project team.

Persistence and validation only: nothing here runs an agent. A task is a card the user and the team
read and move by hand until the board of the next step drives it.

The rule this module exists to enforce: rendering a report and having a task accepted are two separate
acts. A report is evidence submitted for review; acceptance is recorded by a hierarchical superior of
the assignee, or by the user. A "success" sentence in a report proves nothing on its own.
"""
import json

from .store import now, uid
from .teams import ROLE_LABELS

UNHANDLED = object()

STATUSES = {"to_prepare": "À préparer", "ready": "Prête", "in_progress": "En cours",
            "awaiting_information": "En attente d’informations", "in_review": "En revue",
            "to_correct": "À corriger", "done": "Terminée", "failed": "Échouée", "cancelled": "Annulée"}
FINAL = {"done", "failed", "cancelled"}
# Allowed moves. A task leaves `in_review` only through an explicit acceptance or correction request.
TRANSITIONS = {"to_prepare": {"ready", "cancelled"},
               "ready": {"to_prepare", "in_progress", "cancelled"},
               "in_progress": {"awaiting_information", "in_review", "failed", "cancelled"},
               "awaiting_information": {"in_progress", "cancelled"},
               "in_review": {"done", "to_correct", "failed", "cancelled"},
               "to_correct": {"in_progress", "cancelled"},
               "done": set(), "failed": set(), "cancelled": set()}
REVIEW_ONLY = {"done", "to_correct"}
REPORT_FIELDS = {"result": (10000, "Résultat"), "modified_files": (4000, "Fichiers modifiés"),
                 "executed_tests": (4000, "Tests réellement exécutés"), "limits": (2000, "Limites"),
                 "risks": (2000, "Risques"), "requested_decisions": (2000, "Décisions demandées")}
CONSULTATION_STATUSES = {"requested": "Avis demandé", "answered": "Avis rendu", "declined": "Avis décliné"}
ANSWER_SOURCES = {"user": "Saisi par l’utilisateur", "agent": "Rendu par l’agent"}
BOARD_NOTICE = ("Cartes de tâches enregistrées et vérifiées. L’exécution par les agents arrive avec le board : "
                "aucun agent n’est lancé par ces opérations.")


def _text(value, limit, label, required=False):
    text = str(value if value is not None else "").strip()
    if required and not text:
        raise ValueError(label + " requis.")
    if len(text) > limit:
        raise ValueError(label + " limité à " + str(limit) + " caractères.")
    return text


def _project(service, project_id):
    """Same perimeter check as every other project service: an MCP client cannot read past its scope."""
    project = service.store.one("SELECT * FROM projects WHERE id=?", (project_id,))
    service.engine.policy.project(project["root"])
    return project


def _team(service, project_id):
    rows = service.store.rows("SELECT * FROM teams WHERE project_id=?", (project_id,))
    if not rows:
        raise ValueError("Aucune équipe pour ce projet. Composez l’équipe dans l’onglet Équipe avant de créer des tâches.")
    return rows[0]


def _members(service, team_id):
    from .teams import load_member
    return [load_member(row) for row in service.store.rows("SELECT * FROM team_members WHERE team_id=?", (team_id,))]


def _member(members, id, label):
    member = next((m for m in members if m["id"] == id), None)
    if member is None:
        raise ValueError("Le " + label + " indiqué n’appartient pas à l’équipe de ce projet. Choisissez une affectation de cette équipe.")
    return member


def _name(members, id):
    member = next((m for m in members if m["id"] == id), None)
    return member["definition"]["name"] if member else "Affectation retirée"


def _actor(members, data, label):
    """Who is acting. The user drives the board directly; agents act under their own assignment."""
    if data.get("by_user"):
        return None, "Utilisateur"
    member = _member(members, data.get("author_id"), label)
    return member["id"], member["definition"]["name"]


def _author_name(members, task):
    """A null author is the user when the card says so, a deleted assignment otherwise."""
    if task["author_id"]:
        return _name(members, task["author_id"])
    history = task["history"] if isinstance(task["history"], list) else json.loads(task["history"] or "[]")
    return history[0]["author"] if history and history[0].get("author_id") is None else "Affectation retirée"


def _superiors(members, member_id):
    """Assignment ids above this one, chief last. teams.py guarantees the chain has no cycle."""
    index = {m["id"]: m for m in members}
    chain, seen = [], set()
    current = index.get(member_id)
    while current and current.get("manager_id") and current["manager_id"] not in seen:
        seen.add(current["manager_id"])
        chain.append(current["manager_id"])
        current = index.get(current["manager_id"])
    return chain


def _task(service, project_id, id):
    task = service.store.one("SELECT * FROM tasks WHERE id=?", (id,))
    if task["project_id"] != project_id:
        raise ValueError("Cette tâche appartient à un autre projet.")
    return task


def _loaded(row):
    task = dict(row)
    task["dependencies"] = json.loads(task["dependencies"])
    task["history"] = json.loads(task["history"])
    task["status_label"] = STATUSES.get(task["status"], task["status"])
    task["cursors"] = json.loads(task.get("cursors") or "{}")
    return task


def _links(service, team_id, task_id, dependencies, parent_id):
    """Existence, team membership and absence of a cycle — checked on creation and on update alike."""
    if not isinstance(dependencies, list):
        raise ValueError("Les dépendances doivent être une liste d’identifiants de tâches.")
    dependencies = list(dict.fromkeys(str(d) for d in dependencies if d))
    parent_id = parent_id or None
    if task_id and parent_id == task_id:
        raise ValueError("Une tâche ne peut pas être son propre parent.")
    if task_id and task_id in dependencies:
        raise ValueError("Une tâche ne peut pas dépendre d’elle-même.")
    known = {r["id"]: r for r in service.store.rows("SELECT id,parent_id,dependencies,status,objective FROM tasks WHERE team_id=?", (team_id,))}
    for id in dependencies + ([parent_id] if parent_id else []):
        if id not in known and id != task_id:
            raise ValueError("Tâche liée introuvable dans cette équipe : « " + str(id)[:40] + " ». Corrigez le parent ou la dépendance.")
    graph = {id: set(json.loads(row["dependencies"])) | ({row["parent_id"]} if row["parent_id"] else set()) for id, row in known.items()}
    graph[task_id or "__nouvelle__"] = set(dependencies) | ({parent_id} if parent_id else set())
    start = task_id or "__nouvelle__"
    stack, seen = [(start, [start])], set()
    while stack:
        node, path = stack.pop()
        for following in graph.get(node, ()):  # A missing node is a task of another team, already refused above.
            if following in path:
                raise ValueError("Dépendance circulaire refusée : cette liaison ferait dépendre la tâche d’elle-même, directement ou par transitivité.")
            if (node, following) not in seen:
                seen.add((node, following))
                stack.append((following, path + [following]))
    return dependencies, parent_id


def _blocking(service, dependencies):
    if not dependencies:
        return []
    marks = ",".join("?" for _ in dependencies)
    rows = service.store.rows("SELECT id,objective,status FROM tasks WHERE id IN (" + marks + ")", tuple(dependencies))
    return [r for r in rows if r["status"] != "done"]


def _transition(current, target):
    if current == target:
        return False
    allowed = TRANSITIONS.get(current, set())
    if target not in allowed:
        labels = ", ".join(STATUSES[s] for s in sorted(allowed)) if allowed else "aucun autre état : cette tâche est close"
        raise ValueError("Passage de « " + STATUSES.get(current, current) + " » à « " + STATUSES.get(target, target) +
                         " » refusé. Depuis cet état, les suites possibles sont : " + labels + ".")
    return True


def _history(task, status, author_id, author_name, detail):
    history = json.loads(task["history"]) if task["history"] else []
    history.append({"status": status, "author_id": author_id, "author": author_name, "detail": detail, "date": now()})
    return json.dumps(history, ensure_ascii=False)


def _context(service, data, require_team=True):
    project = _project(service, data["project_id"])
    team = _team(service, project["id"]) if require_team else None
    return project, team, _members(service, team["id"]) if team else []


# --- tasks ----------------------------------------------------------------------------------

def create_task(service, data):
    project, team, members = _context(service, data)
    author_id, author_name = _actor(members, data, "auteur")
    assignee_id = data.get("assignee_id") or None
    if assignee_id:
        _member(members, assignee_id, "responsable de la tâche")
    dependencies, parent_id = _links(service, team["id"], None, data.get("dependencies", []), data.get("parent_id"))
    status = str(data.get("status", "to_prepare"))
    if status not in STATUSES:
        raise ValueError("Statut inconnu. Valeurs acceptées : " + ", ".join(sorted(STATUSES)) + ".")
    if status in FINAL or status == "in_review":
        raise ValueError("Une tâche se crée « à préparer » ou « prête » ; les autres états s’atteignent par une transition enregistrée.")
    if status == "ready":
        blocking = _blocking(service, dependencies)
        if blocking:
            raise ValueError("Dépendances non terminées : " + ", ".join(b["objective"][:40] for b in blocking) + ". Créez la tâche « à préparer ».")
    id = uid()
    timestamp = now()
    row = {"history": "[]"}
    service.store.execute(
        "INSERT INTO tasks(id,team_id,project_id,objective,assignee_id,author_id,parent_id,dependencies,file_scope,acceptance_criteria,"
        "deliverables,status,history,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (id, team["id"], project["id"], _text(data.get("objective"), 500, "Objectif de la tâche", required=True), assignee_id, author_id,
         parent_id, json.dumps(dependencies), _text(data.get("file_scope"), 2000, "Périmètre de fichiers"),
         _text(data.get("acceptance_criteria"), 4000, "Critères d’acceptation"), _text(data.get("deliverables"), 4000, "Livrables"),
         status, _history(row, status, author_id, author_name, "Création de la carte."), timestamp, timestamp))
    if data.get("cursors"):
        from .team_lead import clean_cursors
        service.store.execute("UPDATE tasks SET cursors=? WHERE id=?", (json.dumps(clean_cursors(data["cursors"])), id))
    return {"id": id, "status": status, "notice": "Carte créée. Aucun agent n’est lancé : l’exécution arrive avec le board."}


def update_task(service, data):
    project, team, members = _context(service, data)
    task = _task(service, project["id"], data["id"])
    if task["status"] in FINAL:
        raise ValueError("Cette tâche est close (" + STATUSES[task["status"]] + "). Créez une nouvelle carte plutôt que de réécrire son périmètre.")
    assignee_id = (data["assignee_id"] or None) if "assignee_id" in data else task["assignee_id"]
    if assignee_id:
        _member(members, assignee_id, "responsable de la tâche")
    dependencies, parent_id = _links(service, team["id"], task["id"],
                                     data.get("dependencies", json.loads(task["dependencies"])),
                                     data["parent_id"] if "parent_id" in data else task["parent_id"])
    if task["status"] == "ready":
        blocking = _blocking(service, dependencies)
        if blocking:
            raise ValueError("Cette tâche est « prête » : elle ne peut pas dépendre de " +
                             ", ".join(b["objective"][:40] for b in blocking) + ", qui n’est pas terminée. Repassez-la « à préparer » d’abord.")
    service.store.execute(
        "UPDATE tasks SET objective=?,assignee_id=?,parent_id=?,dependencies=?,file_scope=?,acceptance_criteria=?,deliverables=?,updated_at=? WHERE id=?",
        (_text(data.get("objective", task["objective"]), 500, "Objectif de la tâche", required=True), assignee_id, parent_id,
         json.dumps(dependencies), _text(data.get("file_scope", task["file_scope"]), 2000, "Périmètre de fichiers"),
         _text(data.get("acceptance_criteria", task["acceptance_criteria"]), 4000, "Critères d’acceptation"),
         _text(data.get("deliverables", task["deliverables"]), 4000, "Livrables"), now(), task["id"]))
    if "cursors" in data:
        from .team_lead import clean_cursors
        service.store.execute("UPDATE tasks SET cursors=? WHERE id=?", (json.dumps(clean_cursors(data["cursors"])), task["id"]))
    return {"id": task["id"], "notice": "Carte mise à jour."}


def delete_task(service, data):
    project, team, members = _context(service, data)
    task = _task(service, project["id"], data["id"])
    children = service.store.rows("SELECT id FROM tasks WHERE parent_id=?", (task["id"],))
    dependants = [r for r in service.store.rows("SELECT id,dependencies FROM tasks WHERE team_id=?", (team["id"],))
                  if task["id"] in json.loads(r["dependencies"])]
    if (children or dependants) and not data.get("acknowledged"):
        raise ValueError(str(len(children)) + " sous-tâche(s) et " + str(len(dependants)) + " tâche(s) dépendante(s) sont rattachées. "
                         "Confirmez (acknowledged) : les sous-tâches seront supprimées et les dépendances retirées.")
    with service.store.transaction() as db:
        for row in dependants:
            remaining = [d for d in json.loads(row["dependencies"]) if d != task["id"]]
            db.execute("UPDATE tasks SET dependencies=?,updated_at=? WHERE id=?", (json.dumps(remaining), now(), row["id"]))
        db.execute("DELETE FROM tasks WHERE id=?", (task["id"],))
    return {"id": task["id"], "notice": "Carte supprimée avec ses sous-tâches et ses rapports."}


def change_status(service, data):
    project, team, members = _context(service, data)
    author_id, author_name = _actor(members, data, "auteur du changement")
    target = str(data.get("status", ""))
    if target not in STATUSES:
        raise ValueError("Statut inconnu. Valeurs acceptées : " + ", ".join(sorted(STATUSES)) + ".")
    if target in REVIEW_ONLY:
        raise ValueError("« " + STATUSES[target] + " » ne s’obtient pas par un changement de statut : utilisez l’acceptation ou la demande "
                         "de correction, qui enregistrent qui décide et sur quelles preuves.")
    reason = _text(data.get("reason", ""), 1000, "Motif")
    with service.store.transaction() as db:
        task = _task(service, project["id"], data["id"])
        if not _transition(task["status"], target):
            return {"id": task["id"], "status": target, "notice": "Statut déjà à « " + STATUSES[target] + " »."}
        if target == "ready":
            blocking = _blocking(service, json.loads(task["dependencies"]))
            if blocking:
                raise ValueError("Dépendances non terminées : " + ", ".join(b["objective"][:40] for b in blocking) +
                                 ". Terminez-les, ou retirez-les de cette tâche avant de la déclarer prête.")
        db.execute("UPDATE tasks SET status=?,history=?,updated_at=? WHERE id=?",
                   (target, _history(task, target, author_id, author_name, reason or "Changement de statut."), now(), task["id"]))
    return {"id": task["id"], "status": target, "notice": "Statut : " + STATUSES[target] + "."}


def list_tasks(service, data):
    project, team, members = _context(service, data)
    from .team_runtime import reconcile
    reconcile(service, project["id"])
    tasks = [_loaded(r) for r in service.store.rows("SELECT * FROM tasks WHERE team_id=? ORDER BY created_at", (team["id"],))]
    counts = {r["task_id"]: r["n"] for r in service.store.rows(
        "SELECT task_id,COUNT(*) AS n FROM task_reports WHERE task_id IN (SELECT id FROM tasks WHERE team_id=?) GROUP BY task_id", (team["id"],))}
    pending = {r["task_id"]: r["n"] for r in service.store.rows(
        "SELECT task_id,COUNT(*) AS n FROM task_consultations WHERE status='requested' AND task_id IN (SELECT id FROM tasks WHERE team_id=?) GROUP BY task_id", (team["id"],))}
    attempts = {r["task_id"]: r["n"] for r in service.store.rows(
        "SELECT task_id,COUNT(*) AS n FROM task_executions WHERE status<>'running' AND task_id IN (SELECT id FROM tasks WHERE team_id=?) GROUP BY task_id", (team["id"],))}
    running = {r["task_id"] for r in service.store.rows(
        "SELECT task_id FROM task_executions WHERE status='running' AND task_id IN (SELECT id FROM tasks WHERE team_id=?)", (team["id"],))}
    for task in tasks:
        task["reports"] = counts.get(task["id"], 0)
        task["pending_consultations"] = pending.get(task["id"], 0)
        task["running"] = task["id"] in running
        task["attempts"] = attempts.get(task["id"], 0)
        task["assignee"] = _name(members, task["assignee_id"]) if task["assignee_id"] else ""
        task["author"] = _name(members, task["author_id"])
    return {"team_id": team["id"], "project_id": project["id"], "tasks": tasks, "statuses": STATUSES,
            "members": [{"id": m["id"], "name": m["definition"]["name"], "role": m["role"], "role_label": ROLE_LABELS[m["role"]],
                         "manager_id": m["manager_id"], "active": m["active"]} for m in members],
            "notice": BOARD_NOTICE}


def get_task(service, data):
    project, team, members = _context(service, data)
    from .team_runtime import reconcile, executions
    reconcile(service, project["id"])
    task = _loaded(_task(service, project["id"], data["id"]))
    task["assignee"] = _name(members, task["assignee_id"]) if task["assignee_id"] else ""
    task["author"] = _author_name(members, task)
    task["blocking"] = [{"id": b["id"], "objective": b["objective"], "status": b["status"]} for b in _blocking(service, task["dependencies"])]
    task["children"] = service.store.rows("SELECT id,objective,status FROM tasks WHERE parent_id=? ORDER BY created_at", (task["id"],))
    task["reports"] = [dict(r) for r in service.store.rows("SELECT * FROM task_reports WHERE task_id=? ORDER BY created_at", (task["id"],))]
    for report in task["reports"]:
        report["author"] = _name(members, report["author_id"])
        report["source"] = report.get("source", "user")
    task["executions"] = executions(service, members, task["id"])
    from .team_runtime import stalled
    task["stalled"] = stalled(service, task, task["executions"])
    from .learning import evaluations, SCORES
    task["evaluations"] = evaluations(service, members, task["id"])
    task["score_labels"] = SCORES
    task["consultations"] = _consultations(service, members, task["id"])
    task["consultable"] = [{"id": m["id"], "name": m["definition"]["name"], "role": m["role"], "role_label": ROLE_LABELS[m["role"]]}
                           for m in members if m["active"] and m["id"] != task["assignee_id"]]
    task["reviewers"] = [{"id": id, "name": _name(members, id)} for id in eligible_reviewers(members, task)]
    return task


# --- reports and review ---------------------------------------------------------------------

def submit_report(service, data):
    project, team, members = _context(service, data)
    author = _member(members, data.get("author_id"), "auteur du rapport")
    values = {key: _text(data.get(key), limit, label, required=key == "result") for key, (limit, label) in REPORT_FIELDS.items()}
    with service.store.transaction() as db:
        task = _task(service, project["id"], data["id"])
        if task["status"] in FINAL:
            raise ValueError("Cette tâche est close (" + STATUSES[task["status"]] + ") : un rapport ne peut plus y être rattaché.")
        id = uid()
        db.execute("INSERT INTO task_reports(id,task_id,project_id,author_id,result,modified_files,executed_tests,limits,risks,requested_decisions,created_at)"
                   " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   (id, task["id"], project["id"], author["id"], values["result"], values["modified_files"], values["executed_tests"],
                    values["limits"], values["risks"], values["requested_decisions"], now()))
        moved = task["status"] == "in_progress"
        if moved:
            db.execute("UPDATE tasks SET status='in_review',history=?,updated_at=? WHERE id=?",
                       (_history(task, "in_review", author["id"], author["definition"]["name"], "Rapport rendu, en attente de revue."), now(), task["id"]))
        else:
            db.execute("UPDATE tasks SET updated_at=? WHERE id=?", (now(), task["id"]))
    return {"id": id, "task_status": "in_review" if moved else task["status"],
            "notice": ("Rapport enregistré ; la tâche passe en revue. " if moved else "Rapport enregistré. ") +
                      "Un rapport n’est pas une acceptation : le responsable hiérarchique doit examiner les preuves et décider."}


def eligible_reviewers(members, task):
    """Who may accept or send back this task.

    Normally the hierarchical superiors of the assignee. A consultant answers a request without
    belonging to the chain, and the chief has nobody above: in both cases the decision goes up to an
    active chief, and always to the user.
    """
    superiors = _superiors(members, task["assignee_id"]) if task["assignee_id"] else []
    if not superiors:
        superiors = [m["id"] for m in members if m["active"] and m["role"] == "chief"]
    return [id for id in superiors if id != task["assignee_id"]]


def _reviewer(members, task, data, act):
    if data.get("by_user"):
        return None, "Utilisateur"
    reviewer = _member(members, data.get("author_id"), "validateur")
    if reviewer["id"] == task["assignee_id"]:
        raise ValueError("Un agent ne peut pas " + act + " sa propre tâche. Cette décision revient à son responsable hiérarchique, ou à vous.")
    eligible = eligible_reviewers(members, task)
    if reviewer["id"] not in eligible:
        names = ", ".join(_name(members, id) for id in eligible) or "aucune affectation"
        raise ValueError(reviewer["definition"]["name"] + " n’est pas habilité à " + act + " cette tâche. Habilités : " +
                         names + ". Vous pouvez aussi décider vous-même (by_user).")
    return reviewer["id"], reviewer["definition"]["name"]


def accept_task(service, data):
    project, team, members = _context(service, data)
    proofs = _text(data.get("proofs"), 4000, "Preuves examinées", required=True)
    with service.store.transaction() as db:
        task = _task(service, project["id"], data["id"])
        if task["status"] != "in_review":
            raise ValueError("Seule une tâche en revue peut être acceptée. État actuel : « " + STATUSES[task["status"]] +
                             " ». L’agent doit d’abord rendre son rapport.")
        if not service.store.rows("SELECT id FROM task_reports WHERE task_id=?", (task["id"],)):
            raise ValueError("Aucun rapport rattaché à cette tâche : il n’y a rien à examiner. Demandez le rapport avant d’accepter.")
        id, name = _reviewer(members, task, data, "accepter")
        db.execute("UPDATE tasks SET status='done',history=?,updated_at=? WHERE id=?",
                   (_history(task, "done", id, name, "Acceptée. Preuves examinées : " + proofs), now(), task["id"]))
    return {"id": task["id"], "status": "done", "notice": "Tâche acceptée par " + name + ". La décision et les preuves examinées sont enregistrées."}


def request_correction(service, data):
    project, team, members = _context(service, data)
    reason = _text(data.get("reason"), 4000, "Motif de la correction", required=True)
    with service.store.transaction() as db:
        task = _task(service, project["id"], data["id"])
        if task["status"] != "in_review":
            raise ValueError("Seule une tâche en revue peut être renvoyée en correction. État actuel : « " + STATUSES[task["status"]] + " ».")
        id, name = _reviewer(members, task, data, "renvoyer en correction")
        db.execute("UPDATE tasks SET status='to_correct',history=?,updated_at=? WHERE id=?",
                   (_history(task, "to_correct", id, name, "Correction demandée : " + reason), now(), task["id"]))
    return {"id": task["id"], "status": "to_correct", "notice": "Correction demandée par " + name + "."}


# --- consultations --------------------------------------------------------------------------

def _consultation(service, project_id, id):
    row = service.store.one("SELECT * FROM task_consultations WHERE id=?", (id,))
    if row["project_id"] != project_id:
        raise ValueError("Cette consultation appartient à un autre projet.")
    return row


def request_consultation(service, data):
    """Ask a team member for advice on a card. An opinion is not a deliverable: the card does not move,
    and the consulted agent does not become responsible for it."""
    project, team, members = _context(service, data)
    requester_id, requester_name = _actor(members, data, "demandeur")
    consultant = _member(members, data.get("consultant_id"), "consultant")
    if not consultant["active"]:
        raise ValueError(consultant["definition"]["name"] + " est retiré de l’équipe : choisissez une affectation active.")
    question = _text(data.get("question"), 4000, "Question posée", required=True)
    task = _task(service, project["id"], data["id"])
    if task["status"] in FINAL:
        raise ValueError("Cette tâche est close (" + STATUSES[task["status"]] + ") : elle ne peut plus faire l’objet d’un avis.")
    if consultant["id"] == task["assignee_id"]:
        raise ValueError("Le responsable de la tâche rend un rapport, il ne se consulte pas lui-même. "
                         "Demandez l’avis d’un autre agent, par exemple un consultant.")
    id = uid()
    service.store.execute(
        "INSERT INTO task_consultations(id,task_id,project_id,requester_id,consultant_id,question,created_at) VALUES(?,?,?,?,?,?,?)",
        (id, task["id"], project["id"], requester_id, consultant["id"], question, now()))
    return {"id": id, "task_status": task["status"],
            "notice": "Avis demandé à " + consultant["definition"]["name"] + " par " + requester_name +
                      ". Le statut de la tâche ne change pas et son responsable reste inchangé ; la sollicitation "
                      "automatique de l’agent arrivera avec l’exécution."}


def answer_consultation(service, data):
    project, team, members = _context(service, data)
    consultation = _consultation(service, project["id"], data["id"])
    if consultation["status"] != "requested":
        raise ValueError("Cet avis est déjà " + CONSULTATION_STATUSES[consultation["status"]].lower() + " : ouvrez une nouvelle demande.")
    declined = bool(data.get("declined"))
    answer = _text(data.get("answer"), 10000, "Motif du refus" if declined else "Avis rendu", required=True)
    # Today an answer is typed in by the user; execution will let the agent answer for itself.
    source = "agent" if data.get("source") == "agent" else "user"
    service.store.execute("UPDATE task_consultations SET answer=?,status=?,answer_source=?,answered_at=? WHERE id=?",
                          (answer, "declined" if declined else "answered", source, now(), consultation["id"]))
    return {"id": consultation["id"], "status": "declined" if declined else "answered",
            "notice": ("Refus enregistré. " if declined else "Avis enregistré. ") + ANSWER_SOURCES[source] +
                      " — un avis éclaire la décision, il ne vaut ni rapport ni acceptation, et le statut de la tâche est inchangé."}


def _consultations(service, members, task_id):
    rows = []
    for row in service.store.rows("SELECT * FROM task_consultations WHERE task_id=? ORDER BY created_at", (task_id,)):
        entry = dict(row)
        entry["consultant"] = _name(members, entry["consultant_id"])
        entry["requester"] = _name(members, entry["requester_id"]) if entry["requester_id"] else "Utilisateur"
        entry["status_label"] = CONSULTATION_STATUSES.get(entry["status"], entry["status"])
        entry["source_label"] = ANSWER_SOURCES.get(entry["answer_source"], "")
        rows.append(entry)
    return rows


# --- dispatcher -----------------------------------------------------------------------------

def tasks_action(service, action, data):
    if action == "task_list":
        return list_tasks(service, data)
    if action == "task_get":
        return get_task(service, data)
    if action == "task_create":
        return create_task(service, data)
    if action == "task_update":
        return update_task(service, data)
    if action == "task_delete":
        return delete_task(service, data)
    if action == "task_status":
        return change_status(service, data)
    if action == "task_report":
        return submit_report(service, data)
    if action == "task_accept":
        return accept_task(service, data)
    if action == "task_correction":
        return request_correction(service, data)
    if action == "task_consult":
        return request_consultation(service, data)
    if action == "task_consult_answer":
        return answer_consultation(service, data)
    return UNHANDLED
