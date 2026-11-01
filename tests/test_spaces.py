import unittest

import test_core
from cyai import app_mcp


class SpaceTests(unittest.TestCase):
    """Channels created in a project: a whiteboard an AI can draw on, and graphs computed from the project."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        self.board = self.s.action("space_create", {"project_id": self.p, "name": "Idées", "type": "whiteboard"})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def content(self):
        return {"notes": [{"id": "a", "x": 10, "y": 20, "text": "Coque", "color": "blue"},
                          {"id": "b", "x": 300, "y": 20, "text": "Moteurs"}],
                "links": [{"from": "a", "to": "b", "label": "alimente"}]}

    def test_a_whiteboard_is_a_channel_of_its_own_category(self):
        channels = self.s.action("project_channels", {"project_id": self.p})
        channel = next(c for c in channels["channels"] if c["id"] == self.board)
        self.assertEqual((channel["type"], channel["category"], channel["name"]), ("whiteboard", "Espaces", "Idées"))

    def test_notes_and_links_are_saved_and_read_back(self):
        base = self.s.action("space_get", {"project_id": self.p, "id": self.board})["space"]["updated_at"]
        saved = self.s.action("whiteboard_save", {"project_id": self.p, "id": self.board, "data": self.content(), "base": base})
        self.assertEqual((saved["notes"], saved["links"]), (2, 1))
        space = self.s.action("space_get", {"project_id": self.p, "id": self.board})["space"]
        self.assertEqual([n["text"] for n in space["data"]["notes"]], ["Coque", "Moteurs"])
        self.assertEqual(space["data"]["notes"][1]["color"], "yellow", "couleur par défaut")
        self.assertEqual(space["data"]["links"], [{"from": "a", "to": "b", "label": "alimente"}])

    def test_a_board_changed_elsewhere_is_never_overwritten(self):
        base = self.s.action("space_get", {"project_id": self.p, "id": self.board})["space"]["updated_at"]
        self.s.action("whiteboard_save", {"project_id": self.p, "id": self.board, "data": self.content(), "base": base})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("whiteboard_save", {"project_id": self.p, "id": self.board, "data": {"notes": []}, "base": base})
        self.assertIn("modifié ailleurs", str(refusal.exception))
        self.assertEqual(len(self.s.action("space_get", {"project_id": self.p, "id": self.board})["space"]["data"]["notes"]), 2)

    def test_invalid_content_is_refused(self):
        for data in ({"notes": [{"id": "a", "x": 0, "y": 0, "color": "rouge-vif"}]},
                     {"notes": [{"id": "a", "x": 0, "y": 0}], "links": [{"from": "a", "to": "fantome"}]},
                     {"notes": [{"id": "a", "x": 0, "y": 0}, {"id": "a", "x": 1, "y": 1}]}):
            with self.assertRaises(ValueError):
                self.s.action("whiteboard_save", {"project_id": self.p, "id": self.board, "data": data})

    def test_rename_delete_and_project_scope(self):
        self.s.action("space_rename", {"project_id": self.p, "id": self.board, "name": "Concept"})
        self.assertEqual(self.s.action("space_get", {"project_id": self.p, "id": self.board})["space"]["name"], "Concept")
        other = self.s.action("create_project", {"name": "Autre", "root": str(self.fixture.root)})["id"]
        with self.assertRaises(ValueError):
            self.s.action("space_get", {"project_id": other, "id": self.board})
        op = app_mcp.ACTIONS["whiteboard_save"]
        self.assertEqual((op["scope"], op["write"]), ("project_id", True))
        with self.assertRaises(ValueError):
            app_mcp.check_scope(self.s, op, {"project_id": other, "id": self.board, "data": {}}, [self.p])
        self.s.action("space_delete", {"project_id": self.p, "id": self.board})
        self.assertFalse(self.s.store.rows("SELECT id FROM project_spaces"))

    def test_boards_are_backed_up_and_older_backups_still_restore(self):
        self.s.action("whiteboard_save", {"project_id": self.p, "id": self.board, "data": self.content()})
        backup = self.s.action("backup", {})
        self.assertEqual(len(backup["tables"]["project_spaces"]), 1)
        older = {**backup, "tables": {k: v for k, v in backup["tables"].items() if k != "project_spaces"}}
        self.s.action("restore", {"backup": older, "acknowledged": True})
        self.assertFalse(self.s.store.rows("SELECT id FROM project_spaces"), "une sauvegarde plus ancienne n’en contenait pas")
        self.s.action("restore", {"backup": backup, "acknowledged": True})
        self.assertEqual(len(self.s.store.rows("SELECT id FROM project_spaces")), 1)

    # --- graphs ----------------------------------------------------------------------------------------

    def team(self):
        for connector in self.s.engine.connectors.values():
            connector.config["enabled"] = True
        chief = self.s.action("agent_profile_save", {"name": "Chef", "role": "chief", "connector": "alpha"})["id"]
        dev = self.s.action("agent_profile_save", {"name": "Dev", "role": "member", "connector": "alpha"})["id"]
        self.s.action("team_save", {"project_id": self.p})
        c = self.s.action("team_add_member", {"project_id": self.p, "profile_id": chief, "role": "chief"})["id"]
        d = self.s.action("team_add_member", {"project_id": self.p, "profile_id": dev, "role": "member", "manager_id": c})["id"]
        return c, d

    def test_a_task_graph_follows_the_board_as_it_is_now(self):
        chief, dev = self.team()
        graph = self.s.action("space_create", {"project_id": self.p, "name": "Tâches", "type": "graph", "source": "tasks"})["id"]
        self.assertEqual(self.s.action("graph_data", {"project_id": self.p, "id": graph})["nodes"], [])
        a = self.s.action("task_create", {"project_id": self.p, "author_id": chief, "assignee_id": dev, "objective": "Concept"})["id"]
        b = self.s.action("task_create", {"project_id": self.p, "author_id": chief, "assignee_id": dev, "objective": "Modèle",
                                          "dependencies": [a]})["id"]
        data = self.s.action("graph_data", {"project_id": self.p, "id": graph})
        self.assertEqual([n["label"] for n in data["nodes"]], ["Concept", "Modèle"])
        self.assertEqual(data["nodes"][0]["detail"], "Dev")
        self.assertIn({"from": a, "to": b, "kind": "dependency"}, data["edges"])
        self.s.action("task_status", {"project_id": self.p, "id": a, "status": "ready", "author_id": chief})
        self.assertEqual(self.s.action("graph_data", {"project_id": self.p, "id": graph})["nodes"][0]["status"], "ready",
                         "rien n’est figé : le graphe est recalculé à chaque lecture")

    def test_a_team_graph_draws_the_hierarchy(self):
        chief, dev = self.team()
        graph = self.s.action("space_create", {"project_id": self.p, "type": "graph", "source": "team"})["id"]
        data = self.s.action("graph_data", {"project_id": self.p, "id": graph})
        self.assertEqual({n["status"] for n in data["nodes"]}, {"chief", "member"})
        listed = next(c for c in self.s.action("project_channels", {"project_id": self.p})["channels"] if c["id"] == graph)
        self.assertEqual((listed["type"], listed["category"]), ("graph", "Espaces"), "un graphe se liste comme un salon")
        self.assertEqual(data["edges"], [{"from": chief, "to": dev, "kind": "manager"}])
        with self.assertRaises(ValueError):
            self.s.action("space_create", {"project_id": self.p, "type": "graph", "source": "inconnue"})
        with self.assertRaises(ValueError):
            self.s.action("whiteboard_save", {"project_id": self.p, "id": graph, "data": {"notes": []}})


    # --- plugin console --------------------------------------------------------------------------------

    def plugin(self, enabled=True):
        self.s.plugins.config["plugins"]["blender"] = {
            "id": "blender", "name": "Blender", "type": "mcp", "transport": "stdio", "command": "blender-mcp",
            "enabled": enabled, "read_tools": ["scene_info"], "projects": {}}
        self.rpc_calls = []

        def rpc(plugin, method, params):
            self.rpc_calls.append((method, params))
            if method == "tools/list":
                return {"tools": [{"name": "scene_info", "description": "Décrire la scène.", "inputSchema": {"type": "object"}},
                                  {"name": "delete_all", "description": "Tout effacer.", "inputSchema": {"type": "object"}}]}
            if method == "resources/list":
                return {"resources": []}
            return {"content": [{"type": "text", "text": "3 objets : " + str(params["arguments"])}], "isError": False}

        self.s.plugins.rpc = rpc

    def test_a_plugin_console_offers_only_read_tools_and_keeps_its_history(self):
        self.plugin()
        console = self.s.action("space_create", {"project_id": self.p, "type": "plugin", "plugin": "blender"})
        self.assertEqual(console["name"], "Blender")
        view = self.s.action("plugin_console", {"project_id": self.p, "id": console["id"]})
        self.assertEqual([t["name"] for t in view["tools"]], ["scene_info"], "un outil qui agit n’est jamais proposé")
        call = self.s.action("plugin_console_call", {"project_id": self.p, "id": console["id"], "tool": "scene_info",
                                                     "arguments": {"filtre": "mesh"}})["call"]
        self.assertTrue(call["ok"])
        self.assertIn("3 objets", call["result"])
        refused = self.s.action("plugin_console_call", {"project_id": self.p, "id": console["id"], "tool": "delete_all"})["call"]
        self.assertFalse(refused["ok"])
        self.assertIn("non autorisé", refused["error"])
        self.assertNotIn("delete_all", [p.get("name") for m, p in self.rpc_calls if m == "tools/call"], "l’outil refusé n’atteint pas le plugin")
        history = self.s.action("plugin_console", {"project_id": self.p, "id": console["id"]})["calls"]
        self.assertEqual([c["tool"] for c in history], ["delete_all", "scene_info"], "le plus récent d’abord")

    def test_a_disabled_plugin_cannot_get_a_console_and_an_old_console_says_why(self):
        self.plugin(enabled=False)
        with self.assertRaises(ValueError):
            self.s.action("space_create", {"project_id": self.p, "type": "plugin", "plugin": "blender"})
        self.plugin()
        console = self.s.action("space_create", {"project_id": self.p, "type": "plugin", "plugin": "blender"})["id"]
        self.s.plugins.config["plugins"]["blender"]["projects"] = {self.p: {"enabled": False}}
        view = self.s.action("plugin_console", {"project_id": self.p, "id": console})
        self.assertIn("désactivé pour ce projet", view["problem"])
        self.assertEqual(view["tools"], [])
        call = self.s.action("plugin_console_call", {"project_id": self.p, "id": console, "tool": "scene_info"})["call"]
        self.assertFalse(call["ok"])
        listed = next(c for c in self.s.action("project_channels", {"project_id": self.p})["channels"] if c["id"] == console)
        self.assertEqual(listed["type"], "plugin")


if __name__ == "__main__":
    unittest.main()
