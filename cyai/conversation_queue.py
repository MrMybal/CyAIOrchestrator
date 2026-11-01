"""Durable user outbox and return notices for delegated work."""
import json
from .store import uid, now
BUSY = ('queued','running','awaiting_approval','pausing','paused')


def init(s):
    if 'internal_parent_id' not in {r['name'] for r in s.store.rows('PRAGMA table_info(conversations)')}:
        s.store.execute('ALTER TABLE conversations ADD COLUMN internal_parent_id TEXT')
    s.store.execute("CREATE TABLE IF NOT EXISTS conversation_outbox(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, request_key TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, error TEXT, mission_id TEXT, created_at TEXT NOT NULL)")
    s.store.execute("CREATE TABLE IF NOT EXISTS delegation_returns(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, mission_id TEXT, error TEXT, delivered INTEGER NOT NULL DEFAULT 0)")
    if 'outbox_id' not in {r['name'] for r in s.store.rows('PRAGMA table_info(delegation_returns)')}:
        s.store.execute('ALTER TABLE delegation_returns ADD COLUMN outbox_id TEXT')
    s.store.execute("UPDATE conversation_outbox SET status='interrupted',error='Envoi interrompu : vérifiez la mission associée avant de reprendre.' WHERE status='sending'")


def busy(s, conversation):
    return s.store.rows("SELECT id FROM missions WHERE conversation_id=? AND status IN ('queued','running','awaiting_approval','pausing','paused')", (conversation,))


def enqueue(s, data):
    s.project_for_conversation(data['conversation_id'])
    if not str(data.get('instruction','')).strip(): raise ValueError('Message vide.')
    key = data.get('request_key') or uid()
    with s.engine.lock:
        old = s.store.rows('SELECT id,status,mission_id,conversation_id,payload FROM conversation_outbox WHERE request_key=?',(key,))
        if old:
            if old[0]['conversation_id']!=data['conversation_id'] or json.loads(old[0]['payload'])['instruction']!=data['instruction']:
                raise ValueError('Clé d’envoi déjà utilisée pour une autre demande.')
            return {k:old[0][k] for k in ('id','status','mission_id')} | {'queued':True}
        identifier = uid()
        payload = {k:v for k,v in data.items() if k not in ('send_now','_from_outbox')}
        payload['request_key'] = key
        s.store.execute("INSERT INTO conversation_outbox(id,conversation_id,request_key,payload,status,created_at) VALUES(?,?,?,?,?,?)",(identifier,data['conversation_id'],key,json.dumps(payload),'pending',now()))
    return {'id':identifier,'queued':True,'status':'pending'}


def rows(s, conversation):
    return [{**r,'instruction':json.loads(r.pop('payload'))['instruction']} for r in s.store.rows("SELECT * FROM conversation_outbox WHERE conversation_id=? AND status IN ('pending','failed','interrupted') ORDER BY created_at,rowid",(conversation,))]


def change(s, action, data):
    row=s.store.one('SELECT * FROM conversation_outbox WHERE id=?',(data['id'],))
    s.project_for_conversation(row['conversation_id'])
    with s.engine.lock:
        if row['status'] not in ('pending','failed','interrupted'): raise ValueError('Ce message a déjà été envoyé.')
        if action=='outbox_cancel':
            s.store.execute("UPDATE conversation_outbox SET status='cancelled' WHERE id=?",(row['id'],))
        else:
            s.store.execute("UPDATE conversation_outbox SET status='pending',error=NULL,created_at=? WHERE id=?",('0000' if action=='outbox_send_now' else now(),row['id']))
            if action=='outbox_send_now':
                for mission in busy(s,row['conversation_id']): s.engine.cancel(mission['id'])
    pump(s)
    return {'ok':True}


def track(s, source, result, error=None):
    if not source: return
    target=result.get('mission_id') if isinstance(result,dict) else None
    if target:
        child=s.store.one('SELECT conversation_id FROM missions WHERE id=?',(target,))
        if child['conversation_id']==source:return
    outbox=result.get('id') if isinstance(result,dict) and result.get('queued') else None
    if target or error or outbox:
        s.store.execute('INSERT INTO delegation_returns(id,conversation_id,mission_id,error,outbox_id) VALUES(?,?,?,?,?)',(uid(),source,target,error,outbox))


def pump(s):
    if s.engine.closing.is_set():return
    with s.engine.lock:
        for linked in s.store.rows('SELECT r.id,o.status,o.mission_id,o.error FROM delegation_returns r JOIN conversation_outbox o ON o.id=r.outbox_id WHERE r.delivered=0 AND r.mission_id IS NULL'):
            if linked['status']=='sent':s.store.execute('UPDATE delegation_returns SET mission_id=? WHERE id=?',(linked['mission_id'],linked['id']))
            elif linked['status'] in ('failed','interrupted','cancelled'):s.store.execute('UPDATE delegation_returns SET error=? WHERE id=?',(linked['error'] or linked['status'],linked['id']))
        for source in s.store.rows('SELECT DISTINCT conversation_id FROM delegation_returns WHERE delivered=0'):
            cid=source['conversation_id']
            if busy(s,cid):continue
            if s.store.rows("SELECT id FROM mcp_jobs WHERE conversation_id=? AND status IN ('pending','running')",(cid,)):continue
            pending=s.store.rows('SELECT r.*,m.status,m.title FROM delegation_returns r LEFT JOIN missions m ON m.id=r.mission_id WHERE r.conversation_id=? AND r.delivered=0',(cid,))
            if any(r['status'] in (*BUSY,'pending') or (r['outbox_id'] and not r['mission_id'] and not r['error']) for r in pending):continue
            conversation=s.store.one('SELECT * FROM conversations WHERE id=?',(cid,))
            if conversation['archived']:continue
            if not conversation['agent_id']:
                previous=s.store.rows('SELECT s.connector,s.model FROM steps s JOIN missions m ON m.id=s.mission_id WHERE m.conversation_id=? ORDER BY m.created_at DESC,s.position LIMIT 1',(cid,))
                if not previous:continue
                conversation['agent_id']=previous[0]['connector'];conversation['agent_model']=previous[0]['model']
            notice='Retour automatique des tâches déléguées. Consulte leurs résultats, vérifie les limites et poursuis le travail autorisé. Ne demande pas à l’utilisateur de surveiller leur fin. Un échec reste un échec ; ne relance pas aveuglément une action ayant pu produire des effets.\n'+json.dumps([{k:r[k] for k in ('mission_id','title','status','error')} for r in pending],ensure_ascii=False)
            # The stable request key makes notice creation idempotent across a crash.
            enqueue(s,{'conversation_id':cid,'connector':conversation['agent_id'],'model':conversation['agent_model'],'instruction':notice,'request_key':'return:'+pending[0]['id'],'execution_only':True})
            for r in pending:s.store.execute('UPDATE delegation_returns SET delivered=1 WHERE id=?',(r['id'],))
        for row in s.store.rows("SELECT * FROM conversation_outbox WHERE status='pending' ORDER BY created_at,rowid"):
            if busy(s,row['conversation_id']):continue
            s.store.execute("UPDATE conversation_outbox SET status='sending' WHERE id=?",(row['id'],))
            try:
                result=s.action('continue_conversation',{**json.loads(row['payload']),'_from_outbox':True})
                s.store.execute("UPDATE conversation_outbox SET status='sent',mission_id=?,error=NULL WHERE id=?",(result['mission_id'],row['id']))
            except Exception as exc:
                s.store.execute("UPDATE conversation_outbox SET status='failed',error=? WHERE id=?",(str(exc),row['id']))
