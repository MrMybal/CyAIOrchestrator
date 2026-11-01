import io
import json
import time
import unittest

import test_core
from cyai import methods


class MethodWriterTests(unittest.TestCase):
    """Instructions written large: files joined to a task, a workshop with an AI, inputs prepared by an AI."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config = {**connector.config, "enabled": True}
        self.method = self.s.action("method_save", {
            "name": "Affiche", "usage": "Rassemblez le brief complet, puis résumez-le.",
            "inputs": [{"key": "objectif", "name": "Objectif"},
                       {"key": "brief", "name": "Brief complet", "kind": "context", "prepare": "Tout ce que dit le client."},
                       {"key": "court", "name": "Brief court", "kind": "context", "prepare": "Cinq lignes."}],
            "steps": [{"key": "a", "name": "Esquisse", "executor": "any", "instruction": "Esquisse {objectif}.",
                       "inputs": [{"key": "b", "name": "Brief", "kind": "context", "source": {"step": "@entrees", "port": "brief"}}],
                       "outputs": [{"key": "s", "name": "Esquisse"}]},
                      {"key": "b", "name": "Relecture", "executor": "any", "instruction": "Relis l’esquisse.",
                       "inputs": [{"key": "e", "name": "Esquisse", "source": {"step": "a", "port": "s"}}], "outputs": []}]})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def upload(self, name, content):
        return methods.upload_asset(self.s, self.method, name, io.BytesIO(content), len(content))["id"]

    def body(self):
        return self.s.action("method_get", {"id": self.method})["method"]

    def attach(self, *assets):
        body = self.body()
        body["steps"][0]["attachments"] = list(assets)
        return self.s.action("method_save", body)

    def settle(self, mission_id, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            mission = self.s.mission(mission_id)
            if mission["status"] in {"succeeded", "failed", "cancelled"}:
                return mission
            time.sleep(.05)
        raise AssertionError("mission non terminée")

    # --- files joined to a task --------------------------------------------------------------------------

    def test_a_task_carries_its_files_and_only_that_task_receives_them(self):
        palette = self.upload("palette.txt", "BLEU NUIT ET CUIVRE".encode())
        self.attach(palette)
        self.assertEqual(self.body()["steps"][0]["attachments"], [palette])
        applied = self.s.action("method_apply", {"project_id": self.p, "id": self.method, "objective": "une affiche", "connector": "alpha",
                                                 "inputs": {"brief": "BRIEF"}})
        mission = self.s.mission(applied["mission_id"])
        first, second = mission["spec"]["steps"]
        self.assertEqual(len(first["file_ids"]), 1)
        self.assertNotIn("file_ids", second)
        self.assertIn("palette.txt", first["instruction"])
        copy = self.s.store.one("SELECT * FROM files WHERE id=?", (first["file_ids"][0],))
        self.assertEqual((copy["conversation_id"], copy["kind"], copy["name"]), (applied["conversation_id"], "media", "palette.txt"))
        self.s.action("launch_mission", {"mission_id": applied["mission_id"]})
        self.assertEqual(self.settle(applied["mission_id"])["status"], "succeeded")
        calls = [p for p, _ in self.s.engine.connectors["alpha"].calls]
        sketch = next(p for p in calls if "Esquisse une affiche" in p)
        review = next(p for p in calls if "Relis l’esquisse" in p)
        self.assertIn("BLEU NUIT ET CUIVRE", sketch, "le contenu du fichier texte arrive avec sa tâche")
        self.assertNotIn("BLEU NUIT ET CUIVRE", review)

    def test_a_file_in_use_cannot_be_deleted_and_goes_with_its_method(self):
        palette = self.upload("palette.txt", b"x")
        self.attach(palette)
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_asset_delete", {"id": palette})
        self.assertIn("Esquisse", str(refusal.exception))
        self.attach()
        self.s.action("method_asset_delete", {"id": palette})
        self.assertFalse(self.s.action("method_assets", {"id": self.method})["assets"])
        kept = self.upload("garde.txt", b"y")
        self.s.action("method_delete", {"id": self.method})
        self.assertFalse((methods._asset_folder(self.s) / kept).exists(), "les fichiers partent avec la méthode")

    def test_an_unknown_file_is_refused_and_limits_hold(self):
        body = self.body()
        body["steps"][0]["attachments"] = ["0" * 32]
        with self.assertRaises(ValueError):
            self.s.action("method_save", body)
        with self.assertRaises(ValueError):
            methods.upload_asset(self.s, self.method, "vide.txt", io.BytesIO(b""), 0)

    def test_files_travel_in_the_export_and_come_back_attached(self):
        palette = self.upload("palette.txt", "CUIVRE".encode())
        self.attach(palette)
        export = self.s.action("method_export", {"id": self.method})
        self.assertEqual([a["name"] for a in export["assets"]], ["palette.txt"])
        other = test_core.CoreTests()
        other.setUp()
        try:
            result = other.service.action("method_import", {"data": json.dumps(export)})
            step = other.service.action("method_get", {"id": result["id"]})["method"]["steps"][0]
            self.assertEqual(len(step["attachments"]), 1)
            row, meta, path = methods.locate_asset(other.service, step["attachments"][0])
            self.assertEqual((row["name"], path.read_bytes()), ("palette.txt", "CUIVRE".encode()))
        finally:
            other.tearDown()

    def test_files_too_heavy_for_the_export_are_named_not_hidden(self):
        self.attach(self.upload("lourd.bin", b"0" * 64))
        limit = methods.MAX_EMBED_BYTES
        methods.MAX_EMBED_BYTES = 10
        try:
            export = self.s.action("method_export", {"id": self.method})
        finally:
            methods.MAX_EMBED_BYTES = limit
        self.assertEqual(export["skipped_assets"], ["lourd.bin"])
        self.assertIn("lourd.bin", export["notice"])
        other = test_core.CoreTests()
        other.setUp()
        try:
            result = other.service.action("method_import", {"data": export})
            self.assertTrue(any("pas dans l’export" in w["message"] for w in result["warnings"]))
        finally:
            other.tearDown()

    # --- the workshop -----------------------------------------------------------------------------------

    def test_the_workshop_is_one_free_conversation_per_method(self):
        first = self.s.action("method_workshop", {"id": self.method})
        again = self.s.action("method_workshop", {"id": self.method})
        self.assertTrue(first["created"])
        self.assertEqual((again["conversation_id"], again["created"]), (first["conversation_id"], False))
        conversation = self.s.conversation(first["conversation_id"])
        self.assertIn("Atelier · Affiche", conversation["title"])
        project = self.s.store.one("SELECT free_chat FROM projects WHERE id=?", (conversation["project_id"],))
        self.assertEqual(project["free_chat"], 1, "hors de tout projet : aucune mémoire de projet héritée")

    def test_a_workshop_request_carries_the_draft_once_and_the_text_worked_on(self):
        draft = self.body()
        draft["steps"][0]["instruction"] = "BROUILLON NON ENREGISTRÉ"
        sent = self.s.action("method_workshop_send", {"id": self.method, "draft": draft, "target": {"step": "a"},
                                                      "instruction": "Rends-la plus précise.", "connector": "alpha"})
        self.settle(sent["mission_id"])
        message = self.s.store.rows("SELECT content FROM messages WHERE conversation_id=? AND role='user'", (sent["conversation_id"],))[-1]["content"]
        self.assertIn("```json", message)
        self.assertIn("BROUILLON NON ENREGISTRÉ", message, "l’IA voit le brouillon, pas seulement la version enregistrée")
        self.assertIn("```consigne", message)
        self.assertTrue(message.rstrip().endswith("Rends-la plus précise."))
        again = self.s.action("method_workshop_send", {"id": self.method, "draft": draft, "target": {"step": "a"},
                                                       "instruction": "Et plus courte.", "connector": "alpha"})
        self.settle(again["mission_id"])
        second = self.s.store.rows("SELECT content FROM messages WHERE conversation_id=? AND role='user'", (sent["conversation_id"],))[-1]["content"]
        self.assertNotIn("```json", second, "un brouillon inchangé n’est pas renvoyé")
        self.assertIn("inchangée", second)
        self.s.engine.connectors["beta"].config = {"enabled": False}
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_workshop_send", {"id": self.method, "target": {"field": "usage"}, "instruction": "x", "connector": "beta"})
        self.assertIn("désactivé", str(refusal.exception))

    # --- inputs prepared by an AI ----------------------------------------------------------------------

    def test_an_ai_drafts_the_inputs_and_nothing_is_applied(self):
        self.s.engine.connectors["alpha"].answer = lambda prompt: (
            "### Entrée : Brief complet (contexte)\nLE CLIENT VEUT DU CUIVRE\n\nRien d’autre." if "Préparez les entrées" in prompt else "ok")
        started = self.s.action("method_prepare_inputs", {"id": self.method, "objective": "une affiche", "material": "notes du client",
                                                          "connector": "alpha"})
        self.settle(started["mission_id"])
        sent = self.s.engine.connectors["alpha"].calls[-1][0]
        self.assertIn("Rassemblez le brief complet", sent, "le mode d’emploi guide la préparation")
        self.assertIn("### Entrée : Brief court (contexte) — préparation : Cinq lignes.", sent)
        self.assertIn("notes du client", sent)
        result = self.s.action("method_prepared_inputs", {"id": self.method, "mission_id": started["mission_id"]})
        self.assertEqual(result["inputs"], {"brief": "LE CLIENT VEUT DU CUIVRE\n\nRien d’autre."})
        self.assertEqual(result["missing"], ["Brief court"])
        self.assertFalse(self.s.store.rows("SELECT id FROM missions WHERE title LIKE 'Affiche%'"), "préparer n’applique rien")
        other = self.s.action("create_conversation", {"project_id": self.p, "title": "Autre"})["id"]
        foreign = self.s.action("create_mission", {"conversation_id": other, "launch": False,
                                                   "steps": [{"connector": "alpha", "instruction": "x"}]})["mission_id"]
        with self.assertRaises(ValueError):
            self.s.action("method_prepared_inputs", {"id": self.method, "mission_id": foreign})


if __name__ == "__main__":
    unittest.main()
