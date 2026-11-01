import unittest
from cyai.model_memory import estimate

class AdvisoryTests(unittest.TestCase):
 def test_fish_fits_total_despite_low_free(self):
  result = estimate('fish:default', {'gpu_total_gib':24, 'gpu_free_gib':20.5})
  self.assertEqual(result['severity'], 'warning')
  self.assertIn('chargement autorisé', result['warning'])
 def test_red_only_below_minimum(self):
  for total, severity in [(16,'danger'), (20,'warning'), (23.9,'warning'), (24,'')]:
   self.assertEqual(estimate('fish:default', {'gpu_total_gib':total,'gpu_free_gib':total})['severity'], severity)
 def test_unknown_and_cpu(self):
  self.assertEqual(estimate('fish:default', {})['severity'], 'warning')
  self.assertEqual(estimate('piper:test', {})['severity'], '')
