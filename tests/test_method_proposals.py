import time
import unittest

import test_core
from cyai import app_mcp


class MethodProposalTests(unittest.TestCase):
    """Agents propose improvements while they work; a stronger model examines them, questions the author; you adopt."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config = {**connector.config, "enabled": True}
        self.review_answer = "### Sortie : Verdict\nPertinente : le format manquait.\n### Sortie : Précisions\nRends le plan en liste numérotée."
        self.s.engine.connectors["alpha"].answer = self.answer
        self.s.engine.connectors["beta"].answer = self.answer
        self.method = self.s.action("method_save", self.body(True))["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def body(self, proposals):
        return {"name": "Affiche", "options": {"proposals": proposals},
                "steps": [{"key": "a", "name": "Plan", "executor": "any", "instruction": "Planifie {objectif}.", "inputs": [],
                           "outputs": [{"key": "s", "name": "Plan"}]},
                          {"key": "b", "name": "Texte", "executor": "any", "instruction": "Écris le texte.",
                           "inputs": [{"key": "e", "name": "Plan", "source": {"step": "a", "port": "s"}}], "outputs": []}]}

    def answer(self, prompt):
        if "Examinez une proposition" in prompt and "Avant de juger" in prompt:
            return "### Sortie : Questions\nQuel format vous aurait aidé ?"
        if "Répondez brièvement et honnêtement aux questions" in prompt:
            return "Une liste numérotée."
        if "Examinez une proposition" in prompt or "Vous examinez une proposition" in prompt:
            return self.review_answer
        if "Planifie" in prompt:
            return "PLAN EN TROIS POINTS\n\n### Proposition d’amélioration\nPrécisez le format attendu du plan."
        return "Texte final."

    def settle(self, mission_id, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.s.mission(mission_id)["status"] in {"succeeded", "failed", "cancelled"}:
                return self.s.mission(mission_id)
            time.sleep(.05)
        raise AssertionError("mission non terminée")

    def chain(self):
        applied = self.s.action("method_apply", {"project_id": self.p, "id": self.method, "objective": "une affiche", "connector": "alpha"})
        self.s.action("launch_mission", {"mission_id": applied["mission_id"]})
        return self.settle(applied["mission_id"])

    def proposal(self):
        self.chain()
        return self.s.action("method_proposals", {"id": self.method})["proposals"][0]

    def test_agents_are_invited_only_when_the_method_asks(self):
        self.assertTrue(self.s.action("method_get", {"id": self.method})["method"]["options"]["proposals"])
        invited = self.s.mission(self.s.action("method_apply", {"project_id": self.p, "id": self.method, "objective": "x", "connector": "alpha"})["mission_id"])
        self.assertTrue(all("### Proposition d’amélioration" in s["instruction"] for s in invited["steps"]))
        quiet = self.s.action("method_save", {**self.body(False), "name": "Sans"})["id"]
        silent = self.s.mission(self.s.action("method_apply", {"project_id": self.p, "id": quiet, "objective": "x", "connector": "alpha"})["mission_id"])
        self.assertFalse(any("Proposition d’amélioration" in s["instruction"] for s in silent["steps"]))

    def test_a_proposal_never_travels_down_the_chain_and_is_collected_once(self):
        mission = self.chain()
        self.assertEqual(mission["status"], "succeeded")
        text = next(p for p, _ in self.s.engine.connectors["alpha"].calls if "Écris le texte" in p)
        self.assertIn("PLAN EN TROIS POINTS", text)
        self.assertNotIn("Précisez le format", text, "la tâche suivante ne reçoit pas la proposition")
        self.assertEqual(self.s.action("method_get", {"id": self.method})["method"]["proposals_new"], 1)
        self.assertEqual(self.s.action("method_get", {"id": self.method})["method"]["proposals_new"], 1, "relevée une seule fois")
        proposal = self.s.action("method_proposals", {"id": self.method})["proposals"][0]
        self.assertEqual((proposal["step_key"], proposal["step_name"], proposal["connector"], proposal["content"]),
                         ("a", "Plan", "alpha", "Précisez le format attendu du plan."))
        self.assertIn("PLAN EN TROIS POINTS", proposal["excerpt"])

    def test_a_reviewed_proposal_becomes_precisions_for_the_model_that_made_it(self):
        proposal = self.proposal()
        started = self.s.action("method_proposal_review", {"id": proposal["id"], "connector": "beta"})
        self.settle(started["mission_id"])
        sent = self.s.engine.connectors["beta"].calls[-1][0]
        self.assertIn("Planifie {objectif}.", sent, "l’examinateur lit la consigne actuelle")
        self.assertIn("Précisez le format attendu du plan.", sent)
        reviewed = self.s.action("method_proposals", {"id": self.method})["proposals"][0]["reviews"][0]
        self.assertEqual((reviewed["status"], reviewed["data"]["precisions"]), ("succeeded", "Rends le plan en liste numérotée."))
        with self.assertRaises(ValueError):
            self.s.action("method_proposal_adopt", {"run_id": reviewed["id"], "mode": "instruction"})
        self.s.action("method_proposal_adopt", {"run_id": reviewed["id"], "mode": "precisions"})
        step = self.s.action("method_get", {"id": self.method})["method"]["steps"][0]
        self.assertEqual(step["adaptations"], {"alpha:": "Rends le plan en liste numérotée."})
        self.assertEqual(self.s.action("method_proposals", {"id": self.method})["proposals"][0]["status"], "adopted")
        self.assertEqual(self.s.action("method_history", {"id": self.method})["revisions"][0]["source"], "proposal")

    def test_a_discussion_questions_the_author_before_the_verdict(self):
        proposal = self.proposal()
        self.review_answer = "### Sortie : Verdict\nPertinente.\n### Sortie : Consigne\nPlanifie {objectif} en liste numérotée."
        self.settle(self.s.action("method_proposal_review", {"id": proposal["id"], "connector": "beta", "discuss": True})["mission_id"])
        author = next(p for p, _ in self.s.engine.connectors["alpha"].calls if "Répondez brièvement et honnêtement" in p)
        self.assertIn("Quel format vous aurait aidé ?", author, "l’auteur reçoit les questions de l’examinateur")
        reviewed = self.s.action("method_proposals", {"id": self.method})["proposals"][0]["reviews"][0]
        self.assertEqual(reviewed["data"]["answers"], "Une liste numérotée.")
        self.s.action("method_proposal_adopt", {"run_id": reviewed["id"], "mode": "instruction"})
        self.assertEqual(self.s.action("method_get", {"id": self.method})["method"]["steps"][0]["instruction"], "Planifie {objectif} en liste numérotée.")

    def test_a_proposal_can_be_dismissed_and_decisions_stay_with_the_user(self):
        proposal = self.proposal()
        self.s.action("method_proposal_dismiss", {"id": proposal["id"], "reason": "Hors sujet."})
        listed = self.s.action("method_proposals", {"id": self.method})["proposals"][0]
        self.assertEqual((listed["status"], listed["decision"]), ("dismissed", "Hors sujet."))
        self.assertEqual(self.s.action("method_get", {"id": self.method})["method"]["proposals_new"], 0)
        for name in ("method_proposal_review", "method_proposal_adopt", "method_proposal_dismiss"):
            self.assertIn(name, app_mcp.USER_ONLY)
            self.assertNotIn(name, app_mcp.ACTIONS)
        self.assertFalse(app_mcp.ACTIONS["method_proposals"]["write"])


if __name__ == "__main__":
    unittest.main()
