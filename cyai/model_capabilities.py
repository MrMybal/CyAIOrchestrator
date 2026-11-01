"""What a model is good at, to have an idea from the start — from several sources, always yours to correct.

For each model and each area (code, interface, debugging, reasoning, tests, documentation, automation, general), an
estimate on 10 with the sources it comes from:

1. **you** — your own scores (the model rating). They always win;
2. **your projects** — the evaluations of the cards this model did, by the chief, the leads or you (1–5, doubled);
3. **public benchmarks** known to CyAI (Aider Polyglot, for code and debugging);
4. **an AI's estimate**, only when you ask for it: it says what it knows of the model, and its uncertainty.

Without your scores, the estimate is a weighted mean of the others (projects weigh more as they accumulate, an AI's
estimate the least). The technical success of its calls is shown beside, never mixed in: an answer is not a good one.

For each area you can also set an order of preference between models. The orchestrator, the chief and the project
assistant read it; a suggested order follows the estimates until you set yours.
"""
import json
import re

from .store import now

UNHANDLED = object()

AREAS = {"code": "Code", "interface": "Interface", "debug": "Débogage", "raisonnement": "Raisonnement", "tests": "Tests",
         "documentation": "Documentation", "automation": "Automatisation", "general": "Général"}
# What the evaluation criteria of a card say about an area.
CRITERIA = {"quality": ["general", "code"], "integration": ["code"], "tests": ["tests"], "scope": ["general"]}
BENCHMARK_AREAS = {"aider polyglot": ["code", "debug"]}


def _key(connector, model):
    return str(connector) + ":" + str(model or "")


def _evaluations(service, connector, model):
    per_area = {}
    for row in service.store.rows("SELECT scores FROM task_evaluations WHERE connector=? AND model=?", (connector, model or "")):
        for criterion, value in json.loads(row["scores"]).items():
            for area in CRITERIA.get(criterion, []):
                per_area.setdefault(area, []).append(float(value) * 2)
    return per_area


def _benchmarks(service, model):
    from .benchmarks import snapshot, matching
    per_area = {}
    for row in matching(snapshot(service).get("rows", []), model or ""):
        for area in BENCHMARK_AREAS.get(str(row.get("benchmark", "")).lower(), []):
            per_area.setdefault(area, []).append((float(row["score"]) / 10, row["benchmark"] + " " + str(row["score"]) + " % (" + str(row.get("date", "")) + ")"))
    return per_area


def _estimate_ai(service, key):
    reconcile_estimates(service)
    return (service.config.get("model_estimates") or {}).get(key) or {}


def capabilities(service, connector, model):
    key = _key(connector, model)
    rating = (service.config.get("model_ratings") or {}).get(key, {})
    mine = rating.get("scores", {})
    projects, public, ai = _evaluations(service, connector, model), _benchmarks(service, model), _estimate_ai(service, key)
    areas = []
    for area, label in AREAS.items():
        sources, weighted, weights = [], 0.0, 0.0
        if area in projects:
            values = projects[area]
            average = sum(values) / len(values)
            weight = 3 * min(len(values), 5) / 5
            sources.append({"kind": "projects", "label": "vos projets", "value": round(average, 1), "detail": str(len(values)) + " note(s) de cartes"})
            weighted, weights = weighted + average * weight, weights + weight
        if area in public:
            average = sum(v for v, _ in public[area]) / len(public[area])
            sources.append({"kind": "benchmark", "label": "benchmark public", "value": round(average, 1), "detail": "; ".join(d for _, d in public[area])})
            weighted, weights = weighted + average * 2, weights + 2
        if area in (ai.get("areas") or {}):
            value = float(ai["areas"][area])
            sources.append({"kind": "ai", "label": "estimation IA", "value": value,
                            "detail": "par " + ai.get("by", "?") + " le " + ai.get("at", "")[:10] + (" · incertitude " + ai["uncertainty"] if ai.get("uncertainty") else "")})
            weighted, weights = weighted + value, weights + 1
        if area in mine:
            sources.insert(0, {"kind": "you", "label": "vous", "value": float(mine[area]), "detail": "votre note"})
            value, confidence = float(mine[area]), "vous"
        elif weights:
            value = round(weighted / weights * 2) / 2
            confidence = "élevée" if weights >= 4 else "moyenne" if weights >= 2 else "faible"
        else:
            value, confidence = None, ""
        areas.append({"area": area, "label": label, "value": value, "confidence": confidence, "sources": sources})
    rows = service.store.rows("SELECT status FROM steps WHERE connector=? AND model=?", (connector, model or ""))
    return {"key": key, "connector": connector, "model": model or "", "areas": areas, "preference": rating.get("preference", "neutral"),
            "notes": rating.get("notes", ""), "estimate_pending": key in (service.config.get("model_estimate_runs") or {}),
            "observed": {"calls": len(rows), "succeeded": sum(r["status"] == "succeeded" for r in rows),
                         "failed": sum(r["status"] == "failed" for r in rows)}}


