import unittest
from unittest.mock import Mock
from cyai.connectors import mcp_elicitation_response


class ElicitationTests(unittest.TestCase):
    def test_browser_consent_reaches_user_approval(self):
        data = {'mode':'form','serverName':'cua_repl','message':'Allow access?',
                'requestedSchema':{'type':'object','properties':{}},
                '_meta':{'origin':'http://127.0.0.1:8766','persist':'always'}}
        control = Mock()
        control.approve.return_value = True
        self.assertEqual(mcp_elicitation_response(data,control),{'action':'accept','content':{}})
        self.assertEqual(control.approve.call_args.args[0]['request'],data)
        control.approve.return_value = False
        self.assertEqual(mcp_elicitation_response(data,control),{'action':'decline'})

    def test_form_answers_and_external_login_are_never_fabricated(self):
        control = Mock()
        for data in [{'mode':'url','url':'https://example.test/login'},
                     {'mode':'form','requestedSchema':{'type':'object','properties':{'name':{'type':'string'}}}}]:
            self.assertEqual(mcp_elicitation_response(data,control),{'action':'cancel'})
        control.approve.assert_not_called()
