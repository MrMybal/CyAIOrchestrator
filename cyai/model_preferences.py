"""Personal model evaluations, distinct from public benchmark results."""
import json
from pathlib import Path
from datetime import date
from .store import now

AREAS = ('code','interface','debug','raisonnement','tests','documentation','automation','general')

def guidance():
    value=json.loads((Path(__file__).parent/'web'/'model-guidance.json').read_text(encoding='utf-8'))
    value['stale']=(date.today()-date.fromisoformat(value['verified_on'])).days>30
    return value


def catalog(s):
    from .benchmarks import snapshot, matching
    public=snapshot(s)
    ratings=s.config.get('model_ratings',{})
    guide=guidance()
    entries=[]
    for connector,models in s.catalogs.items():
        for m in models:
            key=connector+':'+m['id']
            entries.append({**m,'connector':connector,'key':key,'rating':ratings.get(key,{})})
    for key,rating in ratings.items():
        if not any(m['key']==key for m in entries):
            connector,id=key.split(':',1);entries.append({'connector':connector,'id':id,'name':id,'key':key,'rating':rating,'description':'Fiche personnelle ; disponibilité à actualiser.'})
    for entry in entries:
        provider_guide=guide if entry['connector']=='codex' else next(iter(guide.get('additional_providers',[])),{}) if entry['connector'] in {'claude-code','anthropic'} else {}
        entry['guidance']=provider_guide.get('models',{}).get(entry['id'])
        entry['benchmarks']=matching(public['rows'],entry['id'])
        rows=s.store.rows("SELECT s.status FROM steps s WHERE s.connector=? AND COALESCE((SELECT m.model FROM messages m WHERE m.source_id=s.id AND m.role='assistant' ORDER BY m.seq DESC LIMIT 1),s.model)=?",(entry['connector'],entry['id']))
        entry['observed']={'calls':len(rows),'succeeded':sum(x['status']=='succeeded' for x in rows),'failed':sum(x['status']=='failed' for x in rows)}
    return {'models':entries,'preferences':s.config.get('model_preferences',{}),'updated_at':s.config.get('models_updated_at'),'areas':AREAS,'public_benchmarks':public,'guidance':guide}


def handle(s, action, d):
    if action=='refresh_benchmarks':
        from .benchmarks import refresh
        return refresh(s)
    if action=='model_catalog':
        errors=[]
        if d.get('refresh'):
            ids=[d['connector']] if d.get('connector') else [id for id,c in s.engine.connectors.items() if c.config.get('enabled',True)]
            for id in ids:
                try:s.catalogs[id]=s.engine.connectors[id].models()
                except Exception as e:errors.append({'connector':id,'error':s.engine.secrets.redact(str(e))})
            s.config['models_cache']=s.catalogs;s.config['models_updated_at']=now();s.plugins.persist()
        return {**catalog(s),'errors':errors}
    if action=='model_rating':
        connector=d['connector'];model=str(d['model']).strip()
        if connector not in s.engine.connectors or not model or len(model)>200:raise ValueError('Connecteur ou modèle invalide.')
        preference=d.get('preference','neutral')
        if preference not in {'prefer','neutral','avoid'}:raise ValueError('Préférence invalide.')
        scores={}
        for area,value in d.get('scores',{}).items():
            if area not in AREAS or not 0<=float(value)<=10:raise ValueError('Notes entre 0 et 10.')
            scores[area]=float(value)
        rating={'scores':scores,'preference':preference,'notes':s.engine.secrets.redact(str(d.get('notes',''))[:4000]),'updated_at':now()}
        if d.get('benchmark_score') not in (None,''):
            score=float(d['benchmark_score'])
            source=str(d.get('benchmark_source','')).strip()
            if not 0<=score<=100 or not source:raise ValueError('Benchmark : score sur 100 et source requis.')
            rating.update(benchmark_score=score,benchmark_source=source[:500],benchmark_name=str(d.get('benchmark_name',''))[:200])
        s.config.setdefault('model_ratings',{})[connector+':'+model]=rating;s.plugins.persist()
        return {'ok':True}
    if action=='model_preferences':
        if d.get('priority') not in {'balanced','quality','speed','cost'}:raise ValueError('Priorité invalide.')
        # The orders of preference per area are set elsewhere (model_preference_order): keep them.
        kept={k:v for k,v in (s.config.get('model_preferences') or {}).items() if k=='order'}
        s.config['model_preferences']={**kept,'priority':d['priority'],'instructions':s.engine.secrets.redact(str(d.get('instructions',''))[:5000])};s.plugins.persist()
        return {'ok':True}
    return None


def planning_preferences(s):
    from .benchmarks import snapshot, matching
    guide=guidance()
    documentation='\nInformations de sélection datées, distinctes des préférences et du catalogue réel :\n'+json.dumps(guide,ensure_ascii=False)+'\nNe propose pas un modèle retiré pour la connexion ChatGPT. Ne présume pas une connexion API ou un quota séparé. Ces conseils ne changent pas les préférences utilisateur ; vérifie la disponibilité réelle. Une information ancienne doit être revérifiée, jamais présentée comme une garantie actuelle.\n'
    return documentation+'\nPréférences de sélection de l’utilisateur :\n'+json.dumps({'preferences':s.config.get('model_preferences',{}),'evaluations':s.config.get('model_ratings',{}),'public_benchmarks':[row for models in s.catalogs.values() for model in models for row in matching(snapshot(s).get('rows',[]),model['id'])]},ensure_ascii=False)+'\nUtilise les évaluations par domaine pour répartir le travail ; pour un domaine, preferences.order donne l’ordre de préférence des modèles fixé par l’utilisateur (connecteur:modèle), à suivre quand ils sont disponibles. Évite les modèles marqués avoid, favorise prefer quand adapté. Une note personnelle ou un taux de succès technique ne constitue pas un benchmark public. Explique les choix dans reply. Respecte les efforts et service tiers annoncés ; ne les invente pas.'
