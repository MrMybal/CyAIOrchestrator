"""Calling a specialist as a tool, while an agent is working.

A profile may declare helpers: other profiles of the library it is allowed to call for what they do
better — generating an image, producing a low-resolution shape, checking a direction. During its own
step, the agent sees one MCP tool per helper and calls it like any other tool.

The call is not a mission. It runs the helper's connector directly, inside the caller's step, under the
caller's cancellation and deadline. Three guardrails make that safe to read afterwards:

* every call is recorded as an event of the step, with the helper, the request and what came back, so a
  chain never hides work it did;
* a helper cannot call helpers of its own — one level, no recursion;
* a step may call a bounded number of times, and is told when it reaches the ceiling instead of looping.
"""
import json

from .store import now

MAX_CALLS = 8
MAX_HELPERS = 6
MAX_REQUEST = 20000


def declared(service, definition):
    """The helpers of a definition, resolved to what they actually are today."""
    resolved = []
    for entry in definition.get("helpers", []) or []:
        rows = service.store.rows("SELECT * FROM agent_profiles WHERE id=?", (entry.get("profile_id"),))
        if not rows:
            continue
        profile = dict(rows[0])
        connector = service.engine.connectors.get(profile["connector"])
        evaluations = service.store.rows("SELECT id FROM agent_benchmarks WHERE profile_id=?", (profile["id"],))
        resolved.append({"evaluation_count": len(evaluations), "profile_id": profile["id"], "name": profile["name"], "purpose": entry.get("purpose", ""),
                         "connector": profile["connector"], "model": profile["model"], "prompt": profile["prompt"],
                         "archived": bool(profile["archived"]),
                         "ready": bool(connector and connector.config.get("enabled", False) and not profile["archived"])})
    return resolved


def tool_definition(helpers):
    if not helpers:
        return None
    lines = ["Demander à un spécialiste de la bibliothèque CyAI de faire une partie du travail pour vous.",
             "Spécialistes disponibles :"]
    for helper in helpers:
        detail = helper["purpose"] or "sans description"
        if helper.get("evaluation_count"):
            detail += " — mode d’emploi évalué disponible via evaluation_guides, profile_id " + helper["profile_id"]
        if not helper["ready"]:
            detail += " — INDISPONIBLE (profil archivé ou connecteur désactivé)"
        lines.append("- " + helper["name"] + " : " + detail)
    lines.append("Sa réponse est son compte rendu, pas une preuve : relisez-la et dites dans votre propre réponse "
                 "ce que vous en avez retenu. Au plus " + str(MAX_CALLS) + " appels pour cette étape.")
    return {"name": "cyai_specialist", "description": "\n".join(lines),
            "annotations": {"readOnlyHint": False, "destructiveHint": False},
            "inputSchema": {"type": "object", "additionalProperties": False,
                            "properties": {"specialist": {"type": "string", "enum": [h["name"] for h in helpers]},
                                           "request": {"type": "string"}},
                            "required": ["specialist", "request"]}}


def call_specialist(service, grant, arguments):
    helpers = grant.get("helpers") or []
    control = grant.get("control")
    if not helpers:
        raise ValueError("Aucun spécialiste n’est déclaré pour cet agent.")
    if control is None:
        raise ValueError("Un spécialiste ne se convoque que pendant l’exécution d’un agent.")
    name = str(arguments.get("specialist", ""))
    helper = next((h for h in helpers if h["name"] == name), None)
    if helper is None:
        raise ValueError("Spécialiste inconnu : « " + name[:60] + " ». Déclarés : " + ", ".join(h["name"] for h in helpers) + ".")
    if not helper["ready"]:
        raise ValueError("« " + helper["name"] + " » est indisponible : profil archivé ou connecteur désactivé. "
                         "Faites sans lui et dites-le dans votre réponse.")
    request = str(arguments.get("request", "")).strip()
    if not request:
        raise ValueError("Décrivez ce que vous demandez au spécialiste.")
    if len(request) > MAX_REQUEST:
        raise ValueError("Demande limitée à " + str(MAX_REQUEST) + " caractères.")
    grant["calls"] = grant.get("calls", 0) + 1
    if grant["calls"] > MAX_CALLS:
        raise ValueError("Plafond de " + str(MAX_CALLS) + " appels de spécialistes atteint pour cette étape. "
                         "Terminez avec ce que vous avez et signalez ce qui manque, plutôt que de continuer à demander.")
    control.check()
    emit = getattr(control, "emit", None)
    if emit:
        emit("specialist_requested", {"specialist": helper["name"], "purpose": helper["purpose"],
                                      "connector": helper["connector"], "model": helper["model"],
                                      "call": grant["calls"], "request": request[:2000],
                                      "notice": "Appel d’un spécialiste par l’agent en cours. Sa réponse est un compte rendu, pas une preuve."})
    connector = service.engine.connectors[helper["connector"]]
    prompt = ((helper["prompt"] + "\n\n") if helper["prompt"] else "") + \
             "Un autre agent vous sollicite pendant son travail. Répondez uniquement à sa demande, sans prendre en charge " \
             "le reste de sa tâche, et dites clairement ce que vous n’avez pas pu faire.\n\nDemande :\n" + request
    # A child control: the helper stops when the caller stops, and cannot call helpers of its own.
    child = _child_control(control, helper, grant["calls"])
    try:
        result = service.engine.secrets.redact(connector.run(prompt, grant["root"], helper["model"], None, child))
    except Exception as exc:
        detail = service.engine.secrets.redact(str(exc))
        if emit:
            emit("specialist_failed", {"specialist": helper["name"], "call": grant["calls"], "error": detail})
        raise ValueError("« " + helper["name"] + " » a échoué : " + detail +
                         " Poursuivez sans lui si possible, et signalez-le dans votre réponse.")
    if emit:
        emit("specialist_answered", {"specialist": helper["name"], "call": grant["calls"], "chars": len(result or ""),
                                     "answer": (result or "")[:2000],
                                     "notice": "Compte rendu du spécialiste, non vérifié par CyAI."})
    return {"specialist": helper["name"], "answer": result, "call": grant["calls"], "remaining": MAX_CALLS - grant["calls"],
            "notice": "Réponse du spécialiste. CyAI ne l’a pas vérifiée : relisez-la et dites dans votre réponse ce que vous en retenez."}


