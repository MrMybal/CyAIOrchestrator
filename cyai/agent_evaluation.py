"""Evaluation method and append-only reports tied to an agent. Never launches a candidate implicitly."""
import json
from pathlib import Path
from .store import now, uid

KIT = Path(__file__).parent / 'evaluation_kit'
METHOD_ID = 'cyai-agent-evaluation-v1'

def install(service):
    from .methods import save_method
    if service.store.rows('SELECT id FROM method_templates WHERE id=?', (METHOD_ID,)):
        return {'id': METHOD_ID, 'notice': 'Méthode déjà présente ; vos modifications sont conservées.'}
    protocol = (KIT/'01-PROTOCOLE.md').read_text(encoding='utf-8-sig')
    prompts = (KIT/'02-PROMPTS-OPERATEUR.md').read_text(encoding='utf-8-sig')
    return save_method(service, {
        'id': METHOD_ID, 'name': 'Évaluation d’un agent · diagnostic et mode d’emploi',
        'category': 'Évaluations', 'description': 'Entretien, 12 exercices, comparaison des consignes, rapport signé et fiche pour les prochaines IA. Contexte long sur accord explicite.',
        'preprompt': protocol,
        'usage': 'Dans CyAI, utiliser evaluation_prepare avec la conversation courante et la liste candidates, puis launch_mission. Les candidats travaillent en parallèle dans des sessions internes invisibles ; ne pas créer de discussions visibles par exercice. La fin du lot réveille automatiquement l’évaluateur. Lire evaluation_results, compléter les critères needs_review et enregistrer un rapport signé via evaluation_report_save. Ne pas utiliser continue_conversation pour les exercices, ni le mode planification pour un exercice nommé planning. Choisir une IA évaluatrice, distincte du candidat. Indiquer le profil cible et le périmètre autorisé. La méthode utilise le kit fourni avec CyAI ; elle ne lance aucun test à son installation. Le candidat doit être isolé des corrigés. Si cette isolation ou les appels au candidat ne sont pas disponibles, produire le protocole préparé et les limites, jamais des résultats inventés. Importer le rapport JSON dans la fiche Méthodes de l’agent. Aucun préprompt n’est modifié automatiquement.',
        'requirements': [{'kind': 'note', 'name': 'Évaluateur séparé du candidat ; sessions neuves et accès aux corrigés interdit au candidat.'}],
        'steps': [{'key': 'evaluation', 'name': 'Évaluer et transmettre le mode d’emploi', 'executor': 'any', 'depends_on': [],
                   'instruction': 'Utiliser evaluation_prepare puis launch_mission pour les exercices : sessions internes indépendantes et retour automatique. Lire evaluation_results avant de rédiger le rapport ; ne pas ouvrir une conversation visible par candidat.\n\n' + prompts + '\n\nObjectif demandé : {objectif}\nKit local réservé à l’évaluateur : ' + str(KIT.resolve()) +
                   '\nUtilise les exercices et le correcteur du kit ; joins report-template.json renseigné et un rapport Markdown. Ne place pas les corrigés dans le dossier ou contexte du candidat. Si le périmètre est seulement préparatoire, ne lance aucun appel candidat. Le test approfondi exige un nouveau choix explicite. Enregistrer le rapport via la fiche de l’agent ; identifier clairement les essais non réalisés.'}]},
        source='user', note='Installation du kit d’évaluation 0.1, rapport draft-0.3.')

def ensure_installed(service):
    """Seed once per library; a user deletion remains respected on later starts."""
    with service.store.lock:
        service.store.execute('CREATE TABLE IF NOT EXISTS builtin_methods_seeded (id TEXT PRIMARY KEY)')
        upgrade_builtin(service)
        if service.store.rows('SELECT id FROM builtin_methods_seeded WHERE id=?', (METHOD_ID,)):
            return
        install(service)
        service.store.execute('INSERT OR IGNORE INTO builtin_methods_seeded(id) VALUES(?)', (METHOD_ID,))