def top(service, connector, model, count=3):
    """The strongest known areas, for a profile card or a chief deciding who does what."""
    known = [a for a in capabilities(service, connector, model)["areas"] if a["value"] is not None]
    return sorted(known, key=lambda a: -a["value"])[:count]


def _models(service):
    keys = {}
    for connector, models in (getattr(service, "catalogs", {}) or {}).items():
        for model in models:
            keys[_key(connector, model.get("id", ""))] = (connector, model.get("id", ""))
    for key in list((service.config.get("model_ratings") or {})) + list((service.config.get("model_estimates") or {})):
        connector, model = key.split(":", 1)
        keys.setdefault(key, (connector, model))
    for row in service.store.rows("SELECT connector, model FROM agent_profiles WHERE archived=0"):
        keys.setdefault(_key(row["connector"], row["model"]), (row["connector"], row["model"]))
    return keys


def overview(service, data=None):
    """Every known model with its estimates, and per area your order of preference or the suggested one."""
    entries = [capabilities(service, c, m) for c, m in _models(service).values()]
    orders = ((service.config.get("model_preferences") or {}).get("order") or {})
    rank = {"prefer": 0, "neutral": 1, "avoid": 2}
    result = {}
    for area in AREAS:
        suggested = sorted(entries, key=lambda e: (rank.get(e["preference"], 1),
                                                   -(next(a["value"] for a in e["areas"] if a["area"] == area) or -1)))
        result[area] = {"order": orders.get(area) or [], "suggested": [e["key"] for e in suggested]}
    return {"models": entries, "areas": AREAS, "orders": result,
            "notice": "Des estimations, pas des mesures : vos notes priment, puis vos projets, les benchmarks publics et, au besoin, "
                      "l’avis d’une IA. Le succès technique des appels est montré à part."}


def set_order(service, data):
    """Your order of preference between models for one area. An empty list returns to the suggested order."""
    area = str(data.get("area") or "")
    if area not in AREAS:
        raise ValueError("Domaine inconnu : " + ", ".join(AREAS) + ".")
    models = data.get("models") or []
    if not isinstance(models, list) or len(models) > 40 or any(not re.fullmatch(r"[a-z0-9._-]{1,80}:[^\n]{0,200}", str(m)) for m in models):
        raise ValueError("Ordre : une liste de modèles « connecteur:modèle », 40 au plus.")
    preferences = dict(service.config.get("model_preferences") or {})
    order = dict(preferences.get("order") or {})
    if models:
        order[area] = list(dict.fromkeys(str(m) for m in models))
    else:
        order.pop(area, None)
    preferences["order"] = order
    service.config["model_preferences"] = preferences
    service.plugins.persist()
    return {"area": area, "order": order.get(area, []),
            "notice": ("Ordre de préférence enregistré pour " + AREAS[area] + " : le chef, l’assistant et l’orchestrateur le lisent."
                       if models else "Ordre de préférence retiré pour " + AREAS[area] + " : l’ordre suggéré s’applique.")}


