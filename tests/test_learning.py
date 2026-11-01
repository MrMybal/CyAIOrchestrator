import json
import unittest

import test_core
from cyai import app_mcp
from cyai.connectors import Control
from cyai.context import build_context


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config = {**connector.config, "enabled": True}
        self.profiles = {n: self.s.action("agent_profile_save", {"name": n, "role": r, "connector": "alpha",
                                                                 "prompt": "Consignes de " + n})["id"]
                         for n, r in [("Chef", "chief"), ("Lead", "lead"), ("Dev", "member")]}
        self.s.action("team_save", {"project_id": self.p})
        self.chief = self.s.action("team_add_member", {"project_id": self.p, "profile_id": self.profiles["Chef"], "role": "chief"})["id"]
        self.lead = self.s.action("team_add_member", {"project_id": self.p, "profile_id": self.profiles["Lead"], "role": "lead",
                                                      "manager_id": self.chief})["id"]
        self.dev = self.s.action("team_add_member", {"project_id": self.p, "profile_id": self.profiles["Dev"], "role": "member",
                                                     "manager_id": self.lead})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def reported_task(self, objective="Migrer le schéma"):
        id = self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "assignee_id": self.dev,
                                           "objective": objective})["id"]
        for status in ("ready", "in_progress"):
            self.s.action("task_status", {"project_id": self.p, "id": id, "status": status, "author_id": self.lead})
        report = self.s.action("task_report", {"project_id": self.p, "id": id, "author_id": self.dev,
                                               "result": "Fait", "executed_tests": "12 tests"})["id"]
        return id, report

    # --- the three scopes never merge --------------------------------------------------------

    def test_member_memory_stays_in_its_project_and_never_reaches_the_profile(self):
        id, report = self.reported_task()
        local = self.s.action("agent_memory_save", {"scope": "member", "project_id": self.p, "member_id": self.dev,
                                                    "content": "Ce dépôt exige des messages de commit en français.",
                                                    "category": "Convention", "source_ids": [report]})
        self.assertIn("ne quittera ce projet", local["notice"])
        listed = self.s.action("agent_memory_list", {"scope": "member", "project_id": self.p})
        self.assertEqual([e["member"] for e in listed["entries"]], ["Dev"])
        self.assertFalse(self.s.action("agent_memory_list", {"scope": "profile", "profile_id": self.profiles["Dev"]})["entries"],
                         "une observation locale n’atterrit jamais seule sur le profil global")
        # Another project using the same profile sees nothing of it.
        other = self.s.action("create_project", {"name": "Second", "root": str(self.fixture.root)})["id"]
        self.s.action("team_save", {"project_id": other})
        twin = self.s.action("team_add_member", {"project_id": other, "profile_id": self.profiles["Dev"], "role": "member"})["id"]
        self.assertFalse(self.s.action("agent_memory_list", {"scope": "member", "project_id": other})["entries"])
        # And a scope never changes silently.
        with self.assertRaises(ValueError):
            self.s.action("agent_memory_save", {"scope": "profile", "id": local["id"], "profile_id": self.profiles["Dev"],
                                                "content": "Promotion silencieuse", "transferable": True, "source_ids": [report]})
        self.assertEqual(len(self.s.action("agent_memory_list", {"scope": "member", "project_id": self.p})["entries"]), 1)

    def test_profile_memory_must_be_declared_transferable_with_sources(self):
        id, report = self.reported_task()
        with self.assertRaises(ValueError) as refusal:
            self.s.action("agent_memory_save", {"scope": "profile", "profile_id": self.profiles["Dev"],
                                                "content": "Toujours relire les migrations.", "source_ids": [report]})
        self.assertIn("explicitement déclarée transférable", str(refusal.exception))
        with self.assertRaises(ValueError) as refusal:
            self.s.action("agent_memory_save", {"scope": "profile", "profile_id": self.profiles["Dev"],
                                                "content": "Sans preuve", "transferable": True})
        self.assertIn("au moins une source", str(refusal.exception))
        with self.assertRaises(ValueError):
            self.s.action("agent_memory_save", {"scope": "profile", "profile_id": self.profiles["Dev"], "content": "X",
                                                "transferable": True, "source_ids": ["fantome"]})
        saved = self.s.action("agent_memory_save", {"scope": "profile", "profile_id": self.profiles["Dev"],
                                                    "content": "Toujours relire les migrations.", "transferable": True,
                                                    "source_ids": [report]})
        entries = self.s.action("agent_memory_list", {"scope": "profile", "profile_id": self.profiles["Dev"]})["entries"]
        self.assertEqual([e["id"] for e in entries], [saved["id"]])
        self.assertEqual(entries[0]["source_ids"], [report])
        self.assertIn("révision 1", entries[0]["origin"])

    def test_the_context_of_a_member_carries_its_own_memory_and_its_transferable_methods(self):
        id, report = self.reported_task()
        self.s.action("agent_memory_save", {"scope": "member", "project_id": self.p, "member_id": self.dev,
                                            "content": "OBSERVATION_LOCALE", "source_ids": [report]})
        self.s.action("agent_memory_save", {"scope": "profile", "profile_id": self.profiles["Dev"],
                                            "content": "METHODE_TRANSFERABLE", "transferable": True, "source_ids": [report]})
        self.s.action("agent_memory_save", {"scope": "member", "project_id": self.p, "member_id": self.lead,
                                            "content": "OBSERVATION_DU_LEAD", "source_ids": [report]})
        conversation = self.s.action("team_conversation", {"project_id": self.p, "member_id": self.dev})["id"]
        text = build_context(self.s.store, conversation, "Continuer", {}, 48000)["text"]
        self.assertIn("OBSERVATION_LOCALE", text)
        self.assertIn("METHODE_TRANSFERABLE", text)
        self.assertNotIn("OBSERVATION_DU_LEAD", text, "la mémoire d’un agent ne fuit pas vers un autre")
        self.assertIn("ne la transposez pas ailleurs", text)
        # A normal conversation is untouched by any of this.
        chat = self.s.action("create_conversation", {"project_id": self.p, "title": "Normale"})["id"]
        plain = build_context(self.s.store, chat, "Continuer", {}, 48000)["text"]
        self.assertNotIn("OBSERVATION_LOCALE", plain)
        self.assertNotIn("METHODE_TRANSFERABLE", plain)

    # --- evaluations ------------------------------------------------------------------------

    def test_an_evaluation_records_its_evidence_and_never_ranks_a_model(self):
        id, report = self.reported_task()
        result = self.s.action("task_evaluate", {"project_id": self.p, "id": id, "author_id": self.lead,
                                                 "scores": {"quality": 4, "scope": 5, "tests": 2},
                                                 "comment": "Travail propre mais un seul test ; périmètre respecté."})
        self.assertIn("n’alimente aucun classement automatique", result["notice"])
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        evaluation = task["evaluations"][0]
        self.assertEqual(evaluation["author"], "Lead")
        self.assertEqual(evaluation["member"], "Dev")
        self.assertEqual(evaluation["scores"], {"quality": 4, "scope": 5, "tests": 2})
        self.assertEqual(evaluation["labels"]["Tests réellement fournis"], 2)
        self.assertEqual((evaluation["profile_revision"], evaluation["connector"]), (1, "alpha"))
        self.assertTrue(evaluation["comment"])
        self.assertEqual(self.s.config.get("model_ratings", {}), {}, "aucune note de modèle n’est écrite automatiquement")

    def test_an_evaluation_is_refused_without_work_without_a_comment_or_from_the_worker(self):
        empty = self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "assignee_id": self.dev,
                                              "objective": "Sans rapport"})["id"]
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_evaluate", {"project_id": self.p, "id": empty, "author_id": self.lead,
                                            "scores": {"quality": 5}, "comment": "Excellent"})
        self.assertIn("aucun rapport", str(refusal.exception))
        id, report = self.reported_task()
        with self.assertRaises(ValueError):
            self.s.action("task_evaluate", {"project_id": self.p, "id": id, "author_id": self.lead,
                                            "scores": {"quality": 5}, "comment": "   "})
        with self.assertRaises(ValueError):
            self.s.action("task_evaluate", {"project_id": self.p, "id": id, "author_id": self.lead, "comment": "Sans note", "scores": {}})
        with self.assertRaises(ValueError):
            self.s.action("task_evaluate", {"project_id": self.p, "id": id, "author_id": self.lead,
                                            "scores": {"quality": 9}, "comment": "Hors barème"})
        with self.assertRaises(ValueError):
            self.s.action("task_evaluate", {"project_id": self.p, "id": id, "author_id": self.lead,
                                            "scores": {"rapidite": 4}, "comment": "Critère inventé"})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_evaluate", {"project_id": self.p, "id": id, "author_id": self.dev,
                                            "scores": {"quality": 5}, "comment": "Je me note moi-même"})
        self.assertIn("n’évalue pas son propre travail", str(refusal.exception))
        self.assertFalse(self.s.store.rows("SELECT id FROM task_evaluations"))

    # --- improvement proposals ---------------------------------------------------------------

    def test_adopting_a_prompt_proposal_creates_a_revision_teams_must_still_adopt(self):
        id, report = self.reported_task()
        proposal = self.s.action("improvement_propose", {
            "project_id": self.p, "member_id": self.lead, "profile_id": self.profiles["Dev"], "kind": "prompt",
            "proposed_value": "Consignes de Dev\n\nJoindre la sortie des tests à chaque rapport.",
            "rationale": "Trois rapports sans preuve de test.", "source_ids": [report, id]})
        self.assertIn("Rien ne change tant que vous ne l’adoptez pas", proposal["notice"])
        frozen = [m for m in self.s.action("team_get", {"project_id": self.p})["members"] if m["id"] == self.dev][0]
        self.assertEqual(frozen["definition"]["prompt"], "Consignes de Dev")
        decided = self.s.action("improvement_decide", {"id": proposal["id"], "adopt": True, "decision": "Constat partagé."})
        self.assertEqual(decided["revision"], 2)
        self.assertIn("adopter cette révision explicitement", decided["notice"])
        self.assertEqual(self.s.action("agent_profile_get", {"id": self.profiles["Dev"]})["revision"], 2)
        still = [m for m in self.s.action("team_get", {"project_id": self.p})["members"] if m["id"] == self.dev][0]
        self.assertEqual(still["definition"]["prompt"], "Consignes de Dev", "l’équipe garde sa révision figée")
        self.assertTrue(still["update_available"])
        # Reversible: adopting the previous revision restores the former instructions.
        self.s.action("team_adopt_revision", {"project_id": self.p, "id": self.dev})
        self.s.action("team_adopt_revision", {"project_id": self.p, "id": self.dev, "revision": 1})
        back = [m for m in self.s.action("team_get", {"project_id": self.p})["members"] if m["id"] == self.dev][0]
        self.assertEqual(back["definition"]["prompt"], "Consignes de Dev")

    def test_a_proposal_needs_sources_a_reason_and_a_responsible_author(self):
        id, report = self.reported_task()
        base = {"project_id": self.p, "profile_id": self.profiles["Dev"], "kind": "prompt",
                "proposed_value": "Autre chose", "rationale": "Motif", "source_ids": [report]}
        with self.assertRaises(ValueError) as refusal:
            self.s.action("improvement_propose", {**base, "member_id": self.dev})
        self.assertIn("chef de projet ou un lead", str(refusal.exception))
        with self.assertRaises(ValueError) as refusal:
            self.s.action("improvement_propose", {**base, "member_id": self.lead, "source_ids": []})
        self.assertIn("citer ses sources", str(refusal.exception))
        with self.assertRaises(ValueError):
            self.s.action("improvement_propose", {**base, "member_id": self.lead, "rationale": "  "})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("improvement_propose", {**base, "member_id": self.lead, "proposed_value": "Consignes de Dev"})
        self.assertIn("identique aux consignes actuelles", str(refusal.exception))
        single = self.s.action("improvement_propose", {**base, "member_id": self.lead})
        self.assertIn("incident isolé", single["notice"])
        self.assertFalse(self.s.store.rows("SELECT id FROM agent_profile_revisions WHERE revision=2"))

    def test_a_rejected_proposal_stays_visible_and_changes_nothing(self):
        id, report = self.reported_task()
        proposal = self.s.action("improvement_propose", {
            "project_id": self.p, "member_id": self.chief, "profile_id": self.profiles["Dev"], "kind": "memory",
            "proposed_value": "Relire les migrations deux fois.", "rationale": "Observé une fois.", "source_ids": [report]})
        result = self.s.action("improvement_decide", {"id": proposal["id"], "decision": "Un seul incident."})
        self.assertEqual(result["status"], "rejected")
        listed = self.s.action("improvement_list", {"project_id": self.p})["proposals"]
        self.assertEqual([(p["status_label"], p["kind_label"]) for p in listed], [("Écartée", "Mémoire transférable")])
        self.assertEqual(listed[0]["decision"], "Un seul incident.")
        self.assertFalse(self.s.action("agent_memory_list", {"scope": "profile", "profile_id": self.profiles["Dev"]})["entries"])
        with self.assertRaises(ValueError):
            self.s.action("improvement_decide", {"id": proposal["id"], "adopt": True})

    def test_adopting_a_memory_proposal_carries_its_sources_to_the_profile(self):
        id, report = self.reported_task()
        proposal = self.s.action("improvement_propose", {
            "project_id": self.p, "member_id": self.lead, "profile_id": self.profiles["Dev"], "kind": "memory",
            "proposed_value": "Joindre la sortie brute des tests.", "rationale": "Constant sur trois cartes.",
            "source_ids": [report, id]})
        self.s.action("improvement_decide", {"id": proposal["id"], "adopt": True})
        entries = self.s.action("agent_memory_list", {"scope": "profile", "profile_id": self.profiles["Dev"]})["entries"]
        self.assertEqual(entries[0]["content"], "Joindre la sortie brute des tests.")
        self.assertEqual(sorted(entries[0]["source_ids"]), sorted([report, id]))
        self.assertTrue(entries[0]["transferable"])
        self.assertEqual(self.s.action("agent_profile_get", {"id": self.profiles["Dev"]})["revision"], 1,
                         "une mémoire transférable ne crée pas de révision de consignes")

    # --- verified skills ---------------------------------------------------------------------

    def accepted_task(self, objective="Migrer le schéma"):
        id, report = self.reported_task(objective)
        self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.lead, "proofs": "Tests relus"})
        return id, report

    def test_a_skill_is_attested_only_on_accepted_work_of_that_profile(self):
        self.s.action("agent_profile_save", {"id": self.profiles["Dev"], "name": "Dev", "role": "member", "connector": "alpha",
                                             "prompt": "Consignes de Dev", "skills": ["migrations", "tests"]})
        id, report = self.reported_task()
        with self.assertRaises(ValueError) as refusal:
            self.s.action("skill_attest", {"profile_id": self.profiles["Dev"], "skill": "migrations", "source_ids": [id]})
        self.assertIn("tâche **acceptée**", str(refusal.exception), "une tâche seulement rendue ne prouve rien")
        self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.lead, "proofs": "Migration rejouée"})
        result = self.s.action("skill_attest", {"profile_id": self.profiles["Dev"], "skill": "migrations",
                                                "source_ids": [id], "note": "Deux migrations sans perte."})
        self.assertEqual(result["evidence"], 1)
        self.assertIn("pas ce que l’agent réussira la prochaine fois", result["notice"])
        profile = [x for x in self.s.action("agent_profile_list", {})["profiles"] if x["id"] == self.profiles["Dev"]][0]
        self.assertEqual(profile["attested"], ["migrations"])

    def test_undeclared_skills_and_foreign_evidence_are_refused(self):
        self.s.action("agent_profile_save", {"id": self.profiles["Dev"], "name": "Dev", "role": "member", "connector": "alpha",
                                             "prompt": "Consignes de Dev", "skills": ["migrations"]})
        id, report = self.accepted_task()
        with self.assertRaises(ValueError) as refusal:
            self.s.action("skill_attest", {"profile_id": self.profiles["Dev"], "skill": "cuisine", "source_ids": [id]})
        self.assertIn("n’est pas une compétence déclarée", str(refusal.exception))
        # Accepted work of the lead cannot attest a skill of the dev.
        lead_task = self.s.action("task_create", {"project_id": self.p, "author_id": self.chief, "assignee_id": self.lead,
                                                  "objective": "Travail du lead"})["id"]
        for status in ("ready", "in_progress"):
            self.s.action("task_status", {"project_id": self.p, "id": lead_task, "status": status, "author_id": self.chief})
        self.s.action("task_report", {"project_id": self.p, "id": lead_task, "author_id": self.lead, "result": "Fait"})
        self.s.action("task_accept", {"project_id": self.p, "id": lead_task, "author_id": self.chief, "proofs": "Relu"})
        with self.assertRaises(ValueError):
            self.s.action("skill_attest", {"profile_id": self.profiles["Dev"], "skill": "migrations", "source_ids": [lead_task]})
        partial = self.s.action("skill_attest", {"profile_id": self.profiles["Dev"], "skill": "migrations", "source_ids": [id, lead_task]})
        self.assertEqual(partial["evidence"], 1)
        self.assertIn("1 source(s) écartée(s)", partial["notice"])
        self.s.action("skill_withdraw", {"profile_id": self.profiles["Dev"], "skill": "migrations"})
        self.assertFalse(self.s.store.rows("SELECT id FROM skill_attestations"))

    def test_the_track_record_is_made_of_recorded_facts_only(self):
        empty = self.s.action("profile_track_record", {"profile_id": self.profiles["Dev"]})["record"]
        self.assertEqual((empty["tasks"], empty["accepted"], empty["evaluations"], empty["averages"]), (0, 0, 0, {}))
        id, report = self.accepted_task()
        self.s.action("task_evaluate", {"project_id": self.p, "id": id, "author_id": self.lead,
                                        "scores": {"quality": 4, "tests": 2}, "comment": "Correct, un seul test."})
        second, _ = self.accepted_task("Deuxième migration")
        self.s.action("task_evaluate", {"project_id": self.p, "id": second, "author_id": self.lead,
                                        "scores": {"quality": 5}, "comment": "Propre."})
        result = self.s.action("profile_track_record", {"profile_id": self.profiles["Dev"]})
        record = result["record"]
        self.assertEqual((record["tasks"], record["accepted"], record["evaluations"]), (2, 2, 2))
        self.assertEqual(record["averages"]["Qualité du travail"], {"average": 4.5, "count": 2})
        self.assertEqual(record["averages"]["Tests réellement fournis"], {"average": 2.0, "count": 1}, "l’effectif est toujours montré")
        self.assertIn("ni des benchmarks ni une garantie", result["notice"])
        self.assertNotIn("Migrer", str(record), "le bilan global ne transporte aucun contenu de tâche")

    # --- MCP ---------------------------------------------------------------------------------

    def test_learning_actions_are_scoped_and_authorized(self):
        ops = [op for op in app_mcp.ACTIONS.values() if op["domain"] == "learning"]
        self.assertEqual(len(ops), 10)
        for op in ops:
            app_mcp.Draft202012Validator.check_schema(op["inputSchema"])
            expected = "global" if op["name"] in {"profile_track_record", "skill_attest", "skill_withdraw"} else "project_id"
            self.assertEqual(op["scope"], expected, op["name"])
        other = self.s.action("create_project", {"name": "Voisin", "root": str(self.fixture.root)})["id"]
        control = Control(30, lambda d: True, lambda *_: None)
        id, report = self.reported_task()
        with self.assertRaises(ValueError) as refusal:
            app_mcp.call(self.s, "cyai_call", {"action": "task_evaluate", "arguments": {
                "project_id": other, "id": id, "scores": {"quality": 4}, "comment": "Hors projet"}}, [self.p], control)
        self.assertIn("hors périmètre", str(refusal.exception).lower())
        with self.assertRaises(ValueError):
            app_mcp.call(self.s, "cyai_call", {"action": "agent_memory_save", "arguments": {
                "scope": "member", "project_id": self.p, "member_id": self.dev, "content": "Sans autorisation"}}, [self.p])
        self.assertFalse(self.s.store.rows("SELECT id FROM agent_memory"))
        app_mcp.call(self.s, "cyai_call", {"action": "agent_memory_save", "arguments": {
            "scope": "member", "project_id": self.p, "member_id": self.dev, "content": "Autorisée", "source_ids": [report]}},
            [self.p], control)
        self.assertEqual(len(self.s.store.rows("SELECT id FROM agent_memory")), 1)


if __name__ == "__main__":
    unittest.main()
