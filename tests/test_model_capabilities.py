import time
import unittest

import test_core
from cyai import app_mcp
from cyai.model_preferences import planning_preferences


class ModelCapabilityTests(unittest.TestCase):
    """An idea of each model from several sources, your scores first, and your order of preference per area."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        for connector in self.s.engine.connectors.values():
            connector.config["enabled"] = True

    def tearDown(self):
        self.fixture.tearDown()

    def area(self, result, area):
        return next(a for a in result["areas"] if a["area"] == area)

    def evaluate(self, score_quality, score_tests):
        """A card done by alpha:alpha-1, scored by the lead."""
        ids = {n: self.s.action("agent_profile_save", {"name": n, "role": r, "connector": "alpha", "model": "alpha-1", "prompt": n})["id"]
               for n, r in [("Lead", "lead"), ("Dev", "member")]}
        project = self.fixture.project
        self.s.action("team_save", {"project_id": project})
        lead = self.s.action("team_add_member", {"project_id": project, "profile_id": ids["Lead"], "role": "chief"})["id"]
        dev = self.s.action("team_add_member", {"project_id": project, "profile_id": ids["Dev"], "role": "member", "manager_id": lead})["id"]
        card = self.s.action("task_create", {"project_id": project, "author_id": lead, "assignee_id": dev, "objective": "Module"})["id"]
        self.s.action("task_status", {"project_id": project, "id": card, "status": "ready", "author_id": lead})
        self.s.action("task_status", {"project_id": project, "id": card, "status": "in_progress", "author_id": dev})
        self.s.action("task_report", {"project_id": project, "id": card, "author_id": dev, "result": "Fait", "tests": "ok"})
        self.s.action("task_evaluate", {"project_id": project, "id": card, "author_id": lead, "scores": {"quality": score_quality, "tests": score_tests}, "comment": "Vu"})

    def test_nothing_known_says_so_and_your_score_always_wins(self):
        unknown = self.s.action("model_capabilities", {"connector": "alpha", "model": "alpha-1"})
        self.assertTrue(all(a["value"] is None for a in unknown["areas"]))
        self.evaluate(2, 1)
        self.s.action("model_rating", {"connector": "alpha", "model": "alpha-1", "scores": {"code": 9}})
        result = self.s.action("model_capabilities", {"connector": "alpha", "model": "alpha-1"})
        code = self.area(result, "code")
        self.assertEqual((code["value"], code["confidence"], code["sources"][0]["kind"]), (9.0, "vous", "you"))
        self.assertIn("projects", [s["kind"] for s in code["sources"]], "les autres sources restent visibles")

    def test_your_projects_and_public_benchmarks_feed_the_estimate(self):
        self.evaluate(4, 3)
        mine = self.s.action("model_capabilities", {"connector": "alpha", "model": "alpha-1"})
        self.assertEqual((self.area(mine, "general")["value"], self.area(mine, "tests")["value"]), (8.0, 6.0), "une note de 1 à 5 compte double")
        self.assertIsNone(self.area(mine, "interface")["value"])
        public = self.s.action("model_capabilities", {"connector": "codex", "model": "gpt-5 (high)"})
        code = self.area(public, "code")
        self.assertEqual((code["value"], code["sources"][0]["kind"]), (9.0, "benchmark"))
        self.assertIn("Aider Polyglot 88.0 %", code["sources"][0]["detail"])

    def test_an_ai_estimate_is_one_more_source_on_request(self):
        self.s.engine.connectors["beta"].answer = lambda prompt: ('```json\n{"areas": {"code": 7, "interface": 5, "inconnu": 9}, "incertitude": "forte", '
                                                                  '"notes": "Modèle peu connu."}\n```')
        started = self.s.action("model_estimate", {"connector": "alpha", "model": "alpha-1", "by_connector": "beta"})
        deadline = time.time() + 10
        while self.s.mission(started["mission_id"])["status"] not in {"succeeded", "failed"} and time.time() < deadline:
            time.sleep(.05)
        sent = self.s.engine.connectors["beta"].calls[-1][0]
        self.assertIn("N’invente ni benchmark ni chiffre public", sent)
        result = self.s.action("model_capabilities", {"connector": "alpha", "model": "alpha-1"})
        interface = self.area(result, "interface")
        self.assertEqual((interface["value"], interface["confidence"], interface["sources"][0]["kind"]), (5.0, "faible", "ai"))
        self.assertIn("incertitude forte", interface["sources"][0]["detail"])
        self.assertFalse(result["estimate_pending"])

    def test_an_order_of_preference_per_area_is_kept_and_read_by_the_orchestrator(self):
        self.s.action("model_rating", {"connector": "beta", "model": "b", "scores": {"code": 9}})
        self.s.action("model_rating", {"connector": "alpha", "model": "a", "scores": {"code": 6}, "preference": "prefer"})
        self.s.action("model_rating", {"connector": "alpha", "model": "z", "scores": {"code": 10}, "preference": "avoid"})
        suggested = self.s.action("model_capabilities", {})["orders"]["code"]["suggested"]
        self.assertEqual(suggested[:3], ["alpha:a", "beta:b", "alpha:z"], "préféré d’abord, évité en dernier, sinon par estimation")
        with self.assertRaises(ValueError):
            self.s.action("model_preference_order", {"area": "cuisine", "models": ["alpha:a"]})
        self.s.action("model_preference_order", {"area": "code", "models": ["beta:b", "alpha:a"]})
        self.s.action("model_preferences", {"priority": "quality", "instructions": "local d’abord"})
        self.assertEqual(self.s.action("model_capabilities", {})["orders"]["code"]["order"], ["beta:b", "alpha:a"], "enregistrer la priorité garde l’ordre")
        self.assertIn('"order": {"code": ["beta:b", "alpha:a"]}', planning_preferences(self.s))
        self.s.action("model_preference_order", {"area": "code", "models": []})
        self.assertEqual(self.s.action("model_capabilities", {})["orders"]["code"]["order"], [])

    def test_agents_read_and_only_you_decide(self):
        app_mcp.Draft202012Validator.check_schema(app_mcp.ACTIONS["model_capabilities"]["inputSchema"])
        self.assertFalse(app_mcp.ACTIONS["model_capabilities"]["write"])
        for name in ("model_preference_order", "model_estimate"):
            self.assertIn(name, app_mcp.USER_ONLY)
            self.assertNotIn(name, app_mcp.ACTIONS)


if __name__ == "__main__":
    unittest.main()