def _child_control(parent, helper, call):
    """The helper runs under the caller: same cancellation, same deadline, its own stream, no tools of its own."""
    from .connectors import Control

    def emit(kind, data):
        forward = getattr(parent, "emit", None)
        if forward:
            forward("specialist_stream", {"specialist": helper["name"], "call": call, "kind": kind, "data": data})

    def approve(request):
        # A specialist inherits nothing: it does not get to ask the user for permissions of its own.
        return False

    child = Control(0, approve, emit)
    child.cancelled = parent.cancelled
    child.deadline = getattr(parent, "deadline", None)
    child.timeout_seconds = getattr(parent, "timeout_seconds", 0)
    child.planning = getattr(parent, "planning", False)
    child.conversation_id = getattr(parent, "conversation_id", None)
    child.mcp_servers = {}  # One level only: a specialist gets no specialists of its own.
    return child


def definition_for_step(service, conversation_id, spec_step):
    definition = _definition_for_step(service, conversation_id, spec_step)
    extra = [h for h in (spec_step or {}).get("helpers", []) or [] if isinstance(h, str)]
    if not extra:
        return definition
    definition = dict(definition or {"helpers": [], "tools": []})
    known = {h.get("profile_id") for h in definition.get("helpers", [])}
    definition["helpers"] = (list(definition.get("helpers", [])) +
                             [{"profile_id": h, "purpose": "appelable pour cette tâche de la méthode"} for h in dict.fromkeys(extra) if h not in known])[:MAX_HELPERS]
    return definition


def _definition_for_step(service, conversation_id, spec_step):
    from .teams import load_member, current_definition, _loaded
    if spec_step and spec_step.get("profile_id"):
        rows = service.store.rows("SELECT * FROM agent_profiles WHERE id=?", (spec_step["profile_id"],))
        if rows:
            return current_definition(_loaded(rows[0]))
    rows = service.store.rows("SELECT member_id,profile_id FROM conversations WHERE id=?", (conversation_id,))
    if rows and rows[0]["member_id"]:
        members = service.store.rows("SELECT * FROM team_members WHERE id=?", (rows[0]["member_id"],))
        if members:
            return load_member(members[0])["definition"]
    if rows and rows[0]["profile_id"]:
        profiles = service.store.rows("SELECT * FROM agent_profiles WHERE id=?", (rows[0]["profile_id"],))
        if profiles:
            return current_definition(_loaded(profiles[0]))
    return None


def for_step(service, conversation_id, spec_step):
    """Which helpers the agent about to run may call, from the step, the assignment or the conversation."""
    from .teams import load_member, current_definition, _loaded
    definition = None
    if spec_step and spec_step.get("profile_id"):
        rows = service.store.rows("SELECT * FROM agent_profiles WHERE id=?", (spec_step["profile_id"],))
        if rows:
            definition = current_definition(_loaded(rows[0]))
    if definition is None:
        rows = service.store.rows("SELECT member_id,profile_id FROM conversations WHERE id=?", (conversation_id,))
        if rows and rows[0]["member_id"]:
            members = service.store.rows("SELECT * FROM team_members WHERE id=?", (rows[0]["member_id"],))
            if members:
                definition = load_member(members[0])["definition"]
        elif rows and rows[0]["profile_id"]:
            profiles = service.store.rows("SELECT * FROM agent_profiles WHERE id=?", (rows[0]["profile_id"],))
            if profiles:
                definition = current_definition(_loaded(profiles[0]))
    return declared(service, definition) if definition else []
