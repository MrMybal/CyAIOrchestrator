import time
import unittest

import test_core
from cyai import app_mcp


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config["enabled"] = True
        ids = {n: self.s.action("agent_profile_save", {"name": n, "role": r, "connector": c, "prompt": "Consignes de " + n})["id"]
               for n, r, c in [("Chef", "chief", "alpha"), ("Lead", "lead", "alpha"), ("Dev", "member", "beta"),
                               ("Veille", "consultant", "alpha")]}
        self.profiles = ids
        self.s.action("team_save", {"project_id": self.p})
        self.chief = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Chef"], "role": "chief"})["id"]
        self.lead = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Lead"], "role": "lead",
                                                      "manager_id": self.chief})["id"]
        self.dev = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Dev"], "role": "member",
                                                     "manager_id": self.lead})["id"]
        self.consultant = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Veille"], "role": "consultant"})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def channels(self):
        return self.s.action("project_channels", {"project_id": self.p})

    def member(self, id):
        return next(m for m in self.channels()["members"] if m["id"] == id)

    def wait_state(self, id, state, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.member(id)["state"] == state:
                return
            time.sleep(.05)
        self.fail("état « " + state + " » jamais atteint, dernier : " + self.member(id)["state"])

    def ready_task(self, objective="Migrer le schéma"):
        id = self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "assignee_id": self.dev,
                                           "objective": objective})["id"]
        self.s.action("task_status", {"project_id": self.p, "id": id, "status": "ready", "author_id": self.lead})
        return id

    # --- structure -------------------------------------------------------------------------

    def test_a_project_is_listed_as_typed_channels_in_stable_categories(self):
        result = self.channels()
        # Contract changed on purpose (0.2.24): the project assistant has its own category, above the conversations.
        self.assertEqual(result["categories"], ["Assistant", "Conversations", "Agents", "Espaces", "Équipe", "Projet"])
        by_type = {c["type"]: c for c in result["channels"]}
        for type in ("conversation", "board", "team", "overview", "memory", "pins", "media", "settings"):
            self.assertIn(type, by_type)
        self.assertEqual(by_type["conversation"]["id"], self.fixture.conversation)
        self.assertEqual(by_type["conversation"]["category"], "Conversations")
        self.assertTrue(all(c["category"] in result["categories"] for c in result["channels"]))

    def test_an_agent_conversation_is_filed_under_agents_not_under_conversations(self):
        opened = self.s.action("team_conversation", {"project_id": self.p, "member_id": self.dev})
        channel = next(c for c in self.channels()["channels"] if c["id"] == opened["id"])
        self.assertEqual((channel["type"], channel["category"]), ("agent", "Agents"))

    def test_archived_conversations_are_not_channels(self):
        self.s.action("archive_conversation", {"id": self.fixture.conversation})
        self.assertNotIn(self.fixture.conversation, [c["id"] for c in self.channels()["channels"]])

    def test_badges_count_what_waits_for_the_user(self):
        id = self.ready_task()
        self.s.action("task_status", {"project_id": self.p, "id": id, "status": "in_progress", "author_id": self.dev})
        self.s.action("task_report", {"project_id": self.p, "id": id, "author_id": self.dev, "result": "Fait",
                                      "executed_tests": "3 tests"})
        board = next(c for c in self.channels()["channels"] if c["type"] == "board")
        self.assertEqual(board["badge"], 1, "une carte en revue attend un examen")

    def test_pins_are_memory_notes_proposed_from_a_message_with_their_origin(self):
        self.s.store.execute("INSERT INTO messages(id,conversation_id,role,content,created_at) VALUES(?,?,?,?,?)",
                             ("m-pin", self.fixture.conversation, "assistant", "Réponse à garder", "2026-09-18T10:00:00.000+00:00"))
        self.s.action("save_memory", {"project_id": self.p, "content": "Note épinglée", "source_ids": ["m-pin"]})
        self.s.action("save_memory", {"project_id": self.p, "content": "Note libre"})
        pins = self.s.action("project_pins", {"project_id": self.p})["pins"]
        self.assertEqual([p["content"] for p in pins], ["Note épinglée"])
        self.assertEqual(pins[0]["conversation_id"], self.fixture.conversation)
        self.assertEqual(next(c for c in self.channels()["channels"] if c["type"] == "pins")["badge"], 1)

    # --- presence ---------------------------------------------------------------------------

    def test_members_are_idle_by_default_and_never_online(self):
        members = self.channels()["members"]
        self.assertEqual([m["role"] for m in members], ["chief", "lead", "member", "consultant"])
        self.assertTrue(all(m["state"] == "idle" for m in members))
        self.assertTrue(all(m["state_label"] == "Au repos" for m in members))
        self.assertNotIn("online", {m["state"] for m in members})

    def test_a_disabled_connector_is_shown_as_unavailable(self):
        self.s.engine.connectors["beta"].config["enabled"] = False
        self.assertEqual(self.member(self.dev)["state"], "unavailable")
        self.assertEqual(self.member(self.lead)["state"], "idle")

    def test_an_agent_is_running_only_while_its_mission_is_active(self):
        self.s.engine.connectors["beta"].mode = "wait"
        execution = self.s.action("task_execute", {"project_id": self.p, "id": self.ready_task()})
        self.wait_state(self.dev, "running")
        self.assertEqual(self.member(self.lead)["state"], "idle", "les autres ne sont pas contaminés")
        self.s.action("task_execution_cancel", {"project_id": self.p, "id": execution["id"]})
        self.wait_state(self.dev, "idle")

    def test_an_agent_waiting_for_an_approval_says_so(self):
        self.s.engine.connectors["beta"].mode = "approval"
        execution = self.s.action("task_execute", {"project_id": self.p, "id": self.ready_task()})
        self.wait_state(self.dev, "awaiting")
        self.assertEqual(self.member(self.dev)["state_label"], "Attend votre autorisation")
        self.s.action("task_execution_cancel", {"project_id": self.p, "id": execution["id"]})
        self.wait_state(self.dev, "idle")

    def test_a_project_without_team_has_no_members(self):
        other = self.s.action("create_project", {"name": "Solo", "root": str(self.fixture.root)})["id"]
        result = self.s.action("project_channels", {"project_id": other})
        self.assertEqual(result["members"], [])
        self.assertFalse(result["team"]["exists"])

    # --- MCP --------------------------------------------------------------------------------

    def test_channels_are_readable_through_the_mcp_within_the_project_only(self):
        op = app_mcp.ACTIONS["project_channels"]
        self.assertFalse(op["write"])
        app_mcp.check_scope(self.s, op, {"project_id": self.p}, [self.p])
        other = self.s.action("create_project", {"name": "Autre", "root": str(self.fixture.root)})["id"]
        with self.assertRaises(ValueError):
            app_mcp.check_scope(self.s, op, {"project_id": other}, [self.p])


if __name__ == "__main__":
    unittest.main()
