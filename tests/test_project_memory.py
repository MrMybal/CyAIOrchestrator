import json,unittest
import test_core
from cyai.context import build_context
from cyai.project_memory import project_foundation

class ProjectFoundationTests(unittest.TestCase):
 def setUp(self):self.f=test_core.CoreTests();self.f.setUp()
 def tearDown(self):self.f.tearDown()
 def new_chat(self,project=None):return self.f.service.action('create_conversation',{'project_id':project or self.f.project,'title':'Nouvelle'})['id']
 def test_new_chat_receives_saved_project_summary(self):
  f=self.f;f.service.action('save_memory',{'project_id':f.project,'category':'Présentation du projet','content':'Studio multimédia à nœuds','validated':True})
  context=build_context(f.store,self.new_chat(),'Bonjour',{'message_ids':[]},budget=1)
  self.assertIn('Studio multimédia à nœuds',context['text']);self.assertTrue(context['memory_ids'])
 def test_new_chat_gets_initial_objective_without_replaying_entire_chat(self):
  f=self.f;source=f.store.message(f.conversation,'user','Construire un studio visuel');f.store.message(f.conversation,'assistant','Détail secondaire à ne pas copier')
  context=build_context(f.store,self.new_chat(),'Bonjour',{})
  self.assertIn('Construire un studio visuel',context['text']);self.assertNotIn('Détail secondaire',context['text']);self.assertEqual(project_foundation(f.store,f.project)['source_ids'],[source])
 def test_explicit_description_has_priority(self):
  f=self.f;f.store.message(f.conversation,'user','Ancien objectif');f.store.execute('UPDATE projects SET agent_settings=? WHERE id=?',(json.dumps({'project_summary':'Nouvel objectif'}),f.project))
  context=build_context(f.store,self.new_chat(),'Bonjour',{})
  self.assertIn('Nouvel objectif',context['text']);self.assertNotIn('Ancien objectif',context['text'])
 def test_project_scope_is_preserved(self):
  f=self.f;f.store.message(f.conversation,'user','Objectif privé')
  (f.root/'other').mkdir()
  other=f.service.action('create_project',{'name':'Autre','root':str(f.root/'other')})['id']
  self.assertNotIn('Objectif privé',build_context(f.store,self.new_chat(other),'Bonjour',{})['text'])
 def test_the_initial_request_is_not_sent_again_to_a_session_that_already_has_it(self):
  f=self.f;first=f.store.message(f.conversation,'user','Objectif initial détaillé')
  normal=build_context(f.store,f.conversation,'Suite',{})
  self.assertIn('Objectif initial détaillé',normal['text'])
  seq=f.store.one('SELECT seq FROM messages WHERE id=?',(first,))['seq']
  resumed=build_context(f.store,f.conversation,'Suite',{},last_seq=seq)
  self.assertNotIn('Objectif initial détaillé',resumed['text'])
  self.assertIn('déjà présente dans la session native reprise',resumed['text'])
  self.assertIn('Objectif initial détaillé',build_context(f.store,self.new_chat(),'Bonjour',{})['text'],'une autre conversation le reçoit toujours')
