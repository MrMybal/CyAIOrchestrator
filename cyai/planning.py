"""Structured, reviewable plans produced by an orchestrator conversation."""
import json


def parse_proposal(text, connectors):
    value = text.strip()
    if value.startswith('```'):
        value = value.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    reply = json.loads(value)
    if not isinstance(reply, dict) or not isinstance(reply.get('reply'), str):
        raise ValueError('L’orchestrateur doit fournir une réponse structurée avec reply et plan.')
    choices = reply.get('choices', [])
    if not isinstance(choices, list) or len(choices)>4 or any(not isinstance(c, str) or not c.strip() or len(c)>300 for c in choices):
        raise ValueError('Proposez au maximum quatre choix textuels de 300 caractères.')
    reply['choices'] = choices
    plan = reply.get('plan')
    if plan is None:
        return reply
    if not isinstance(plan, dict) or not isinstance(plan.get('title'), str):
        raise ValueError('Titre de plan invalide.')
    steps = plan.get('steps')
    if not isinstance(steps, list) or not steps:
        raise ValueError('Le plan doit contenir au moins une tâche.')
    cleaned = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or step.get('connector') not in connectors:
            raise ValueError('Le plan référence un agent inconnu.')
        if not connectors[step['connector']].config.get('enabled', True):
            raise ValueError('Le plan référence un agent désactivé.')
        if not isinstance(step.get('instruction'), str) or not step['instruction'].strip():
            raise ValueError('Chaque tâche doit contenir une instruction.')
        if not isinstance(step.get('model', ''), str):
            raise ValueError('Identifiant de modèle invalide.')
        deps = step.get('depends_on', list(range(i)))
        if not isinstance(deps, list) or any(type(d) is not int or not 0 <= d < i for d in deps):
            raise ValueError('Le graphe doit être sans cycle et ordonné selon ses dépendances.')
        validation = step.get('validation', {})
        if not isinstance(validation, dict) or validation.get('type') not in {None, 'contains', 'json', 'file_exists'}:
            raise ValueError('Contrôle de tâche invalide.')
        cleaned.append({'name': str(step.get('name', f'Tâche {i+1}'))[:120],
            'connector': step['connector'], 'model': step.get('model', ''),
            'instruction': step['instruction'], 'depends_on': deps, 'validation': validation, 'effort':str(step.get('effort','')), 'service_tier':str(step.get('service_tier',''))})
    return {'reply': reply['reply'], 'choices': choices, 'plan': {'title': plan['title'][:200], 'steps': cleaned}}


def planning_instruction(message, catalog, failures):
    return '''Tu es l’orchestrateur du projet. Discute en français avec l’utilisateur et utilise sa mémoire partagée.
Tu peux clarifier l’objectif ou proposer un plan de travail réparti entre les agents disponibles.
Tu es en phase de discussion et planification : ne réalise aucune tâche, ne modifie aucun fichier.
Le travail sera exécuté uniquement après autorisation explicite de l’utilisateur sur le graphe.
Réponds UNIQUEMENT en JSON : {"reply":"Ta réponse à l’utilisateur", "plan":null}.
Si une décision utilisateur manque, ajoute choices: une liste de 2 à 4 réponses courtes, avec la recommandation en premier, et garde plan à null. L’utilisateur peut aussi répondre librement.
Quand l’objectif est assez clair, remplace null par {"title":"Titre", "steps":[{"name":"Tâche", "connector":"identifiant disponible", "model":"modèle disponible ou chaîne vide pour le défaut", "instruction":"Travail précis", "depends_on":[], "validation":{"type":"contains","value":"texte attendu"}}]}.
Les branches indépendantes seront exécutées en parallèle après validation. Répartis leurs modifications dans des fichiers distincts ; ajoute une dépendance lorsque deux tâches modifient les mêmes fichiers. Prévois une étape d’intégration après les branches.
Les dépendances sont les indices zéro des tâches précédentes. Aucun cycle.
Les validations autorisées sont contains, json, file_exists ; omets validation si aucun contrôle mécanique pertinent.
Chaque tâche peut préciser effort et service_tier, uniquement parmi les valeurs annoncées pour le modèle. Laisse vide pour le défaut.
Prévois une tâche de vérification qualitative par une IA quand nécessaire. Ne confonds pas réponse non vide et travail correct.
Choisis les agents et modèles selon leurs capacités, le budget connu et le besoin. N’invente ni disponibilité ni coût.
Si un travail précédent a échoué ou a été jugé insuffisant, analyse le retour et propose une nouvelle répartition,
y compris un autre modèle si pertinent. Conserve le travail réussi et ne propose de refaire que ce qui est nécessaire.
Ne considère jamais un ancien plan comme déjà autorisé. Aucun outil de délégation récursive.
Catalogue (les états installés/non vérifiés ne garantissent pas l’authentification) :
''' + json.dumps(catalog, ensure_ascii=False) + '\nRésultats et erreurs récents :\n' + json.dumps(failures, ensure_ascii=False) + '\nMessage utilisateur :\n' + message


def adjusted_plan(proposal, overrides, connectors, catalogs):
    """Only runtime assignments may change; preserve instructions and graph."""
    import copy
    plan=copy.deepcopy(proposal)
    if not isinstance(overrides,list) or len(overrides)!=len(plan['steps']):
        raise ValueError('Un réglage est requis pour chaque étape.')
    for step, change in zip(plan['steps'],overrides):
        connector=change.get('connector',step['connector'])
        if connector not in connectors or not connectors[connector].config.get('enabled',True):
            raise ValueError('Agent indisponible ou désactivé.')
        model=change.get('model',step.get('model',''))
        info=next((m for m in catalogs.get(connector,[]) if m['id']==model),None)
        if model and not info and (connector,model)!=(step['connector'],step.get('model','')):
            raise ValueError('Actualisez le catalogue avant de choisir ce modèle.')
        effort=change.get('effort','');tier=change.get('service_tier','')
        efforts=[e['reasoningEffort'] for e in (info or {}).get('efforts',[])]
        tiers=[t['id'] for t in (info or {}).get('service_tiers',[])]
        same=(connector,model)==(step['connector'],step.get('model',''))
        if effort and effort not in efforts and not (same and effort==step.get('effort','')):
            raise ValueError('Effort non annoncé pour ce modèle.')
        if tier and tier not in tiers and not (same and tier==step.get('service_tier','')):
            raise ValueError('Vitesse non annoncée pour ce modèle.')
        step.update(connector=connector,model=model,effort=effort,service_tier=tier)
    return plan
