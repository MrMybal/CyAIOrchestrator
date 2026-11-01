import copy
import json
import unittest
import test_core
from cyai.agent_evaluation import KIT

class AgentEvaluationTests(unittest.TestCase):
 def setUp(self):
  self.fixture=test_core.CoreTests();self.fixture.setUp();self.s=self.fixture.service
  self.id=self.s.action('agent_profile_save',{'name':'Candidat','role':'consultant','connector':'alpha','prompt':'Consignes originales'})['id']
 def tearDown(self):self.fixture.tearDown()
 def report(self):
  r=json.loads((KIT/'report-template.json').read_text(encoding='utf8'))
  r['agent']['id']=self.id
  r['provenance']['report_created_at']='2026-09-19T20:00:00+02:00'
  r['provenance']['contributors'][0].update(agent_name='Juge',roles=['evaluation','rédaction'])
  return r
 def test_install_idempotent_preserves_edits_no_execution(self):
  a=self.s.action('evaluation_method_install',{});b=self.s.action('evaluation_method_install',{})
  self.assertEqual(a['id'],b['id']);self.assertEqual(len(self.s.store.rows('SELECT * FROM method_templates')),1)
  self.assertEqual(self.s.store.rows('SELECT * FROM missions'),[])
 def test_startup_seeds_once_and_preserves_edits_and_deletion(self):
  from cyai.agent_evaluation import ensure_installed, METHOD_ID
  from cyai.app_mcp import ACTIONS
  ensure_installed(self.s)
  self.s.store.execute('UPDATE method_templates SET preprompt=? WHERE id=?', ('Mes consignes',METHOD_ID))
  ensure_installed(self.s);self.s.action('evaluation_method_install',{})
  self.assertEqual(self.s.store.one('SELECT preprompt FROM method_templates WHERE id=?',(METHOD_ID,))['preprompt'],'Mes consignes')
  self.s.action('method_delete',{'id':METHOD_ID})
  ensure_installed(self.s)
  self.assertEqual(self.s.store.rows('SELECT * FROM method_templates'),[])
  self.assertEqual(self.s.store.rows('SELECT * FROM missions'),[])
  self.assertEqual(ACTIONS['evaluation_method_install']['scope'],'global')
  self.assertTrue(ACTIONS['evaluation_method_install']['write'])
 def test_provenance_required_and_profile_binding(self):
  r=self.report();r['agent']['id']='other'
  with self.assertRaises(ValueError):self.s.action('evaluation_report_save',{'profile_id':self.id,'report':r})
  r=self.report();r['provenance']['report_created_at']='2026-09-19'
  with self.assertRaises(ValueError):self.s.action('evaluation_report_save',{'profile_id':self.id,'report':r})
 def test_history_backup_guides_and_no_prompt_mutation(self):
  r=self.report();r['private_reference']='NE PAS TRANSMETTRE'
  for _ in range(2):self.s.action('evaluation_report_save',{'profile_id':self.id,'report':r})
  reports=self.s.action('evaluation_reports',{'profile_id':self.id})['reports'];self.assertEqual(len(reports),2)
  self.assertNotIn('NE PAS TRANSMETTRE',json.dumps(self.s.action('evaluation_guides',{'profile_id':self.id})))
  self.assertEqual(self.s.action('agent_profile_get',{'id':self.id})['prompt'],'Consignes originales')
  self.assertEqual(len(self.s.action('backup',{})['tables']['agent_benchmarks']),2)

if __name__=='__main__':unittest.main()
