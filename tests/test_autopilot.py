import time
import unittest

import test_core
from cyai import app_mcp, autopilot


class AutopilotTests(unittest.TestCase):
    """The delegation automaton moves the board within limits, and never makes a report true."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config["enabled"] = True
        ids = {n: self.s.action("agent_profile_save", {"name": n, "role": r, "connector": "alpha", "prompt": "Consignes de " + n})["id"]
               for n, r in [("Chef", "chief"), ("Lead", "lead"), ("Dev", "member")]}
        self.s.action("team_save", {"project_id": self.p})
        self.chief = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Chef"], "role": "chief"})["id"]
        self.lead = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Lead"], "role": "lead", "manager_id": self.chief})["id"]
        self.dev = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Dev"], "role": "member", "manager_id": self.lead})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def card(self, objective, status="ready", dependencies=()):
        id = self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "assignee_id": self.dev,
                                           "objective": objective, "dependencies": list(dependencies)})["id"]
        if status == "ready":
            self.s.action("task_status", {"project_id": self.p, "id": id, "status": "ready", "author_id": self.lead})
        return id

    def settle(self, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.s.store.rows("SELECT id FROM missions WHERE status IN ('queued','running','awaiting_approval','pausing')"):
                autopilot.plan(self.s, {"project_id": self.p})  # reconcile on read
                return
            time.sleep(.05)
        raise AssertionError("missions non terminées")

    def test_a_plan_launches_nothing_and_says_what_waits(self):
        ready = self.card("Concept")
        blocked = self.card("Modèle", status="to_prepare", dependencies=[ready])  # the board refuses « prête » before its dependencies
        self.card("Brouillon", status="to_prepare")
        plan = self.s.action("team_autopilot_plan", {"project_id": self.p})
        self.assertEqual([e["task_id"] for e in plan["launch"]], [ready])
        self.assertNotIn(blocked, [e["task_id"] for e in plan["launch"]], "une dépendance non terminée attend")
        self.assertFalse(self.s.store.rows("SELECT id FROM missions"), "voir le plan ne lance rien")
        self.s.engine.connectors["alpha"].config["enabled"] = False
        waiting = self.s.action("team_autopilot_plan", {"project_id": self.p})["waiting"]
        self.assertIn("indisponible", waiting[0]["reason"])

    def test_one_step_launches_then_sends_the_report_to_the_superior_once(self):
        task = self.card("Concept")
        done = self.s.action("team_autopilot_step", {"project_id": self.p})
        self.assertEqual(done["launched"], ["Concept"])
        self.settle()
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": task})["status"], "in_review")
        plan = self.s.action("team_autopilot_plan", {"project_id": self.p})
        self.assertEqual([(r["task_id"], r["reviewer_id"]) for r in plan["reviews"]], [(task, self.lead)], "le supérieur relit")
        done = self.s.action("team_autopilot_step", {"project_id": self.p})
        self.assertEqual(len(done["reviews"]), 1)
        review = self.s.store.rows("SELECT m.*, c.member_id FROM missions m JOIN conversations c ON c.id=m.conversation_id WHERE m.title LIKE 'Revue%'")
        self.assertEqual(review[0]["member_id"], self.lead)
        self.settle()
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": task})["status"], "in_review",
                         "une revue d’agent sans décision ne vaut pas acceptation")
        self.assertFalse(self.s.action("team_autopilot_plan", {"project_id": self.p})["reviews"], "un compte rendu n’est envoyé qu’une fois")

    def test_capacity_limits_a_round(self):
        for name in ("A", "B", "C"):
            self.card(name)
        self.s.engine.connectors["alpha"].mode = "wait"
        done = self.s.action("team_autopilot_step", {"project_id": self.p})
        self.assertEqual(len(done["launched"]), 2, "deux à la fois par défaut")
        self.assertEqual(self.s.action("team_autopilot_plan", {"project_id": self.p})["capacity"], 0)
        for row in self.s.store.rows("SELECT id FROM task_executions WHERE status='running'"):
            self.s.action("task_execution_cancel", {"project_id": self.p, "id": row["id"]})

    def test_automatic_mode_spends_only_its_budget_and_stops_by_itself(self):
        for name in ("A", "B", "C"):
            self.card(name)
        with self.assertRaises(ValueError):
            self.s.action("team_autopilot_set", {"project_id": self.p, "enabled": True, "budget": 0})
        autopilot.configure(self.s, {"project_id": self.p, "enabled": True, "budget": 2, "max_parallel": 3})
        autopilot.tick(self.s)
        state = self.s.action("team_autopilot_plan", {"project_id": self.p})["autopilot"]
        self.assertEqual((state["budget"], state["launched"]), (0, 2), "le budget borne les lancements, même avec de la place")
        self.settle()
        autopilot.tick(self.s)
        state = self.s.action("team_autopilot_plan", {"project_id": self.p})["autopilot"]
        self.assertFalse(state["enabled"])
        self.assertIn("budget", state["stopped"])

    def test_a_failure_stops_the_automatic_mode(self):
        self.card("A")
        self.s.engine.connectors["alpha"].mode = "fail"
        autopilot.configure(self.s, {"project_id": self.p, "enabled": True, "budget": 5})
        autopilot.tick(self.s)
        self.settle()
        autopilot.tick(self.s)
        state = self.s.action("team_autopilot_plan", {"project_id": self.p})["autopilot"]
        self.assertFalse(state["enabled"])
        self.assertIn("échoué", state["stopped"])

    def test_a_pilot_never_resumes_after_a_restart(self):
        autopilot.configure(self.s, {"project_id": self.p, "enabled": True, "budget": 3})
        autopilot.stop_after_restart(self.s)
        state = self.s.action("team_autopilot_plan", {"project_id": self.p})["autopilot"]
        self.assertFalse(state["enabled"])
        self.assertIn("redémarrage", state["stopped"])

    def test_agents_can_read_the_plan_but_not_start_the_pilot(self):
        self.assertFalse(app_mcp.ACTIONS["team_autopilot_plan"]["write"])
        self.assertNotIn("team_autopilot_step", app_mcp.ACTIONS)
        self.assertNotIn("team_autopilot_set", app_mcp.ACTIONS)
        self.assertIn("team_autopilot_set", app_mcp.USER_ONLY)


    # --- spontaneous proposals, opt-in, from the reviewer ----------------------------------------

    def reviewed(self):
        task = self.card("Concept")
        self.s.action("team_autopilot_step", {"project_id": self.p})
        self.settle()
        self.s.action("team_autopilot_step", {"project_id": self.p})
        self.settle()
        review = self.s.store.rows("SELECT s.instruction FROM steps s JOIN missions m ON m.id=s.mission_id WHERE m.title LIKE 'Revue%'")
        return task, review[0]["instruction"]

    def test_reviewers_are_not_invited_to_propose_by_default(self):
        self.assertFalse(self.s.action("team_autopilot_plan", {"project_id": self.p})["autopilot"]["invite_proposals"])
        task, instruction = self.reviewed()
        self.assertNotIn("improvement_propose", instruction)

    def test_when_invited_the_reviewer_gets_what_a_valid_proposal_needs(self):
        result = self.s.action("team_autopilot_options", {"project_id": self.p, "invite_proposals": True})
        self.assertTrue(result["autopilot"]["invite_proposals"])
        task, instruction = self.reviewed()
        self.assertIn("improvement_propose", instruction)
        report = self.s.store.one("SELECT id FROM task_reports WHERE task_id=?", (task,))["id"]
        profile = self.s.store.one("SELECT profile_id FROM team_members WHERE id=?", (self.dev,))["profile_id"]
        for needed in (self.lead, profile, task, report):
            self.assertIn(needed, instruction)
        # What the instruction asks for is exactly what the existing rules accept from a lead.
        proposal = self.s.action("improvement_propose", {"project_id": self.p, "member_id": self.lead, "profile_id": profile,
                                                         "kind": "prompt", "proposed_value": "Consignes de Dev, avec les tests.",
                                                         "rationale": "Le compte rendu ne cite aucun test.", "source_ids": [task, report]})
        self.assertIn("Rien ne change", proposal["notice"])
        self.assertNotIn("team_autopilot_options", app_mcp.ACTIONS)
        self.assertIn("team_autopilot_options", app_mcp.USER_ONLY)


if __name__ == "__main__":
    unittest.main()
