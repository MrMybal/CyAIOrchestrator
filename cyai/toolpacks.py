"""Tool packs: the plugins a profile may use directly while it works.

A modeller that must drive Blender, an imager that must call a generation service: those capabilities
live in MCP plugins configured once in CyAI. A profile declares which plugins it may use; when it runs,
their tools are exposed to it — and only to it — under the names `outil__<plugin>__<tool>`.

Same policy as everywhere else in CyAI:

* a plugin must be enabled, and not disabled for the project the agent works in;
* a tool listed as read-only by the plugin runs without asking; any other tool goes through the
  approval policy of the conversation, exactly like a native tool of the agent;
* every call is recorded as an event of the step;
* a specialist called by the agent gets no tool pack of its own.

A declared tool pack is a permission, not a capability test: CyAI does not check that the plugin does
what its name says.
"""
import json

PREFIX = "outil__"


def _plugin_ids(service):
    return set(service.plugins.config.get("plugins", {}))


def validate(service, value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Les outils d’un profil sont une liste d’identifiants de plugins.")
    known = _plugin_ids(service) if service is not None else None
    tools = []
    for item in value:
        id = str(item or "").strip()
        if not id or id in tools:
            continue
        if known is not None and id not in known:
            raise ValueError("Plugin inconnu : « " + id[:40] + " ». Configurez-le d’abord dans Données & paramètres → Plugins.")
        tools.append(id)
    return tools


def available(service, project_id, definition):
    """The declared packs that can actually be used here, with the reason when one cannot."""
    packs = []
    for id in definition.get("tools", []) or []:
        entry = {"id": id, "ready": False, "reason": ""}
        try:
            plugin = service.plugins.plugin(id, project_id)
            entry.update({"ready": True, "name": plugin.get("name", id), "read_tools": list(plugin.get("read_tools", []))})
        except ValueError as exc:
            entry["reason"] = str(exc)
        packs.append(entry)
    return packs


def exposed(service, grant):
    """Tool definitions for the declared packs, discovered once per step."""
    if "tool_cache" in grant:
        return grant["tool_cache"]
    listed = []
    for pack in grant.get("packs") or []:
        if not pack["ready"]:
            continue
        try:
            plugin = {**service.plugins.plugin(pack["id"], grant["projects"][0]), "_cytools_scope": grant["projects"][0]}
            tools = service.plugins.rpc(plugin, "tools/list", {}).get("tools", [])
        except Exception:
            continue
        for tool in tools:
            name = tool.get("name", "")
            if not name:
                continue
            read_only = name in pack.get("read_tools", [])
            listed.append({"name": PREFIX + pack["id"] + "__" + name,
                           "description": "[" + pack.get("name", pack["id"]) + (" · lecture" if read_only else " · peut agir, soumis à autorisation") +
                                          "] " + tool.get("description", "") + (" " + plugin.get("instructions", "") if plugin.get("cytools") else ""),
                           "inputSchema": tool.get("inputSchema") or {"type": "object"},
                           "annotations": {"readOnlyHint": read_only, "destructiveHint": not read_only}})
    grant["tool_cache"] = listed
    return listed


def call(service, grant, name, arguments):
    if not name.startswith(PREFIX):
        raise ValueError("Outil inconnu.")
    plugin_id, _, tool = name[len(PREFIX):].partition("__")
    pack = next((p for p in grant.get("packs") or [] if p["id"] == plugin_id), None)
    if pack is None:
        raise ValueError("Ce plugin ne fait pas partie des outils déclarés pour cet agent.")
    if not pack["ready"]:
        raise ValueError("Plugin indisponible : " + pack["reason"])
    control = grant.get("control")
    if control is None:
        raise ValueError("Les outils d’un profil ne s’utilisent que pendant son exécution.")
    control.check()
    plugin = {**service.plugins.plugin(plugin_id, grant["projects"][0]), "_cytools_scope": grant["projects"][0]}
    read_only = tool in plugin.get("read_tools", [])
    emit = getattr(control, "emit", None)
    if not read_only:
        approve = getattr(control, "approve", None)
        if not approve or not approve({"provider": "Plugin " + plugin.get("name", plugin_id), "tool": tool,
                                       "request": {"arguments": arguments,
                                                   "reason": "Outil du profil en cours d’exécution, déclaré dans sa boîte à outils."}}):
            if emit:
                emit("tool_refused", {"plugin": plugin_id, "tool": tool})
            raise ValueError("Utilisation de « " + tool + " » refusée. Poursuivez sans cet outil et dites-le dans votre réponse.")
    if emit:
        emit("tool_called", {"plugin": plugin_id, "tool": tool, "read_only": read_only,
                             "arguments": json.dumps(arguments, ensure_ascii=False)[:2000]})
    result = service.plugins.rpc(plugin, "tools/call", {"name": tool, "arguments": arguments or {}})
    if emit:
        emit("tool_answered", {"plugin": plugin_id, "tool": tool,
                               "error": bool(result.get("isError")) if isinstance(result, dict) else False})
    return result
