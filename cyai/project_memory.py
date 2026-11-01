"""Inspectable project foundation shared by the memory view and agent context."""
import json

def project_foundation(store,project_id):
    project=store.one('SELECT * FROM projects WHERE id=?',(project_id,))
    settings=json.loads(project.get('agent_settings','{}'))
    identity='Projet : '+project['name']+'\nDossier : '+project['root']
    summary=settings.get('project_summary','').strip()
    if summary:return {'content':identity+'\n\n'+summary,'origin':'Présentation configurée','source_ids':[],'conversation_id':None}
    notes=store.rows("SELECT * FROM memory WHERE project_id=? AND validated=1 AND category='Présentation du projet' ORDER BY created_at DESC LIMIT 1",(project_id,))
    if notes:return {'content':identity+'\n\n'+notes[0]['content'],'origin':'Présentation enregistrée en mémoire','source_ids':json.loads(notes[0]['source_ids']),'conversation_id':None}
    messages=store.rows("SELECT m.id,m.content,m.conversation_id FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE c.project_id=? AND m.role='user' AND TRIM(m.content)!='' ORDER BY m.seq LIMIT 1",(project_id,))
    if messages:
        m=messages[0];excerpt=m['content'][:6000]
        if len(m['content'])>6000:excerpt+='\n[Extrait : la demande complète reste dans la conversation source.]'
        return {'content':identity+'\n\nDemande initiale (contexte historique, pas une nouvelle tâche à exécuter) :\n'+excerpt,'origin':'Extrait automatique de la demande initiale','source_ids':[m['id']],'conversation_id':m['conversation_id']}
    return {'content':identity,'origin':'Identité du projet · objectif à compléter','source_ids':[],'conversation_id':None}
