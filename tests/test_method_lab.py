import json
import time
import unittest

import test_core
from cyai import app_mcp, method_lab


EVALUATION = "Évaluez le résultat d’un test"


class MethodLabTests(unittest.TestCase):
    """Tests saved with a method, scored, checked for understanding, and the method refined — never without you."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config = {**connector.config, "enabled": True}
        self.scores = []
        self.proposals = []
        self.s.engine.connectors["alpha"].answer = self.answer
        self.s.engine.connectors["beta"].answer = self.answer
        self.method = self.s.action("method_save", {
            "name": "Affiche", "inputs": [{"key": "objectif", "name": "Objectif"}, {"key": "brief", "name": "Brief", "kind": "context"}],
            "outputs": [{"key": "texte", "name": "Texte final", "source": {"step": "b", "port": "t"}}],
            "steps": [{"key": "a", "name": "Esquisse", "executor": "any", "instruction": "Esquisse {objectif}.",
                       "inputs": [{"key": "c", "name": "Brief", "kind": "context", "source": {"step": "@entrees", "port": "brief"}}],
                       "outputs": [{"key": "s", "name": "Esquisse"}]},
                      {"key": "b", "name": "Rédaction", "executor": "any", "instruction": "Rédige le texte de l’affiche.",
                       "inputs": [{"key": "e", "name": "Esquisse", "source": {"step": "a", "port": "s"}}],
                       "outputs": [{"key": "t", "name": "Texte"}]}]})["id"]
        self.test = self.s.action("method_test_save", {"method_id": self.method, "name": "Cargo", "objective": "une affiche de cargo",
                                                       "inputs": {"brief": "Cuivre et nuit.", "inconnue": "ignorée"},
                                                       "expected": "Un slogan de moins de dix mots."})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def answer(self, prompt):
        if EVALUATION in prompt:
            score = self.scores.pop(0) if self.scores else 3
            return 'Voici :\n```json\n{"score": %d, "verdict": "Correct", "points_forts": ["court"], "problemes": ["trop vague"], "suggestions": ["préciser"]}\n```' % score
        if "Améliorez la méthode" in prompt:
            if self.proposals:
                return self.proposals.pop(0)
            body = json.loads(prompt.split("```json\n", 1)[1].split("\n```", 1)[0])
            body["steps"][1]["instruction"] = "Rédige un slogan de moins de dix mots."
            return "### Sortie : Explication\nPlus précis.\n### Sortie : Méthode\n```json\n" + json.dumps(body, ensure_ascii=False) + "\n```"
        if "rédigez la version finale des précisions" in prompt:
            return "### Sortie : Adaptation\nRends trois variantes numérotées.\n### Sortie : Explication\nIl ne numérotait pas."
        if "Répondez aux questions ci-dessous" in prompt:
            return "Je rendrais un paragraphe."
        if "Vous affinez une consigne" in prompt:
            return "### Sortie : Questions\nQuel format ?\n### Sortie : Brouillon\nDonne trois variantes."
        if "VÉRIFICATION DE COMPRÉHENSION" in prompt:
            return "### Sortie : Compréhension\nUne esquisse.\n### Sortie : Ambiguïtés\nLe format."
        if "Esquisse une affiche" in prompt:
            return "### Sortie : Esquisse\nUn cargo sur fond de nuit."
        return "SLOGAN : Le cuivre traverse la nuit."

    def settle(self, mission_id, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.s.mission(mission_id)["status"] in {"succeeded", "failed", "cancelled"}:
                return
            time.sleep(.05)
        raise AssertionError("mission non terminée")

    def test_mcp_can_launch_hidden_test_and_evaluation_with_project_scope(self):
        from types import SimpleNamespace
        cid = self.fixture.conversation
        approvals = []
        control = SimpleNamespace(conversation_id=cid, planning=False, check=lambda:None,
                                  approve=lambda value: approvals.append(value) or True)
        started = app_mcp.call(self.s, "cyai_call", {"action":"method_test_run", "arguments":
            {"test_id":self.test,"conversation_id":cid,"connector":"alpha","concurrency":4}}, [self.p], control)
        self.settle(started["mission_id"])
        self.assertEqual(self.s.mission(started["mission_id"])["status"], "succeeded")
        self.assertNotIn(started["conversation_id"], [c["id"] for c in self.s.state()["conversations"]])
        self.assertEqual(self.s.store.one("SELECT internal_parent_id FROM conversations WHERE id=?", (started["conversation_id"],))["internal_parent_id"], cid)
        self.assertTrue(self.s.store.rows("SELECT id FROM delegation_returns WHERE mission_id=?", (started["mission_id"],)))
        evaluated = app_mcp.call(self.s, "cyai_call", {"action":"method_run_evaluate", "arguments":
            {"run_id":started["id"],"connector":"beta"}}, [self.p], control)
        self.settle(evaluated["mission_id"])
        self.assertEqual(self.s.mission(evaluated["mission_id"])["status"], "succeeded")
        self.assertEqual([a["tool"] for a in approvals], ["method_test_run", "method_run_evaluate"])
        for name in ("method_test_run", "method_run_evaluate"):
            self.assertIn(name, app_mcp.ACTIONS)
            self.assertNotIn(name, app_mcp.USER_ONLY)
        with self.assertRaisesRegex(ValueError, "périmètre"):
            app_mcp.call(self.s, "cyai_call", {"action":"method_run_evaluate", "arguments":
                {"run_id":started["id"],"connector":"beta"}}, ["unrelated"], control)
        with self.assertRaisesRegex(ValueError, "lecture seule"):
            app_mcp.call(self.s, "cyai_call", {"action":"method_test_run", "arguments":
                {"test_id":self.test,"conversation_id":cid,"connector":"alpha"}}, [self.p])

    def run_test(self):
        started = self.s.action("method_test_run", {"test_id": self.test, "connector": "alpha"})
        self.settle(started["mission_id"])
        return started

    # --- tests and their runs ----------------------------------------------------------------------------

    def test_a_test_is_saved_with_the_method_and_runs_in_a_test_project(self):
        test = self.s.action("method_tests", {"id": self.method})["tests"][0]
        self.assertEqual(test["inputs"], {"brief": "Cuivre et nuit."}, "une entrée inconnue de la méthode n’est pas gardée")
        first = self.run_test()
        again = self.run_test()
        conversations = [self.s.conversation(r["conversation_id"]) for r in (first, again)]
        self.assertEqual(len({c["project_id"] for c in conversations}), 1, "un seul projet de tests, réutilisé")
        project = self.s.store.one("SELECT * FROM projects WHERE id=?", (conversations[0]["project_id"],))
        self.assertEqual(project["name"], "Tests de méthodes")
        self.assertNotEqual(project["id"], self.p, "vos projets ne se remplissent pas de tests")
        self.assertIn("Test · Affiche · Cargo · v1", conversations[0]["title"])
        run = self.s.action("method_tests", {"id": self.method})["tests"][0]["runs"][0]
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["data"]["outputs"], [{"name": "Texte final", "content": "SLOGAN : Le cuivre traverse la nuit.", "found": True}])

    def test_you_score_a_run_or_an_ai_evaluates_it_against_what_you_expect(self):
        run = self.run_test()["id"]
        with self.assertRaises(ValueError):
            self.s.action("method_run_rate", {"run_id": run, "score": 6})
        self.scores = [4]
        started = self.s.action("method_run_evaluate", {"run_id": run, "connector": "beta"})
        self.settle(started["mission_id"])
        sent = self.s.engine.connectors["beta"].calls[-1][0]
        self.assertIn("Un slogan de moins de dix mots.", sent, "l’attendu de l’utilisateur guide l’évaluation")
        self.assertIn("SLOGAN : Le cuivre traverse la nuit.", sent)
        self.assertNotIn("Esquisse une affiche", sent, "l’évaluation ne reçoit que les sorties, pas la conversation de la chaîne")
        evaluation = self.s.action("method_runs", {"id": self.method, "kind": "evaluation"})["runs"][0]
        self.assertEqual((evaluation["score"], evaluation["data"]["problems"]), (4, ["trop vague"]))
        tested = self.s.action("method_tests", {"id": self.method})["tests"][0]["runs"][0]
        self.assertEqual((tested["score"], tested["rating_by"]), (4, "ai"))
        self.s.action("method_run_rate", {"run_id": run, "score": 2, "notes": "Trop long."})
        tested = self.s.action("method_tests", {"id": self.method})["tests"][0]["runs"][0]
        self.assertEqual((tested["score"], tested["rating_by"], tested["notes"]), (2, "user", "Trop long."), "votre note prime")

    def test_an_unreadable_evaluation_is_a_failure_not_a_score(self):
        run = self.run_test()["id"]
        self.s.engine.connectors["beta"].answer = lambda prompt: "C’est plutôt bien."
        self.settle(self.s.action("method_run_evaluate", {"run_id": run, "connector": "beta"})["mission_id"])
        evaluation = self.s.action("method_runs", {"id": self.method, "kind": "evaluation"})["runs"][0]
        self.assertEqual(evaluation["status"], "failed")
        self.assertIn("illisible", evaluation["data"]["error"])
        self.assertIsNone(self.s.action("method_tests", {"id": self.method})["tests"][0]["runs"][0]["score"])

    # --- understanding and precisions per model ------------------------------------------------------------

    def test_a_model_reports_what_it_understood_without_doing_the_task(self):
        started = self.s.action("method_check_understanding", {"id": self.method, "step_key": "b", "test_id": self.test})
        self.settle(started["mission_id"])
        sent = self.s.engine.connectors["alpha"].calls[-1][0]
        self.assertIn("ne réalisez pas la tâche", sent)
        self.assertIn("Rédige le texte de l’affiche.", sent, "la consigne exacte est montrée")
        self.assertIn("Esquisse (de « Esquisse »)", sent, "les entrées venant d’autres tâches sont nommées")
        check = self.s.action("method_runs", {"id": self.method, "kind": "check"})["runs"][0]
        self.assertEqual((check["status"], check["step_key"], check["connector"]), ("succeeded", "b", "alpha"))
        self.assertIn("Le format.", check["data"]["report"])
        self.assertEqual(self.s.conversation(started["conversation_id"])["title"], "Atelier · Affiche", "hors de tout projet, dans l’atelier")

    def test_a_stronger_model_writes_precisions_for_the_checked_model_only(self):
        check = self.s.action("method_check_understanding", {"id": self.method, "step_key": "b", "connector": "alpha"})
        self.settle(check["mission_id"])
        refine = self.s.action("method_refine_for_model", {"check_id": check["id"], "connector": "beta"})
        self.settle(refine["mission_id"])
        answers = [p for p, _ in self.s.engine.connectors["alpha"].calls if "Répondez aux questions ci-dessous" in p]
        self.assertIn("Quel format ?", answers[0], "le modèle vérifié reçoit les questions du relecteur")
        self.assertNotIn("Donne trois variantes", answers[0], "pas le brouillon")
        self.assertNotIn("VÉRIFICATION DE COMPRÉHENSION", answers[0], "la consigne de la tâche, sans le cadre de la vérification")
        result = self.s.action("method_runs", {"id": self.method, "kind": "refine"})["runs"][0]
        self.assertEqual((result["data"]["target"], result["data"]["adaptation"]), ("alpha:", "Rends trois variantes numérotées."))
        self.s.action("method_adaptation_set", {"id": self.method, "step_key": "b", "target": "alpha:", "text": result["data"]["adaptation"]})
        alpha = self.s.mission(self.s.action("method_apply", {"project_id": self.p, "id": self.method, "objective": "x", "connector": "alpha",
                                                              "inputs": {"brief": "b"}})["mission_id"])
        self.assertIn("Précisions pour ce modèle (alpha:) :\nRends trois variantes numérotées.", alpha["steps"][1]["instruction"])
        self.assertNotIn("Précisions pour ce modèle", alpha["steps"][0]["instruction"], "seulement la tâche affinée")
        beta = self.s.mission(self.s.action("method_apply", {"project_id": self.p, "id": self.method, "objective": "x", "connector": "beta",
                                                             "inputs": {"brief": "b"}})["mission_id"])
        self.assertNotIn("Précisions pour ce modèle", beta["steps"][1]["instruction"], "un autre modèle ne les reçoit pas")

    # --- improvement proposed by an AI ------------------------------------------------------------------------

    def test_a_proposal_is_read_before_it_becomes_a_version(self):
        run = self.run_test()["id"]
        self.s.action("method_run_rate", {"run_id": run, "score": 2, "notes": "Trop long."})
        before = self.s.action("method_get", {"id": self.method})["method"]["revision"]
        started = self.s.action("method_improve", {"id": self.method, "connector": "beta", "request": "Plus court."})
        self.settle(started["mission_id"])
        sent = self.s.engine.connectors["beta"].calls[-1][0]
        self.assertIn("Trop long.", sent)
        self.assertIn("Plus court.", sent)
        proposal = self.s.action("method_runs", {"id": self.method, "kind": "improve"})["runs"][0]
        self.assertEqual(proposal["status"], "succeeded")
        self.assertIn("tâche modifiée : Rédaction", proposal["data"]["changes"])
        self.assertEqual(self.s.action("method_get", {"id": self.method})["method"]["revision"], before, "rien ne change avant adoption")
        adopted = self.s.action("method_improvement_adopt", {"run_id": proposal["id"]})
        method = self.s.action("method_get", {"id": self.method})["method"]
        self.assertEqual(method["revision"], adopted["revision"])
        self.assertEqual(method["steps"][1]["instruction"], "Rédige un slogan de moins de dix mots.")
        self.assertEqual(self.s.action("method_history", {"id": self.method})["revisions"][0]["source"], "ai")

    def test_an_invalid_proposal_is_refused_with_its_reason(self):
        self.proposals = ["### Sortie : Méthode\n```json\n{\"name\": \"x\", \"steps\": [{\"key\": \"a\", \"depends_on\": [\"a\"], \"instruction\": \"A\"}]}\n```"]
        self.settle(self.s.action("method_improve", {"id": self.method, "connector": "beta"})["mission_id"])
        proposal = self.s.action("method_runs", {"id": self.method, "kind": "improve"})["runs"][0]
        self.assertEqual(proposal["status"], "failed")
        self.assertIn("Proposition invalide", proposal["data"]["error"])
        with self.assertRaises(ValueError):
            self.s.action("method_improvement_adopt", {"run_id": proposal["id"]})

    # --- the loop -----------------------------------------------------------------------------------------------

    def loop(self, **extra):
        values = {"test_id": self.test, "confirm": True, "target": 5, "max_rounds": 3, "run": {"connector": "alpha"},
                  "evaluator": {"connector": "beta"}, "improver": {"connector": "beta"}}
        values.update(extra)
        return self.s.action("method_loop_start", values)

    def spin(self, loop_id, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            method_lab.tick(self.s)
            loop = self.s.action("method_loops", {"id": self.method})["loops"][0]
            if loop["status"] != "running":
                return loop
            time.sleep(.05)
        raise AssertionError("boucle non terminée")

    def test_a_loop_needs_your_agreement_and_limits(self):
        with self.assertRaises(ValueError):
            self.loop(confirm=False)
        with self.assertRaises(ValueError):
            self.loop(max_rounds=0)
        with self.assertRaises(ValueError):
            self.loop(max_rounds=11)
        self.assertEqual(self.s.action("method_loop_estimate", {"id": self.method, "max_rounds": 3})["maximum"], 3 * 4 - 1)

    def test_a_loop_improves_until_the_score_and_keeps_every_version(self):
        self.scores = [2, 5]
        started = self.loop()
        self.assertIn("Au plus 11 exécutions", started["notice"])
        loop = self.spin(started["id"])
        self.assertEqual(loop["status"], "succeeded", loop["reason"])
        self.assertIn("5/5 atteinte au tour 2", loop["reason"])
        self.assertEqual([h["score"] for h in loop["state"]["history"]], [2, 5])
        history = self.s.action("method_history", {"id": self.method})["revisions"]
        self.assertEqual(history[0]["source"], "ai-loop")
        self.assertIn("Boucle · tour 1 · note 2", history[0]["note"])

    def test_a_loop_stops_at_its_round_limit_and_after_a_restart(self):
        self.scores = [2, 2]
        loop = self.spin(self.loop(max_rounds=1)["id"])
        self.assertEqual(loop["status"], "stopped")
        self.assertIn("Limite de 1 tour(s)", loop["reason"])
        self.scores = [1, 1, 1]
        started = self.loop()
        method_lab.stop_after_restart(self.s)
        loop = self.s.action("method_loops", {"id": self.method})["loops"][0]
        self.assertEqual(loop["status"], "stopped")
        self.assertIn("redémarrage", loop["reason"])
        self.assertTrue(started["id"])

    def test_spending_stays_with_the_user(self):
        for name in ("method_check_understanding", "method_refine_for_model",
                     "method_improve", "method_improvement_adopt", "method_loop_start", "method_adaptation_set", "method_run_rate"):
            self.assertIn(name, app_mcp.USER_ONLY)
            self.assertNotIn(name, app_mcp.ACTIONS)
        for name in ("method_tests", "method_runs", "method_test_save"):
            app_mcp.Draft202012Validator.check_schema(app_mcp.ACTIONS[name]["inputSchema"])
        self.assertTrue(app_mcp.ACTIONS["method_test_save"]["write"])


if __name__ == "__main__":
    unittest.main()
