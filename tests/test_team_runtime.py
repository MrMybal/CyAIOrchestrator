import json
import time
import unittest

import test_core
from cyai import app_mcp
from cyai.connectors import Control


class TeamRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.p = self.fixture.project
        for connector in self.s.engine.connectors.values():
            connector.config["enabled"] = True
        ids = {n: self.s.action("agent_profile_save", {"name": n, "role": r, "connector": c, "prompt": "Consignes de " + n,
                                                       "skills": ["analyse"], "description": "Profil " + n})["id"]
               for n, r, c in [("Chef", "chief", "alpha"), ("Lead", "lead", "alpha"), ("Dev", "member", "beta")]}
        self.profiles = ids
        self.s.action("team_save", {"project_id": self.p})
        self.chief = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Chef"], "role": "chief"})["id"]
        self.lead = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Lead"], "role": "lead", "manager_id": self.chief})["id"]
        self.dev = self.s.action("team_add_member", {"project_id": self.p, "profile_id": ids["Dev"], "role": "member",
                                                     "manager_id": self.lead, "responsibility": "Migrations et tests"})["id"]

    def tearDown(self):
        self.fixture.tearDown()

    def ready_task(self, objective="Migrer le schéma"):
        id = self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "assignee_id": self.dev,
                                           "objective": objective, "file_scope": "cyai/store.py",
                                           "acceptance_criteria": "Migration vérifiée"})["id"]
        self.s.action("task_status", {"project_id": self.p, "id": id, "status": "ready", "author_id": self.lead})
        return id

    def settle(self, task_id, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            task = self.s.action("task_get", {"project_id": self.p, "id": task_id})
            if not any(e["running"] for e in task["executions"]):
                return task
            time.sleep(.05)
        raise AssertionError("exécution non terminée dans le délai imparti")

    # --- member conversations ---------------------------------------------------------------

    def test_each_assignment_gets_its_own_conversation_from_its_frozen_definition(self):
        opened = self.s.action("team_conversation", {"project_id": self.p, "member_id": self.dev})
        self.assertTrue(opened["created"])
        self.assertEqual((opened["connector"], opened["model"]), ("beta", ""))
        conversation = self.s.conversation(opened["id"])
        self.assertEqual(conversation["mode"], "team")
        self.assertEqual(conversation["member_id"], self.dev)
        instructions = json.loads(conversation["agent_settings"])["instructions"]
        for expected in ("Dev", "membre de l’équipe", "Migrations et tests", "Consignes de Dev", "n’est pas une capacité vérifiée"):
            self.assertIn(expected, instructions)
        # Reopening returns the same conversation instead of forking a second one.
        again = self.s.action("team_conversation", {"project_id": self.p, "member_id": self.dev})
        self.assertEqual((again["id"], again["created"]), (opened["id"], False))
        self.assertEqual(len(self.s.action("team_conversations", {"project_id": self.p})["conversations"]), 1)

    def test_conversations_are_not_shared_between_projects_nor_with_the_profile(self):
        other = self.s.action("create_project", {"name": "Second", "root": str(self.fixture.root)})["id"]
        self.s.action("team_save", {"project_id": other})
        twin = self.s.action("team_add_member", {"project_id": other, "profile_id": self.profiles["Dev"], "role": "member"})["id"]
        first = self.s.action("team_conversation", {"project_id": self.p, "member_id": self.dev})["id"]
        second = self.s.action("team_conversation", {"project_id": other, "member_id": twin})["id"]
        self.assertNotEqual(first, second)
        self.assertEqual(len(self.s.action("team_conversations", {"project_id": self.p})["conversations"]), 1)
        with self.assertRaises(ValueError):
            self.s.action("team_conversation", {"project_id": self.p, "member_id": twin})
        self.assertFalse(self.s.store.rows("SELECT id FROM sessions"), "aucune session n’est ouverte par la simple création")

    def test_existing_modes_are_untouched_and_a_retired_member_has_no_conversation(self):
        chat = self.s.action("create_conversation", {"project_id": self.p, "title": "Discussion normale"})["id"]
        self.assertEqual(self.s.conversation(chat)["mode"], "chat")
        self.s.action("team_remove_member", {"project_id": self.p, "id": self.dev})
        with self.assertRaises(ValueError) as refusal:
            self.s.action("team_conversation", {"project_id": self.p, "member_id": self.dev})
        self.assertIn("retiré de l’équipe", str(refusal.exception))
        self.assertEqual(self.s.conversation(chat)["mode"], "chat")

    # --- executing a card ---------------------------------------------------------------------

    def test_running_a_card_produces_a_report_attributed_to_the_agent_and_stops_at_review(self):
        id = self.ready_task()
        launched = self.s.action("task_execute", {"project_id": self.p, "id": id})
        self.assertIn("n’est pas une tâche faite", launched["notice"])
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": id})["status"], "in_progress")
        task = self.settle(id)
        self.assertEqual(task["status"], "in_review", "un agent qui répond ne termine pas la tâche")
        self.assertEqual(len(task["reports"]), 1)
        report = task["reports"][0]
        self.assertEqual((report["source"], report["author"]), ("agent", "Dev"))
        self.assertEqual(report["result"], "beta résultat vérifiable")
        self.assertIn("CyAI n’a pas vérifié", report["limits"])
        self.assertEqual(report["executed_tests"], "", "aucun test n’est inventé à partir du texte de l’agent")
        self.assertEqual([e["status"] for e in task["executions"]], ["succeeded"])
        # The instruction actually sent carries the card, not just its title.
        prompt = self.s.engine.connectors["beta"].calls[0][0]
        for expected in ("Migrer le schéma", "cyai/store.py", "Migration vérifiée", "N’annoncez pas un succès"):
            self.assertIn(expected, prompt)

    def test_an_agent_report_does_not_accept_the_task(self):
        id = self.ready_task()
        self.s.action("task_execute", {"project_id": self.p, "id": id})
        self.settle(id)
        with self.assertRaises(ValueError):
            self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.dev, "proofs": "mon propre compte rendu"})
        self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.lead,
                                      "proofs": "Compte rendu relu ; tests rejoués à la main."})
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual(task["status"], "done")
        self.assertEqual(task["history"][-1]["author"], "Lead")

    def test_a_failed_execution_records_the_error_without_inventing_a_report(self):
        self.s.engine.connectors["beta"].mode = "fail"
        id = self.ready_task()
        self.s.action("task_execute", {"project_id": self.p, "id": id})
        task = self.settle(id)
        self.assertEqual(task["reports"], [], "aucun rapport n’est fabriqué quand l’agent échoue")
        self.assertEqual(task["status"], "in_progress", "l’échec d’une exécution ne clôt pas la carte")
        self.assertEqual([e["status"] for e in task["executions"]], ["failed"])
        self.assertIn("Erreur injectée", task["executions"][0]["detail"])
        self.assertIn("vérifiez les effets déjà produits", task["history"][-1]["detail"])
        with self.assertRaises(ValueError):
            self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.lead, "proofs": "rien"})

    def test_launch_is_refused_when_the_configuration_cannot_support_it(self):
        id = self.ready_task()
        unassigned = self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "objective": "Sans responsable"})["id"]
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_execute", {"project_id": self.p, "id": unassigned})
        self.assertIn("pas de responsable", str(refusal.exception))
        draft = self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "assignee_id": self.dev, "objective": "Brouillon"})["id"]
        with self.assertRaises(ValueError):
            self.s.action("task_execute", {"project_id": self.p, "id": draft})
        self.s.engine.connectors["beta"].config["enabled"] = False
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_execute", {"project_id": self.p, "id": id})
        self.assertIn("désactivé", str(refusal.exception))
        self.assertFalse(self.s.store.rows("SELECT id FROM task_executions"), "aucun lancement enregistré après un refus")

    def test_two_executions_of_the_same_card_never_run_at_once(self):
        self.s.engine.connectors["beta"].mode = "wait"
        id = self.ready_task()
        self.s.action("task_execute", {"project_id": self.p, "id": id})
        deadline = time.time() + 5
        while time.time() < deadline and not self.s.store.rows("SELECT id FROM steps WHERE status='running'"):
            time.sleep(.05)
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_execute", {"project_id": self.p, "id": id})
        self.assertIn("déjà en cours", str(refusal.exception))
        execution = self.s.action("task_get", {"project_id": self.p, "id": id})["executions"][0]
        self.assertTrue(execution["running"])
        result = self.s.action("task_execution_cancel", {"project_id": self.p, "id": execution["id"]})
        self.assertIn("effets déjà produits", result["notice"])
        task = self.settle(id)
        self.assertEqual(task["executions"][0]["status"], "cancelled")
        self.assertEqual(task["reports"], [])

    def test_an_interrupted_service_is_reported_rather_than_silently_lost(self):
        id = self.ready_task()
        self.s.action("task_execute", {"project_id": self.p, "id": id})
        self.settle(id)
        # Simulate a crash before the outcome was materialised: the execution is pending again.
        self.s.store.execute("UPDATE task_executions SET status='running',report_id=NULL,settled_at='' WHERE task_id=?", (id,))
        self.s.store.execute("DELETE FROM task_reports WHERE task_id=?", (id,))
        self.s.store.execute("UPDATE missions SET status='interrupted' WHERE id IN (SELECT mission_id FROM task_executions WHERE task_id=?)", (id,))
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual([e["status"] for e in task["executions"]], ["interrupted"])
        self.assertEqual(task["reports"], [])
        self.assertIn("Aucun compte rendu", task["history"][-1]["detail"])

    def test_two_members_work_in_parallel_in_their_own_conversations(self):
        second = self.s.action("team_add_member", {"project_id": self.p, "profile_id": self.profiles["Lead"],
                                                   "role": "member", "manager_id": self.lead})["id"]
        slow = self.ready_task("Tâche longue")
        quick = self.s.action("task_create", {"project_id": self.p, "author_id": self.lead, "assignee_id": second,
                                              "objective": "Tâche courte"})["id"]
        self.s.action("task_status", {"project_id": self.p, "id": quick, "status": "ready", "author_id": self.lead})
        self.s.engine.connectors["beta"].mode = "wait"
        self.s.action("task_execute", {"project_id": self.p, "id": slow})
        self.s.action("task_execute", {"project_id": self.p, "id": quick})
        finished = self.settle(quick)
        self.assertEqual(finished["status"], "in_review", "la seconde tâche n’attend pas la première")
        still = self.s.action("task_get", {"project_id": self.p, "id": slow})
        self.assertTrue(still["executions"][0]["running"], "la première est toujours en cours")
        conversations = self.s.action("team_conversations", {"project_id": self.p})["conversations"]
        self.assertEqual(len({c["id"] for c in conversations}), 2, "chaque agent travaille dans sa propre conversation")
        self.s.action("task_execution_cancel", {"project_id": self.p, "id": still["executions"][0]["id"]})
        self.settle(slow)

    def test_a_local_edit_changes_what_actually_runs(self):
        self.s.action("team_update_member", {"project_id": self.p, "id": self.dev, "overrides": {
            "connector": "alpha", "model": "alpha-local", "prompt": "CONSIGNE_LOCALE_DU_PROJET"}})
        conversation = self.s.action("team_conversation", {"project_id": self.p, "member_id": self.dev})
        self.assertEqual((conversation["connector"], conversation["model"]), ("alpha", "alpha-local"))
        instructions = json.loads(self.s.conversation(conversation["id"])["agent_settings"])["instructions"]
        self.assertIn("CONSIGNE_LOCALE_DU_PROJET", instructions)
        id = self.ready_task()
        self.s.action("task_execute", {"project_id": self.p, "id": id})
        task = self.settle(id)
        self.assertEqual(task["reports"][0]["result"], "alpha résultat vérifiable", "le connecteur surchargé est celui qui a tourné")
        self.assertFalse(self.s.engine.connectors["beta"].calls, "le connecteur de la révision figée n’a pas été appelé")

    # --- guards against turning without advancing ---------------------------------------------

    def rerun(self, id, times, acknowledged=False):
        for _ in range(times):
            self.s.action("task_status", {"project_id": self.p, "id": id, "status": "in_progress", "author_id": self.dev})
            self.s.store.execute("UPDATE tasks SET status='to_correct' WHERE id=?", (id,))
            self.s.action("task_execute", {"project_id": self.p, "id": id, **({"acknowledged": True} if acknowledged else {})})
            self.settle(id)
            self.s.store.execute("UPDATE tasks SET status='to_correct' WHERE id=?", (id,))

    def test_repeated_failures_are_raised_instead_of_being_relaunched_blindly(self):
        self.s.engine.connectors["beta"].mode = "fail"
        id = self.ready_task()
        self.s.action("task_execute", {"project_id": self.p, "id": id})
        self.settle(id)
        self.s.store.execute("UPDATE tasks SET status='to_correct' WHERE id=?", (id,))
        self.s.action("task_execute", {"project_id": self.p, "id": id})
        self.settle(id)
        self.s.store.execute("UPDATE tasks SET status='to_correct' WHERE id=?", (id,))
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual(task["stalled"]["code"], "repeated_failures")
        self.assertIn("peu de chances d’aboutir", task["stalled"]["message"])
        with self.assertRaises(ValueError) as refusal:
            self.s.action("task_execute", {"project_id": self.p, "id": id})
        self.assertIn("Confirmez (acknowledged)", str(refusal.exception))
        self.assertEqual(len(self.s.store.rows("SELECT id FROM task_executions")), 2, "aucun lancement apres le refus")
        # The user can still insist deliberately: CyAI raises the problem, it does not decide for them.
        self.s.action("task_execute", {"project_id": self.p, "id": id, "acknowledged": True})
        self.settle(id)
        self.assertEqual(len(self.s.store.rows("SELECT id FROM task_executions")), 3)

    def test_a_card_relaunched_without_ever_being_accepted_is_raised(self):
        id = self.ready_task()
        self.rerun(id, 3, acknowledged=True)
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual(task["stalled"]["code"], "no_progress")
        self.assertEqual(task["stalled"]["attempts"], 3)
        self.assertIn("ne fait pas avancer le board", task["stalled"]["message"])
        listed = [x for x in self.s.action("task_list", {"project_id": self.p})["tasks"] if x["id"] == id][0]
        self.assertEqual(listed["attempts"], 3)
        # Accepting clears it: the card has advanced.
        self.s.store.execute("UPDATE tasks SET status='in_review' WHERE id=?", (id,))
        self.s.action("task_accept", {"project_id": self.p, "id": id, "author_id": self.lead, "proofs": "Compte rendu relu"})
        self.assertIsNone(self.s.action("task_get", {"project_id": self.p, "id": id})["stalled"])

    def test_a_correction_loop_points_at_the_statement_not_at_the_worker(self):
        id = self.ready_task()
        for _ in range(3):
            self.s.action("task_execute", {"project_id": self.p, "id": id, "acknowledged": True})
            self.settle(id)
            self.s.action("task_correction", {"project_id": self.p, "id": id, "author_id": self.lead, "reason": "Toujours pas ce qu’il faut"})
        task = self.s.action("task_get", {"project_id": self.p, "id": id})
        self.assertEqual(task["stalled"]["code"], "correction_loop")
        self.assertIn("l’énoncé ou les critères", task["stalled"]["message"])

    def test_an_execution_can_be_paused_and_resumed_from_the_board(self):
        self.s.engine.connectors["beta"].mode = "wait"
        id = self.ready_task()
        self.s.action("task_execute", {"project_id": self.p, "id": id})
        deadline = time.time() + 5
        while time.time() < deadline and not self.s.store.rows("SELECT id FROM steps WHERE status='running'"):
            time.sleep(.05)
        execution = self.s.action("task_get", {"project_id": self.p, "id": id})["executions"][0]
        result = self.s.action("task_execution_pause", {"project_id": self.p, "id": execution["id"]})
        self.assertIn("n’annule pas ce qu’il a déjà écrit", result["notice"])
        self.s.engine.connectors["beta"].mode = "success"
        self.s.engine.cancel(execution["mission_id"])
        self.settle(id)
        self.assertEqual(self.s.action("task_get", {"project_id": self.p, "id": id})["executions"][0]["status"], "cancelled")

    # --- delegation through the CyAI MCP ------------------------------------------------------

    def delegating(self, connector_id, request):
        """Make a fixture agent call the CyAI MCP exactly as a real CLI would, through the same gateway."""
        connector = self.s.engine.connectors[connector_id]
        seen = {}

        def run(prompt, root, model, native_id, control):
            control.emit("session", {"native_id": native_id or "native"})
            token = control.mcp_servers["cyai_plugins"]["env"]["CYAI_PLUGIN_TOKEN"]
            seen["token"] = token
            seen["answer"] = self.s.plugins.gateway(token, {"method": "tools/call", "params": request})
            return "delegation tentee"

        connector.run = run
        return seen

    def test_a_chief_can_create_and_assign_a_card_from_its_own_conversation(self):
        # The write still goes through an approval; 'auto' stands for the user accepting it.
        self.s.engine.approval_default = "auto"
        conversation = self.s.action("team_conversation", {"project_id": self.p, "member_id": self.chief})["id"]
        seen = self.delegating("alpha", {"name": "cyai_call", "arguments": {"action": "task_create", "arguments": {
            "project_id": self.p, "author_id": self.chief, "assignee_id": self.dev,
            "objective": "Decoupe du domaine backend", "acceptance_criteria": "Tests verts"}}})
        mission = self.s.action("continue_conversation", {"conversation_id": conversation, "connector": "alpha",
                                                          "instruction": "Prepare le decoupage."})["mission_id"]
        deadline = time.time() + 10
        while time.time() < deadline and self.s.store.one("SELECT status FROM missions WHERE id=?", (mission,))["status"] in (
                "queued", "running", "awaiting_approval", "pausing"):
            time.sleep(.05)
        self.assertFalse(seen["answer"].get("isError"), seen["answer"])
        tasks = self.s.action("task_list", {"project_id": self.p})["tasks"]
        self.assertEqual([t["objective"] for t in tasks], ["Decoupe du domaine backend"])
        self.assertEqual((tasks[0]["assignee"], tasks[0]["author"]), ("Dev", "Chef"))
        self.assertEqual(tasks[0]["status"], "to_prepare", "une carte cree par le chef n est pas lancee toute seule")

    def test_an_agent_cannot_write_outside_the_project_of_its_conversation(self):
        self.s.engine.approval_default = "auto"
        other = self.s.action("create_project", {"name": "Voisin", "root": str(self.fixture.root)})["id"]
        conversation = self.s.action("team_conversation", {"project_id": self.p, "member_id": self.chief})["id"]
        seen = self.delegating("alpha", {"name": "cyai_call", "arguments": {"action": "task_create", "arguments": {
            "project_id": other, "author_id": self.chief, "objective": "Carte chez le voisin"}}})
        mission = self.s.action("continue_conversation", {"conversation_id": conversation, "connector": "alpha",
                                                          "instruction": "Essaie chez le voisin."})["mission_id"]
        deadline = time.time() + 10
        while time.time() < deadline and self.s.store.one("SELECT status FROM missions WHERE id=?", (mission,))["status"] in (
                "queued", "running", "awaiting_approval", "pausing"):
            time.sleep(.05)
        self.assertTrue(seen["answer"]["isError"])
        self.assertIn("hors périmètre", seen["answer"]["content"][0]["text"].lower())
        self.assertFalse(self.s.store.rows("SELECT id FROM tasks"))

    def test_launching_a_member_from_inside_a_mission_is_deferred_not_recursive(self):
        self.s.engine.approval_default = "auto"
        id = self.ready_task()
        conversation = self.s.action("team_conversation", {"project_id": self.p, "member_id": self.chief})["id"]
        seen = self.delegating("alpha", {"name": "cyai_call", "arguments": {"action": "task_execute", "arguments": {
            "project_id": self.p, "id": id}}})
        mission = self.s.action("continue_conversation", {"conversation_id": conversation, "connector": "alpha",
                                                          "instruction": "Lance le dev."})["mission_id"]
        deadline = time.time() + 10
        while time.time() < deadline and self.s.store.one("SELECT status FROM missions WHERE id=?", (mission,))["status"] in (
                "queued", "running", "awaiting_approval", "pausing"):
            time.sleep(.05)
        answer = json.loads(seen["answer"]["content"][0]["text"])
        self.assertIn("job_id", answer, answer)
        self.assertEqual(answer["status"], "pending")
        # The deferred job runs only once no mission is active, so no agent launches another one mid-flight.
        deadline = time.time() + 10
        while time.time() < deadline and not self.s.store.rows("SELECT id FROM task_executions"):
            time.sleep(.05)
        self.assertEqual(len(self.s.store.rows("SELECT id FROM task_executions")), 1)
        self.settle(id)

    # --- MCP --------------------------------------------------------------------------------

    def test_runtime_actions_are_project_scoped_and_authorized(self):
        ops = [app_mcp.ACTIONS[n] for n in ("team_conversation", "team_conversations", "task_execute", "task_execution_cancel")]
        for op in ops:
            app_mcp.Draft202012Validator.check_schema(op["inputSchema"])
            self.assertEqual(op["scope"], "project_id", op["name"])
        other = self.s.action("create_project", {"name": "Hors périmètre", "root": str(self.fixture.root)})["id"]
        approvals = []
        control = Control(30, lambda d: approvals.append(d) or True, lambda *_: None)
        id = self.ready_task()
        with self.assertRaises(ValueError) as refusal:
            app_mcp.call(self.s, "cyai_call", {"action": "task_execute", "arguments": {"project_id": other, "id": id}}, [self.p], control)
        self.assertIn("hors périmètre", str(refusal.exception).lower())
        with self.assertRaises(ValueError):
            app_mcp.call(self.s, "cyai_call", {"action": "task_execute", "arguments": {"project_id": self.p, "id": id}}, [self.p])
        self.assertFalse(self.s.store.rows("SELECT id FROM task_executions"))
        self.assertEqual(len(app_mcp.call(self.s, "cyai_call", {"action": "team_conversations", "arguments": {"project_id": self.p}},
                                          [self.p])["conversations"]), 0)


if __name__ == "__main__":
    unittest.main()
