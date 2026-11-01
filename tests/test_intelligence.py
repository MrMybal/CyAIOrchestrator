import json
import time
import unittest
from unittest.mock import Mock
import test_workspace
from cyai.context import build_context
from cyai.intelligence import effective, capture


class IntelligenceTests(unittest.TestCase):
    setUp = test_workspace.WorkspaceTests.setUp
    tearDown = test_workspace.WorkspaceTests.tearDown
    def test_inheritance_skills_and_override(self):
        self.s.action('agent_settings',{'scope':'project','id':self.p,'settings':{'instructions':'Respecter la convention locale','skills':[{'name':'Tests','content':'Vérifier les cas limites','enabled':True}],'context_chars':7000}})
        self.assertEqual(effective(self.store,self.c)['context_chars'],7000)
        context=build_context(self.store,self.c,'Bonjour',{})
        self.assertIn('Vérifier les cas limites',context['text'])
        self.s.action('agent_settings',{'scope':'conversation','id':self.c,'settings':{'skills':[],'context_chars':3000}})
        self.assertNotIn('Vérifier les cas limites',build_context(self.store,self.c,'Bonjour',{})['text'])
        self.assertEqual(effective(self.store,self.c)['context_chars'],3000)
        self.s.action('agent_settings',{'scope':'conversation','id':self.c,'settings':{}})
        self.assertEqual(effective(self.store,self.c)['context_chars'],7000)

    def test_compaction_keeps_history_and_manual_selection(self):
        old=self.store.message(self.c,'user','Ancien texte exact')
        self.s.action('conversation_summary',{'id':self.c,'summary':'Résumé contrôlé'})
        self.store.message(self.c,'user','Message récent')
        context=build_context(self.store,self.c,'Continuer',{})
        self.assertNotIn('Ancien texte exact',context['text'])
        self.assertIn('Résumé contrôlé',context['text'])
        self.assertIn('Message récent',context['text'])
        self.assertIn('Ancien texte exact',build_context(self.store,self.c,'Continuer',{'message_ids':[old]})['text'])
        self.assertEqual(len(self.s.conversation(self.c)['messages']),2)

    def test_automatic_memory_optin_sources_and_duplicate(self):
        source=self.store.message(self.c,'assistant','Réponse')
        payload={'summary':'Projet en cours','memory':[{'category':'Décisions','content':'Utiliser SQLite'}]}
        result='<cyai-continuity>'+json.dumps(payload)+'</cyai-continuity>'
        self.assertFalse(capture(self.store,self.c,result,source,{}))
        settings={'auto_memory':True,'auto_compact':True}
        self.assertTrue(capture(self.store,self.c,result,source,settings))
        capture(self.store,self.c,result,source,settings)
        notes=self.s.memory(self.p)
        self.assertEqual(len(notes),1)
        self.assertEqual(json.loads(notes[0]['source_ids']),[source])
        self.assertEqual(notes[0]['category'],'Décisions')
        self.assertEqual(notes[0]['automatic'],1)
        self.assertFalse(capture(self.store,self.c,'<cyai-continuity>oops</cyai-continuity>',source,settings))
        self.assertTrue(capture(self.store,self.c,json.dumps({'reply':'ok','plan':None,'cyai_continuity':payload}),source,settings))

    def test_mcp_import_separates_token(self):
        manifest=dict(self.s.config['plugins']['cyaicodex'])
        block=json.dumps({'mcpServers':{'methodes':{'type':'http','url':'http://127.0.0.1:8765/mcp','headers':{'Authorization':'Bearer test-import-secret'}}}})
        self.s.action('plugin_save',{'manifest':manifest,'mcp_config':block})
        self.engine.secrets.set.assert_called_with('plugin:cyaicodex','test-import-secret')
        self.assertNotIn('test-import-secret',self.s.config_path.read_text(encoding='utf-8'))
        with self.assertRaises(ValueError):self.s.action('plugin_save',{'manifest':manifest,'mcp_config':block.replace('127.0.0.1','example.org')})

    def test_custom_theme_validation(self):
        self.s.action('save_theme',{'name':'Sable',**{k:'#abcdef' for k in ('bg','panel','text','muted','accent','line')}})
        theme=self.s.config['settings']['theme']
        self.s.action('save_settings',{'theme':theme})
        with self.assertRaises(ValueError):self.s.action('save_theme',{'name':'Erreur','bg':'url(https://example.org)'})

    def test_engine_captures_continuity_after_success(self):
        self.s.action('agent_settings',{'scope':'project','id':self.p,'settings':{'auto_memory':True,'auto_compact':True,'fresh_session':True}})
        output='Réponse utile<cyai-continuity>'+json.dumps({'summary':'Décision retenue','memory':[{'category':'Architecture','content':'Moteur local'}]})+'</cyai-continuity>'
        connector=Mock(config={'enabled':True,'model':''},run=Mock(return_value=output))
        self.engine.connectors['fake']=connector
        id=self.engine.create({'conversation_id':self.c,'steps':[{'connector':'fake','instruction':'Répondre'}]})
        self.engine.launch(id)
        deadline=time.time()+5
        while time.time()<deadline:
            status=self.store.one('SELECT status FROM missions WHERE id=?',(id,))['status']
            if status in ('succeeded','failed'):break
            time.sleep(.03)
        self.assertEqual(status,'succeeded')
        self.assertEqual(self.s.conversation(self.c)['summary'],'Décision retenue')
        self.assertEqual(self.s.memory(self.p)[0]['content'],'Moteur local')
        self.assertIn('<cyai-continuity>',connector.run.call_args.args[0])

    def test_legacy_backup_migrates_new_fields(self):
        self.s.action('save_memory',{'project_id':self.p,'content':'Ancienne note','validated':True})
        backup=self.s.action('backup',{})
        for table,keys in {'projects':['agent_settings'],'conversations':['agent_settings','summary','summary_seq'],'memory':['category','automatic']}.items():
            for row in backup['tables'][table]:
                for key in keys:row.pop(key,None)
        self.s.action('restore',{'backup':backup,'acknowledged':True})
        self.assertEqual(self.s.memory(self.p)[0]['category'],'Général')
        self.assertEqual(self.s.conversation(self.c)['summary'],'')
