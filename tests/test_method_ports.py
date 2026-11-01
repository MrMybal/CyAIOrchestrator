import json
import time
import unittest

import test_core
from cyai import app_mcp
from cyai.methods import extract_section


class MethodPortTests(unittest.TestCase):
    """A method is a function: named inputs and outputs, contexts distributed by wires, sub-methods unfolded."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config = {**connector.config, "enabled": True}

    def tearDown(self):
        self.fixture.tearDown()

    def contexts(self, **extra):
        """Plan writes two sections; the modeller gets the complete context, the reviewer the simplified one."""
        return self.s.action("method_save", {
            "name": "Contextes", "usage": "Préparez un contexte complet puis un résumé de dix lignes.",
            "inputs": [{"key": "objectif", "name": "Objectif"},
                       {"key": "complet", "name": "Contexte complet", "kind": "context", "required": True, "prepare": "Tout le cahier des charges."},
                       {"key": "simple", "name": "Contexte simplifié", "kind": "context", "prepare": "Dix lignes."}],
            "outputs": [{"key": "verdict", "name": "Verdict", "source": {"step": "revue", "port": "avis"}}],
            "steps": [
                {"key": "plan", "name": "Plan", "executor": "any", "instruction": "Planifie {objectif}.",
                 "inputs": [{"key": "ctx", "name": "Contexte", "kind": "context", "source": {"step": "@entrees", "port": "complet"}}],
                 "outputs": [{"key": "etapes", "name": "Étapes"}, {"key": "risques", "name": "Risques", "description": "trois au plus"}]},
                {"key": "modele", "name": "Modèle", "executor": "any", "instruction": "Modélise.",
                 "inputs": [{"key": "ctx", "name": "Contexte", "kind": "context", "source": {"step": "@entrees", "port": "complet"}},
                            {"key": "etapes", "name": "Étapes", "source": {"step": "plan", "port": "etapes"}}],
                 "outputs": [{"key": "fichier", "name": "Maillage", "kind": "file", "path": "modele/cargo.obj"}]},
                {"key": "revue", "name": "Revue", "executor": "any", "instruction": "Relis.",
                 "inputs": [{"key": "ctx", "name": "Résumé", "kind": "context", "source": {"step": "@entrees", "port": "simple"}},
                            {"key": "risques", "name": "Risques", "source": {"step": "plan", "port": "risques"}},
                            {"key": "maillage", "name": "Maillage", "kind": "file", "source": {"step": "modele", "port": "fichier"}}],
                 "outputs": [{"key": "avis", "name": "Avis"}]},
                {"key": "note", "name": "Note", "executor": "any", "instruction": "Écris une note libre.", "inputs": [], "outputs": []}],
            **extra})

    def apply(self, method_id, **extra):
        values = {"project_id": self.p, "id": method_id, "objective": "un cargo", "connector": "alpha",
                  "inputs": {"complet": "CAHIER COMPLET", "simple": "RÉSUMÉ COURT"}}
        values.update(extra)
        return self.s.action("method_apply", values)

    def settle(self, mission_id, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            mission = self.s.mission(mission_id)
            if mission["status"] in {"succeeded", "failed", "cancelled"}:
                return mission
            time.sleep(.05)
        raise AssertionError("chaîne non terminée")

    # --- authoring ----------------------------------------------------------------------------------

    def test_pins_are_saved_and_a_wire_orders_the_tasks(self):
        method = self.s.action("method_get", {"id": self.contexts()["id"]})["method"]
        self.assertEqual([p["key"] for p in method["inputs"]], ["objectif", "complet", "simple"])
        self.assertTrue(method["inputs"][0]["required"])
        self.assertEqual(method["inputs"][1]["prepare"], "Tout le cahier des charges.")
        order = [s["key"] for s in method["steps"]]
        self.assertLess(order.index("plan"), order.index("modele"), "un fil suffit à ordonner, sans dépendance explicite")
        self.assertLess(order.index("modele"), order.index("revue"))
        self.assertEqual({s["receives"] for s in method["steps"]}, {"inputs"}, "une tâche à broches ne reçoit que ses entrées par défaut")
        self.assertEqual(method["outputs"][0]["source"], {"step": "revue", "port": "avis"})

    def test_the_objective_is_always_an_input(self):
        saved = self.s.action("method_save", {"name": "Sans entrées", "steps": [{"key": "a", "executor": "any", "instruction": "A"}]})
        method = self.s.action("method_get", {"id": saved["id"]})["method"]
        self.assertEqual([(p["key"], p["required"]) for p in method["inputs"]], [("objectif", True)])
        self.assertEqual(method["steps"][0]["receives"], "chain", "une tâche sans broches garde le comportement d’avant")

    def test_a_wire_must_land_on_a_pin_that_exists_and_never_loop(self):
        base = {"key": "a", "executor": "any", "instruction": "A", "outputs": [{"key": "r", "name": "R"}]}
        for bad in ({"step": "fantome", "port": "r"}, {"step": "a", "port": "absente"}, {"step": "@entrees", "port": "inconnue"}):
            with self.assertRaises(ValueError):
                self.s.action("method_save", {"name": "Fils", "steps": [base, {"key": "b", "executor": "any", "instruction": "B",
                                                                              "inputs": [{"name": "X", "source": bad}]}]})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_save", {"name": "Boucle", "steps": [
                {**base, "inputs": [{"name": "X", "source": {"step": "b", "port": "r"}}]},
                {"key": "b", "executor": "any", "instruction": "B", "outputs": [{"key": "r", "name": "R"}],
                 "inputs": [{"name": "Y", "source": {"step": "a", "port": "r"}}]}]})
        self.assertIn("boucle", str(refusal.exception))

    # --- what each task receives ----------------------------------------------------------------------

    def test_each_task_receives_the_context_wired_to_it_and_no_other(self):
        applied = self.apply(self.contexts()["id"])
        mission = self.s.mission(applied["mission_id"])
        spec = {s["method_step"]: s for s in mission["spec"]["steps"]}
        opening = self.s.store.rows("SELECT content FROM messages WHERE conversation_id=? ORDER BY seq", (applied["conversation_id"],))[0]["content"]
        self.assertIn("Contextes", opening)
        self.assertNotIn("CAHIER COMPLET", opening, "le message d’ouverture ne répète pas les contextes réservés à une tâche")
        self.assertIn("CAHIER COMPLET", spec["plan"]["instruction"])
        self.assertNotIn("RÉSUMÉ COURT", spec["plan"]["instruction"])
        self.assertIn("RÉSUMÉ COURT", spec["revue"]["instruction"])
        self.assertNotIn("CAHIER COMPLET", spec["revue"]["instruction"], "le relecteur n’a que le contexte simplifié")
        self.assertNotIn("CAHIER", spec["note"]["instruction"])
        self.assertNotIn("RÉSUMÉ", spec["note"]["instruction"], "une tâche sans fil de contexte n’en reçoit aucun")
        self.assertTrue(all(s["isolated"] for s in spec.values()))
        self.assertIn("### Sortie : Étapes", spec["plan"]["instruction"])
        self.assertIn("### Sortie : Risques — trois au plus", spec["plan"]["instruction"])
        self.assertEqual(spec["modele"]["validation"], {"type": "file_exists", "value": "modele/cargo.obj"})
        self.assertIn("modele/cargo.obj", spec["revue"]["instruction"], "une entrée fichier désigne le fichier à lire")
        plan = mission["spec"]["steps"].index(spec["plan"])
        self.assertEqual([(w["from"], w["section"]) for w in spec["revue"]["inputs"]], [(plan, "Risques")])
        self.assertIn(plan, spec["revue"]["depends_on"])
        self.assertEqual(mission["spec"]["method"]["outputs"][0]["name"], "Verdict")

    def test_a_required_input_must_be_given(self):
        saved = self.contexts()
        with self.assertRaises(ValueError) as refusal:
            self.apply(saved["id"], inputs={"simple": "court"})
        self.assertIn("Contexte complet", str(refusal.exception))
        self.assertFalse(self.s.store.rows("SELECT id FROM missions"))

    def test_running_passes_only_the_section_and_not_the_chain(self):
        def answer(prompt):
            if "Planifie" in prompt:
                return "### Sortie : Étapes\nCOQUE PUIS PONT\n### Sortie : Risques\nMASSE TROP HAUTE"
            if "Modélise" in prompt:
                (self.fixture.root / "modele").mkdir(exist_ok=True)
                (self.fixture.root / "modele" / "cargo.obj").write_text("o cargo", encoding="utf-8")
                return "Maillage écrit."
            return "Vu."
        self.s.engine.connectors["alpha"].answer = answer
        result = self.apply(self.contexts()["id"])
        self.s.action("launch_mission", {"mission_id": result["mission_id"]})
        mission = self.settle(result["mission_id"])
        self.assertEqual(mission["status"], "succeeded", [s.get("error") for s in mission["steps"]])
        review = next(p for p, _ in self.s.engine.connectors["alpha"].calls if "Relis." in p)
        self.assertIn("MASSE TROP HAUTE", review, "la section branchée arrive")
        self.assertNotIn("COQUE PUIS PONT", review, "la section non branchée n’arrive pas")
        self.assertNotIn("Planifie", review, "la conversation de la chaîne n’est pas renvoyée à une tâche isolée")
        modeller = next(p for p, _ in self.s.engine.connectors["alpha"].calls if "Modélise." in p)
        self.assertIn("COQUE PUIS PONT", modeller)
        self.assertNotIn("MASSE TROP HAUTE", modeller)

    def test_a_missing_section_sends_the_whole_answer_and_says_so(self):
        content, found = extract_section("Pas de titre ici.", "Plan")
        self.assertEqual((content, found), ("Pas de titre ici.", False))
        content, found = extract_section("## sortie : plan \nA\n### Sortie : Autre\nB", "Plan")
        self.assertEqual((content, found), ("A", True))

    # --- sub-methods --------------------------------------------------------------------------------

    def sub(self):
        return self.s.action("method_save", {
            "name": "Résumer", "inputs": [{"key": "texte", "name": "Texte", "kind": "context", "required": True}],
            "outputs": [{"key": "resume", "name": "Résumé", "source": {"step": "r", "port": "out"}}],
            "steps": [{"key": "r", "name": "Condenser", "executor": "connector", "connector": "beta", "instruction": "Condense en dix lignes.",
                       "inputs": [{"key": "t", "name": "Texte", "kind": "context", "source": {"step": "@entrees", "port": "texte"}}],
                       "outputs": [{"key": "out", "name": "Résumé"}]}]})["id"]

    def outer(self, sub):
        return self.s.action("method_save", {
            "name": "Brief", "inputs": [{"key": "objectif", "name": "Objectif"}, {"key": "doc", "name": "Document", "kind": "context", "required": True}],
            "steps": [
                {"key": "res", "kind": "method", "method_id": sub, "inputs": [{"key": "texte", "source": {"step": "@entrees", "port": "doc"}}]},
                {"key": "ecrire", "name": "Écrire", "executor": "any", "instruction": "Écris le brief.",
                 "inputs": [{"key": "r", "name": "Résumé", "source": {"step": "res", "port": "resume"}}], "outputs": [{"key": "b", "name": "Brief"}]}]})["id"]

    def test_a_sub_method_is_unfolded_with_its_inputs_bound(self):
        outer = self.outer(self.sub())
        node = self.s.action("method_get", {"id": outer})["method"]["steps"][0]
        self.assertEqual((node["kind"], node["name"], [p["key"] for p in node["outputs"]]), ("method", "Résumer", ["resume"]))
        mission = self.s.mission(self.s.action("method_apply", {"project_id": self.p, "id": outer, "objective": "un brief",
                                                                "connector": "alpha", "inputs": {"doc": "LONG DOCUMENT"}})["mission_id"])
        names = [s["name"] for s in mission["spec"]["steps"]]
        self.assertEqual(names, ["Résumer › Condenser", "Écrire"])
        condense, write = mission["spec"]["steps"]
        self.assertEqual(condense["connector"], "beta", "la sous-méthode garde ses exécutants")
        self.assertIn("LONG DOCUMENT", condense["instruction"], "l’entrée du nœud devient l’entrée de la sous-méthode")
        self.assertNotIn("LONG DOCUMENT", write["instruction"])
        self.assertEqual([(w["from"], w["task"]) for w in write["inputs"]], [(0, "Résumer › Condenser")])

    def test_a_method_cannot_include_itself_even_indirectly(self):
        sub = self.sub()
        outer = self.outer(sub)
        body = self.s.action("method_get", {"id": sub})["method"]
        body["steps"].append({"key": "boucle", "kind": "method", "method_id": outer})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_save", body)
        self.assertIn("s’inclure elle-même", str(refusal.exception))
        with self.assertRaises(ValueError) as refusal:
            self.s.action("method_delete", {"id": sub})
        self.assertIn("Brief", str(refusal.exception), "une sous-méthode utilisée ne disparaît pas sous une autre")

    def test_an_export_carries_its_sub_methods_and_imports_them_first(self):
        outer = self.outer(self.sub())
        export = self.s.action("method_export", {"id": outer})
        self.assertEqual(export["version"], 2)
        self.assertEqual([m["method"]["name"] for m in export["methods"]], ["Résumer"])
        other = test_core.CoreTests()
        other.setUp()
        try:
            result = other.service.action("method_import", {"data": json.dumps(export)})
            names = {m["name"] for m in other.service.action("method_list", {})["methods"]}
            self.assertEqual(names, {"Brief", "Résumer"})
            node = other.service.action("method_get", {"id": result["id"]})["method"]["steps"][0]
            local = next(m for m in other.service.action("method_list", {})["methods"] if m["name"] == "Résumer")
            self.assertEqual(node["method_id"], local["id"])
        finally:
            other.tearDown()

    def test_a_simple_method_still_exports_in_the_old_format(self):
        saved = self.s.action("method_save", {"name": "Simple", "steps": [{"key": "a", "executor": "any", "instruction": "A"}]})
        self.assertEqual(self.s.action("method_export", {"id": saved["id"]})["version"], 1)

    # --- versions ----------------------------------------------------------------------------------

    def test_every_save_is_a_version_that_can_come_back(self):
        saved = self.contexts()
        body = self.s.action("method_get", {"id": saved["id"]})["method"]
        body["steps"][0]["instruction"] = "Planifie autrement {objectif}."
        second = self.s.action("method_save", {**body, "note": "consigne revue"})
        self.assertEqual(second["revision"], 2)
        self.assertEqual(self.s.action("method_save", body)["revision"], 2, "enregistrer sans changement ne crée pas de version")
        history = self.s.action("method_history", {"id": saved["id"]})["revisions"]
        self.assertEqual([(r["revision"], r["note"]) for r in history], [(2, "consigne revue"), (1, "")])
        restored = self.s.action("method_restore", {"id": saved["id"], "revision": 1})
        self.assertEqual(restored["revision"], 3)
        self.assertEqual(self.s.action("method_get", {"id": saved["id"]})["method"]["steps"][0]["instruction"], "Planifie {objectif}.")

    def test_the_mcp_describes_pins_and_keeps_writes_global(self):
        for name in ("method_history", "method_restore"):
            app_mcp.Draft202012Validator.check_schema(app_mcp.ACTIONS[name]["inputSchema"])
            self.assertEqual(app_mcp.ACTIONS[name]["scope"], "global")
        self.assertTrue(app_mcp.ACTIONS["method_restore"]["write"])
        self.assertFalse(app_mcp.ACTIONS["method_history"]["write"])
        self.assertIn("@entrees", app_mcp.ACTIONS["method_save"]["description"])
        self.assertIn("inputs", app_mcp.ACTIONS["method_apply"]["inputSchema"]["properties"])


if __name__ == "__main__":
    unittest.main()
