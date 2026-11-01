"""Source-specific benchmark snapshots, never merged with personal ratings."""
import hashlib
import json
from pathlib import Path
import re
import urllib.request
from .store import now

AIDER_URL='https://raw.githubusercontent.com/Aider-AI/aider/main/aider/website/_data/polyglot_leaderboard.yml'
AIDER_PAGE='https://aider.chat/docs/leaderboards/'


def parse_aider(text):
    # The publisher's flat YAML records: read only documented scalar fields.
    rows=[]
    for block in re.split(r'(?m)^- ',text)[1:]:
        fields={}
        for line in block.splitlines():
            match=re.match(r'^  (model|pass_rate_2|date|edit_format|command):\s*(.+)$',line)
            if match:fields[match[1]]=match[2].strip().strip('"').strip("'")
        try: score=float(fields['pass_rate_2'])
        except (KeyError,ValueError):continue
        if not fields.get('model') or not 0<=score<=100:continue
        rows.append({'model':fields['model'],'score':score,'date':fields.get('date',''),
                     'variant':fields.get('edit_format',''),'benchmark':'Aider Polyglot','unit':'% tâches réussies',
                     'source':AIDER_PAGE,'command':fields.get('command','')})
    if not rows:raise ValueError('Format Aider non reconnu ; le cache précédent est conservé.')
    return sorted(rows,key=lambda x:x['score'],reverse=True)


def snapshot(service):
    path=service.store.path.parent/'benchmarks.json'
    if path.is_file():return json.loads(path.read_text(encoding='utf-8'))
    seed=Path(__file__).parent/'web'/'benchmarks-seed.json'
    return json.loads(seed.read_text(encoding='utf-8')) if seed.is_file() else {'rows':[],'updated_at':None}


def refresh(service):
    with urllib.request.urlopen(urllib.request.Request(AIDER_URL,headers={'User-Agent':'CyAI'}),timeout=30) as response:
        raw=response.read(2_000_001)
    if len(raw)>2_000_000:raise ValueError('Source trop volumineuse.')
    result={'rows':parse_aider(raw.decode('utf-8')),'updated_at':now(),'source':AIDER_PAGE,'sha256':hashlib.sha256(raw).hexdigest()}
    path=service.store.path.parent/'benchmarks.json';tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)
    return result


def matching(rows, model):
    # Deliberately avoid fuzzy matching across distinct models or reasoning variants.
    norm=lambda s:re.sub(r'[^a-z0-9]','',s.lower())
    return [r for r in rows if norm(r['model'])==norm(model)]