def save_report(service, data):
    profile = service.store.one('SELECT id FROM agent_profiles WHERE id=?', (data['profile_id'],))
    report = data.get('report')
    if isinstance(report, str): report = json.loads(report)
    if not isinstance(report, dict): raise ValueError('Rapport JSON attendu.')
    if (report.get('agent') or {}).get('id') != profile['id']:
        raise ValueError('Le champ agent.id du rapport doit désigner ce profil ; ne pas attribuer le bilan à un autre agent.')
    provenance = report.get('provenance') or {}
    authors = provenance.get('contributors') or []
    if not authors or not any(a.get('agent_name') and a.get('roles') for a in authors if isinstance(a, dict)):
        raise ValueError('Indiquez l’IA auteure et ses rôles dans provenance.contributors ; modèle non vérifié accepté à null.')
    if not provenance.get('report_created_at'):
        raise ValueError('Indiquez la date de création du rapport avec son fuseau.')
    from datetime import datetime
    try:
        stamp = datetime.fromisoformat(provenance['report_created_at'].replace('Z', '+00:00'))
        if stamp.utcoffset() is None: raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('Date de création ISO 8601 avec fuseau requise.')
    if not isinstance(report.get('handoff_guide'), dict):
        raise ValueError('La fiche handoff_guide destinée aux prochaines IA est requise.')
    id = uid()
    service.store.execute('INSERT INTO agent_benchmarks(id,profile_id,report,imported_at) VALUES(?,?,?,?)',
                          (id, profile['id'], json.dumps(report, ensure_ascii=False), now()))
    return {'id': id, 'notice': 'Rapport associé à l’agent. Historique conservé ; aucune consigne ni mémoire modifiée.'}

def handle(service, action, data):
    if action == 'evaluation_prepare': return prepare(service,data)
    if action == 'evaluation_results': return results(service,data)
    if action == 'evaluation_method_install': return install(service)
    if action == 'evaluation_report_save': return save_report(service, data)
    if action == 'evaluation_guides':
        service.store.one('SELECT id FROM agent_profiles WHERE id=?', (data['profile_id'],))
        return {'guides': [{
            'report_id': r['id'], 'provenance': json.loads(r['report']).get('provenance'),
            'agent': json.loads(r['report']).get('agent'),
            'guide': json.loads(r['report']).get('handoff_guide'),
            'identity_verified_by_application': False
        } for r in service.store.rows('SELECT id,report FROM agent_benchmarks WHERE profile_id=? ORDER BY imported_at DESC', (data['profile_id'],))],
            'notice': 'Rapports importés : identité des auteurs déclarée, non authentifiée par CyAI. Vérifier modèle, profil et paramètres avant réemploi. Aucun corrigé fourni.'}
    if action == 'evaluation_reports':
        service.store.one('SELECT id FROM agent_profiles WHERE id=?', (data['profile_id'],))
        return {'reports': [{**r, 'report': json.loads(r['report'])} for r in service.store.rows(
            'SELECT * FROM agent_benchmarks WHERE profile_id=? ORDER BY imported_at DESC', (data['profile_id'],))]}
    raise ValueError('Action d’évaluation inconnue.')


def prepare(service,data):
    """A hidden batch, one fresh native session/workdir per candidate and exercise."""
    parent=service.store.one('SELECT * FROM conversations WHERE id=?',(data['conversation_id'],))
    candidates=data.get('candidates') or []
    if not candidates: raise ValueError('Au moins un candidat est requis.')
    form=data.get('form','A')
    if form not in ('A','B'): raise ValueError('Formulaire A ou B attendu. Le contexte long est un protocole séparé, sur accord explicite.')
    cases=[c for c in json.loads((KIT/'exercises.json').read_text(encoding='utf-8-sig')) if c['form']==form]
    steps=[]
    for candidate in candidates:
        if candidate.get('connector') not in service.engine.connectors: raise ValueError('Connecteur candidat inconnu.')
        for case in cases:
            steps.append({'name':(candidate.get('name') or candidate.get('model') or candidate['connector'])+' · '+case['id'],
                'connector':candidate['connector'],'model':candidate.get('model',''),'instruction':case['turns'][0]['content'],
                'depends_on':[], 'isolated':True, 'benchmark_case':case['id'], 'benchmark_turns':[t['content'] for t in case['turns']]})
    if data.get('request_key'):
        previous=service.store.rows('SELECT m.*,c.internal_parent_id FROM missions m JOIN conversations c ON c.id=m.conversation_id WHERE m.request_key=?',(data['request_key'],))
        if previous:
            old=previous[0]
            if old['internal_parent_id']!=parent['id'] or json.loads(old['spec'])['steps']!=steps:
                raise ValueError('Clé d’évaluation déjà utilisée pour un autre lot.')
            return {'mission_id':old['id'],'cases':len(steps),'internal':True}
    # All writes are local preparation; callers launch the returned mission via the normal authorized action.
    cid=uid()
    service.store.execute('INSERT INTO conversations(id,project_id,title,created_at,mode,agent_settings,internal_parent_id) VALUES(?,?,?,?,?,?,?)',
        (cid,parent['project_id'],'Évaluation interne · '+form,now(),'chat',json.dumps({'approval_mode':json.loads(parent['agent_settings']).get('approval_mode',service.engine.approval_default)}),parent['id']))
    try:
        result=service.action('create_mission',{'conversation_id':cid,'title':'Évaluation · '+str(len(candidates))+' candidats · '+str(len(steps))+' exercices',
            'steps':steps,'concurrency':data.get('concurrency',32),'launch':False,'request_key':data.get('request_key') or uid()})
    except Exception:
        service.store.execute('DELETE FROM conversations WHERE id=?',(cid,));raise
    return {**result,'cases':len(steps),'internal':True,'notice':'Lot préparé, pas encore lancé. Utiliser launch_mission : les exercices sont indépendants, sans mode planification ; evaluation_results fournit les réponses et corrections automatiques. Aucun contexte long.'}


