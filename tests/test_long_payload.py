import time,unittest
import test_core
from cyai.methods import _text,MAX_INPUT_CHARS,wired_inputs

class LongPayloadTests(unittest.TestCase):
    def test_large_instruction_reaches_connector_intact(self):
        f=test_core.CoreTests();f.setUp()
        try:
            corpus='START_CORPUS\n'+('fiche 0123456789 abcdefghijklmnop\n'*16000)+'END_CORPUS'
            self.assertGreater(len(corpus),461544)
            self.assertEqual(_text(corpus,MAX_INPUT_CHARS,'Corpus'),corpus)
            mid=f.service.action('create_mission',{'conversation_id':f.conversation,'steps':[{'connector':'alpha','instruction':corpus}],'launch':True})['mission_id']
            deadline=time.monotonic()+15
            while time.monotonic()<deadline and f.service.mission(mid)['status'] not in ('succeeded','failed'):time.sleep(.02)
            self.assertEqual(f.service.mission(mid)['status'],'succeeded')
            self.assertIn(corpus,f.connectors['alpha'].calls[0][0])
            step=f.store.one('SELECT * FROM steps WHERE mission_id=?',(mid,))
            self.assertEqual(step['instruction'],corpus)
            f.store.execute('UPDATE steps SET result=? WHERE id=?',(corpus,step['id']))
            self.assertIn(corpus,wired_inputs(f.store,mid,[{'from':0,'name':'Corpus','kind':'context'}]))
        finally:f.tearDown()