def _conversation(service):
    current = service.config.get("model_estimates_conversation")
    if current and service.store.rows("SELECT id FROM conversations WHERE id=? AND archived=0", (current,)):
        return current
    project = service.free_workspace()
    conversation = service.action("create_conversation", {"project_id": project, "title": "Estimation des modèles"})["id"]
    service.config["model_estimates_conversation"] = conversation
    service.plugins.persist()
    return conversation


def estimate(service, data):
    """Ask an AI what it knows of a model, area by area, with its uncertainty. One call, on your request."""
    target_connector, target_model = str(data.get("connector") or ""), str(data.get("model") or "")
    if not target_connector or len(target_model) > 200:
        raise ValueError("Modèle à estimer requis.")
    by = str(data.get("by_connector") or "")
    connector = service.engine.connectors.get(by)
    if connector is None or not connector.config.get("enabled", False):
        raise ValueError("IA qui estime : connecteur absent ou désactivé.")
    instruction = ("Estime les capacités du modèle « " + (target_model or "modèle par défaut") + " » (fournisseur ou connecteur « " + target_connector +
                   " ») dans ces domaines, de 0 à 10 : " + ", ".join(k + " (" + v + ")" for k, v in AREAS.items()) + ".\n"
                   "Appuie-toi sur ce que tu sais réellement de ce modèle ou de sa famille ; si tu ne le connais pas, dis-le et reste prudent. "
                   "N’invente ni benchmark ni chiffre public. Réponds uniquement par un bloc ```json {\"areas\": {\"code\": 7, …}, "
                   "\"incertitude\": \"faible|moyenne|forte\", \"notes\": \"deux ou trois phrases : forces, limites\"} ```.")
    conversation = _conversation(service)
    mission = service.action("create_mission", {"conversation_id": conversation, "title": "Estimation · " + target_model,
                                                "steps": [{"name": "Estimation", "connector": by, "model": str(data.get("by_model") or ""),
                                                           "instruction": instruction, "isolated": True}],
                                                "launch": True, "message": "Estimation des capacités de " + target_connector + ":" + target_model + "."})["mission_id"]
    runs = dict(service.config.get("model_estimate_runs") or {})
    runs[_key(target_connector, target_model)] = {"mission_id": mission, "by": by + (":" + str(data["by_model"]) if data.get("by_model") else "")}
    service.config["model_estimate_runs"] = runs
    service.plugins.persist()
    return {"mission_id": mission, "notice": "Estimation demandée à " + by + " : un appel. Elle s’ajoutera aux sources, sans remplacer vos notes."}


def reconcile_estimates(service):
    runs = dict(service.config.get("model_estimate_runs") or {})
    changed = False
    for key, run in list(runs.items()):
        rows = service.store.rows("SELECT status FROM missions WHERE id=?", (run["mission_id"],))
        if rows and rows[0]["status"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            del runs[key]
            changed = True
            if rows[0]["status"] != "succeeded":
                continue
            from .method_lab import _json_object
            result = service.store.rows("SELECT result FROM steps WHERE mission_id=? ORDER BY position DESC LIMIT 1", (run["mission_id"],))
            parsed = _json_object((result[0]["result"] if result else "") or "") or {}
            areas = {a: float(v) for a, v in (parsed.get("areas") or {}).items() if a in AREAS and isinstance(v, (int, float)) and 0 <= v <= 10}
            if areas:
                estimates = dict(service.config.get("model_estimates") or {})
                estimates[key] = {"areas": areas, "uncertainty": str(parsed.get("incertitude", ""))[:20], "notes": str(parsed.get("notes", ""))[:1000],
                                  "by": run.get("by", ""), "at": now()}
                service.config["model_estimates"] = estimates
    if changed:
        service.config["model_estimate_runs"] = runs
        service.plugins.persist()


def model_capabilities_action(service, action, data):
    if action == "model_capabilities":
        if data.get("connector"):
            return capabilities(service, data["connector"], data.get("model", ""))
        return overview(service, data)
    if action == "model_preference_order":
        return set_order(service, data)
    if action == "model_estimate":
        return estimate(service, data)
    return UNHANDLED
