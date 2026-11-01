"""The delegation automaton: the board moves on without being relaunched by hand, within limits you set.

A round looks at the board as it is and does two things:
- launch the cards that can run — ready or to correct, dependencies done, assignee active, connector enabled,
  not already running, and not raised as stalled (a stalled card waits for you, it is never relaunched here);
- send each new report to a reviewer agent — the assignee's superior — who accepts it or asks for a
  correction through the CyAI MCP. A report is sent once; a card with no reviewer agent waits for you.

It runs in two ways. **One step**: you see the round before it starts and confirm it. **Automatic**: rounds
follow one another, but only within a budget of launches you set, and it stops by itself when the budget is
spent, when an execution fails, or when nothing can move. Every write an agent makes still goes through the
authorisation policy of its conversation. Nothing here makes an agent's work true: reviews stay reviews.

Spontaneous proposals are opt-in, off by default. When on, a reviewer — a chief or a lead, never the agent about
its own work — is invited to propose one improvement of the assignee's instructions if the report shows a gap,
citing the card and the report. A proposal changes nothing until you adopt it.
"""
import json
import threading

from .store import now

UNHANDLED = object()

INTERVAL = 20
MAX_BUDGET = 50
MAX_PARALLEL = 6
DEFAULTS = {"enabled": False, "budget": 0, "max_parallel": 2, "reviews": {}, "stopped": "", "since": "", "launched": 0,
            "invite_proposals": False}
PUBLIC = ("enabled", "budget", "max_parallel", "stopped", "since", "launched", "invite_proposals")


def _state(team):
    try:
        state = json.loads(team.get("autopilot") or "{}")
    except ValueError:
        state = {}
    return {**DEFAULTS, **state}


def _save(service, team_id, state):
    service.store.execute("UPDATE teams SET autopilot=? WHERE id=?", (json.dumps(state, ensure_ascii=False), team_id))


def _ready(service, member):
    connector = service.engine.connectors.get(member["definition"]["connector"])
    return bool(connector and connector.config.get("enabled", False))


def plan(service, data):
    """What a round would do now, and what waits for you. Nothing is launched here."""
    from .tasks import _context, _blocking, eligible_reviewers, STATUSES
    from .team_runtime import LAUNCHABLE, reconcile, stalled, executions
    project, team, members = _context(service, data)
    reconcile(service, project["id"])
    state = _state(team)
    by_id = {m["id"]: m for m in members}
    running = {r["task_id"] for r in service.store.rows("SELECT task_id FROM task_executions WHERE project_id=? AND status='running'", (project["id"],))}
    reviewing = {mission for mission in state["reviews"].values()
                 if service.store.rows("SELECT id FROM missions WHERE id=? AND status IN ('queued','running','awaiting_approval','pausing')", (mission,))}
    launch, reviews, waiting = [], [], []
    for row in service.store.rows("SELECT * FROM tasks WHERE team_id=? ORDER BY created_at", (team["id"],)):
        task = {**dict(row), "dependencies": json.loads(row["dependencies"])}
        member = by_id.get(task["assignee_id"])
        if task["status"] in LAUNCHABLE and task["id"] not in running:
            reason = ""
            if not member:
                reason = "sans responsable"
            elif not member["active"]:
                reason = member["definition"]["name"] + " est retiré de l’équipe"
            elif _blocking(service, task["dependencies"]):
                continue  # waits for its dependencies: nothing to decide yet
            else:
                stall = stalled(service, task, executions(service, members, task["id"]))
                if not _ready(service, member):
                    reason = "connecteur « " + member["definition"]["connector"] + " » indisponible"
                elif stall:
                    reason = stall["message"]
            entry = {"task_id": task["id"], "objective": task["objective"], "status": STATUSES[task["status"]],
                     "member": member["definition"]["name"] if member else ""}
            (waiting if reason else launch).append({**entry, **({"reason": reason} if reason else {})})
        elif task["status"] == "in_review":
            report = service.store.rows("SELECT id FROM task_reports WHERE task_id=? ORDER BY created_at DESC LIMIT 1", (task["id"],))
            if not report or report[0]["id"] in state["reviews"]:
                continue
            reviewers = [by_id[id] for id in eligible_reviewers(members, task) if id in by_id and by_id[id]["active"]]
            usable = [m for m in reviewers if _ready(service, m)]
            entry = {"task_id": task["id"], "objective": task["objective"], "report_id": report[0]["id"],
                     "member": member["definition"]["name"] if member else ""}
            if usable:
                reviews.append({**entry, "reviewer_id": usable[0]["id"], "reviewer": usable[0]["definition"]["name"]})
            else:
                waiting.append({**entry, "reason": "revue à faire par vous : aucun responsable agent disponible"})
    capacity = max(0, state["max_parallel"] - len(running) - len(reviewing))
    return {"project_id": project["id"], "team_id": team["id"], "launch": launch, "reviews": reviews, "waiting": waiting,
            "running": len(running), "reviewing": len(reviewing), "capacity": capacity,
            "autopilot": {k: state[k] for k in PUBLIC},
            "notice": "Un tour lance au plus " + str(capacity) + " exécution(s) ou revue(s) maintenant. Chaque écriture d’un agent "
                      "reste soumise aux autorisations de sa conversation ; une revue d’agent reste une revue, pas une preuve."}


