import unittest

import test_core
from cyai import app_mcp


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        for connector in self.s.engine.connectors.values():
            connector.config["enabled"] = True
        self.profile = self.s.action("agent_profile_save", {"name": "Modeleur", "connector": "alpha", "prompt": "Blender"})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def get(self, id):
        return next(p for p in self.s.action("agent_profile_list", {})["profiles"] if p["id"] == id)

    # --- categories ---------------------------------------------------------------------------

    def test_a_category_files_the_profile_without_a_new_revision(self):
        result = self.s.action("agent_profile_category", {"id": self.profile, "category": "3D"})
        self.assertIn("3D", result["notice"])
        profile = self.get(self.profile)
        self.assertEqual((profile["category"], profile["revision"]), ("3D", 1))
        self.s.action("agent_profile_category", {"id": self.profile, "category": ""})
        self.assertEqual(self.get(self.profile)["category"], "")

    def test_the_profile_form_can_file_it_too_still_without_a_revision(self):
        created = self.s.action("agent_profile_save", {"name": "Texturiste", "connector": "alpha", "category": "3D"})
        self.assertEqual(self.get(created["id"])["category"], "3D")
        current = self.get(self.profile)
        unchanged = self.s.action("agent_profile_save", {**{k: current[k] for k in ("name", "connector", "prompt")},
                                                         "id": self.profile, "category": "Recherche"})
        self.assertTrue(unchanged.get("unchanged"), "ranger n’est pas modifier les consignes")
        self.assertEqual((self.get(self.profile)["category"], self.get(self.profile)["revision"]), ("Recherche", 1))

    def test_a_duplicate_stays_in_the_same_category(self):
        self.s.action("agent_profile_category", {"id": self.profile, "category": "3D"})
        copy = self.s.action("agent_profile_duplicate", {"id": self.profile})["id"]
        self.assertEqual(self.get(copy)["category"], "3D")

    def test_a_category_is_short_text(self):
        with self.assertRaises(ValueError):
            self.s.action("agent_profile_category", {"id": self.profile, "category": "x" * 61})

    def test_filing_a_profile_is_a_global_write_through_the_mcp(self):
        op = app_mcp.ACTIONS["agent_profile_category"]
        self.assertEqual((op["scope"], op["write"]), ("global", True))
        with self.assertRaises(ValueError):
            app_mcp.check_scope(self.s, op, {"id": self.profile, "category": "3D"}, [self.fixture.project])

    # --- direct messages with a profile ----------------------------------------------------------

    def test_a_direct_message_opens_the_profile_outside_any_project(self):
        result = self.s.action("agent_direct_message", {"profile_id": self.profile})
        project = self.s.store.one("SELECT * FROM projects WHERE id=?", (result["project_id"],))
        self.assertEqual(project["free_chat"], 1, "un espace de discussion libre, pas un projet")
        conversation = self.s.store.one("SELECT * FROM conversations WHERE id=?", (result["id"],))
        self.assertEqual((conversation["profile_id"], conversation["profile_revision"], conversation["title"]),
                         (self.profile, 1, "Modeleur"))
        self.assertEqual(conversation["agent_id"], "alpha")
        self.assertIn("Blender", conversation["agent_settings"], "ses consignes l’accompagnent")
        other = self.s.action("agent_direct_message", {"profile_id": self.profile})
        self.assertNotEqual(other["project_id"], result["project_id"], "chaque discussion a son propre espace isolé")

    def test_an_archived_profile_cannot_be_messaged(self):
        self.s.action("agent_profile_archive", {"id": self.profile})
        with self.assertRaises(ValueError):
            self.s.action("agent_direct_message", {"profile_id": self.profile})

    def test_a_direct_message_opened_by_mcp_joins_its_allowed_projects(self):
        projects = [self.fixture.project]
        result = app_mcp.call(self.s, "cyai_call", {"action": "agent_direct_message",
                                                       "arguments": {"profile_id": self.profile}},
                              projects, allow_write=True)
        self.assertIn(result["project_id"], projects)


if __name__ == "__main__":
    unittest.main()