def results(service,data):
    import importlib.util
    spec=importlib.util.spec_from_file_location('cyai_evalkit',KIT/'evalkit.py')
    kit=importlib.util.module_from_spec(spec);spec.loader.exec_module(kit)
    mission=service.store.one('SELECT * FROM missions WHERE id=?',(data['mission_id'],))
    steps=json.loads(mission['spec'])['steps'];out=[]
    refs=json.loads((KIT/'references.json').read_text(encoding='utf-8-sig'))
    for row in service.store.rows('SELECT * FROM steps WHERE mission_id=? ORDER BY position',(mission['id'],)):
        case=steps[row['position']].get('benchmark_case')
        if not case:continue
        ref=refs[case]
        grade={'status':'not_run'} if row['status']!='succeeded' else {'status':'needs_review','criteria':ref['criteria']} if ref['kind']=='human' else kit.judge(row['result'],ref['expected'])
        actual=service.store.rows('SELECT model FROM messages WHERE source_id=? ORDER BY seq DESC LIMIT 1',(row['id'],))
        out.append({'requested_model':row['model'],'reported_model':actual[0]['model'] if actual else None,'step_id':row['id'],'case':case,'connector':row['connector'],'model':row['model'],'execution_status':row['status'],
            'answer':row['result'],'error':row['error'],'grade':grade,'usage':json.loads(row['usage']) if row['usage'] else None})
    return {'mission_id':mission['id'],'status':mission['status'],'cases':out,'notice':'Notes automatiques sur les réponses brutes ; les critères humains restent à évaluer. Sessions et contexte CyAI séparés, pas une garantie de cloisonnement système des outils natifs. Conserver les limites dans le rapport signé.'}


def upgrade_builtin(service):
    """Upgrade only the original, untouched installed recipe; keep user revisions intact."""
    from .methods import _load, _body, save_method
    rows=service.store.rows('SELECT * FROM method_templates WHERE id=?',(METHOD_ID,))
    if not rows:return
    row=rows[0]
    if row['revision']!=1 or 'evaluation_prepare' in row['usage']:return
    revision=service.store.one('SELECT body,note FROM method_revisions WHERE method_id=? AND revision=1',(METHOD_ID,))
    if revision['note']!='Installation du kit d’évaluation 0.1, rapport draft-0.3.':return
    body=_body(_load(service,METHOD_ID))
    if body!=json.loads(revision['body']):return
    guide='Dans CyAI, utiliser evaluation_prepare dans la conversation courante avec candidates puis launch_mission : lot parallèle interne, sans discussions visibles. Le lot terminé réveille automatiquement l’évaluateur ; lire evaluation_results, noter les critères needs_review et enregistrer un rapport signé via evaluation_report_save. Ne pas activer le mode planification pour un exercice. Aucun contexte long sans accord explicite. '
    body['usage']=guide+body['usage']
    import re
    for step in body['steps']:
        step['instruction']=guide+'\n\n'+re.sub(r'Kit local réservé à l’évaluateur : [^\n]+',lambda _: 'Kit local réservé à l’évaluateur : '+str(KIT.resolve()),step['instruction'])
    save_method(service,{'id':METHOD_ID,**body},source='user',note='Mise à jour du protocole fourni : évaluation parallèle interne et retour automatique.')
