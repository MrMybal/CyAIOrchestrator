import time
import unittest

import test_core
from cyai import app_mcp
from cyai.context import build_context
from cyai.team_lead import effort_for, effective


class TeamLeadTests(unittest.TestCase):
    """The chief and the leads judge the agents they manage, act on it, and set the cursors of the work."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config["enabled"] = True
        profile = lambda name, role: self.s.action("agent_profile_save", {"name": name, "role": role, "connector": "alpha", "prompt": "Consignes de " + name})["id"]
        self.profiles = {n: profile(n, r) for n, r in [("Chef", "chief"), ("Lead", "lead"), ("Dev", "member"), ("Dev2", "member"), ("Nouveau", "member")]}
        self.s.action("team_save", {"project_id": self.p})
        add = lambda name, role, manager=None: self.s.action("team_add_member", {"project_id": self.p, "profile_id": self.profiles[name], "role": role,
                                                                                **({"manager_id": manager} if manager else {})})["id"]
        self.chief = add("Chef", "chief")
        self.lead = add("Lead", "lead", self.chief)
        self.dev = add("Dev", "member", self.lead)
        self.dev2 = add("Dev2", "member", self.lead)

    def tearDown(self):
        self.fixture.tearDown()

    def card(self, objective="Écrire le module", assignee=None, **extra):
        id = self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "assignee_id": assignee or self.dev,
                                           "objective": objective, **extra})["id"]
        self.s.action("task_status", {"project_id": self.p, "id": id, "status": "ready", "author_id": self.lead})
        return id

    def settle(self, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.s.store.rows("SELECT id FROM missions WHERE status IN ('queued','running')"):
                return
            time.sleep(.05)
        raise AssertionError("missions non terminées")

    # --- judging ----------------------------------------------------------------------------------------------

    def test_only_a_superior_judges_an_agent(self):
        done = self.s.action("member_assess", {"project_id": self.p, "member_id": self.dev, "author_id": self.lead, "verdict": "watch",
                                               "weaknesses": "Oublie les tests."})
        self.assertIn("À surveiller", done["notice"])
        self.s.action("member_assess", {"project_id": self.p, "member_id": self.lead, "author_id": self.chief, "verdict": "reliable", "strengths": "Solide."})
        self.s.action("member_assess", {"project_id": self.p, "member_id": self.dev2, "by_user": True, "verdict": "adapt", "recommendation": "Plus de tests."})
        for author, target in ((self.dev, self.lead), (self.dev2, self.dev), (self.dev, self.dev)):
            with self.assertRaises(ValueError):
                self.s.action("member_assess", {"project_id": self.p, "member_id": target, "author_id": author, "verdict": "watch", "weaknesses": "x"})
        with self.assertRaises(ValueError):
            self.s.action("member_assess", {"project_id": self.p, "member_id": self.dev, "author_id": self.lead, "verdict": "nul", "weaknesses": "x"})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("member_assess", {"project_id": self.p, "member_id": self.dev, "author_id": self.lead, "verdict": "watch"})
        self.assertIn("raisons", str(refusal.exception))

    def test_a_peer_no_longer_scores_a_card_of_its_colleague(self):
        id = self.card()
        self.s.action("task_status", {"project_id": self.p, "id": id, "status": "in_progress", "author_id": self.dev})
        self.s.action("task_report", {"project_id": self.p, "id": id, "author_id": self.dev, "result": "Fait", "tests": "ok"})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_evaluate", {"project_id": self.p, "id": id, "author_id": self.dev2, "scores": {"quality": 2}, "comment": "Bof"})
        self.assertIn("n’encadre pas", str(refusal.exception))
        self.s.action("task_evaluate", {"project_id": self.p, "id": id, "author_id": self.chief, "scores": {"quality": 4}, "comment": "Bien"})

    def test_the_scorecard_puts_facts_beside_judgements(self):
        id = self.card()
        self.s.action("task_status", {"project_id": self.p, "id": id, "status": "in_progress", "author_id": self.dev})
        self.s.action("task_report", {"project_id": self.p, "id": id, "author_id": self.dev, "result": "Fait", "tests": "ok"})
        self.s.action("task_evaluate", {"project_id": self.p, "id": id, "author_id": self.lead, "scores": {"quality": 2, "tests": 1}, "comment": "Fragile"})
        self.s.action("member_assess", {"project_id": self.p, "member_id": self.dev, "author_id": self.lead, "verdict": "reassign",
                                        "weaknesses": "Tests absents.", "recommendation": "Sur la documentation."})
        card = {m["name"]: m for m in self.s.action("team_scorecard", {"project_id": self.p})["members"]}["Dev"]
        self.assertEqual((card["verdict"], card["evaluations"]["count"], card["evaluations"]["average"]), ("reassign", 2, 1.5))
        self.assertEqual(card["tasks"]["in_review"], 1)
        self.assertEqual(card["assessments"][0]["author"], "Lead")

    def test_agents_read_their_assessment_and_superiors_read_their_team(self):
        self.s.action("member_assess", {"project_id": self.p, "member_id": self.dev, "author_id": self.lead, "verdict": "adapt",
                                        "weaknesses": "Comptes rendus vagues.", "recommendation": "Citer les commandes lancées."})
        context = lambda member: build_context(self.s.store, self.s.action("team_conversation", {"project_id": self.p, "member_id": member})["id"], "x", {})["text"]
        dev = context(self.dev)
        self.assertIn("Dernier bilan de votre travail dans ce projet (À adapter", dev)
        self.assertIn("Citer les commandes lancées.", dev)
        lead = context(self.lead)
        self.assertIn("Dev [" + self.dev + "]", lead)
        self.assertIn("bilan : À adapter", lead)
        self.assertNotIn("Chef [", lead, "un lead ne voit que ceux qu’il encadre")
        self.assertIn("Lead [" + self.lead + "]", context(self.chief), "le chef voit toute l’équipe")
        self.assertNotIn("Les agents que vous encadrez", context(self.dev2))

    # --- acting on it ----------------------------------------------------------------------------------------

    def test_a_lead_reassigns_the_open_cards_of_an_agent(self):
        open_card, other = self.card("Un"), self.card("Deux")
        with self.assertRaises(ValueError):
            self.s.action("task_reassign", {"project_id": self.p, "member_id": self.dev, "to_member_id": self.dev2, "author_id": self.dev2})
        moved = self.s.action("task_reassign", {"project_id": self.p, "member_id": self.dev, "to_member_id": self.dev2, "author_id": self.lead,
                                                "task_ids": [open_card], "reason": "Trop d’erreurs."})
        self.assertEqual(moved["moved"], ["Un"])
        task = self.s.action("task_get", {"project_id": self.p, "id": open_card})
        self.assertEqual(task["assignee_id"], self.dev2)
        self.assertIn("Trop d’erreurs.", task["history"][-1]["detail"])
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": other})["assignee_id"], self.dev)

    def test_the_chief_replaces_an_agent_in_the_same_place(self):
        card = self.card(assignee=self.lead)
        with self.assertRaises(ValueError):
            self.s.action("team_replace_member", {"project_id": self.p, "member_id": self.lead, "profile_id": self.profiles["Nouveau"], "author_id": self.dev2})
        replaced = self.s.action("team_replace_member", {"project_id": self.p, "member_id": self.lead, "profile_id": self.profiles["Nouveau"],
                                                         "author_id": self.chief, "reason": "Échecs répétés."})
        new = self.s.store.one("SELECT * FROM team_members WHERE id=?", (replaced["id"],))
        self.assertEqual((new["role"], new["manager_id"]), ("lead", self.chief), "même rôle, même responsable")
        for under in (self.dev, self.dev2):
            self.assertEqual(self.s.store.one("SELECT manager_id FROM team_members WHERE id=?", (under,))["manager_id"], replaced["id"])
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": card})["assignee_id"], replaced["id"])
        self.assertEqual(self.s.store.one("SELECT active FROM team_members WHERE id=?", (self.lead,))["active"], 0, "retiré, pas supprimé")
        self.assertIn("Échecs répétés.", replaced["notice"])

    # --- cursors --------------------------------------------------------------------------------------------------

    def test_cursors_come_from_the_project_the_card_and_the_launch(self):
        with self.assertRaises(ValueError):
            self.s.action("team_cursors_set", {"project_id": self.p, "author_id": self.lead, "cursors": {"rigor": 2}})
        with self.assertRaises(ValueError):
            self.s.action("team_cursors_set", {"project_id": self.p, "author_id": self.chief, "cursors": {"rigor": 7}})
        self.s.action("team_cursors_set", {"project_id": self.p, "author_id": self.chief, "cursors": {"rigor": 2, "autonomy": 3}})
        id = self.card(cursors={"rigor": 5})
        with self.assertRaises(ValueError):
            self.s.action("task_cursors_set", {"project_id": self.p, "id": id, "author_id": self.dev2, "cursors": {"creativity": 1}})
        self.s.action("task_cursors_set", {"project_id": self.p, "id": id, "author_id": self.lead, "cursors": {"rigor": 5, "creativity": 1}})
        self.s.action("task_execute", {"project_id": self.p, "id": id, "cursors": {"autonomy": 5}})
        self.settle()
        prompt = self.s.engine.connectors["alpha"].calls[-1][0]
        self.assertIn("Rigueur 5/5 (carte) : Vérifiez tout", prompt, "la carte prime sur le projet")
        self.assertIn("Autonomie 5/5 (lancement)", prompt, "le lancement prime sur tout")
        self.assertIn("Créativité 1/5 (carte)", prompt)
        self.assertNotIn("Rigueur 2/5", prompt)
        self.assertEqual(self.s.action("team_scorecard", {"project_id": self.p})["cursors"], {"rigor": 2, "autonomy": 3})

    def test_the_effort_cursor_reaches_models_that_have_one(self):
        cursors = effective(self.s, self.p, {"cursors": {"effort": 5}})
        self.assertEqual((effort_for(cursors, "codex"), effort_for(cursors, "claude-code"), effort_for(cursors, "alpha")), ("xhigh", "xhigh", ""))
        self.assertEqual(effort_for(effective(self.s, self.p, {"cursors": {"effort": 1}}), "codex"), "low")

    def test_the_mcp_lets_superiors_act_with_approval(self):
        for name in ("team_scorecard", "member_assess", "task_reassign", "team_replace_member", "team_cursors_set", "task_cursors_set"):
            app_mcp.Draft202012Validator.check_schema(app_mcp.ACTIONS[name]["inputSchema"])
            self.assertEqual(app_mcp.ACTIONS[name]["scope"], "project_id")
        self.assertFalse(app_mcp.ACTIONS["team_scorecard"]["write"])
        self.assertTrue(app_mcp.ACTIONS["team_replace_member"]["write"])
        self.assertIn("cursors", app_mcp.ACTIONS["task_execute"]["inputSchema"]["properties"])


if __name__ == "__main__":
    unittest.main()