def _request_review(service, project, members, task_id, reviewer_id, report_id, invite_proposals=False):
    from .team_runtime import open_conversation, _member_row
    task = dict(service.store.one("SELECT * FROM tasks WHERE id=?", (task_id,)))
    report = dict(service.store.one("SELECT * FROM task_reports WHERE id=?", (report_id,)))
    reviewer = _member_row(service, project["id"], reviewer_id)
    assignee = next((m["definition"]["name"] for m in members if m["id"] == task["assignee_id"]), "le responsable")
    conversation = open_conversation(service, {"project_id": project["id"], "member_id": reviewer_id, "task_id": task_id})
    instruction = ("Revue de la carte « " + task["objective"] + " » (identifiant " + task_id + "), confiée à " + assignee + ".\n\n"
                   "Critères d’acceptation : " + (task.get("acceptance_criteria") or "non précisés") + "\n\n"
                   "Compte rendu rendu :\n" + report["result"][:6000] + "\n\n"
                   "Un compte rendu n’est pas une preuve : vérifiez dans le projet ce qui peut l’être. Puis décidez, par le MCP CyAI :\n"
                   "- accepter : action task_accept avec project_id=" + project["id"] + ", id=" + task_id + ", author_id=" + reviewer_id +
                   " et proofs = ce que vous avez effectivement vérifié ;\n"
                   "- ou demander une correction : action task_correction avec project_id=" + project["id"] + ", id=" + task_id +
                   ", author_id=" + reviewer_id + " et reason = ce qui manque.\n"
                   "Si vous ne pouvez pas trancher, dites-le : la décision reviendra à l’utilisateur.")
    profile_id = next((m["profile_id"] for m in members if m["id"] == task["assignee_id"]), "")
    if invite_proposals and profile_id:
        instruction += ("\n\nSi ce compte rendu montre un manque dans les consignes de " + assignee + " — pas une erreur ponctuelle —, "
                        "vous pouvez proposer une amélioration : action improvement_propose avec project_id=" + project["id"] +
                        ", member_id=" + reviewer_id + ", profile_id=" + profile_id + ", kind=prompt, proposed_value = ses consignes "
                        "complètes corrigées, rationale = ce que vous avez constaté, source_ids=[" + task_id + ", " + report_id + "]. "
                        "Une proposition au plus, et seulement si elle s’appuie sur ce travail. Elle ne change rien tant que "
                        "l’utilisateur ne l’adopte pas. Sinon, n’en faites pas.")
    mission = service.engine.create({
        "conversation_id": conversation["id"], "title": ("Revue · " + task["objective"])[:120],
        "request_key": "review:" + report_id, "message": "Revue demandée pour « " + task["objective"] + " ».",
        "steps": [{"name": ("Revue · " + task["objective"])[:120], "connector": reviewer["definition"]["connector"],
                   "model": reviewer["definition"]["model"], "instruction": instruction}]})
    service.engine.launch(mission)
    return mission


def step(service, data, automatic=False):
    """Run one round: launches then reviews, within the free capacity (and the budget when automatic)."""
    from .tasks import _context
    from .team_runtime import execute_task
    current = plan(service, data)
    project, team, members = _context(service, data)
    state = _state(team)
    room = current["capacity"] if not automatic else min(current["capacity"], state["budget"])
    done = {"launched": [], "reviews": [], "errors": []}
    for entry in current["launch"]:
        if room <= 0:
            break
        try:
            execute_task(service, {"project_id": project["id"], "id": entry["task_id"]})
            done["launched"].append(entry["objective"])
            room -= 1
        except ValueError as exc:
            done["errors"].append(entry["objective"] + " : " + str(exc))
    for entry in current["reviews"]:
        if room <= 0:
            break
        try:
            mission = _request_review(service, project, members, entry["task_id"], entry["reviewer_id"], entry["report_id"],
                                      state["invite_proposals"])
            state = _state(dict(service.store.one("SELECT * FROM teams WHERE id=?", (team["id"],))))
            state["reviews"][entry["report_id"]] = mission
            _save(service, team["id"], state)
            done["reviews"].append(entry["objective"] + " → " + entry["reviewer"])
            room -= 1
        except ValueError as exc:
            done["errors"].append(entry["objective"] + " : " + str(exc))
    count = len(done["launched"]) + len(done["reviews"])
    if automatic and count:
        state = _state(dict(service.store.one("SELECT * FROM teams WHERE id=?", (team["id"],))))
        state["budget"] = max(0, state["budget"] - count)
        state["launched"] += count
        _save(service, team["id"], state)
    done["notice"] = (str(len(done["launched"])) + " exécution(s) lancée(s), " + str(len(done["reviews"])) + " revue(s) demandée(s)." +
                      (" " + str(len(done["errors"])) + " refus : " + " ; ".join(done["errors"]) if done["errors"] else ""))
    return done


