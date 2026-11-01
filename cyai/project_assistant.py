"""The project assistant: the first conversation of a project, above the others, to set it up and keep it going.

It is an ordinary conversation of the project — any AI you choose answers in it — with a skill that says what it is
for: understand a project taken over (by reading its folder), frame a new one, write its presentation and its
instructions, compose its team, prepare its first cards. It acts through the CyAI MCP, so every write goes through
your authorisation, like any agent's. Nothing is created without you.
"""
UNHANDLED = object()

PURPOSE = "assistant"
TITLE = "Assistant du projet"
SKILL = "Assistant du projet"
SKILL_TEXT = """Tu es l’assistant de ce projet dans CyAI Orchestrator. Ton rôle : aider l’utilisateur à mettre le projet en place, puis à le faire avancer.

- Reprise d’un projet existant : explore d’abord le dossier du projet (structure, fichiers clés, README et documentation, configuration, historique git s’il existe). Résume ce que tu as compris, ce qui manque ou semble inachevé, puis propose la suite. N’invente rien que tu n’as pas lu.
- Nouveau projet : pose les questions utiles (but, public, contraintes, technologies, livrables, échéances) avant de proposer un plan.
- Mise en place : propose une présentation du projet et des consignes pour ses agents, puis enregistre-les avec l’accord de l’utilisateur (action agent_settings, scope « project », réglages project_summary et instructions). Tu peux noter les décisions importantes en mémoire (save_memory).
- Équipe : propose les rôles (chef de projet, leads, membres), en réutilisant les profils de la bibliothèque (agent_profile_list) ou en en créant (agent_profile_save), puis compose l’équipe (team_save, team_add_member). Tu peux préparer les premières cartes du board (task_create) et appliquer une méthode de la bibliothèque (method_list, method_apply).
- Tu agis par le MCP CyAI : cyai_actions pour découvrir les actions, cyai_call pour les appeler. Dis toujours ce que tu vas créer ou modifier avant de le faire ; chaque écriture passe par l’autorisation de l’utilisateur."""


def find(service, project_id):
    rows = service.store.rows("SELECT id FROM conversations WHERE project_id=? AND purpose=? AND archived=0 ORDER BY created_at LIMIT 1",
                              (project_id, PURPOSE))
    return rows[0]["id"] if rows else None


def ensure(service, project_id):
    """The project's assistant conversation, created the first time it is asked for."""
    project = service.store.one("SELECT id,free_chat FROM projects WHERE id=?", (project_id,))
    if project["free_chat"]:
        raise ValueError("Une discussion libre n’a pas d’assistant de projet.")
    existing = find(service, project["id"])
    if existing:
        return {"conversation_id": existing, "created": False}
    conversation = service.action("create_conversation", {"project_id": project["id"], "title": TITLE})["id"]
    service.store.execute("UPDATE conversations SET purpose=?, position=-1 WHERE id=?", (PURPOSE, conversation))
    service.action("agent_settings", {"scope": "conversation", "id": conversation,
                                      "settings": {"skills": [{"name": SKILL, "content": SKILL_TEXT, "enabled": True, "source_id": "project-assistant"}]}})
    return {"conversation_id": conversation, "created": True,
            "notice": "Assistant du projet prêt : dites-lui s’il s’agit d’une reprise ou d’un nouveau projet."}


def fresh(service, conversation_id):
    """Still to be met: nothing written to it yet."""
    return not service.store.rows("SELECT id FROM messages WHERE conversation_id=? AND role='user' LIMIT 1", (conversation_id,))


def project_assistant_action(service, action, data):
    if action == "project_assistant":
        return ensure(service, data["project_id"])
    return UNHANDLED
