import json
import time
import unittest

import test_core
from cyai import toolpacks
from cyai.connectors import Control


class ToolPackTests(unittest.TestCase):
    """A profile that may drive a plugin (here a Blender-like MCP server) while it works."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config = {**connector.config, "enabled": True}
        self.s.plugins.config["plugins"]["blender"] = {
            "id": "blender", "name": "Blender", "type": "mcp", "transport": "stdio", "command": "blender-mcp",
            "enabled": True, "read_tools": ["scene_info"], "projects": {}}
        self.calls = []

        def rpc(plugin, method, params):
            self.calls.append((plugin["id"], method, params))
            if method == "tools/list":
                return {"tools": [{"name": "scene_info", "description": "Décrire la scène.", "inputSchema": {"type": "object"}},
                                  {"name": "create_object", "description": "Créer un objet.",
                                   "inputSchema": {"type": "object", "properties": {"kind": {"type": "string"}}}}]}
            return {"content": [{"type": "text", "text": "ok:" + params["name"]}], "isError": False}

        self.s.plugins.rpc = rpc
        self.modeller = self.s.action("agent_profile_save", {"name": "Modeleur", "role": "member", "connector": "alpha",
                                                             "tools": ["blender"], "prompt": "Tu modélises dans Blender."})["id"]
        self.conversation = self.s.action("create_conversation", {"project_id": self.p, "title": "Modelage"})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def run_agent(self, profile, script):
        seen = {"tools": [], "results": []}

        def run(prompt, root, model, native_id, control):
            control.emit("session", {"native_id": "n"})
            token = control.mcp_servers["cyai_plugins"]["env"]["CYAI_PLUGIN_TOKEN"]
            seen["tools"] = self.s.plugins.gateway(token, {"method": "tools/list"})["tools"]
            for name, arguments in script:
                seen["results"].append(self.s.plugins.gateway(token, {"method": "tools/call",
                                                                      "params": {"name": name, "arguments": arguments}}))
            return "terminé"

        self.s.engine.connectors["alpha"].run = run
        mission = self.s.action("create_mission", {"conversation_id": self.conversation, "title": "Essai",
                                                   "steps": [{"profile_id": profile, "instruction": "Modélise."}]})["mission_id"]
        self.s.engine.launch(mission)
        deadline = time.time() + 20
        while time.time() < deadline and self.s.store.one("SELECT status FROM missions WHERE id=?", (mission,))["status"] in (
                "queued", "running", "awaiting_approval", "pausing"):
            time.sleep(.05)
        return seen, self.s.mission(mission)

    # --- exposure ---------------------------------------------------------------------------

    def test_the_tools_of_a_pack_reach_only_the_profile_that_declares_it(self):
        seen, mission = self.run_agent(self.modeller, [])
        names = {t["name"]: t for t in seen["tools"]}
        self.assertIn("outil__blender__scene_info", names)
        self.assertIn("outil__blender__create_object", names)
        self.assertTrue(names["outil__blender__scene_info"]["annotations"]["readOnlyHint"])
        self.assertFalse(names["outil__blender__create_object"]["annotations"]["readOnlyHint"])
        self.assertIn("soumis à autorisation", names["outil__blender__create_object"]["description"])
        plain = self.s.action("agent_profile_save", {"name": "Sans outil", "role": "member", "connector": "alpha"})["id"]
        seen, mission = self.run_agent(plain, [])
        self.assertFalse([t for t in seen["tools"] if t["name"].startswith("outil__")], "aucun outil de plugin sans déclaration")

    def test_a_plugin_disabled_for_the_project_is_neither_listed_nor_callable(self):
        self.s.plugins.config["plugins"]["blender"]["projects"] = {self.p: {"enabled": False}}
        seen, mission = self.run_agent(self.modeller, [("outil__blender__scene_info", {})])
        self.assertFalse([t for t in seen["tools"] if t["name"].startswith("outil__")])
        self.assertTrue(seen["results"][0]["isError"])
        self.assertIn("Plugin indisponible", seen["results"][0]["content"][0]["text"])
        self.assertFalse([c for c in self.calls if c[1] == "tools/call"])

    # --- calls ------------------------------------------------------------------------------

    def test_a_read_tool_runs_freely_and_is_recorded(self):
        seen, mission = self.run_agent(self.modeller, [("outil__blender__scene_info", {})])
        self.assertEqual(seen["results"][0]["content"][0]["text"], "ok:scene_info")
        self.assertIn(("blender", "tools/call", {"name": "scene_info", "arguments": {}}), self.calls)
        called = [e["data"] for e in mission["events"] if e["kind"] == "tool_called"]
        self.assertEqual((called[0]["plugin"], called[0]["tool"], called[0]["read_only"]), ("blender", "scene_info", True))
        self.assertNotIn("approval_requested", [e["kind"] for e in mission["events"]], "une lecture ne demande rien")

    def test_an_acting_tool_goes_through_the_approval_policy(self):
        self.s.engine.approval_default = "auto"  # Stands for the user accepting.
        seen, mission = self.run_agent(self.modeller, [("outil__blender__create_object", {"kind": "coque"})])
        self.assertEqual(seen["results"][0]["content"][0]["text"], "ok:create_object")
        kinds = [e["kind"] for e in mission["events"]]
        self.assertIn("approval_resolved", kinds, "l’outil qui agit est passé par l’autorisation")
        self.assertIn("tool_called", kinds)
        self.assertIn(("blender", "tools/call", {"name": "create_object", "arguments": {"kind": "coque"}}), self.calls)

    def test_a_refused_acting_tool_never_reaches_the_plugin(self):
        events = []
        control = Control(30, lambda request: False, lambda kind, data: events.append((kind, data)))
        grant = {"projects": [self.p], "control": control,
                 "packs": toolpacks.available(self.s, self.p, {"tools": ["blender"]})}
        with self.assertRaises(ValueError) as refusal:
            toolpacks.call(self.s, grant, "outil__blender__create_object", {"kind": "coque"})
        self.assertIn("refusée", str(refusal.exception))
        self.assertIn("Poursuivez sans cet outil", str(refusal.exception))
        self.assertFalse([c for c in self.calls if c[1] == "tools/call"])
        self.assertEqual(events[0][0], "tool_refused")

    def test_a_tool_outside_the_declared_pack_is_refused(self):
        self.s.plugins.config["plugins"]["autre"] = {"id": "autre", "name": "Autre", "type": "mcp", "transport": "stdio",
                                                     "command": "x", "enabled": True, "read_tools": ["lire"], "projects": {}}
        seen, mission = self.run_agent(self.modeller, [("outil__autre__lire", {})])
        self.assertTrue(seen["results"][0]["isError"])
        self.assertIn("ne fait pas partie des outils déclarés", seen["results"][0]["content"][0]["text"])

    # --- declaration ------------------------------------------------------------------------

    def test_a_pack_is_validated_versioned_and_overridable(self):
        profile = self.s.action("agent_profile_get", {"id": self.modeller})
        self.assertEqual(profile["tools"], ["blender"])
        self.assertEqual(profile["revisions"][0]["definition"]["tools"], ["blender"])
        with self.assertRaises(ValueError) as refusal:
            self.s.action("agent_profile_save", {"id": self.modeller, "name": "Modeleur", "connector": "alpha", "tools": ["inexistant"]})
        self.assertIn("Configurez-le d’abord", str(refusal.exception))
        with self.assertRaises(ValueError):
            self.s.action("agent_profile_save", {"id": self.modeller, "name": "Modeleur", "connector": "alpha",
                                                 "tools": ["blender"] * 3 + [str(i) for i in range(12)]})
        self.s.action("team_save", {"project_id": self.p})
        member = self.s.action("team_add_member", {"project_id": self.p, "profile_id": self.modeller, "role": "chief"})["id"]
        self.s.action("team_update_member", {"project_id": self.p, "id": member, "overrides": {"tools": []}})
        card = [m for m in self.s.action("team_get", {"project_id": self.p})["members"] if m["id"] == member][0]
        self.assertEqual((card["definition"]["tools"], card["frozen"]["tools"]), ([], ["blender"]))
        self.assertIn("Outils (plugins)", card["override_labels"])


if __name__ == "__main__":
    unittest.main()
