import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from cyai.store import Store,uid,now
from cyai.security import PathPolicy
from cyai.free_workspaces import migrate_legacy
class WorkspaceMigrationTests(unittest.TestCase):
 def test_migration_preserves_files_and_protection(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp).resolve();data=base/'chosen-cache';data.mkdir();old=base/'CyAI-Discussions'/uid();old.mkdir(parents=True);(old/'note.txt').write_text('keep me')
   store=Store(data/'cyai.sqlite3');pid=uid();cid=uid();store.execute('INSERT INTO projects(id,name,root,created_at,free_chat) VALUES(?,?,?,?,1)',(pid,'Libre',str(old),now()));store.execute('INSERT INTO conversations(id,project_id,title,created_at) VALUES(?,?,?,?)',(cid,pid,'Title',now()))
   config={'allowed_roots':[str(old)]};s=SimpleNamespace(store=store,config=config,config_path=base/'config.json',engine=SimpleNamespace(policy=PathPolicy([old],[data])))
   migrate_legacy(s);new=Path(store.one('SELECT root FROM projects WHERE id=?',(pid,))['root'])
   self.assertEqual(new.parent,data/'discussion-workspaces');self.assertEqual((new/'note.txt').read_text(),'keep me');self.assertFalse(old.exists());self.assertFalse(old.parent.exists());self.assertEqual(s.engine.policy.project(new),str(new))
   with self.assertRaises(ValueError):s.engine.policy.project(data)
   self.assertEqual(store.one('SELECT title FROM conversations WHERE id=?',(cid,))['title'],'Title');self.assertEqual(json.loads(s.config_path.read_text())['allowed_roots'],[str(new)])
   migrate_legacy(s);store.close()
