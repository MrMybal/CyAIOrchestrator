import json
import sys
import unittest

import test_core
from cyai import app_mcp
from cyai.specialists import definition_for_step


class MethodGraphTests(unittest.TestCase):
    """Methods as graphs usable by any AI, carried between machines with their warnings."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config = {**connector.config, "enabled": True}
        self.concept = self.s.action("agent_profile_save", {"name": "Concepteur", "connector": "alpha", "model": "alpha-1",
                                                            "prompt": "Tu produis le concept."})["id"]
        self.images = self.s.action("agent_profile_save", {"name": "Imagier", "connector": "beta", "prompt": "Tu fais des images."})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def graph(self, **extra):
        return self.s.action("method_save", {
            "name": "Vaisseau", "preprompt": "Méthode maison pour {objectif}. Travaille proprement.",
            "steps": [
                {"key": "revue", "executor": "any", "instruction": "Relis le concept.", "depends_on": ["concept"],
                 "position": {"x": 400, "y": 80}},
                {"key": "concept", "executor": "profile", "profile_id": self.concept, "instruction": "Conçois {objectif}.",
                 "depends_on": [], "helpers": [self.images], "position": {"x": 80, "y": 80}},
                {"key": "brut", "executor": "connector", "connector": "beta", "model": "beta-2",
                 "instruction": "Produis la silhouette.", "depends_on": ["concept"]}], **extra})

    # --- authoring --------------------------------------------------------------------------------

    def test_a_graph_is_saved_in_dependency_order_with_its_positions(self):
        saved = self.graph()
        method = self.s.action("method_get", {"id": saved["id"]})["method"]
        self.assertEqual([s["key"] for s in method["steps"]], ["concept", "revue", "brut"],
                         "une tâche peut dépendre d’une tâche écrite plus loin : l’ordre vient des dépendances")
        self.assertEqual(method["steps"][0]["position"], {"x": 80.0, "y": 80.0})
        self.assertEqual(method["steps"][0]["helpers"], [self.images])
        self.assertEqual(method["steps"][1]["executor"], "any")
        self.assertEqual((method["steps"][2]["connector"], method["steps"][2]["model"]), ("beta", "beta-2"))
        self.assertIn("{objectif}", method["preprompt"])

    def test_a_loop_is_refused_even_across_several_tasks(self):
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_save", {"name": "Boucle", "steps": [
                {"key": "a", "executor": "any", "instruction": "A", "depends_on": ["c"]},
                {"key": "b", "executor": "any", "instruction": "B", "depends_on": ["a"]},
                {"key": "c", "executor": "any", "instruction": "C", "depends_on": ["b"]}]})
        self.assertIn("boucle", str(refusal.exception))
        self.assertIn("se pilote sur le board", str(refusal.exception))
        with self.assertRaises(ValueError):
            self.s.action("method_save", {"name": "Fantôme", "steps": [
                {"key": "a", "executor": "any", "instruction": "A", "depends_on": ["nulle-part"]}]})

    def test_a_draft_task_without_instruction_is_kept_but_cannot_be_applied(self):
        saved = self.s.action("method_save", {"name": "Brouillon", "steps": [{"key": "a", "executor": "any", "instruction": ""}]})
        self.assertTrue(any("aucune consigne" in w["message"] for w in saved["warnings"]))
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_apply", {"project_id": self.p, "id": saved["id"], "objective": "x", "connector": "alpha"})
        self.assertIn("sans consigne", str(refusal.exception))

    # --- applying ---------------------------------------------------------------------------------

    def test_applying_resolves_every_kind_of_executor_and_the_base_prompt(self):
        saved = self.graph()
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_apply", {"project_id": self.p, "id": saved["id"], "objective": "un cargo"})
        self.assertIn("n’importe quelle IA", str(refusal.exception))
        result = self.s.action("method_apply", {"project_id": self.p, "id": saved["id"], "objective": "un cargo",
                                                "connector": "alpha", "model": "alpha-9"})
        mission = self.s.mission(result["mission_id"])
        self.assertEqual(mission["status"], "pending", "rien ne démarre")
        concept, revue, brut = mission["steps"]
        self.assertEqual((concept["connector"], revue["connector"], revue["model"], brut["connector"], brut["model"]),
                         ("alpha", "alpha", "alpha-9", "beta", "beta-2"))
        self.assertTrue(concept["instruction"].startswith("Tu produis le concept."), "les consignes du profil passent en premier")
        self.assertIn("Méthode maison pour un cargo.", concept["instruction"])
        self.assertIn("Méthode maison pour un cargo.", brut["instruction"], "le prompt de base précède chaque tâche")
        self.assertEqual(mission["spec"]["steps"][1]["depends_on"], [0])
        self.assertEqual(mission["spec"]["steps"][0]["helpers"], [self.images])

    def test_the_agents_of_a_task_become_callable_during_that_task(self):
        conversation = self.fixture.conversation
        definition = definition_for_step(self.s, conversation, {"profile_id": self.concept, "helpers": [self.images]})
        self.assertIn(self.images, [h["profile_id"] for h in definition["helpers"]])
        anonymous = definition_for_step(self.s, conversation, {"connector": "alpha", "helpers": [self.images]})
        self.assertEqual([h["profile_id"] for h in anonymous["helpers"]], [self.images], "même sans profil, la tâche peut appeler un agent")
        self.assertIsNone(definition_for_step(self.s, conversation, {"connector": "alpha"}))

    # --- this machine -------------------------------------------------------------------------------

    def test_missing_software_is_a_warning_never_a_refusal(self):
        saved = self.graph(requirements=[
            {"kind": "software", "name": "Blender", "executable": "blender-introuvable-cyai"},
            {"kind": "software", "name": "Python", "executable": sys.executable},
            {"kind": "plugin", "name": "blender-mcp"},
            {"kind": "note", "name": "Tablette graphique", "detail": "une tablette pour les retouches"}])
        warnings = {(w["where"], w["level"]) for w in self.s.action("method_check", {"id": saved["id"]})["warnings"]}
        self.assertIn(("Prérequis « Blender »", "warning"), warnings)
        self.assertNotIn(("Prérequis « Python »", "warning"), warnings, "un programme trouvé ne produit aucun avertissement")
        self.assertIn(("Prérequis « blender-mcp »", "warning"), warnings)
        self.assertIn(("Prérequis « Tablette graphique »", "info"), warnings)
        result = self.s.action("method_apply", {"project_id": self.p, "id": saved["id"], "objective": "un cargo", "connector": "alpha"})
        self.assertIn("Blender", result["notice"], "l’application prévient sans refuser")

    def test_a_disabled_connector_is_reported_per_task(self):
        saved = self.graph()
        self.s.engine.connectors["beta"].config = {**self.s.engine.connectors["beta"].config, "enabled": False}
        warnings = self.s.action("method_check", {"id": saved["id"]})["warnings"]
        self.assertTrue(any(w["where"] == "Tâche « Tâche 3 »" and "désactivé" in w["message"] for w in warnings))

    # --- moving between machines --------------------------------------------------------------------

    def exported(self):
        return self.s.action("method_export", {"id": self.graph()["id"]})

    def test_an_export_carries_the_profiles_it_uses_and_no_secret(self):
        export = self.exported()
        self.assertEqual((export["format"], export["version"]), ("cyai-method", 1))
        self.assertEqual({p["name"] for p in export["profiles"]}, {"Concepteur", "Imagier"})
        self.assertEqual(export["profiles"][0]["definition"]["prompt"], "Tu produis le concept.")
        text = json.dumps(export).lower()
        for secret in ("token", "api_key", "native_id", "password"):
            self.assertNotIn(secret, text)

    def test_importing_on_another_machine_recreates_the_profiles_with_warnings(self):
        export = self.exported()
        other = test_core.CoreTests()
        other.setUp()
        try:
            service = other.service
            service.engine.connectors["alpha"].config = {"enabled": True}
            result = service.action("method_import", {"data": json.dumps(export)})
            self.assertEqual(sorted(result["created_profiles"]), ["Concepteur", "Imagier"])
            names = {p["name"] for p in service.action("agent_profile_list", {})["profiles"]}
            self.assertEqual(names, {"Concepteur", "Imagier"})
            self.assertTrue(any("beta" in w["message"] and w["level"] == "warning" for w in result["warnings"]),
                            "ce qui manque ici est signalé, pas refusé")
            method = service.action("method_get", {"id": result["id"]})["method"]
            self.assertEqual(method["steps"][0]["executor"], "profile")
            self.assertEqual(len(method["steps"][0]["helpers"]), 1)
        finally:
            other.tearDown()

    def test_without_creating_profiles_their_tasks_go_to_any_ai(self):
        export = self.exported()
        other = test_core.CoreTests()
        other.setUp()
        try:
            result = other.service.action("method_import", {"data": export, "create_profiles": False})
            self.assertFalse(result["created_profiles"])
            method = other.service.action("method_get", {"id": result["id"]})["method"]
            self.assertEqual({s["executor"] for s in method["steps"]}, {"any", "connector"})
            self.assertTrue(any("n’importe quelle IA" in w["message"] for w in result["warnings"]))
            self.assertFalse(other.service.action("agent_profile_list", {})["profiles"], "rien n’est créé sans votre accord")
        finally:
            other.tearDown()

    def test_an_import_on_the_same_machine_reuses_the_profiles_and_keeps_both_methods(self):
        export = self.exported()
        result = self.s.action("method_import", {"data": export})
        self.assertFalse(result["created_profiles"])
        self.assertEqual(result["name"], "Vaisseau (importée)")
        self.assertEqual(len(self.s.action("method_list", {})["methods"]), 2)

    def test_a_foreign_or_newer_file_is_refused(self):
        with self.assertRaises(ValueError):
            self.s.action("method_import", {"data": "{pas du json"})
        with self.assertRaises(ValueError):
            self.s.action("method_import", {"data": {"format": "autre", "method": {}}})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_import", {"data": {"format": "cyai-method", "version": 99, "method": {"name": "x", "steps": []}}})
        self.assertIn("plus récente", str(refusal.exception))

    def test_an_ai_can_create_a_method_through_the_mcp_only_with_a_global_grant(self):
        arguments = {"name": "Par une IA", "steps": [{"key": "a", "executor": "any", "instruction": "Fais {objectif}."}]}
        with self.assertRaises(ValueError):
            app_mcp.call(self.s, "cyai_call", {"action": "method_save", "arguments": arguments}, [self.p], allow_write=True)
        created = app_mcp.call(self.s, "cyai_call", {"action": "method_save", "arguments": arguments}, [self.p],
                               allow_write=True, allow_global=True)
        self.assertEqual(self.s.action("method_get", {"id": created["id"]})["method"]["name"], "Par une IA")


    # --- a method as a skill any AI follows ------------------------------------------------------------

    def test_a_method_becomes_a_skill_of_a_project_and_reaches_the_context(self):
        saved = self.graph()
        result = self.s.action("method_as_skill", {"id": saved["id"], "project_id": self.p})
        self.assertIn("pas une chaîne lancée", result["notice"])
        self.s.action("method_as_skill", {"id": saved["id"], "project_id": self.p})
        skills = json.loads(self.s.store.one("SELECT agent_settings FROM projects WHERE id=?", (self.p,))["agent_settings"])["skills"]
        self.assertEqual(len(skills), 1, "réajouter la méthode la remplace")
        self.assertIn("Conçois {objectif}.", skills[0]["content"])
        self.assertIn("Relis le concept.", skills[0]["content"])
        from cyai.context import build_context
        context = build_context(self.s.store, self.fixture.conversation, "Continuer", {})
        self.assertIn("Méthode : Vaisseau", context["text"])
        self.assertFalse(self.s.store.rows("SELECT id FROM missions"), "un skill ne lance rien")
        with self.assertRaises(ValueError):
            self.s.action("method_as_skill", {"id": saved["id"]})


if __name__ == "__main__":
    unittest.main()
