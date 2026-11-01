import unittest

import test_core
from cyai import app_mcp
from cyai.connectors import Control


class TeamMcpTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        self.other = self.s.action("create_project", {"name": "Hors périmètre", "root": str(self.fixture.root)})["id"]
        self.approvals = []
        self.control = Control(30, lambda d: self.approvals.append(d) or True, lambda *_: None)
        self.control.conversation_id = self.fixture.conversation

    def tearDown(self):
        self.fixture.tearDown()

    def call(self, name, args=None, projects=None, control=None, allow_write=False, allow_global=False):
        return app_mcp.call(self.s, "cyai_call", {"action": name, "arguments": args or {}},
                            projects or [self.p], control, allow_write, allow_global)

    def test_every_team_action_declares_a_valid_schema_and_a_scope(self):
        team = [op for op in app_mcp.ACTIONS.values() if op["domain"] == "teams"]
        self.assertTrue(team)
        for op in team:
            app_mcp.Draft202012Validator.check_schema(op["inputSchema"])
            self.assertIn(op["scope"], {"global", "project_id"}, op["name"])
            if op["scope"] == "global":
                self.assertTrue(op["description"].startswith("GLOBAL"), op["name"])
        catalog = app_mcp.call(self.s, "cyai_actions", {"domain": "teams"}, [self.p])
        self.assertIn("team_add_member", {a["name"] for a in catalog["actions"]})
        self.assertFalse(catalog["global_writes"])
        self.assertIn("bibliothèque globale", catalog["instruction"])

    def test_a_project_client_reads_the_library_but_cannot_write_it(self):
        profile = self.s.action("agent_profile_save", {"name": "Lead", "role": "lead", "connector": "alpha"})["id"]
        self.assertEqual(len(self.call("agent_profile_list", allow_write=True)["profiles"]), 1)
        self.assertEqual(self.call("agent_profile_get", {"id": profile}, allow_write=True)["revision"], 1)
        for name, args in [("agent_profile_save", {"name": "Nouveau", "connector": "alpha"}),
                           ("agent_profile_archive", {"id": profile}),
                           ("agent_profile_duplicate", {"id": profile}),
                           ("team_template_delete", {"id": "inconnu"})]:
            with self.assertRaises(ValueError) as refusal:
                self.call(name, args, allow_write=True)
            self.assertIn("--allow-global", str(refusal.exception))
        self.assertEqual(len(self.s.action("agent_profile_list", {})["profiles"]), 1)
        self.assertFalse(self.s.store.rows("SELECT id FROM agent_profiles WHERE name='Nouveau'"))

    def test_a_global_client_manages_the_library_without_a_browser(self):
        created = self.call("agent_profile_save", {"name": "Chef", "role": "chief", "connector": "alpha", "prompt": "Coordonne"},
                            allow_write=True, allow_global=True)
        self.assertEqual(created["revision"], 1)
        self.call("team_save", {"project_id": self.p}, allow_write=True)
        chief = self.call("team_add_member", {"project_id": self.p, "profile_id": created["id"], "role": "chief"}, allow_write=True)["id"]
        team = self.call("team_get", {"project_id": self.p})
        self.assertEqual([m["id"] for m in team["members"]], [chief])
        self.assertEqual(team["issues"], [])
        self.call("team_save_template", {"project_id": self.p, "name": "Modèle MCP"}, allow_write=True, allow_global=True)
        self.assertEqual(len(self.call("team_template_list")["templates"]), 1)

    def test_team_writes_stay_inside_the_authorized_projects(self):
        profile = self.s.action("agent_profile_save", {"name": "Chef", "role": "chief", "connector": "alpha"})["id"]
        self.s.action("team_save", {"project_id": self.other})
        foreign = self.s.action("team_add_member", {"project_id": self.other, "profile_id": profile, "role": "chief"})["id"]
        for name, args in [("team_get", {"project_id": self.other}),
                           ("team_save", {"project_id": self.other, "name": "Renommée"}),
                           ("team_add_member", {"project_id": self.other, "profile_id": profile}),
                           ("team_update_member", {"project_id": self.other, "id": foreign, "role": "lead"}),
                           ("team_remove_member", {"project_id": self.other, "id": foreign}),
                           ("team_apply_template", {"project_id": self.other, "template_id": "x"})]:
            with self.assertRaises(ValueError) as refusal:
                self.call(name, args, allow_write=True, allow_global=True)
            self.assertIn("hors périmètre", str(refusal.exception).lower())
        self.assertEqual(self.s.action("team_get", {"project_id": self.other})["members"][0]["role"], "chief")
        # An assignment id from another project is refused even when the authorized project is named.
        self.s.action("team_save", {"project_id": self.p})
        with self.assertRaises(ValueError):
            self.call("team_update_member", {"project_id": self.p, "id": foreign, "role": "lead"}, allow_write=True)

    def test_an_in_app_agent_needs_an_approval_for_every_write(self):
        with self.assertRaises(ValueError):
            self.call("agent_profile_save", {"name": "Sans autorisation", "connector": "alpha"})
        self.call("agent_profile_save", {"name": "Autorisé", "connector": "alpha"}, control=self.control)
        self.assertEqual(len(self.approvals), 1)
        self.assertEqual(self.approvals[0]["scope"], "bibliothèque globale")
        self.assertEqual(self.approvals[0]["tool"], "agent_profile_save")
        self.call("team_save", {"project_id": self.p}, control=self.control)
        self.assertEqual(self.approvals[-1]["scope"], "projet")
        self.control.approve = lambda _: False
        with self.assertRaises(ValueError):
            self.call("agent_profile_save", {"name": "Refusé", "connector": "alpha"}, control=self.control)
        self.control.approve = lambda d: True
        self.control.planning = True
        with self.assertRaises(ValueError):
            self.call("team_add_member", {"project_id": self.p, "profile_id": "x"}, control=self.control)
        self.assertEqual({p["name"] for p in self.s.action("agent_profile_list", {})["profiles"]}, {"Autorisé"})

    def test_team_reads_are_available_to_a_read_only_client(self):
        profile = self.s.action("agent_profile_save", {"name": "Chef", "role": "chief", "connector": "alpha"})["id"]
        self.s.action("team_save", {"project_id": self.p})
        member = self.s.action("team_add_member", {"project_id": self.p, "profile_id": profile, "role": "chief"})["id"]
        self.assertEqual(len(self.call("team_get", {"project_id": self.p})["members"]), 1)
        self.assertEqual(self.call("team_revision_preview", {"project_id": self.p, "id": member})["changes"], [])
        with self.assertRaises(ValueError):
            self.call("team_adopt_revision", {"project_id": self.p, "id": member})


if __name__ == "__main__":
    unittest.main()
