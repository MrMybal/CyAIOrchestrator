import json
import tempfile
import unittest
from pathlib import Path
import evalkit as e

class EvaluationTests(unittest.TestCase):
    def test_oracles(self):
        refs=e.read(e.ROOT/'references.json')
        for form in ['A','B']:
            answers={k:json.dumps(v['expected']) for k,v in refs.items() if v['kind']=='json' and k.endswith('-'+form)}
            report=e.grade(answers,form)
            self.assertEqual(report['expected_cases'],12)
            self.assertEqual(sum(r['status']=='pass' for r in report['results']),8)
            self.assertEqual(sum(r['status']=='not_run' for r in report['results']),4)
        self.assertEqual(refs['planning-A']['expected'],{'minutes':11})
        self.assertEqual(refs['planning-B']['expected'],{'minutes':11})
        self.assertEqual(refs['calcul-A']['expected'],{'total_euros':114})
        self.assertEqual(refs['calcul-B']['expected'],{'total_euros':111})
    def test_reject_wrong_and_format(self):
        for raw in ['{"x":true}','{"x":2}','{"x":1,"y":0}','```json\n{"x":1}\n```','{"x":0,"x":1}','{"x":NaN}']:
            self.assertEqual(e.judge(raw,{'x':1})['status'],'fail',raw)
        self.assertEqual(e.judge('{"x":1.0}',{'x':1})['status'],'pass')
    def test_coverage(self):
        self.assertTrue(all(r['status']=='not_run' for r in e.grade({},'A')['results']))
        report=e.grade({'code-A':'réponse','typo':'réponse'},'A')
        self.assertEqual(report['unknown_ids'],['typo'])
        self.assertEqual(next(r for r in report['results'] if r['id']=='code-A')['status'],'needs_review')
    def test_candidate_separation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'candidate'; e.prepare('A',p)
            self.assertFalse((p/'references.json').exists())
            manifest=e.read(p/'run-manifest.json')
            self.assertEqual(len(manifest),12)
            self.assertEqual(len(next(c for c in manifest if c['id']=='revision-A')['files_in_order']),2)
    def test_context_proofs(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'packet'; e.context(40,701,p)
            packet=(p/'candidate.txt').read_text(encoding='utf8'); oracle=e.read(p/'oracle.private.json')
            for item in oracle.values():
                line=next(l for l in packet.splitlines() if l.startswith(item['preuve']+' |'))
                self.assertIn(str(item['code']) if item['code'] is not None else 'absent',line)
            self.assertEqual(e.judge(json.dumps(oracle),oracle)['status'],'pass')
            wrong=dict(oracle); wrong['DELTA']={'code':9,'preuve':oracle['DELTA']['preuve']}
            self.assertEqual(e.judge(json.dumps(wrong),oracle)['status'],'fail')
            self.assertFalse(e.read(p/'metadata.private.json')['explicit_approval_to_submit'])

if __name__=='__main__': unittest.main()

