import unittest

import test_core
from cyai import app_mcp
from cyai.context import build_context


class ProjectAssistantTests(unittest.TestCase):
    """A new project comes with its look and its assistant, the first conversation to talk to."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.root = self.fixture.root / "cymd"
        self.root.mkdir()

    def tearDown(self):
        self.fixture.tearDown()

    def create(self, **extra):
        return self.s.action("create_project", {"name": "CyMD", "root": str(self.root), **extra})

    def test_a_project_is_created_with_its_colour_icon_and_category(self):
        project = self.create(color="#e0b040", icon="📝", category="Outils")["id"]
        row = self.s.store.one("SELECT * FROM projects WHERE id=?", (project,))
        self.assertEqual((row["color"], row["icon"], row["category"]), ("#e0b040", "📝", "Outils"))
        self.assertIn("Outils", self.s.config["categories"], "une catégorie nouvelle est créée au passage")
        with self.assertRaises(ValueError):
            self.s.action("create_project", {"name": "Refus", "root": str(self.root), "color": "jaune"})
        self.assertFalse(self.s.store.rows("SELECT id FROM projects WHERE name='Refus'"), "rien n’est créé à moitié")

    def test_the_assistant_comes_first_and_stays_highlighted_until_you_write_to_it(self):
        created = self.create(assistant=True)
        assistant = created["assistant_conversation_id"]
        channels = self.s.action("project_channels", {"project_id": created["id"]})
        first = channels["channels"][0]
        self.assertEqual((first["type"], first["id"], first["category"], first["fresh"]), ("assistant", assistant, "Assistant", True))
        self.assertNotIn(assistant, [c["id"] for c in channels["channels"] if c["type"] == "conversation"], "pas en double parmi les conversations")
        self.assertEqual(self.s.conversation(assistant)["purpose"], "assistant")
        text = build_context(self.s.store, assistant, "Bonjour", {})["text"]
        self.assertIn("Skill activé [Assistant du projet]", text)
        self.assertIn("explore d’abord le dossier du projet", text)
        self.s.store.message(assistant, "user", "C’est une reprise de projet.")
        self.assertFalse(self.s.action("project_channels", {"project_id": created["id"]})["channels"][0]["fresh"])

    def test_an_older_project_gets_its_assistant_when_asked_once(self):
        project = self.fixture.project
        channel = self.s.action("project_channels", {"project_id": project})["channels"][0]
        self.assertEqual((channel["type"], channel["exists"], channel["id"]), ("assistant", False, ""))
        first = self.s.action("project_assistant", {"project_id": project})
        again = self.s.action("project_assistant", {"project_id": project})
        self.assertTrue(first["created"])
        self.assertEqual((again["conversation_id"], again["created"]), (first["conversation_id"], False))
        free = self.s.action("create_free_conversation", {"title": "Libre"})
        with self.assertRaises(ValueError):
            self.s.action("project_assistant", {"project_id": free["project_id"]})
        app_mcp.Draft202012Validator.check_schema(app_mcp.ACTIONS["project_assistant"]["inputSchema"])
        self.assertEqual(app_mcp.ACTIONS["project_assistant"]["scope"], "project_id")

    def test_projects_made_by_the_app_itself_get_no_assistant(self):
        self.s.free_workspace()
        self.assertFalse(self.s.store.rows("SELECT id FROM conversations WHERE purpose='assistant'"))


if __name__ == "__main__":
    unittest.main()
