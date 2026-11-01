import json
import time
import unittest

import test_core
from cyai import app_mcp
from cyai.context import build_context


class SpecialistTests(unittest.TestCase):
    """A profile is a person you can call on: in a team, in a chain, or in a plain conversation."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config = {**connector.config, "enabled": True}
        self.expert = self.s.action("agent_profile_save", {
            "name": "Iris · recherche", "role": "consultant", "connector": "beta", "model": "beta-2", "icon": "🔎",
            "description": "Spécialiste de la recherche documentaire.", "skills": ["recherche", "synthèse"],
            "prompt": "CONSIGNES_DU_SPECIALISTE : cite toujours tes sources."})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    # --- summoned in a plain conversation ------------------------------------------------

    def test_a_profile_is_summoned_in_a_conversation_without_any_team(self):
        self.assertFalse(self.s.store.rows("SELECT id FROM teams"), "aucune équipe n’est nécessaire")
        opened = self.s.action("profile_conversation", {"project_id": self.p, "profile_id": self.expert})
        self.assertEqual((opened["connector"], opened["model"], opened["revision"]), ("beta", "beta-2", 1))
        self.assertIn("Aucune équipe n’est nécessaire", opened["notice"])
        conversation = self.s.conversation(opened["id"])
        self.assertEqual(conversation["mode"], "chat", "le mode normal reste le mode normal")
        self.assertEqual((conversation["profile_id"], conversation["profile_revision"]), (self.expert, 1))
        self.assertEqual((conversation["agent_id"], conversation["agent_model"]), ("beta", "beta-2"))
        text = build_context(self.s.store, opened["id"], "Bonjour", {}, 48000)["text"]
        self.assertIn("CONSIGNES_DU_SPECIALISTE", text)
        self.assertIn("spécialiste sollicité directement, hors hiérarchie", text)
        self.assertIn("n’est pas une capacité vérifiée", text)

    def test_a_later_profile_edit_does_not_change_an_open_conversation(self):
        opened = self.s.action("profile_conversation", {"project_id": self.p, "profile_id": self.expert})
        self.s.action("agent_profile_save", {"id": self.expert, "name": "Iris · recherche", "role": "consultant",
                                             "connector": "beta", "model": "beta-9", "prompt": "CONSIGNES_REVISEES"})
        self.assertEqual(self.s.action("agent_profile_get", {"id": self.expert})["revision"], 2)
        conversation = self.s.conversation(opened["id"])
        self.assertEqual(conversation["profile_revision"], 1)
        self.assertEqual(conversation["agent_model"], "beta-2")
        text = build_context(self.s.store, opened["id"], "Suite", {}, 48000)["text"]
        self.assertIn("CONSIGNES_DU_SPECIALISTE", text)
        self.assertNotIn("CONSIGNES_REVISEES", text)
        # A new conversation picks up the new revision.
        again = self.s.action("profile_conversation", {"project_id": self.p, "profile_id": self.expert})
        self.assertEqual((again["revision"], again["model"]), (2, "beta-9"))

    def test_an_archived_profile_is_not_summoned(self):
        self.s.action("agent_profile_archive", {"id": self.expert})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("profile_conversation", {"project_id": self.p, "profile_id": self.expert})
        self.assertIn("réactivez-le", str(refusal.exception))

    # --- called inside a chain ------------------------------------------------------------

    def test_a_chain_step_can_call_a_profile_instead_of_a_raw_connector(self):
        conversation = self.s.action("create_conversation", {"project_id": self.p, "title": "Chaîne"})["id"]
        mission = self.s.action("create_mission", {"conversation_id": conversation, "title": "Avec spécialiste", "launch": False,
                                                   "steps": [{"profile_id": self.expert, "instruction": "Cherche les sources publiques."},
                                                             {"connector": "alpha", "instruction": "Synthétise.", "depends_on": [0]}]})["mission_id"]
        steps = self.s.mission(mission)["steps"]
        self.assertEqual([s["connector"] for s in steps], ["beta", "alpha"])
        self.assertEqual(steps[0]["model"], "beta-2")
        self.assertEqual(steps[0]["name"], "Iris · recherche")
        self.assertIn("CONSIGNES_DU_SPECIALISTE", steps[0]["instruction"])
        self.assertIn("Cherche les sources publiques.", steps[0]["instruction"])
        self.assertNotIn("CONSIGNES_DU_SPECIALISTE", steps[1]["instruction"], "seul le pas du spécialiste reçoit ses consignes")

    def test_a_chain_refuses_an_archived_profile_and_keeps_explicit_overrides(self):
        conversation = self.s.action("create_conversation", {"project_id": self.p, "title": "Chaîne"})["id"]
        mission = self.s.action("create_mission", {"conversation_id": conversation, "launch": False,
                                                   "steps": [{"profile_id": self.expert, "model": "beta-force",
                                                              "name": "Pas nommé", "instruction": "Cherche."}]})["mission_id"]
        step = self.s.mission(mission)["steps"][0]
        self.assertEqual((step["model"], step["name"]), ("beta-force", "Pas nommé"), "un choix explicite prime sur le profil")
        self.s.action("agent_profile_archive", {"id": self.expert})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("create_mission", {"conversation_id": conversation, "launch": False,
                                             "steps": [{"profile_id": self.expert, "instruction": "Encore."}]})
        self.assertIn("Profil archivé", str(refusal.exception))

    # --- asked to work directly, without a lead -------------------------------------------

    def test_a_specialist_is_given_a_card_directly_without_going_through_a_lead(self):
        self.s.action("team_save", {"project_id": self.p})
        chief_profile = self.s.action("agent_profile_save", {"name": "Chef", "role": "chief", "connector": "alpha"})["id"]
        chief = self.s.action("team_add_member", {"project_id": self.p, "profile_id": chief_profile, "role": "chief"})["id"]
        specialist = self.s.action("team_add_member", {"project_id": self.p, "profile_id": self.expert, "role": "consultant"})["id"]
        # No lead in this team at all: the user commissions the card and the specialist executes it.
        card = self.s.action("task_create", {"project_id": self.p, "by_user": True, "assignee_id": specialist,
                                             "objective": "Rassembler les sources publiques"})["id"]
        self.s.action("task_status", {"project_id": self.p, "id": card, "status": "ready", "by_user": True})
        self.s.action("task_execute", {"project_id": self.p, "id": card})
        deadline = time.time() + 10
        while time.time() < deadline:
            task = self.s.action("task_get", {"project_id": self.p, "id": card})
            if not any(e["running"] for e in task["executions"]):
                break
            time.sleep(.05)
        self.assertEqual(task["status"], "in_review")
        self.assertEqual(task["reports"][0]["author"], "Iris · recherche")
        # Review still goes up: with no superior in the chain, the chief or the user decides.
        self.assertEqual([r["name"] for r in task["reviewers"]], ["Chef"])
        self.s.action("task_accept", {"project_id": self.p, "id": card, "by_user": True, "proofs": "Sources ouvertes une à une."})
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": card})["status"], "done")

    def test_the_same_profile_serves_a_team_a_chain_and_a_conversation_at_once(self):
        self.s.action("team_save", {"project_id": self.p})
        assignment = self.s.action("team_add_member", {"project_id": self.p, "profile_id": self.expert, "role": "chief"})["id"]
        direct = self.s.action("profile_conversation", {"project_id": self.p, "profile_id": self.expert})["id"]
        team_chat = self.s.action("team_conversation", {"project_id": self.p, "member_id": assignment})["id"]
        chain = self.s.action("create_conversation", {"project_id": self.p, "title": "Chaîne"})["id"]
        self.s.action("create_mission", {"conversation_id": chain, "launch": False,
                                         "steps": [{"profile_id": self.expert, "instruction": "Cherche."}]})
        self.assertEqual(len({direct, team_chat, chain}), 3, "trois usages, trois conversations distinctes")
        self.assertFalse(self.s.store.rows("SELECT id FROM sessions"), "aucune session native n’est partagée")
        modes = {r["id"]: r["mode"] for r in self.s.store.rows("SELECT id,mode FROM conversations")}
        self.assertEqual((modes[direct], modes[team_chat], modes[chain]), ("chat", "team", "chat"))

    # --- MCP --------------------------------------------------------------------------------

    def test_summoning_a_profile_is_a_scoped_authorised_write(self):
        op = app_mcp.ACTIONS["profile_conversation"]
        app_mcp.Draft202012Validator.check_schema(op["inputSchema"])
        self.assertEqual((op["scope"], op["write"]), ("project_id", True))
        other = self.s.action("create_project", {"name": "Voisin", "root": str(self.fixture.root)})["id"]
        from cyai.connectors import Control
        control = Control(30, lambda d: True, lambda *_: None)
        with self.assertRaises(ValueError):
            app_mcp.call(self.s, "cyai_call", {"action": "profile_conversation",
                                               "arguments": {"project_id": other, "profile_id": self.expert}}, [self.p], control)
        with self.assertRaises(ValueError):
            app_mcp.call(self.s, "cyai_call", {"action": "profile_conversation",
                                               "arguments": {"project_id": self.p, "profile_id": self.expert}}, [self.p])
        self.assertFalse(self.s.store.rows("SELECT id FROM conversations WHERE profile_id IS NOT NULL"))


if __name__ == "__main__":
    unittest.main()
