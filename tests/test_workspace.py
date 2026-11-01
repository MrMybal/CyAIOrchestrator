import base64
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock
from cyai.engine import Engine
from cyai.store import Store
from cyai.service import Service
from cyai.security import PathPolicy, scoped_workspace
from cyai.workspace import git_status

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.store=Store(self.root/'db.sqlite3')
        self.engine=Engine(self.store,{},PathPolicy([self.root]),Mock(redact=lambda v:v))
        self.s=Service(self.store,self.engine,{'allowed_roots':[str(self.root)]},self.root/'config.json')
        self.p=self.s.action('create_project',{'name':'Test','root':str(self.root)})['id']
        self.c=self.s.action('create_conversation',{'project_id':self.p,'title':'Test'})['id']
    def tearDown(self):
        self.engine.shutdown();self.store.close();self.tmp.cleanup()
    def test_organization_and_backup_roundtrip(self):
        self.s.action('category',{'name':'Outils'})
        self.s.action('organize',{'kind':'project','id':self.p,'favorite':True,'color':'#ff3344','icon':'X','category':'Outils'})
        self.s.action('organize',{'kind':'conversation','id':self.c,'archived':True})
        backup=self.s.action('backup',{})
        self.s.action('restore',{'backup':backup,'acknowledged':True})
        row=self.store.one('SELECT * FROM projects WHERE id=?',(self.p,))
        self.assertEqual(row['color'],'#ff3344');self.assertEqual(row['favorite'],1)
        self.assertEqual(self.s.conversation(self.c)['archived'],1)
        self.s.action('category',{'old':'Outils','name':'Applications'})
        self.assertEqual(self.store.one('SELECT category FROM projects WHERE id=?',(self.p,))['category'],'Applications')
    def test_reorder_rejects_missing_or_cross_project_items(self):
        second=self.s.action('create_conversation',{'project_id':self.p,'title':'Deux'})['id']
        self.s.action('reorder',{'kind':'conversation','project_id':self.p,'ids':[second,self.c]})
        self.assertEqual(self.s.state()['conversations'][0]['id'],second)
        with self.assertRaises(ValueError):self.s.action('reorder',{'kind':'conversation','project_id':self.p,'ids':[self.c]})
    def test_multi_directory_scope_and_session_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            other=Path(directory);(other/'allowed.txt').write_text('ok')
            self.s.action('conversation_workdirs',{'id':self.c,'workdirs':[directory]})
            self.assertEqual(scoped_workspace(self.root,str(other/'allowed.txt'),[directory]),(other/'allowed.txt').resolve())
            with self.assertRaises(ValueError):scoped_workspace(self.root,str(other/'allowed.txt'),[])
            (other/'.env').write_text('secret')
            with self.assertRaises(ValueError):scoped_workspace(self.root,str(other/'.env'),[directory])
            self.assertEqual(json.loads(self.s.conversation(self.c)['workdirs']),[str(other.resolve())])
    def test_plugin_toggle_preserves_binding_and_other_project(self):
        self.s.plugins.rpc=Mock(return_value={'content':[{'type':'text','text':json.dumps({'projects':[{'id':'bible','name':'Bible'}]})}]})
        self.s.plugins.bind({'id':'cyprojectcodex','project_id':self.p,'external_project_id':'bible','auto_memory':True,'enabled':True})
        self.s.plugins.bind({'id':'cyprojectcodex','project_id':self.p,'enabled':False})
        b=self.s.plugins.config['plugins']['cyprojectcodex']['projects'][self.p]
        self.assertEqual(b['external_project_id'],'bible');self.assertTrue(b['auto_memory']);self.assertFalse(b['enabled'])
    def test_annotation_save_reopen_and_scope(self):
        image='data:image/png;base64,'+base64.b64encode(b'\x89PNG\r\n\x1a\n').decode()
        doc={'version':1,'annotations':[{'id':'a','text':'Corriger'}]}
        result=self.s.action('annotation_save',{'conversation_id':self.c,'name':'capture.png','image':image,'document':doc})
        opened=self.s.action('annotation_open',{'conversation_id':self.c,'id':result['id']})
        self.assertEqual(opened['document'],doc);self.assertEqual(opened['image'],image)
        other=self.s.action('create_conversation',{'project_id':self.p,'title':'Autre'})['id']
        with self.assertRaises(ValueError):self.s.action('annotation_open',{'conversation_id':other,'id':result['id']})
        self.s.plugins.bind({'id':'cyannota','project_id':self.p,'enabled':False})
        with self.assertRaises(ValueError):self.s.action('annotation_open',{'conversation_id':self.c,'id':result['id']})
    @unittest.skipUnless(shutil.which('git'),'Git absent')
    def test_git_initialization_does_not_commit(self):
        self.assertFalse(git_status(str(self.root))['repository'])
        result=self.s.action('git_init',{'project_id':self.p})
        self.assertTrue(result['repository'])
        self.assertFalse((self.root/'.git/refs/heads/master').exists())


    def test_logs_filter_and_redact_details(self):
        self.store.log('error','connector.test','Failure SECRET-TEST')
        self.store.log('info','settings','Done')
        self.engine.secrets.redact=lambda value:json.loads(json.dumps(value).replace('SECRET-TEST','[redacted]'))
        result=self.s.logs({'level':'error','source':'application','text':'connector'})
        self.assertEqual(len(result['entries']),1)
        self.assertEqual(result['entries'][0]['detail'],'Failure [redacted]')
