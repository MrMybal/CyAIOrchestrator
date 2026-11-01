"""Logical storage attribution and provider-reported execution statistics."""
import json
from pathlib import Path
from datetime import datetime
from statistics import median
from .security import scoped_workspace


def report(s, project_id, conversation_id=None):
    project=s.store.one('SELECT * FROM projects WHERE id=?',(project_id,))
    conversations=s.store.rows('SELECT * FROM conversations WHERE project_id=?',(project_id,))
    if conversation_id:
        conversations=[c for c in conversations if c['id']==conversation_id]
        if not conversations: raise ValueError('Conversation hors projet.')
    logical={'messages':0,'references':0,'contextes_resultats':0,'evenements':0,'configuration':0}
    media={}; files=[]; models={}; days={}; elapsed=[]; statuses={}; messages_count=0; tool_calls=0; approvals=0
    for c in conversations:
        messages=s.store.rows('SELECT * FROM messages WHERE conversation_id=?',(c['id'],))
        messages_count+=len(messages)
        logical['messages']+=sum(len(m['content'].encode('utf-8')) for m in messages)
        logical['configuration']+=len((c.get('agent_settings','')+c.get('summary','')).encode('utf-8'))
        for f in s.store.rows('SELECT * FROM files WHERE conversation_id=?',(c['id'],)):
            logical['references']+=len(f['content'].encode('utf-8'))
            if f['kind']=='media':
                from .media import locate
                try:
                    _,meta,path=locate(s.store,f['id']);key=str(path)
                    media[key]={'path':key,'bytes':meta['bytes'],'type':'images' if meta['mime'].startswith('image/') else 'videos' if meta['mime'].startswith('video/') else 'autres'}
                except (ValueError,OSError):pass
            paths=[f['name']]
            try:
                obj=json.loads(f['content'])
                if isinstance(obj,dict) and obj.get('image_path'):paths.append(obj['image_path'])
            except ValueError: pass
            if f['kind']=='annotation':paths.extend(line.strip() for line in f['content'].splitlines() if '.cyai-annotations' in line)
            attached=[]
            for raw in paths:
                try:
                    path=scoped_workspace(project['root'],raw,json.loads(c.get('workdirs','[]')))
                    if not path.is_file():continue
                    key=str(path)
                    size=path.stat().st_size
                    suffix=path.suffix.lower()
                    kind='images' if suffix in {'.png','.jpg','.jpeg','.webp','.gif','.bmp','.svg'} else 'videos' if suffix in {'.mp4','.webm','.mov','.avi','.mkv'} else 'autres'
                    media[key]={'path':key,'bytes':size,'type':kind}
                    attached.append(key)
                except (ValueError,OSError):continue
            files.append({'id':f['id'],'name':f['name'],'kind':f['kind'],'conversation':c['title'],'content_bytes':len(f['content'].encode('utf-8')),'paths':attached})
        missions=s.store.rows('SELECT * FROM missions WHERE conversation_id=?',(c['id'],))
        for m in missions:
            statuses[m['status']]=statuses.get(m['status'],0)+1
            day=m['created_at'][:10];d=days.setdefault(day,{'date':day,'missions':0,'input':0,'output':0});d['missions']+=1
            if m['status'] not in {'running','queued','pending','awaiting_approval'}:
                elapsed.append(max(0,(datetime.fromisoformat(m['updated_at'])-datetime.fromisoformat(m['created_at'])).total_seconds()))
            logical['configuration']+=len(m['spec'].encode('utf-8'))
            events=s.store.rows('SELECT kind,data FROM events WHERE mission_id=?',(m['id'],))
            logical['evenements']+=sum(len(e['data'].encode('utf-8')) for e in events)
            tool_calls+=sum(e['kind'] in {'tool','tool_call','tool_started'} for e in events)
            approvals+=sum(e['kind']=='approval_requested' for e in events)
            for step in s.store.rows('SELECT * FROM steps WHERE mission_id=?',(m['id'],)):
                logical['contextes_resultats']+=sum(len((step[k] or '').encode('utf-8')) for k in ('context','result','error','usage'))
                actual=next((x['model'] for x in reversed(messages) if x.get('source_id')==step['id'] and x.get('model')),step['model'])
                key=step['connector']+' / '+(actual or 'défaut')
                g=models.setdefault(key,{'model':actual,'connector':step['connector'],'calls':0,'succeeded':0,'failed':0,'attempts':0,'input':0,'output':0,'cached_input':0,'cache_known':0,'usage_known':0,'cost_usd':0,'cost_known':0})
                g['calls']+=1;g['attempts']+=step['attempts'];g['succeeded']+=step['status']=='succeeded';g['failed']+=step['status']=='failed'
                try:u=json.loads(step['usage'] or 'null')
                except ValueError:u=None
                if isinstance(u,dict):
                    tokens=u.get('last') or u.get('tokens') or u
                    inp=tokens.get('input_tokens',tokens.get('inputTokens',tokens.get('input',tokens.get('prompt_tokens'))))
                    out=tokens.get('output_tokens',tokens.get('outputTokens',tokens.get('output',tokens.get('completion_tokens'))))
                    if isinstance(inp,(int,float)) and isinstance(out,(int,float)):
                        g['input']+=inp;g['output']+=out;g['usage_known']+=1;d['input']+=inp;d['output']+=out
                    cached=tokens.get('cached_input_tokens',tokens.get('cachedInputTokens',tokens.get('cache_read_input_tokens')))
                    if isinstance(cached,(int,float)):g['cached_input']+=cached;g['cache_known']+=1
                    if isinstance(u.get('cost_usd'),(int,float)):g['cost_usd']+=u['cost_usd'];g['cost_known']+=1
    memory=s.store.rows('SELECT content FROM memory WHERE project_id=?',(project_id,))
    media_sizes={k:sum(f['bytes'] for f in media.values() if f['type']==k) for k in ('images','videos','autres')}
    return {'project_id':project_id,'conversation_id':conversation_id,'conversations':len(conversations),'messages':messages_count,'missions':sum(statuses.values()),'statuses':statuses,'models':list(models.values()),'daily':sorted(days.values(),key=lambda d:d['date']),'median_elapsed_seconds':median(elapsed) if elapsed else None,'tool_events':tool_calls,'approval_events':approvals,'storage':{'logical_bytes':sum(logical.values()),'logical_breakdown':logical,'referenced_files_bytes':sum(media_sizes.values()),'media_breakdown':media_sizes,'referenced_files_count':len(media),'shared_memory_bytes':sum(len(m['content'].encode('utf-8')) for m in memory),'database_physical_bytes':sum(p.stat().st_size for p in (s.store.path,Path(str(s.store.path)+'-wal'),Path(str(s.store.path)+'-shm')) if p.exists())},'files':files,'notice':'Tailles logiques des contenus UTF-8, distinctes de la taille physique SQLite commune à tous les projets. Fichiers référencés dédupliqués dans cette vue, sans scanner le dossier de travail. La mémoire du projet est partagée, non additionnée par conversation. Les succès sont des contrôles techniques, pas des notes de qualité. Usage et coûts partiels si non transmis par le fournisseur.'}
