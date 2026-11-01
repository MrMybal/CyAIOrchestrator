"""Managed free-chat workspaces belong to the configured application storage."""
import json,re
from pathlib import Path

def migrate_legacy(s):
 data=s.store.path.parent.resolve();legacy=(data.parent/'CyAI-Discussions').resolve();managed=data/'discussion-workspaces'
 replacements={}
 for p in s.store.rows('SELECT id,root FROM projects WHERE free_chat=1'):
  source=Path(p['root']).resolve()
  if source.parent!=legacy or not re.fullmatch('[a-f0-9]{32}',source.name):continue
  target=(managed/source.name).resolve()
  if not target.is_relative_to(data) or source==target:raise ValueError('Migration du dossier de discussion invalide.')
  managed.mkdir(parents=True,exist_ok=True)
  if source.exists():
   if target.exists():raise ValueError('Deux dossiers existent pour la discussion ; migration interrompue pour éviter tout écrasement.')
   source.rename(target)
  elif not target.is_dir():raise ValueError('Dossier de discussion introuvable.')
  with s.store.transaction() as db:
   db.execute('UPDATE projects SET root=? WHERE id=?',(str(target),p['id']))
   db.execute('UPDATE sessions SET native_id=NULL,last_seq=0 WHERE conversation_id IN (SELECT id FROM conversations WHERE project_id=?)',(p['id'],))
   for f in db.execute("SELECT id,content FROM files WHERE kind='cyannota' AND conversation_id IN (SELECT id FROM conversations WHERE project_id=?)",(p['id'],)).fetchall():
    value=json.loads(f['content']);old=Path(value['image_path']).resolve()
    if old.is_relative_to(source):value['image_path']=str(target/old.relative_to(source));db.execute('UPDATE files SET content=? WHERE id=?',(json.dumps(value,ensure_ascii=False),f['id']))
  replacements[str(source)]=str(target)
 if replacements:
  s.config['allowed_roots']=[replacements.get(str(Path(r).resolve()),r) for r in s.config['allowed_roots']]
  from .security import PathPolicy
  s.engine.policy=PathPolicy(s.config['allowed_roots'],s.engine.policy.protected_roots)
  temp=Path(str(s.config_path)+'.migration-tmp');temp.write_text(json.dumps(s.config,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(s.config_path)
  if legacy.is_dir() and not any(legacy.iterdir()):legacy.rmdir()
