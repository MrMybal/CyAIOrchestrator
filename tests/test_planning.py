import json
import unittest
from unittest.mock import Mock
from cyai.planning import parse_proposal


class PlanningTests(unittest.TestCase):
    def test_cycle_and_unknown_connector_rejected(self):
        connectors={'codex':Mock(config={})}
        for step in [{'connector':'codex','instruction':'x','depends_on':[0]}, {'connector':'inconnu','instruction':'x'}]:
            with self.assertRaises(ValueError):
                parse_proposal(json.dumps({'reply':'Plan','plan':{'title':'Test','steps':[step]}}),connectors)

    def test_discussion_does_not_require_plan(self):
        self.assertIsNone(parse_proposal('{"reply":"Quel résultat attendez-vous ?","plan":null}',{})['plan'])

    def test_choices_validate_and_survive_with_plan(self):
        value={'reply':'Choisir','choices':['Rapide','Complet'],'plan':{'title':'P','steps':[{'connector':'a','instruction':'Do'}]}}
        self.assertEqual(parse_proposal(json.dumps(value),{'a':Mock(config={})})['choices'],value['choices'])
        value['choices']=['x']*5
        with self.assertRaises(ValueError):parse_proposal(json.dumps(value),{})

    def test_adjustments_validate_runtime_and_preserve_graph(self):
        from cyai.planning import adjusted_plan
        plan={'title':'P','steps':[{'connector':'a','model':'old','instruction':'Keep','depends_on':[]}]}
        connectors={'a':Mock(config={}), 'off':Mock(config={'enabled':False})}
        catalogs={'a':[{'id':'new','efforts':[{'reasoningEffort':'low'}],'service_tiers':[]}]}
        result=adjusted_plan(plan,[{'connector':'a','model':'new','effort':'low'}],connectors,catalogs)
        self.assertEqual(result['steps'][0]['instruction'],'Keep')
        self.assertEqual(result['steps'][0]['depends_on'],[])
        self.assertEqual(plan['steps'][0]['model'],'old')
        for change in ({'model':'missing'},{'connector':'off'},{'model':'new','effort':'ultra'},{'model':'new','service_tier':'priority'}):
            with self.assertRaises(ValueError):adjusted_plan(plan,[change],connectors,catalogs)
