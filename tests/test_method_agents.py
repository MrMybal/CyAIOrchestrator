import json
import tempfile
import unittest
from pathlib import Path

import test_core
from cyai import app_mcp
from cyai.connectors import Control
from cyai.context import build_context


class MethodAgentTests(unittest.TestCase):
    """Agents prefer or must use methods, keep their own note on them, and the programs a method needs are located."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config = {**connector.config, "enabled": True}
        self.modeller = self.s.action("agent_profile_save", {"name": "Modeleur", "connector": "alpha", "prompt": "Tu modélises."})["id"]
        self.writer = self.s.action("agent_profile_save", {"name": "Rédacteur", "connector": "alpha", "prompt": "Tu écris."})["id"]
        self.mesh = self.s.action("method_save", {
            "name": "Maillage", "description": "Nettoyer un maillage.", "usage": "Donnez le fichier source.",
            "requirements": [{"kind": "software", "name": "LocalMesh", "executable": "localmesh-introuvable-cyai", "detail": "https://example.org/localmesh"}],
            "steps": [{"key": "a", "executor": "profile", "profile_id": self.modeller, "instruction": "Nettoie {objectif}."}]})["id"]
        self.brief = self.s.action("method_save", {"name": "Brief", "steps": [{"key": "a", "executor": "any", "instruction": "Écris."}]})["id"]
        self.other = self.s.action("method_save", {"name": "Autre", "steps": [{"key": "a", "executor": "any", "instruction": "Autre."}]})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def link(self, profile, method, mode):
        return self.s.action("profile_method_set", {"profile_id": profile, "method_id": method, "mode": mode})

    def test_a_profile_prefers_or_must_use_methods_and_they_come_first(self):
        self.link(self.modeller, self.brief, "preferred")
        result = self.link(self.modeller, self.mesh, "always")
        self.assertIn("LocalMesh", result["notice"], "un logiciel absent est dit dès le lien")
        listed = self.s.action("profile_methods", {"profile_id": self.modeller})["methods"]
        self.assertEqual([(m["name"], m["mode"]) for m in listed], [("Maillage", "always"), ("Brief", "preferred")])
        search = self.s.action("method_list", {"profile_id": self.modeller})["methods"]
        self.assertEqual([m["name"] for m in search], ["Maillage", "Brief", "Autre"])
        self.assertEqual(search[0]["preference"], "always")
        self.assertEqual([m["name"] for m in self.s.action("method_list", {})["methods"]], ["Autre", "Brief", "Maillage"], "sans profil : ordre alphabétique")
        agents = self.s.action("method_agents", {"id": self.mesh})["agents"]
        self.assertEqual([(a["name"], a["mode"]) for a in agents], [("Modeleur", "always")])

    def test_the_note_survives_the_link_and_goes_with_its_method(self):
        self.link(self.modeller, self.mesh, "preferred")
        self.s.action("method_note_save", {"profile_id": self.modeller, "method_id": self.mesh, "content": "Toujours fusionner les sommets."})
        self.link(self.modeller, self.mesh, "none")
        kept = self.s.action("profile_methods", {"profile_id": self.modeller})["methods"]
        self.assertEqual([(m["mode"], m["note"], m["note_author"]) for m in kept], [("", "Toujours fusionner les sommets.", "user")])
        self.assertFalse(self.s.action("profile_methods_summary", {})["profiles"], "une note seule n’est pas une préférence")
        self.s.action("method_note_save", {"profile_id": self.modeller, "method_id": self.mesh, "content": ""})
        self.assertFalse(self.s.action("profile_methods", {"profile_id": self.modeller})["methods"])
        self.link(self.modeller, self.mesh, "always")
        self.s.action("method_delete", {"id": self.brief})
        self.s.action("method_delete", {"id": self.mesh})
        self.assertFalse(self.s.store.rows("SELECT * FROM profile_methods"), "les liens partent avec la méthode")

    def test_an_agent_reads_its_methods_and_its_note_in_its_context(self):
        self.link(self.modeller, self.mesh, "always")
        self.s.action("method_note_save", {"profile_id": self.modeller, "method_id": self.mesh, "content": "Vérifier les normales."})
        conversation = self.s.action("profile_conversation", {"project_id": self.p, "profile_id": self.modeller})["id"]
        text = build_context(self.s.store, conversation, "Continuer", {})["text"]
        self.assertIn("« Maillage » [" + self.mesh + "] — à utiliser pour ce type de travail : Nettoyer un maillage.", text)
        self.assertIn("Logiciels requis : LocalMesh", text)
        self.assertIn("Votre note d’usage : Vérifier les normales.", text)
        self.assertIn("method_note_save (profile_id " + self.modeller + ")", text)
        other = self.s.action("profile_conversation", {"project_id": self.p, "profile_id": self.writer})["id"]
        self.assertNotIn("Méthodes de votre profil", build_context(self.s.store, other, "x", {})["text"])
        self.assertNotIn("Méthodes de votre profil", build_context(self.s.store, self.fixture.conversation, "x", {})["text"])

    def test_an_agent_writes_only_its_own_note_and_it_is_signed(self):
        mine = self.s.action("profile_conversation", {"project_id": self.p, "profile_id": self.modeller})["id"]
        control = Control(30, lambda d: True, lambda *_: None)
        control.conversation_id = mine
        app_mcp.call(self.s, "cyai_call", {"action": "method_note_save", "arguments": {
            "profile_id": self.modeller, "method_id": self.mesh, "content": "Ma note."}}, [self.p], control)
        note = self.s.action("method_agents", {"id": self.mesh})["agents"][0]
        self.assertEqual((note["note"], note["note_author"]), ("Ma note.", "agent"))
        with self.assertRaises(ValueError) as refusal:
            app_mcp.call(self.s, "cyai_call", {"action": "method_note_save", "arguments": {
                "profile_id": self.writer, "method_id": self.mesh, "content": "Note d’un autre."}}, [self.p], control)
        self.assertIn("propre profil", str(refusal.exception))
        self.assertIn("software_path_set", app_mcp.USER_ONLY)
        self.assertNotIn("software_path_set", app_mcp.ACTIONS)

    def test_a_program_located_on_this_machine_reaches_the_tasks(self):
        warnings = self.s.action("method_check", {"id": self.mesh})["warnings"]
        self.assertTrue(any(w["where"] == "Prérequis « LocalMesh »" and "Installation : https://example.org/localmesh" in w["message"] for w in warnings))
        with self.assertRaises(ValueError):
            self.s.action("software_path_set", {"name": "LocalMesh", "path": "relatif/localmesh.exe"})
        with self.assertRaises(ValueError):
            self.s.action("software_path_set", {"name": "LocalMesh", "path": str(self.fixture.root / "absent.exe")})
        program = self.fixture.root / "LocalMesh.exe"
        program.write_bytes(b"MZ")
        self.s.action("software_path_set", {"name": "LocalMesh", "path": str(program)})
        self.assertFalse(any(w["where"] == "Prérequis « LocalMesh »" for w in self.s.action("method_check", {"id": self.mesh})["warnings"]))
        saved = json.loads(self.s.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["software_paths"], {"localmesh": str(program)}, "le chemin est gardé pour cette machine")
        self.link(self.modeller, self.mesh, "preferred")
        self.assertEqual(self.s.action("profile_methods_summary", {})["profiles"][self.modeller]["software"], [{"name": "LocalMesh", "found": True}])
        self.s.action("method_note_save", {"profile_id": self.modeller, "method_id": self.mesh, "content": "Exporter en OBJ."})
        mission = self.s.mission(self.s.action("method_apply", {"project_id": self.p, "id": self.mesh, "objective": "la coque"})["mission_id"])
        instruction = mission["steps"][0]["instruction"]
        self.assertIn("LocalMesh → " + str(program), instruction)
        self.assertIn("Votre note d’usage de cette méthode", instruction)
        self.assertIn("Exporter en OBJ.", instruction)
        self.s.action("software_path_set", {"name": "LocalMesh", "path": ""})
        self.assertTrue(any(w["where"] == "Prérequis « LocalMesh »" for w in self.s.action("method_check", {"id": self.mesh})["warnings"]))


if __name__ == "__main__":
    unittest.main()