def configure(service, data):
    from .tasks import _context
    project, team, members = _context(service, data)
    state = _state(team)
    enabled = bool(data.get("enabled", state["enabled"]))
    if enabled:
        try:
            budget = int(data.get("budget", state["budget"]))
            parallel = int(data.get("max_parallel", state["max_parallel"]))
        except (TypeError, ValueError):
            raise ValueError("Budget et parallélisme sont des nombres entiers.")
        if not 1 <= budget <= MAX_BUDGET:
            raise ValueError("Budget : entre 1 et " + str(MAX_BUDGET) + " lancements. Il se renouvelle à votre demande, jamais seul.")
        if not 1 <= parallel <= MAX_PARALLEL:
            raise ValueError("Parallélisme : entre 1 et " + str(MAX_PARALLEL) + ".")
        state.update(enabled=True, budget=budget, max_parallel=parallel, stopped="", since=now(), launched=0)
        notice = ("Pilote automatique activé : au plus " + str(budget) + " lancement(s), relectures comprises, " + str(parallel) + " à la fois. "
                  "Il s’arrête seul à la fin du budget, à la première exécution échouée, ou quand plus rien ne peut avancer.")
    else:
        state.update(enabled=False, stopped=data.get("reason") or "Arrêté par vous.")
        notice = "Pilote automatique arrêté. Les exécutions en cours continuent ; rien de nouveau ne sera lancé."
    _save(service, team["id"], state)
    return {"autopilot": {k: state[k] for k in PUBLIC}, "notice": notice}


def set_options(service, data):
    """Options of the reviews the automaton requests. Only the user sets them."""
    from .tasks import _context
    project, team, members = _context(service, data)
    state = _state(team)
    state["invite_proposals"] = bool(data.get("invite_proposals", state["invite_proposals"]))
    _save(service, team["id"], state)
    return {"autopilot": {k: state[k] for k in PUBLIC},
            "notice": ("Les relecteurs pourront proposer une amélioration des consignes, à adopter par vous." if state["invite_proposals"]
                       else "Les relecteurs ne sont plus invités à proposer d’améliorations.")}


def _stop(service, team_id, reason):
    state = _state(dict(service.store.one("SELECT * FROM teams WHERE id=?", (team_id,))))
    state.update(enabled=False, stopped=reason)
    _save(service, team_id, state)


def tick(service):
    """One automatic round for every team whose pilot is on. Called by the background loop, and by tests."""
    for team in service.store.rows("SELECT * FROM teams"):
        state = _state(dict(team))
        if not state["enabled"]:
            continue
        project_id = team["project_id"]
        try:
            failed = service.store.rows("SELECT id FROM task_executions WHERE project_id=? AND status NOT IN ('running','succeeded') AND settled_at>=?",
                                        (project_id, state["since"]))
            if failed:
                _stop(service, team["id"], "Arrêt automatique : une exécution a échoué ou a été interrompue. Examinez-la avant de relancer le pilote.")
                continue
            if state["budget"] <= 0:
                _stop(service, team["id"], "Arrêt automatique : budget de lancements épuisé.")
                continue
            current = plan(service, {"project_id": project_id})
            if not current["launch"] and not current["reviews"] and not current["running"] and not current["reviewing"]:
                _stop(service, team["id"], "Arrêt automatique : plus rien ne peut avancer sans vous." +
                      (" En attente : " + "; ".join(w["objective"][:40] + " (" + w["reason"] + ")" for w in current["waiting"])[:600] if current["waiting"] else ""))
                continue
            if current["capacity"]:
                step(service, {"project_id": project_id}, automatic=True)
        except Exception as exc:
            _stop(service, team["id"], "Arrêt automatique : " + str(exc)[:400])


def stop_after_restart(service):
    """A pilot never resumes by itself after CyAI restarts: spending starts again only when you say so."""
    for team in service.store.rows("SELECT id,autopilot FROM teams"):
        if _state(dict(team))["enabled"]:
            _stop(service, team["id"], "Arrêté au redémarrage de CyAI : réactivez-le si vous voulez qu’il continue.")


_loops = {}


def ensure_loop(service):
    """Start the background loop once per service. It does nothing while no pilot is on."""
    thread = _loops.get(id(service))
    if thread and thread.is_alive():
        return

    def run():
        while not service.engine.closing.wait(INTERVAL):
            try:
                tick(service)
            except Exception:
                pass

    _loops[id(service)] = threading.Thread(target=run, daemon=True, name="cyai-autopilot")
    _loops[id(service)].start()


def autopilot_action(service, action, data):
    if action == "team_autopilot_plan":
        return plan(service, data)
    if action == "team_autopilot_step":
        return step(service, data)
    if action == "team_autopilot_options":
        return set_options(service, data)
    if action == "team_autopilot_set":
        result = configure(service, data)
        if result["autopilot"]["enabled"]:
            ensure_loop(service)
        return result
    return UNHANDLED
