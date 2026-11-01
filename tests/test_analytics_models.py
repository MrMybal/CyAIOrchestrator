import json
import unittest
from unittest.mock import Mock, patch
import test_workspace
from cyai.analytics import report
from cyai.intelligence import capture
from cyai.connectors import Codex, Control


class AnalyticsModelsTests(unittest.TestCase):
    setUp=test_workspace.WorkspaceTests.setUp
    tearDown=test_workspace.WorkspaceTests.tearDown

    def test_storage_deduplicates_media_and_scopes_conversation(self):
        image=self.root/'image.png';image.write_bytes(b'1234567890')
        self.store.message(self.c,'user','été')
        for i in range(2):self.store.execute('INSERT INTO files VALUES(?,?,?,?,?,?)',(str(i),self.c,'capture',json.dumps({'image_path':str(image)}),'annotation','2026-01-01T00:00:00+00:00'))
        second=self.s.action('create_conversation',{'project_id':self.p,'title':'Autre'})['id']
        self.store.message(second,'user','Autre conversation')
        result=report(self.s,self.p,self.c)
        self.assertEqual(result['messages'],1)
        self.assertEqual(result['storage']['logical_breakdown']['messages'],len('été'.encode()))
        self.assertEqual(result['storage']['referenced_files_bytes'],10)
        self.assertEqual(result['storage']['referenced_files_count'],1)
        with self.assertRaises(ValueError):report(self.s,self.p,'other')

    def test_ratings_reach_planner_and_do_not_invent_benchmark(self):
        self.engine.connectors['fake']=Mock(config={'enabled':True},models=Mock(return_value=[{'id':'test','description':'Test model'}]))
        result=self.s.action('model_catalog',{'refresh':True,'connector':'fake'})
        self.assertEqual(result['models'][0]['rating'],{})
        self.s.action('model_rating',{'connector':'fake','model':'test','scores':{'tests':9},'preference':'prefer'})
        from cyai.model_preferences import planning_preferences
        self.assertIn('"tests": 9.0',planning_preferences(self.s))
        with self.assertRaises(ValueError):self.s.action('model_rating',{'connector':'fake','model':'test','scores':{'tests':11}})
        with self.assertRaises(ValueError):self.s.action('model_rating',{'connector':'fake','model':'test','benchmark_score':80})

    def test_documented_guidance_is_scoped_and_preserves_preferences(self):
        from cyai.model_preferences import catalog, planning_preferences
        self.s.catalogs={'codex':[{'id':'gpt-5.4'}],'claude-code':[{'id':'claude-sonnet-5'},{'id':'sonnet'}],'anthropic':[{'id':'claude-haiku-4-5-20251001'}],'fake':[{'id':'claude-sonnet-5'}]}
        ratings={'claude-code:claude-sonnet-5':{'preference':'avoid','notes':'Personal'}}
        self.s.config['model_ratings']=ratings.copy()
        result=catalog(self.s)
        rows={m['key']:m for m in result['models']}
        self.assertIsNotNone(rows['claude-code:claude-sonnet-5']['guidance'])
        self.assertIsNotNone(rows['anthropic:claude-haiku-4-5-20251001']['guidance'])
        self.assertIsNone(rows['claude-code:sonnet']['guidance'])
        self.assertIsNone(rows['fake:claude-sonnet-5']['guidance'])
        self.assertEqual(self.s.config['model_ratings'],ratings)
        prompt=planning_preferences(self.s)
        for value in ('gpt-5.4','claude-sonnet-5','Agent SDK','avoid','verified_on'):
            self.assertIn(value,prompt)

    def test_ai_skills_are_saved_inactive_with_source(self):
        source=self.store.message(self.c,'assistant','Automation testée')
        result='<cyai-continuity>'+json.dumps({'skills':[{'name':'Vérifier UI','content':'# Test\nExécuter le script de test.'}]})+'</cyai-continuity>'
        capture(self.store,self.c,result,source,{'capture_skills':True})
        skills=json.loads(self.s.project(self.p)['agent_settings'])['skills']
        self.assertEqual(len(skills),1);self.assertFalse(skills[0]['enabled']);self.assertEqual(skills[0]['source_id'],source)

    def test_codex_effort_and_speed_are_transmitted(self):
        calls=[]
        class RPC:
            def __init__(self,*a):pass
            def request(self,method,params):
                calls.append((method,params))
                if method=='model/list':return {'data':[{'model':'test','supportedReasoningEfforts':[{'reasoningEffort':'ultra'}],'serviceTiers':[{'id':'priority'}]}]}
                return {'thread':{'id':'native'},'model':'test','turn':{'id':'turn'}}
            def send(self,v):pass
            def next(self):return {'method':'turn/completed','params':{'turn':{'status':'completed'}}}
            def close(self):pass
        control=Control(10,lambda _:False,lambda *_:None);control.effort='ultra';control.service_tier='priority'
        with patch('cyai.connectors.JsonProcess',RPC),patch('cyai.connectors.executable',return_value=['codex']),patch.object(Codex,'configuration',return_value={'mcp_servers':{}}):
            Codex('codex',{},Mock()).run('Test',str(self.root),'test',None,control)
        params=next(p for m,p in calls if m=='turn/start')
        self.assertEqual(params['effort'],'ultra');self.assertEqual(params['serviceTier'],'priority')

    def test_web_bootstrap_only_uses_local_application_token(self):
        import sqlite3
        db=sqlite3.connect(self.root/'methodes.sqlite3');db.execute('CREATE TABLE settings(key,value)');db.execute("INSERT INTO settings VALUES('admin_token','local-bootstrap')");db.commit();db.close()
        p=self.s.config['plugins']['cyaicodex'];p['web_data_dir']=str(self.root);p['web_url']='http://127.0.0.1:8765/'
        self.assertTrue(self.s.plugins.web_url('cyaicodex')['url'].endswith('#token=local-bootstrap'))
        p['web_url']='https://example.org/'
        self.assertNotIn('local-bootstrap',self.s.plugins.web_url('cyaicodex')['url'])
