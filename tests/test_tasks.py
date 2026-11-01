import unittest

import test_core
from cyai import app_mcp
from cyai.connectors import Control


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        ids = {n: self.s.action("agent_profile_save", {"name": n, "role": r, "connector": "alpha"})["id"]
               for n, r in [("Chef", "chief"), ("Lead", "lead"), ("Dev", "member"), ("Autre dev", "member")]}
        self.profiles = ids
        self.s.action("team_save", {"project_id": self.p})
        self.chief = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Chef"], "role": "chief"})["id"]
        self.lead = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Lead"], "role": "lead", "manager_id": self.chief})["id"]
        self.dev = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Dev"], "role": "member", "manager_id": self.lead})["id"]
        self.other_dev = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Autre dev"], "role": "member", "manager_id": self.lead})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def task(self, objective="Migrer le schéma", **extra):
        return self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "assignee_id": self.dev,
                                             "objective": objective, **extra})["id"]

    def advance(self, id, *statuses, author=None):
        for status in statuses:
            self.s.action("task_status", {"project_id": self.p, "id": id, "status": status, "author_id": author or self.dev})

    # --- creation and links ---------------------------------------------------------------

    def test_a_card_is_created_without_starting_anything(self):
        id = self.task(file_scope="cyai/store.py", acceptance_criteria="Migration vérifiée", deliverables="Schéma")
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual((task["status"], task["status_label"]), ("to_prepare", "À préparer"))
        self.assertEqual((task["assignee"], task["author"]), ("Dev", "Lead"))
        self.assertEqual([h["status"] for h in task["history"]], ["to_prepare"])
        self.assertEqual(task["reports"], [])
        self.assertFalse(self.s.store.rows("SELECT id FROM missions"), "aucune mission ne doit être créée")
        self.assertIn("Aucun agent n’est lancé", self.s.action("task_list", {"project_id": self.p})["notice"] +
                      self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "objective": "X"})["notice"])

    def test_members_of_another_team_are_refused_as_author_or_assignee(self):
        other = self.s.action("create_project", {"name": "Autre", "root": str(self.fixture.root)})["id"]
        self.s.action("team_save", {"project_id": other})
        foreign = self.s.action("team_add_member", {"project_id": other, "profile_id": self.profiles["Chef"], "role": "chief"})["id"]
        with self.assertRaises(ValueError):
            self.s.action("task_create", {"project_id": self.p, "author_id": foreign, "objective": "X"})
        with self.assertRaises(ValueError):
            self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "assignee_id": foreign, "objective": "X"})
        id = self.task()
        with self.assertRaises(ValueError):
            self.s.action("task_update", {"project_id": self.p, "id": id, "assignee_id": foreign})
        with self.assertRaises(ValueError):
            self.s.action("task_get", {"project_id": other, "id": id})

    def test_unknown_or_circular_links_are_refused_on_creation_and_on_update(self):
        first = self.task("Première")
        second = self.task("Seconde", dependencies=[first])
        with self.assertRaises(ValueError):
            self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "objective": "X", "dependencies": ["fantome"]})
        # The update path validates exactly like the creation path.
        with self.assertRaises(ValueError):
            self.s.action("task_update", {"project_id": self.p, "id": second, "dependencies": ["fantome"]})
        with self.assertRaises(ValueError):
            self.s.action("task_update", {"project_id": self.p, "id": second, "parent_id": "fantome"})
        with self.assertRaises(ValueError):
            self.s.action("task_update", {"project_id": self.p, "id": second, "dependencies": [second]})
        with self.assertRaises(ValueError):
            self.s.action("task_update", {"project_id": self.p, "id": second, "parent_id": second})
        with self.assertRaises(ValueError):
            self.s.action("task_update", {"project_id": self.p, "id": first, "dependencies": [second]})
        third = self.task("Troisième", dependencies=[second])
        with self.assertRaises(ValueError):
            self.s.action("task_update", {"project_id": self.p, "id": first, "dependencies": [third]})
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": second})["dependencies"], [first])

    def test_a_task_is_ready_only_when_its_dependencies_are_done(self):
        first = self.task("Première")
        second = self.task("Seconde", dependencies=[first])
        with self.assertRaises(ValueError):
            self.s.action("task_status", {"project_id": self.p, "id": second, "status": "ready", "author_id": self.lead})
        self.advance(first, "ready", "in_progress")
        self.s.action("task_report", {"project_id": self.p, "id": first, "author_id": self.dev, "result": "Fait", "executed_tests": "12 tests"})
        self.s.action("task_accept", {"project_id": self.p, "id": first, "author_id": self.lead, "proofs": "Sortie des tests relue"})
        self.s.action("task_status", {"project_id": self.p, "id": second, "status": "ready", "author_id": self.lead})
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": second})["status"], "ready")
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": second})["blocking"], [])

    # --- status machine -------------------------------------------------------------------

    def test_forbidden_transitions_are_refused_with_the_possible_next_states(self):
        id = self.task()
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_status", {"project_id": self.p, "id": id, "status": "in_progress", "author_id": self.dev})
        self.assertIn("Prête", str(refusal.exception))
        self.advance(id, "ready", "in_progress", "awaiting_information")
        with self.assertRaises(ValueError):
            self.s.action("task_status", {"project_id": self.p, "id": id, "status": "in_review", "author_id": self.dev})
        self.advance(id, "in_progress")
        self.s.action("task_status", {"project_id": self.p, "id": id, "status": "cancelled", "author_id": self.chief, "reason": "Périmètre abandonné"})
        for target in ("in_progress", "ready", "to_prepare"):
            with self.assertRaises(ValueError):
                self.s.action("task_status", {"project_id": self.p, "id": id, "status": target, "author_id": self.chief})
        history = self.s.action("task_get", {"project_id": self.p, "id": id})["history"]
        self.assertEqual([h["status"] for h in history], ["to_prepare", "ready", "in_progress", "awaiting_information", "in_progress", "cancelled"])
        self.assertEqual(history[-1]["detail"], "Périmètre abandonné")
        self.assertEqual(history[-1]["author"], "Chef")

    def test_done_and_to_correct_are_not_reachable_by_a_plain_status_change(self):
        id = self.task()
        self.advance(id, "ready", "in_progress")
        for target in ("done", "to_correct"):
            with self.assertRaises(ValueError) as refusal:
                self.s.action("task_status", {"project_id": self.p, "id": id, "status": target, "author_id": self.lead})
            self.assertIn("preuves", str(refusal.exception))

    # --- report and acceptance are two distinct acts ----------------------------------------

    def test_a_report_never_completes_a_task(self):
        id = self.task()
        self.advance(id, "ready", "in_progress")
        result = self.s.action("task_report", {"project_id": self.p, "id": id, "author_id": self.dev,
                                               "result": "Terminé avec succès", "modified_files": "cyai/store.py",
                                               "executed_tests": "unittest : 192 tests", "limits": "Non testé sous Linux",
                                               "risks": "Migration irréversible", "requested_decisions": "Valider le nom des colonnes"})
        self.assertEqual(result["task_status"], "in_review")
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual(task["status"], "in_review", "un rapport met en revue, il ne termine pas")
        self.assertEqual(len(task["reports"]), 1)
        self.assertEqual(task["reports"][0]["author"], "Dev")
        self.assertEqual(task["reports"][0]["executed_tests"], "unittest : 192 tests")
        self.assertIn("pas une acceptation", result["notice"])

    def test_an_agent_cannot_accept_its_own_work(self):
        id = self.task()
        self.advance(id, "ready", "in_progress")
        self.s.action("task_report", {"project_id": self.p, "id": id, "author_id": self.dev, "result": "Fait"})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.dev, "proofs": "je valide mon travail"})
        self.assertIn("propre tâche", str(refusal.exception))
        with self.assertRaises(ValueError):
            self.s.action("task_correction", {"project_id": self.p, "id": id, "author_id": self.dev, "reason": "je me corrige"})
        # A peer is not a superior either; a superior further up the chain is accepted.
        with self.assertRaises(ValueError):
            self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.other_dev, "proofs": "collègue"})
        self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.chief, "proofs": "Revue du chef"})
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": id})["status"], "done")

    def test_acceptance_requires_a_review_state_evidence_and_a_report(self):
        id = self.task()
        with self.assertRaises(ValueError):
            self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.lead, "proofs": "rien vu"})
        self.advance(id, "ready", "in_progress")
        self.s.store.execute("UPDATE tasks SET status='in_review' WHERE id=?", (id,))
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.lead, "proofs": "aucune"})
        self.assertIn("Aucun rapport", str(refusal.exception))
        self.s.action("task_report", {"project_id": self.p, "id": id, "author_id": self.dev, "result": "Fait"})
        with self.assertRaises(ValueError):
            self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.lead, "proofs": ""})
        self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.lead, "proofs": "Tests relus ligne à ligne"})
        history = self.s.action("task_get", {"project_id": self.p, "id": id})["history"]
        self.assertIn("Tests relus ligne à ligne", history[-1]["detail"])
        self.assertEqual(history[-1]["author"], "Lead")

    def test_a_correction_sends_the_task_back_and_the_user_can_decide_directly(self):
        id = self.task()
        self.advance(id, "ready", "in_progress")
        self.s.action("task_report", {"project_id": self.p, "id": id, "author_id": self.dev, "result": "Première tentative"})
        self.s.action("task_correction", {"project_id": self.p, "id": id, "author_id": self.lead, "reason": "Tests absents"})
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual(task["status"], "to_correct")
        self.assertIn("Tests absents", task["history"][-1]["detail"])
        self.advance(id, "in_progress")
        self.s.action("task_report", {"project_id": self.p, "id": id, "author_id": self.dev, "result": "Corrigé", "executed_tests": "8 tests"})
        self.s.action("task_accept", {"project_id": self.p, "id": id, "by_user": True, "proofs": "Vérifié par l’utilisateur"})
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual(task["status"], "done")
        self.assertEqual(task["history"][-1]["author"], "Utilisateur")
        self.assertIsNone(task["history"][-1]["author_id"])

    def test_a_consultant_task_is_reviewed_by_a_chief_or_by_the_user(self):
        expert = self.s.action("agent_profile_save", {"name": "Chercheur web", "role": "consultant", "connector": "beta"})["id"]
        consultant = self.s.action("team_add_member", {"project_id": self.p, "profile_id": expert, "role": "consultant"})["id"]
        id = self.task("Chercher les sources publiques", assignee_id=consultant)
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual([r["id"] for r in task["reviewers"]], [self.chief],
                         "hors hiérarchie, la décision remonte au chef de projet")
        self.advance(id, "ready", "in_progress", author=consultant)
        self.s.action("task_report", {"project_id": self.p, "id": id, "author_id": consultant,
                                      "result": "Cinq sources", "limits": "Pages non archivées"})
        with self.assertRaises(ValueError):
            self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": consultant, "proofs": "moi-même"})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.lead, "proofs": "le lead"})
        self.assertIn("Habilités : Chef", str(refusal.exception))
        self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.chief, "proofs": "Sources ouvertes une à une"})
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": id})["status"], "done")

    def test_a_task_assigned_to_the_chief_is_accepted_by_the_user_alone(self):
        id = self.s.action("task_create", {"project_id": self.p, "author_id": self.chief, "assignee_id": self.chief,
                                           "objective": "Cadrer le besoin"})["id"]
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": id})["reviewers"], [])
        self.advance(id, "ready", "in_progress", author=self.chief)
        self.s.action("task_report", {"project_id": self.p, "id": id, "author_id": self.chief, "result": "Périmètre arrêté"})
        for author in (self.chief, self.lead):
            with self.assertRaises(ValueError):
                self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": author, "proofs": "x"})
        self.s.action("task_accept", {"project_id": self.p, "id": id, "by_user": True, "proofs": "Lu et validé"})
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": id})["history"][-1]["author"], "Utilisateur")

    # --- consultations ----------------------------------------------------------------------

    def consultant(self, name="Chercheur web"):
        profile = self.s.action("agent_profile_save", {"name": name, "role": "consultant", "connector": "beta"})["id"]
        return self.s.action("team_add_member", {"project_id": self.p, "profile_id": profile, "role": "consultant"})["id"]

    def test_an_opinion_never_moves_the_card_nor_transfers_its_responsibility(self):
        expert = self.consultant()
        id = self.task()
        self.advance(id, "ready", "in_progress")
        result = self.s.action("task_consult", {"project_id": self.p, "id": id, "consultant_id": expert,
                                                "author_id": self.lead, "question": "Quelles sources publiques existent ?"})
        self.assertEqual(result["task_status"], "in_progress")
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual(task["status"], "in_progress", "demander un avis ne déplace pas la carte")
        self.assertEqual(task["assignee_id"], self.dev, "le consultant ne devient pas responsable")
        self.assertEqual(len(task["consultations"]), 1)
        self.assertEqual(task["consultations"][0]["status_label"], "Avis demandé")
        self.assertEqual((task["consultations"][0]["consultant"], task["consultations"][0]["requester"]), ("Chercheur web", "Lead"))
        self.assertEqual(task["reports"], [], "un avis n’est pas un rapport")
        self.s.action("task_consult_answer", {"project_id": self.p, "id": result["id"], "answer": "Trois sources, une payante."})
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual(task["status"], "in_progress")
        self.assertEqual(task["consultations"][0]["status"], "answered")
        self.assertEqual(task["consultations"][0]["source_label"], "Saisi par l’utilisateur")
        self.assertEqual(task["reports"], [])

    def test_a_typed_answer_is_never_presented_as_the_agent_having_worked(self):
        expert = self.consultant()
        id = self.task()
        asked = self.s.action("task_consult", {"project_id": self.p, "id": id, "by_user": True, "consultant_id": expert,
                                               "question": "Un avis rapide ?"})
        self.assertIn("Utilisateur", self.s.action("task_get", {"project_id": self.p, "id": id})["consultations"][0]["requester"])
        answered = self.s.action("task_consult_answer", {"project_id": self.p, "id": asked["id"], "answer": "Rien à signaler."})
        self.assertIn("Saisi par l’utilisateur", answered["notice"])
        self.assertIn("ne vaut ni rapport ni acceptation", answered["notice"])
        # Answering twice is refused: a new question opens a new consultation.
        with self.assertRaises(ValueError):
            self.s.action("task_consult_answer", {"project_id": self.p, "id": asked["id"], "answer": "Encore"})

    def test_consulting_the_assignee_or_a_closed_card_is_refused(self):
        expert = self.consultant()
        id = self.task()
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_consult", {"project_id": self.p, "id": id, "consultant_id": self.dev,
                                           "author_id": self.lead, "question": "Ton avis ?"})
        self.assertIn("rend un rapport", str(refusal.exception))
        self.s.action("task_status", {"project_id": self.p, "id": id, "status": "cancelled", "author_id": self.chief})
        with self.assertRaises(ValueError):
            self.s.action("task_consult", {"project_id": self.p, "id": id, "consultant_id": expert,
                                           "author_id": self.lead, "question": "Trop tard ?"})
        other = self.s.action("create_project", {"name": "Voisin", "root": str(self.fixture.root)})["id"]
        second = self.task("Autre carte")
        asked = self.s.action("task_consult", {"project_id": self.p, "id": second, "consultant_id": expert,
                                               "author_id": self.lead, "question": "Sources ?"})
        with self.assertRaises(ValueError):
            self.s.action("task_consult_answer", {"project_id": other, "id": asked["id"], "answer": "Hors projet"})

    def test_a_declined_opinion_is_recorded_with_its_reason(self):
        expert = self.consultant()
        id = self.task()
        asked = self.s.action("task_consult", {"project_id": self.p, "id": id, "consultant_id": expert,
                                               "author_id": self.lead, "question": "Peux-tu chercher ?"})
        self.s.action("task_consult_answer", {"project_id": self.p, "id": asked["id"], "declined": True,
                                              "answer": "Hors de mon périmètre déclaré."})
        consultation = self.s.action("task_get", {"project_id": self.p, "id": id})["consultations"][0]
        self.assertEqual((consultation["status"], consultation["status_label"]), ("declined", "Avis décliné"))
        self.assertEqual(consultation["answer"], "Hors de mon périmètre déclaré.")
        self.assertEqual(self.s.action("task_list", {"project_id": self.p})["tasks"][0]["pending_consultations"], 0)

    # --- deletion, reading and persistence ---------------------------------------------------

    def test_deleting_a_linked_task_requires_a_confirmation_and_cleans_the_links(self):
        parent = self.task("Parent")
        child = self.task("Enfant", parent_id=parent)
        dependant = self.task("Dépendante", dependencies=[parent])
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_delete", {"project_id": self.p, "id": parent})
        self.assertIn("sous-tâche", str(refusal.exception))
        self.s.action("task_delete", {"project_id": self.p, "id": parent, "acknowledged": True})
        self.assertFalse(self.s.store.rows("SELECT id FROM tasks WHERE id=?", (child,)), "la sous-tâche suit son parent")
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": dependant})["dependencies"], [])

    def test_reports_and_history_survive_a_member_being_removed(self):
        id = self.task()
        self.advance(id, "ready", "in_progress")
        self.s.action("task_report", {"project_id": self.p, "id": id, "author_id": self.dev, "result": "Rendu avant départ"})
        self.s.action("team_remove_member", {"project_id": self.p, "id": self.dev, "delete": True, "acknowledged": True})
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual(task["status"], "in_review")
        self.assertEqual(task["reports"][0]["result"], "Rendu avant départ")
        self.assertEqual(task["reports"][0]["author"], "Affectation retirée")
        self.assertEqual(task["history"][0]["author"], "Lead")

    def test_a_team_is_required_and_the_board_is_announced_as_next(self):
        other = self.s.action("create_project", {"name": "Sans équipe", "root": str(self.fixture.root)})["id"]
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_list", {"project_id": other})
        self.assertIn("onglet Équipe", str(refusal.exception))
        listing = self.s.action("task_list", {"project_id": self.p})
        self.assertIn("board", listing["notice"])
        self.assertEqual({m["id"] for m in listing["members"]}, {self.chief, self.lead, self.dev, self.other_dev})


class TaskMcpTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        self.other = self.s.action("create_project", {"name": "Hors périmètre", "root": str(self.fixture.root)})["id"]
        profile = self.s.action("agent_profile_save", {"name": "Chef", "role": "chief", "connector": "alpha"})["id"]
        for project in (self.p, self.other):
            self.s.action("team_save", {"project_id": project})
            member = self.s.action("team_add_member", {"project_id": project, "profile_id": profile, "role": "chief"})["id"]
            setattr(self, "chief" if project == self.p else "foreign_chief", member)
        self.approvals = []
        self.control = Control(30, lambda d: self.approvals.append(d) or True, lambda *_: None)
        self.control.conversation_id = self.fixture.conversation

    def tearDown(self):
        self.fixture.tearDown()

    def call(self, name, args=None, control=None, allow_write=False):
        return app_mcp.call(self.s, "cyai_call", {"action": name, "arguments": args or {}}, [self.p], control, allow_write)

    def test_task_actions_are_project_scoped_and_schemas_are_valid(self):
        ops = [op for op in app_mcp.ACTIONS.values() if op["domain"] == "tasks"]
        self.assertEqual({op["name"] for op in ops},
                         {"task_list", "task_get", "task_create", "task_update", "task_delete", "task_status",
                          "task_report", "task_accept", "task_correction", "task_consult", "task_consult_answer",
                          "task_execute", "task_execution_cancel", "task_execution_pause",
                          # 0.2.15: the delegation automaton's plan, read-only; stepping and the pilot stay user-only.
                          "team_autopilot_plan"})
        for op in ops:
            app_mcp.Draft202012Validator.check_schema(op["inputSchema"])
            self.assertEqual(op["scope"], "project_id", op["name"])

    def test_a_client_cannot_touch_the_board_of_another_project(self):
        for name, args in [("task_list", {"project_id": self.other}),
                           ("task_create", {"project_id": self.other, "author_id": self.foreign_chief, "objective": "X"})]:
            with self.assertRaises(ValueError) as refusal:
                self.call(name, args, allow_write=True)
            self.assertIn("hors périmètre", str(refusal.exception).lower())
        self.assertFalse(self.s.store.rows("SELECT id FROM tasks"))

    def test_writes_need_an_authorization_and_reads_do_not(self):
        with self.assertRaises(ValueError):
            self.call("task_create", {"project_id": self.p, "author_id": self.chief, "objective": "Sans autorisation"})
        self.assertEqual(self.call("task_list", {"project_id": self.p})["tasks"], [])
        created = self.call("task_create", {"project_id": self.p, "author_id": self.chief, "objective": "Autorisée"}, control=self.control)
        self.assertEqual(len(self.approvals), 1)
        self.assertEqual(self.approvals[0]["scope"], "projet")
        self.assertEqual(len(self.call("task_list", {"project_id": self.p})["tasks"]), 1)
        self.assertEqual(self.call("task_get", {"project_id": self.p, "id": created["id"]})["objective"], "Autorisée")


if __name__ == "__main__":
    unittest.main()
