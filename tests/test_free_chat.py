import unittest,shutil,json
from pathlib import Path
from test_core import CoreTests
from cyai.context import build_context
class FreeChatTests(unittest.TestCase):
 def test_isolated_chat_runs_and_survives_restore(self):
  f=CoreTests();f.setUp();roots=[]
  try:
   f.service.action('save_memory',{'project_id':f.project,'content':'PROJECT_SECRET_SENTINEL','validated':True,'source_ids':[]})
   chats=[f.service.action('create_free_conversation',{'title':title}) for title in ('Libre A','Libre B')]
   for chat in chats:roots.append(Path(f.service.project(chat['project_id'])['root']))
   self.assertNotEqual(chats[0]['project_id'],chats[1]['project_id'])
   self.assertTrue(f.service.project(chats[0]['project_id'])['free_chat'])
   f.conversation=chats[0]['id'];result=f.run_job(f.spec());self.assertEqual(result['status'],'succeeded')
   self.assertNotIn('PROJECT_SECRET_SENTINEL',f.connectors['alpha'].calls[-1][0])
   self.assertEqual(f.service.conversation(chats[0]['id'])['title'],'Libre A')
   backup=f.service.action('backup',{});f.service.action('restore',{'backup':backup,'acknowledged':True})
   self.assertTrue(f.service.project(chats[0]['project_id'])['free_chat'])
  finally:
   f.tearDown()
   for root in roots:shutil.rmtree(root,ignore_errors=True)
