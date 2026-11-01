import json
import unittest

import test_core
from cyai import app_mcp
from cyai.connectors import Control


class MethodTests(unittest.TestCase):
    """A method is a chain of specialists replayed on a new objective, with declared artefacts."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config = {**connector.config, "enabled": True}
        self.ids = {}
        for name, prompt in [("Concepteur", "Tu produis le concept et les proportions."),
                             ("Sculpteur", "Tu construis la forme basse résolution qui fixe la silhouette."),
                             ("Modeleur", "Tu modélises dans Blender en suivant la silhouette fournie."),
                             ("Relecteur", "Tu dis si la direction prise correspond au concept."),
                             ("Texturier", "Tu poses les textures et les matériaux.")]:
            self.ids[name] = self.s.action("agent_profile_save", {
                "name": name, "role": "consultant", "connector": "alpha", "model": "alpha-1", "prompt": prompt})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def ship_method(self):
        return self.s.action("method_save", {
            "name": "Vaisseau 3D", "description": "Du concept aux matériaux.",
            "steps": [
                {"key": "concept", "profile_id": self.ids["Concepteur"], "depends_on": [],
                 "instruction": "Produis le concept de {objectif} : planches, proportions, silhouette.",
                 "artifact": "concept/planches.md"},
                {"key": "silhouette", "profile_id": self.ids["Sculpteur"], "depends_on": ["concept"],
                 "instruction": "À partir des planches, produis une forme basse résolution aux bonnes proportions.",
                 "artifact": "modele/silhouette.obj"},
                {"key": "modele", "profile_id": self.ids["Modeleur"], "depends_on": ["concept", "silhouette"],
                 "instruction": "Modélise dans Blender en suivant la silhouette et les planches.",
                 "artifact": "modele/vaisseau.blend"},
                {"key": "revue", "profile_id": self.ids["Relecteur"], "depends_on": ["modele"],
                 "instruction": "Dis si la direction prise correspond au concept, et ce qui manque."},
                {"key": "textures", "profile_id": self.ids["Texturier"], "depends_on": ["modele"],
                 "instruction": "Pose les textures et les matériaux.", "artifact": "modele/materiaux.json"}]})

    # --- authoring --------------------------------------------------------------------------

    def test_a_method_chains_specialists_and_declares_what_each_must_leave_behind(self):
        saved = self.ship_method()
        self.assertEqual(saved["steps"], 5)
        method = self.s.action("method_list", {})["methods"][0]
        self.assertEqual([s["name"] for s in method["steps"]],
                         ["Concepteur", "Sculpteur", "Modeleur", "Relecteur", "Texturier"])
        self.assertEqual(method["steps"][2]["depends_on"], ["concept", "silhouette"])
        self.assertEqual(method["steps"][2]["artifact"], "modele/vaisseau.blend")
        self.assertEqual(method["steps"][3]["artifact"], "", "une revue ne produit pas de fichier")
        self.assertFalse(any(s["profile_missing"] or s["profile_archived"] for s in method["steps"]))
        self.assertIn("ne juge pas leur qualité", self.s.action("method_list", {})["notice"])

    def test_a_method_only_moves_forward_and_needs_real_profiles(self):
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_save", {"name": "Boucle", "steps": [
                {"key": "a", "profile_id": self.ids["Concepteur"], "instruction": "Fais", "depends_on": ["b"]},
                {"key": "b", "profile_id": self.ids["Relecteur"], "instruction": "Relis"}]})
        self.assertIn("se pilote sur le board", str(refusal.exception))
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_save", {"name": "Sans profil", "steps": [{"key": "a", "profile_id": "fantome", "instruction": "Fais"}]})
        self.assertIn("Profil introuvable", str(refusal.exception))
        with self.assertRaises(ValueError):
            self.s.action("method_save", {"name": "Vide", "steps": []})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_save", {"name": "Doublon", "steps": [
                {"key": "a", "profile_id": self.ids["Concepteur"], "instruction": "Un"},
                {"key": "a", "profile_id": self.ids["Relecteur"], "instruction": "Deux"}]})
        self.assertIn("double", str(refusal.exception))
        self.assertFalse(self.s.store.rows("SELECT id FROM method_templates"))

    # --- applying ---------------------------------------------------------------------------

    def test_applying_a_method_prepares_a_chain_without_launching_it(self):
        self.ship_method()
        method = self.s.action("method_list", {})["methods"][0]
        result = self.s.action("method_apply", {"project_id": self.p, "id": method["id"],
                                                "objective": "un croiseur minier cyberpunk"})
        self.assertIn("sans être lancée", result["notice"])
        mission = self.s.mission(result["mission_id"])
        self.assertEqual(mission["status"], "pending", "rien ne démarre à la préparation")
        self.assertFalse(self.s.engine.connectors["alpha"].calls, "aucun agent n’a été appelé")
        steps = mission["steps"]
        self.assertEqual(len(steps), 5)
        self.assertIn("un croiseur minier cyberpunk", steps[0]["instruction"])
        self.assertIn("Tu produis le concept", steps[0]["instruction"], "les consignes du profil sont transmises")
        self.assertEqual(mission["spec"]["steps"][2]["depends_on"], [0, 1], "les dépendances par clé deviennent des positions")
        self.assertEqual(mission["spec"]["steps"][2]["validation"], {"type": "file_exists", "value": "modele/vaisseau.blend"})
        self.assertIn("Son absence fera échouer l’étape ; sa présence ne prouve pas sa qualité.", steps[2]["instruction"])
        self.assertNotIn("validation", mission["spec"]["steps"][3], "l’étape de revue ne réclame aucun fichier")
        conversation = self.s.conversation(result["conversation_id"])
        self.assertIn("Vaisseau 3D", conversation["title"])
        self.assertIn("croiseur minier", conversation["title"])

    def test_the_objective_lands_where_the_method_puts_it(self):
        self.s.action("method_save", {"name": "Deux styles", "steps": [
            {"key": "a", "profile_id": self.ids["Concepteur"], "instruction": "Conçois {objectif} en trois variantes."},
            {"key": "b", "profile_id": self.ids["Relecteur"], "depends_on": ["a"], "instruction": "Choisis la meilleure variante."}]})
        method = self.s.action("method_list", {})["methods"][0]
        mission = self.s.mission(self.s.action("method_apply", {"project_id": self.p, "id": method["id"],
                                                                "objective": "une navette de sauvetage"})["mission_id"])
        self.assertIn("Conçois une navette de sauvetage en trois variantes.", mission["steps"][0]["instruction"])
        self.assertNotIn("Objectif de la chaîne", mission["steps"][0]["instruction"])
        self.assertIn("Objectif de la chaîne : une navette de sauvetage", mission["steps"][1]["instruction"])

    def test_an_archived_profile_blocks_the_method_with_its_name(self):
        self.ship_method()
        method = self.s.action("method_list", {})["methods"][0]
        self.s.action("agent_profile_archive", {"id": self.ids["Modeleur"]})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_apply", {"project_id": self.p, "id": method["id"], "objective": "un chasseur"})
        self.assertIn("Modeleur", str(refusal.exception))
        self.assertFalse(self.s.store.rows("SELECT id FROM missions"))
        self.assertTrue(self.s.action("method_list", {})["methods"][0]["steps"][2]["profile_archived"])
        self.s.action("agent_profile_archive", {"id": self.ids["Modeleur"], "archived": False})
        self.assertTrue(self.s.action("method_apply", {"project_id": self.p, "id": method["id"], "objective": "un chasseur"})["mission_id"])

    def test_an_artifact_outside_the_project_folder_is_refused(self):
        self.s.action("method_save", {"name": "Fuite", "steps": [
            {"key": "a", "profile_id": self.ids["Concepteur"], "instruction": "Écris", "artifact": "../dehors.txt"}]})
        method = self.s.action("method_list", {})["methods"][0]
        with self.assertRaises(ValueError):
            self.s.action("method_apply", {"project_id": self.p, "id": method["id"], "objective": "essai"})

    def test_a_disabled_connector_names_the_step_and_the_connector(self):
        self.ship_method()
        method = self.s.action("method_list", {})["methods"][0]
        self.assertTrue(all(s["connector_ready"] for s in method["steps"]))
        self.s.engine.connectors["alpha"].config = {**self.s.engine.connectors["alpha"].config, "enabled": False}
        listed = self.s.action("method_list", {})["methods"][0]
        self.assertFalse(listed["steps"][0]["connector_ready"])
        self.assertIn("désactivé", listed["steps"][0]["connector_detail"])
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_apply", {"project_id": self.p, "id": method["id"], "objective": "un chasseur"})
        message = str(refusal.exception)
        self.assertIn("Concepteur", message)
        self.assertIn("alpha", message)
        self.assertIn("Activez ces connecteurs", message)
        self.assertFalse(self.s.store.rows("SELECT id FROM missions"))

    # --- capturing a chain that worked --------------------------------------------------------

    def test_a_chain_that_worked_becomes_a_method(self):
        conversation = self.s.action("create_conversation", {"project_id": self.p, "title": "Essai"})["id"]
        mission = self.s.action("create_mission", {"conversation_id": conversation, "title": "Essai vaisseau", "launch": False,
                                                   "steps": [{"name": "Concept", "connector": "alpha", "instruction": "Conçois."},
                                                             {"name": "Modèle", "connector": "alpha", "instruction": "Modélise.",
                                                              "depends_on": [0], "validation": {"type": "file_exists", "value": "modele/x.blend"}}]})["mission_id"]
        # Contract changed on purpose (methods usable by any AI): a step without a profile keeps the
        # connector and model that actually ran it, instead of being refused.
        anonymous = self.s.action("method_from_mission", {"mission_id": mission, "name": "Anonyme", "profiles": {}})
        kept = self.s.action("method_get", {"id": anonymous["id"]})["method"]["steps"]
        self.assertEqual([(s["executor"], s["connector"]) for s in kept], [("connector", "alpha"), ("connector", "alpha")])
        self.s.action("method_delete", {"id": anonymous["id"]})
        self.s.action("method_from_mission", {"mission_id": mission, "name": "Repris",
                                              "profiles": {"0": self.ids["Concepteur"], "1": self.ids["Modeleur"]}})
        method = self.s.action("method_list", {})["methods"][0]
        self.assertEqual([s["profile_name"] for s in method["steps"]], ["Concepteur", "Modeleur"])
        self.assertEqual(method["steps"][1]["depends_on"], ["e0"])
        self.assertEqual(method["steps"][1]["artifact"], "modele/x.blend", "le livrable contrôlé est conservé")

    # --- MCP ------------------------------------------------------------------------------------

    def test_method_writes_are_global_and_applying_stays_in_the_project(self):
        ops = {name: app_mcp.ACTIONS[name] for name in ("method_list", "method_save", "method_delete", "method_apply", "method_from_mission",
                                                         "method_get", "method_check", "method_export", "method_import")}
        for op in ops.values():
            app_mcp.Draft202012Validator.check_schema(op["inputSchema"])
        self.assertEqual(ops["method_apply"]["scope"], "project_id")
        self.assertTrue(all(ops[n]["scope"] == "global" for n in ("method_list", "method_save", "method_delete", "method_from_mission",
                                                                  "method_get", "method_check", "method_export", "method_import")))
        self.assertTrue(ops["method_import"]["write"])
        self.assertFalse(any(ops[n]["write"] for n in ("method_get", "method_check", "method_export")))
        self.ship_method()
        method = self.s.action("method_list", {})["methods"][0]
        with self.assertRaises(ValueError) as refusal:
            app_mcp.call(self.s, "cyai_call", {"action": "method_delete", "arguments": {"id": method["id"]}}, [self.p], allow_write=True)
        self.assertIn("--allow-global", str(refusal.exception))
        other = self.s.action("create_project", {"name": "Voisin", "root": str(self.fixture.root)})["id"]
        control = Control(30, lambda d: True, lambda *_: None)
        with self.assertRaises(ValueError):
            app_mcp.call(self.s, "cyai_call", {"action": "method_apply", "arguments": {
                "project_id": other, "id": method["id"], "objective": "hors projet"}}, [self.p], control)
        self.assertEqual(len(self.s.action("method_list", {})["methods"]), 1)


if __name__ == "__main__":
    unittest.main()
