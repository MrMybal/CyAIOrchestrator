import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from cyai.context import build_context
from cyai.engine import Engine
from cyai.mcp import call_tool
from cyai.security import PathPolicy, SecretStore, scoped_path
from cyai.server import make_server
from cyai.service import Service
from cyai.store import Store, now, uid


class TestSecrets:
    def redact(self, value):
        return value


class FixtureConnector:
    """Test-only adapter, never registered in the production application."""
    kind = "agent"
    config = {}
    def __init__(self, id):
        self.id, self.calls = id, []
        self.config = {}  # Per instance: a test enabling a connector must not leak into the next one.
        self.mode = "success"
        self.answer = None  # Optional: a test can make the answer depend on the prompt received.
    def check(self):
        return {"status": "operational"}
    def run(self, prompt, root, model, native_id, control):
        self.calls.append((prompt, native_id))
        control.emit("session", {"native_id": native_id or uid()})
        control.emit("delta", {"text": self.id + " résultat"})
        if self.mode == "approval":
            if not control.approve({"tool": "write_file", "path": "answer.txt"}):
                raise ValueError("Refus utilisateur")
        if self.mode == "fail":
            raise ValueError("Erreur injectée")
        if self.mode == "wait":
            while True:
                control.check()
                time.sleep(.01)
        return self.answer(prompt) if self.answer else self.id + " résultat vérifiable"


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "db.sqlite3")
        self.connectors = {k: FixtureConnector(k) for k in ("alpha", "beta")}
        self.policy = PathPolicy([self.root])
        self.engine = Engine(self.store, self.connectors, self.policy, TestSecrets())
        self.service = Service(self.store, self.engine, {"allowed_roots": [str(self.root)]}, self.root / "config.json")
        self.project = self.service.action("create_project", {"name": "Projet test", "root": str(self.root)})["id"]
        self.conversation = self.service.action("create_conversation", {"project_id": self.project, "title": "Conversation test"})["id"]
    def tearDown(self):
        self.engine.shutdown()
        self.store.close()
        self.tmp.cleanup()

    def test_create_project_outside_initial_root_and_persist(self):
        with tempfile.TemporaryDirectory() as other:
            project = self.service.action('create_project', {'name': 'Autre dossier', 'root': other})
            conversation = self.service.action('create_conversation', {'project_id': project['id'], 'title': 'Travail'})
            self.assertEqual(self.service.conversation(conversation['id'])['project_id'], project['id'])
            saved = json.loads(self.service.config_path.read_text(encoding='utf-8'))
            self.assertIn(str(Path(other).resolve()), saved['allowed_roots'])

    def test_project_data_directory_remains_protected(self):
        protected = self.root / 'private-data'
        protected.mkdir()
        self.engine.policy.protected_roots = [protected]
        with self.assertRaises(ValueError):
            self.service.action('create_project', {'name': 'Refus', 'root': str(protected)})

    def test_orchestrator_plan_waits_for_explicit_approval(self):
        c = self.action_conversation('orchestrator')
        observed = []
        def planner(prompt, root, model, native_id, control):
            observed.append((control.planning, control.approve({'tool': 'write'})))
            return json.dumps({'reply':'Voici le plan.', 'plan': {'title':'Plan test', 'steps':[
                {'name':'Travail','connector':'beta','model':'model-b','instruction':'Produire un résultat','depends_on':[]}]}})
        self.connectors['alpha'].run = planner
        planning = self.service.action('continue_conversation', {'conversation_id':c,'connector':'alpha','instruction':'Prépare le travail'})['mission_id']
        self.wait(planning, 'succeeded')
        self.assertEqual(observed, [(True, False)])
        self.assertEqual(len(self.connectors['beta'].calls), 0)
        proposal = self.service.conversation(c)['plans'][0]
        self.assertIsNone(proposal['execution'])
        with self.assertRaises(ValueError):
            self.service.action('approve_plan', {'id':planning})
        mission = self.service.action('approve_plan', {'id':planning, 'acknowledged':True})['mission_id']
        self.wait(mission, 'succeeded')
        self.assertEqual(len(self.connectors['beta'].calls), 1)
        self.assertEqual(self.service.action('approve_plan', {'id':planning, 'acknowledged':True})['mission_id'], mission)
        self.assertEqual(self.service.project(self.project)['conversations'][0]['mode'], 'orchestrator')

    def action_conversation(self, mode):
        return self.service.action('create_conversation', {'project_id':self.project,'title':'Mode test','mode':mode})['id']

    def test_normal_mode_allows_switch_with_history(self):
        c=self.action_conversation('chat')
        mission=self.service.action('continue_conversation',{'conversation_id':c,'connector':'alpha','model':'a','instruction':'Premier message'})['mission_id']
        self.wait(mission,'succeeded')
        for connector,model in [('alpha','b'),('beta','c'),('alpha','a')]:
            mission=self.service.action('continue_conversation',{'conversation_id':c,'connector':connector,'model':model,'instruction':'Autre agent'})['mission_id']
            self.wait(mission,'succeeded')
            prompt,native=self.connectors[connector].calls[-1]
            self.assertIn('beta résultat vérifiable' if native else 'Premier message',prompt)
        self.assertEqual(len(self.store.rows('SELECT * FROM sessions WHERE conversation_id=?',(c,))),3)
        self.assertEqual(self.service.conversation(c)['agent_model'],'a')
    def spec(self, **kwargs):
        return {"conversation_id": self.conversation, "title": "Test", "steps": [{"connector": "alpha", "instruction": "Décision A"}], **kwargs}
    def wait(self, id, expected=None):
        # The suite now runs many engines side by side; 4s was marginal on a loaded machine and made
        # this helper flaky. Only the waiting time changes, never what is asserted.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            m = self.service.mission(id)
            if (m["status"] == expected if expected else m["status"] not in {"queued", "running", "awaiting_approval", "pending"}):
                return m
            time.sleep(.015)
        self.fail("Mission restée active : " + str(m))
    def run_job(self, spec=None):
        id = self.service.action("create_mission", spec or self.spec())["mission_id"]
        return self.wait(id)
    def test_persistence_and_native_resume_after_restart(self):
        self.assertEqual(self.run_job()["status"], "succeeded")
        first_session = self.service.conversation(self.conversation)["sessions"][0]["native_id"]
        self.engine.shutdown()
        self.store.close()
        self.store = Store(self.root / "db.sqlite3")
        self.engine = Engine(self.store, self.connectors, self.policy, TestSecrets())
        self.service = Service(self.store, self.engine, {}, self.root / "config.json")
        self.run_job(self.spec(steps=[{"connector": "alpha", "instruction": "Continuer"}]))
        self.assertEqual(self.connectors["alpha"].calls[-1][1], first_session)
        self.assertEqual(len(self.service.conversation(self.conversation)["messages"]), 4)
    def test_handoff_transmits_result_and_validated_memory(self):
        self.service.action("save_memory", {"project_id": self.project, "content": "Mémoire approuvée", "validated": True})
        self.service.action("save_memory", {"project_id": self.project, "content": "Proposition privée", "validated": False})
        mission = self.run_job(self.spec(steps=[{"connector": "alpha", "instruction": "Plan"}, {"connector": "beta", "instruction": "Réalise"}]))
        prompt = self.connectors["beta"].calls[0][0]
        self.assertEqual(mission["status"], "succeeded")
        self.assertIn("alpha résultat", prompt)
        self.assertIn("Mémoire approuvée", prompt)
        self.assertNotIn("Proposition privée", prompt)
        sessions = self.service.conversation(self.conversation)["sessions"]
        self.assertEqual(len(sessions), 2)
        self.assertNotEqual(sessions[0]["native_id"], sessions[1]["native_id"])
    def test_explicit_context_starts_fresh_session(self):
        self.run_job()
        message = self.service.conversation(self.conversation)["messages"][0]
        self.run_job(self.spec(context={"message_ids": [message["id"]]}))
        self.assertIsNone(self.connectors["alpha"].calls[-1][1])
    def test_cross_conversation_context_is_rejected(self):
        other = self.service.action("create_conversation", {"project_id": self.project})["id"]
        id = self.store.message(other, "user", "Privé")
        with self.assertRaises(ValueError):
            build_context(self.store, self.conversation, "Test", {"message_ids": [id]})
    def test_context_budget_never_silently_drops_manual_selection(self):
        id = self.store.message(self.conversation, "user", "A" * 4000)
        selected = build_context(self.store, self.conversation, "Test", {"message_ids": [id]}, 1000)
        self.assertEqual(selected['source_ids'], [id])
        self.assertFalse(selected['omitted_ids'])
        self.assertIn('A'*4000, selected['text'])
        self.assertTrue(selected['budget_expanded'])
        required = build_context(self.store, self.conversation, 'B'*6000, {}, 1000)
        self.assertIn('B'*6000, required['text'])
        self.assertTrue(required['budget_expanded'])
        result = build_context(self.store, self.conversation, "Test", {}, 1000)
        self.assertIn(id, result["omitted_ids"])
        self.assertTrue(result["budget_expanded"])
        self.assertEqual(result["project_foundation"]["source_ids"], [id])
        self.assertIn("A"*4000,result["project_foundation"]["content"])
        self.assertLessEqual(result["chars"], result["budget_chars"])
    def test_idempotency_and_duplicate_launch(self):
        spec = self.spec(request_key="stable-key", launch=False)
        first = self.service.action("create_mission", spec)["mission_id"]
        second = self.service.action("create_mission", spec)["mission_id"]
        self.assertEqual(first, second)
        self.engine.launch(first)
        self.engine.launch(first)
        self.wait(first)
        self.assertEqual(len(self.connectors["alpha"].calls), 1)
        self.assertEqual(len(self.service.conversation(self.conversation)["messages"]), 2)
        with self.assertRaises(ValueError):
            self.service.action("create_mission", self.spec(request_key="stable-key", title="Autre"))
    def test_dependency_cycles_and_recursion_rejected(self):
        for spec in [self.spec(parent_mission_id="parent"), self.spec(delegation_depth=1), self.spec(steps=[{"connector": "alpha", "instruction": "Test", "depends_on": [0]}])]:
            with self.assertRaises(ValueError):
                self.engine.create(spec)
    def test_cancellation_propagates(self):
        self.connectors["alpha"].mode = "wait"
        id = self.service.action("create_mission", self.spec())["mission_id"]
        self.wait(id, "running")
        self.engine.cancel(id)
        self.assertEqual(self.wait(id)["status"], "cancelled")
    def test_graceful_shutdown_marks_interrupted(self):
        self.connectors["alpha"].mode = "wait"
        id = self.service.action("create_mission", self.spec())["mission_id"]
        self.wait(id, "running")
        self.engine.shutdown()
        self.assertEqual(self.service.mission(id)["status"], "interrupted")
    def test_crash_recovery_never_auto_replays(self):
        id = self.engine.create(self.spec())
        self.store.execute("UPDATE missions SET status='running' WHERE id=?", (id,))
        self.store.execute("UPDATE steps SET status='running' WHERE mission_id=?", (id,))
        self.store.recover()
        self.assertEqual(self.service.mission(id)["status"], "interrupted")
        self.assertEqual(len(self.connectors["alpha"].calls), 0)
    def test_retry_keeps_successful_steps(self):
        self.connectors["beta"].mode = "fail"
        spec = self.spec(steps=[{"connector": "alpha", "instruction": "Plan"}, {"connector": "beta", "instruction": "Modifie"}])
        m = self.run_job(spec)
        self.assertEqual(m["status"], "failed")
        with self.assertRaises(ValueError):
            self.engine.retry(m["id"])
        self.connectors["beta"].mode = "success"
        self.engine.retry(m["id"], True)
        self.assertEqual(self.wait(m["id"])["status"], "succeeded")
        self.assertEqual(len(self.connectors["alpha"].calls), 1)
        self.assertEqual(len(self.connectors["beta"].calls), 2)
    def test_max_attempts(self):
        self.connectors["alpha"].mode = "fail"
        m = self.run_job(self.spec(max_attempts=1))
        with self.assertRaises(ValueError):
            self.engine.retry(m["id"], False)
        with self.assertRaises(ValueError):
            self.engine.retry(m["id"], True, concurrency=33)
        self.connectors["alpha"].mode = "success"
        self.service.action('retry_mission', {'mission_id':m['id'],'acknowledged':True,'concurrency':32})
        self.engine.jobs.join()
        resumed=self.service.mission(m['id'])
        self.assertEqual(resumed['status'],'succeeded')
        self.assertEqual(resumed['spec']['concurrency'],32)
        self.assertEqual(resumed['steps'][0]['attempts'],2)
    def test_approval_and_rejection(self):
        self.connectors["alpha"].mode = "approval"
        id = self.service.action("create_mission", self.spec())["mission_id"]
        self.wait(id, "awaiting_approval")
        approval = self.service.state()["approvals"][0]
        self.engine.approve(approval["id"], False)
        self.assertEqual(self.wait(id)["status"], "failed")
        self.assertFalse(self.engine.approvals)
    def test_auto_approval_is_scoped_and_audited(self):
        self.connectors['alpha'].mode = 'approval'
        self.service.action('approval_settings', {'conversation_id': self.conversation, 'mode':'auto'})
        m = self.run_job()
        self.assertEqual(m['status'], 'succeeded')
        self.assertTrue(any(e['kind']=='approval_resolved' and e['data'].get('automatic') for e in m['events']))
        self.service.action('approval_settings', {'conversation_id': self.conversation, 'mode':'manual'})
        id = self.service.action('create_mission',self.spec())['mission_id']
        self.wait(id,'awaiting_approval')
        self.engine.approve(self.service.state()['approvals'][0]['id'],False)
        self.assertEqual(self.wait(id)['status'],'failed')

    def test_auto_approval_can_resolve_current_wait(self):
        self.connectors['alpha'].mode = 'approval'
        id = self.service.action('create_mission',self.spec())['mission_id']
        self.wait(id,'awaiting_approval')
        self.service.action('approval_settings', {'conversation_id': self.conversation, 'mode':'auto'})
        self.assertEqual(self.wait(id)['status'],'succeeded')

    def test_approval_accept(self):
        self.connectors["alpha"].mode = "approval"
        id = self.service.action("create_mission", self.spec())["mission_id"]
        self.wait(id, "awaiting_approval")
        self.engine.approve(self.service.state()["approvals"][0]["id"], True)
        self.assertEqual(self.wait(id)["status"], "succeeded")
    def test_validation_failure_retains_response(self):
        m = self.run_job(self.spec(steps=[{"connector": "alpha", "instruction": "Test", "validation": {"type": "contains", "value": "absent"}}]))
        self.assertEqual(m["status"], "failed")
        self.assertIn("résultat", m["steps"][0]["result"])
        self.assertEqual(len(self.service.conversation(self.conversation)["messages"]), 2)
    def test_branch_copies_until_anchor_without_native_state(self):
        self.run_job()
        self.run_job()
        msgs = self.service.conversation(self.conversation)["messages"]
        id = self.service.action("branch", {"conversation_id": self.conversation, "message_id": msgs[1]["id"]})["id"]
        branch = self.service.conversation(id)
        self.assertEqual(len(branch["messages"]), 2)
        self.assertEqual(branch["sessions"], [])
        self.assertEqual(branch["messages"][0]["source_id"], msgs[0]["id"])
        self.assertEqual(branch["messages"][0]["created_at"], msgs[0]["created_at"])
    def test_path_traversal_and_sensitive_files(self):
        for path in ("../outside.txt", ".env", ".git/config", ".codex/auth.json", "credentials.json"):
            with self.assertRaises((ValueError, FileNotFoundError)):
                scoped_path(self.root, path, must_exist=False)
        with self.assertRaises(ValueError):
            self.policy.project(self.root.parent)
    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as other:
            try:
                (self.root / "link").symlink_to(other, target_is_directory=True)
            except OSError:
                self.skipTest("Création de lien non autorisée sur ce Windows")
            with self.assertRaises(ValueError):
                scoped_path(self.root, "link/file.txt", must_exist=False)
    def test_attachment_copy_and_backup_restore(self):
        (self.root / "notes.txt").write_text("Décision durable", encoding="utf-8")
        self.service.action("attach_file", {"conversation_id": self.conversation, "path": "notes.txt"})
        self.run_job()
        backup = self.service.action("backup", {})
        self.service.action("delete_conversation", {"id": self.conversation})
        self.service.action("restore", {"backup": backup, "acknowledged": True})
        conv = self.service.conversation(self.conversation)
        self.assertEqual(len(conv["messages"]), 2)
        self.assertEqual(conv["files"][0]["name"], "notes.txt")
        self.assertIsNone(conv["sessions"][0]["native_id"])
    def test_invalid_restore_is_atomic(self):
        backup = self.service.action("backup", {})
        backup["tables"]["conversations"][0]["project_id"] = "missing"
        with self.assertRaises(Exception):
            self.service.action("restore", {"backup": backup, "acknowledged": True})
        self.assertEqual(self.service.conversation(self.conversation)["project_id"], self.project)
    def test_search_filters_and_archive(self):
        self.run_job()
        self.service.action("archive_conversation", {"id": self.conversation})
        results = self.service.search({"text": "résultat", "connector": "alpha", "project_id": self.project, "status": "succeeded"})
        self.assertEqual(len(results), 1)
        with self.assertRaises(ValueError):
            self.engine.create(self.spec())
    def test_mcp_scope_and_shared_engine(self):
        with self.assertRaises(ValueError):
            call_tool(self.service, "list_projects", {}, [])
        with self.assertRaises(ValueError):
            call_tool(self.service, "create_mission", {"conversation_id": self.conversation, "steps": self.spec()["steps"], "request_key": uid()}, ["other"])
        r = call_tool(self.service, "create_mission", {"conversation_id": self.conversation, "steps": self.spec()["steps"], "request_key": uid()}, [self.project], allow_write=True)
        call_tool(self.service, "launch_mission", r, [self.project], allow_write=True)
        self.assertEqual(self.wait(r["mission_id"])["status"], "succeeded")
    def test_mcp_delegation_blocked_while_agent_runs(self):
        self.connectors["alpha"].mode = "wait"
        id = self.service.action("create_mission", self.spec())["mission_id"]
        self.wait(id, "running")
        with self.assertRaises(ValueError):
            call_tool(self.service, "create_mission", {"conversation_id": self.conversation, "steps": self.spec()["steps"], "request_key": uid()}, [self.project], allow_write=True)
        self.engine.cancel(id)
        self.wait(id)
    def test_http_local_auth_and_origin(self):
        server, token = make_server(self.service, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urllib.request.urlopen(base) as res:
                self.assertIn("SameSite=Strict", res.headers["Set-Cookie"])
            for headers in ({}, {"Authorization": "Bearer " + token, "Origin": "https://evil.example"}, {"Authorization": "Bearer " + token, "Host": "evil.example"}):
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(urllib.request.Request(base + "/api/state", headers=headers))
            with urllib.request.urlopen(urllib.request.Request(base + "/api/state", headers={"Authorization": "Bearer " + token})) as res:
                self.assertEqual(json.load(res)["projects"][0]["id"], self.project)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
