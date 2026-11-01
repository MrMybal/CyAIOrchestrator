"""SQLite is the source of truth. Every operation is transactional."""
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def uid():
    return uuid.uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS agent_benchmarks(id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES agent_profiles(id) ON DELETE CASCADE,
 report TEXT NOT NULL, imported_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS app_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, level TEXT NOT NULL, operation TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, root TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 title TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0, parent_id TEXT, branch_message_id TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
 conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, role TEXT NOT NULL, connector TEXT,
 provider TEXT, model TEXT, content TEXT NOT NULL, created_at TEXT NOT NULL, source_id TEXT);
CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id,seq);
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 connector TEXT NOT NULL, model TEXT NOT NULL, native_id TEXT, last_seq INTEGER DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 title TEXT NOT NULL, status TEXT NOT NULL, request_key TEXT UNIQUE NOT NULL, spec TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS steps(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
 position INTEGER NOT NULL, name TEXT NOT NULL, connector TEXT NOT NULL, model TEXT NOT NULL, instruction TEXT NOT NULL,
 status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, context TEXT, result TEXT, error TEXT, usage TEXT, UNIQUE(mission_id,position));
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
 step_id TEXT, kind TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memory(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 content TEXT NOT NULL, validated INTEGER NOT NULL DEFAULT 0, source_ids TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 name TEXT NOT NULL, content TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_profiles(id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 role TEXT NOT NULL DEFAULT 'member', skills TEXT NOT NULL DEFAULT '[]', connector TEXT NOT NULL DEFAULT '',
 model TEXT NOT NULL DEFAULT '', prompt TEXT NOT NULL DEFAULT '', settings TEXT NOT NULL DEFAULT '{}',
 revision INTEGER NOT NULL DEFAULT 1, archived INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_profile_revisions(id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES agent_profiles(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL, definition TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, UNIQUE(profile_id,revision));
CREATE TABLE IF NOT EXISTS teams(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS teams_current_project ON teams(project_id);
CREATE TABLE IF NOT EXISTS team_members(id TEXT PRIMARY KEY, team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, profile_id TEXT NOT NULL REFERENCES agent_profiles(id),
 profile_revision INTEGER NOT NULL, definition TEXT NOT NULL, role TEXT NOT NULL, responsibility TEXT NOT NULL DEFAULT '',
 manager_id TEXT, active INTEGER NOT NULL DEFAULT 1, position INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS team_members_team ON team_members(team_id,position);
CREATE TABLE IF NOT EXISTS team_templates(id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 composition TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, objective TEXT NOT NULL,
 assignee_id TEXT REFERENCES team_members(id) ON DELETE SET NULL, author_id TEXT REFERENCES team_members(id) ON DELETE SET NULL,
 parent_id TEXT REFERENCES tasks(id) ON DELETE CASCADE, dependencies TEXT NOT NULL DEFAULT '[]', file_scope TEXT NOT NULL DEFAULT '',
 acceptance_criteria TEXT NOT NULL DEFAULT '', deliverables TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'to_prepare',
 history TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS tasks_team ON tasks(team_id,created_at);
CREATE TABLE IF NOT EXISTS task_reports(id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, author_id TEXT REFERENCES team_members(id) ON DELETE SET NULL,
 result TEXT NOT NULL, modified_files TEXT NOT NULL DEFAULT '', executed_tests TEXT NOT NULL DEFAULT '', limits TEXT NOT NULL DEFAULT '',
 risks TEXT NOT NULL DEFAULT '', requested_decisions TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS task_reports_task ON task_reports(task_id,created_at);
CREATE TABLE IF NOT EXISTS task_consultations(id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, requester_id TEXT REFERENCES team_members(id) ON DELETE SET NULL,
 consultant_id TEXT REFERENCES team_members(id) ON DELETE SET NULL, question TEXT NOT NULL, answer TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'requested', answer_source TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, answered_at TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS task_consultations_task ON task_consultations(task_id,created_at);
CREATE TABLE IF NOT EXISTS task_executions(id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, member_id TEXT REFERENCES team_members(id) ON DELETE SET NULL,
 conversation_id TEXT, mission_id TEXT, status TEXT NOT NULL DEFAULT 'running', report_id TEXT, detail TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, settled_at TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS task_executions_task ON task_executions(task_id,created_at);
CREATE TABLE IF NOT EXISTS agent_memory(id TEXT PRIMARY KEY, scope TEXT NOT NULL,
 project_id TEXT REFERENCES projects(id) ON DELETE CASCADE, member_id TEXT REFERENCES team_members(id) ON DELETE CASCADE,
 profile_id TEXT REFERENCES agent_profiles(id) ON DELETE CASCADE, content TEXT NOT NULL, category TEXT NOT NULL DEFAULT '',
 source_ids TEXT NOT NULL DEFAULT '[]', transferable INTEGER NOT NULL DEFAULT 0, origin TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS agent_memory_member ON agent_memory(member_id,created_at);
CREATE INDEX IF NOT EXISTS agent_memory_profile ON agent_memory(profile_id,created_at);
CREATE TABLE IF NOT EXISTS task_evaluations(id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, member_id TEXT REFERENCES team_members(id) ON DELETE SET NULL,
 author_id TEXT REFERENCES team_members(id) ON DELETE SET NULL, scores TEXT NOT NULL DEFAULT '{}',
 duration_seconds INTEGER NOT NULL DEFAULT 0, usage TEXT NOT NULL DEFAULT '', comment TEXT NOT NULL,
 profile_revision INTEGER NOT NULL DEFAULT 0, connector TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS task_evaluations_task ON task_evaluations(task_id,created_at);
CREATE TABLE IF NOT EXISTS improvement_proposals(id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
 member_id TEXT REFERENCES team_members(id) ON DELETE SET NULL, profile_id TEXT NOT NULL REFERENCES agent_profiles(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, current_value TEXT NOT NULL DEFAULT '', proposed_value TEXT NOT NULL, rationale TEXT NOT NULL,
 source_ids TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'proposed', decision TEXT NOT NULL DEFAULT '',
 revision INTEGER, created_at TEXT NOT NULL, decided_at TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS improvement_proposals_profile ON improvement_proposals(profile_id,created_at);
CREATE TABLE IF NOT EXISTS method_templates(id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 steps TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS method_revisions(id TEXT PRIMARY KEY, method_id TEXT NOT NULL REFERENCES method_templates(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL, body TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'user', note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
 UNIQUE(method_id,revision));
CREATE TABLE IF NOT EXISTS method_assets(id TEXT PRIMARY KEY, method_id TEXT NOT NULL REFERENCES method_templates(id) ON DELETE CASCADE,
 name TEXT NOT NULL, mime TEXT NOT NULL, bytes INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS profile_methods(profile_id TEXT NOT NULL REFERENCES agent_profiles(id) ON DELETE CASCADE,
 method_id TEXT NOT NULL REFERENCES method_templates(id) ON DELETE CASCADE, mode TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
 note_author TEXT NOT NULL DEFAULT '', note_updated_at TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, PRIMARY KEY(profile_id,method_id));
CREATE TABLE IF NOT EXISTS method_tests(id TEXT PRIMARY KEY, method_id TEXT NOT NULL REFERENCES method_templates(id) ON DELETE CASCADE,
 name TEXT NOT NULL, objective TEXT NOT NULL, inputs TEXT NOT NULL DEFAULT '{}', expected TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS method_runs(id TEXT PRIMARY KEY, method_id TEXT NOT NULL REFERENCES method_templates(id) ON DELETE CASCADE,
 test_id TEXT REFERENCES method_tests(id) ON DELETE CASCADE, kind TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, step_key TEXT NOT NULL DEFAULT '',
 connector TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '', mission_id TEXT, conversation_id TEXT, parent_id TEXT, status TEXT NOT NULL,
 score INTEGER, rating_by TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', data TEXT NOT NULL DEFAULT '{}', loop_id TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS method_runs_method ON method_runs(method_id,kind,created_at);
CREATE TABLE IF NOT EXISTS method_loops(id TEXT PRIMARY KEY, method_id TEXT NOT NULL REFERENCES method_templates(id) ON DELETE CASCADE,
 test_id TEXT NOT NULL REFERENCES method_tests(id) ON DELETE CASCADE, status TEXT NOT NULL, config TEXT NOT NULL, state TEXT NOT NULL DEFAULT '{}',
 reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS method_chains(mission_id TEXT PRIMARY KEY, method_id TEXT NOT NULL REFERENCES method_templates(id) ON DELETE CASCADE,
 harvested INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS method_proposals(id TEXT PRIMARY KEY, method_id TEXT NOT NULL REFERENCES method_templates(id) ON DELETE CASCADE,
 mission_id TEXT NOT NULL, step_id TEXT NOT NULL, step_key TEXT NOT NULL, step_name TEXT NOT NULL, connector TEXT NOT NULL, model TEXT NOT NULL DEFAULT '',
 content TEXT NOT NULL, excerpt TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'new', decision TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(step_id));
CREATE TABLE IF NOT EXISTS member_assessments(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 member_id TEXT NOT NULL REFERENCES team_members(id) ON DELETE CASCADE, author_id TEXT, verdict TEXT NOT NULL, strengths TEXT NOT NULL DEFAULT '',
 weaknesses TEXT NOT NULL DEFAULT '', recommendation TEXT NOT NULL DEFAULT '', source_ids TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS project_spaces(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 type TEXT NOT NULL, name TEXT NOT NULL, position INTEGER NOT NULL DEFAULT 0, data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS skill_attestations(id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES agent_profiles(id) ON DELETE CASCADE,
 skill TEXT NOT NULL, source_ids TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, UNIQUE(profile_id,skill));
PRAGMA user_version=1;
"""


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.listeners = []  # Called after each recorded event (the voice reads answers as they are written).
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        if 'mode' not in [r[1] for r in self.db.execute('PRAGMA table_info(conversations)')]:
            self.db.execute("ALTER TABLE conversations ADD COLUMN mode TEXT NOT NULL DEFAULT 'chat'")
            self.db.commit()
        for column in ('agent_id', 'agent_model'):
            if column not in [r[1] for r in self.db.execute('PRAGMA table_info(conversations)')]:
                self.db.execute(f'ALTER TABLE conversations ADD COLUMN {column} TEXT')
                self.db.commit()
        additions = {
            'projects': {'archived': 'INTEGER NOT NULL DEFAULT 0', 'favorite': 'INTEGER NOT NULL DEFAULT 0', 'position': 'INTEGER NOT NULL DEFAULT 0', 'color': "TEXT NOT NULL DEFAULT '#b6a1f4'", 'icon': "TEXT NOT NULL DEFAULT ''", 'category': "TEXT NOT NULL DEFAULT ''"},
            'conversations': {'favorite': 'INTEGER NOT NULL DEFAULT 0', 'position': 'INTEGER NOT NULL DEFAULT 0', 'workdirs': "TEXT NOT NULL DEFAULT '[]'"}}
        additions['projects']['free_chat'] = 'INTEGER NOT NULL DEFAULT 0'
        additions['projects']['agent_settings'] = "TEXT NOT NULL DEFAULT '{}'"
        additions['conversations'].update({'agent_settings': "TEXT NOT NULL DEFAULT '{}'", 'summary': "TEXT NOT NULL DEFAULT ''", 'summary_seq': 'INTEGER NOT NULL DEFAULT 0'})
        additions['memory'] = {'category': "TEXT NOT NULL DEFAULT 'Général'", 'automatic': 'INTEGER NOT NULL DEFAULT 0'}
        # Team conversations belong to one assignment, and may be about one card.
        additions['conversations'].update({'member_id': 'TEXT', 'task_id': 'TEXT'})
        # A report typed by the user is not a report produced by an agent.
        additions['task_reports'] = {'source': "TEXT NOT NULL DEFAULT 'user'"}
        # An agent is editable where you look at it: the revision stays frozen, local edits live beside it.
        additions['agent_profiles'] = {'icon': "TEXT NOT NULL DEFAULT ''", 'helpers_json': "TEXT NOT NULL DEFAULT '[]'", 'tools_json': "TEXT NOT NULL DEFAULT '[]'",
                                       # Where the profile is filed in the library: organisation only, never part of a revision.
                                       'category': "TEXT NOT NULL DEFAULT ''"}
        additions['team_members'] = {'overrides': "TEXT NOT NULL DEFAULT '{}'"}
        # The delegation automaton of a team: off, budget, parallelism, reviews already requested.
        additions['teams'] = {'autopilot': "TEXT NOT NULL DEFAULT '{}'",
                              # Cursors of the work set for the project by the chief (or the user): autonomy, rigour…
                              'cursors': "TEXT NOT NULL DEFAULT '{}'"}
        # …and for one card, by whoever frames it. The most specific wins when the task is launched.
        additions['tasks'] = {'cursors': "TEXT NOT NULL DEFAULT '{}'"}
        # Methods as graphs usable by any AI: a base prompt, what the machine needs, a place in the library.
        additions['method_templates'] = {'preprompt': "TEXT NOT NULL DEFAULT ''", 'requirements': "TEXT NOT NULL DEFAULT '[]'",
                                         'category': "TEXT NOT NULL DEFAULT ''",
                                         # Methods as functions: a user guide for the AI that applies them, named inputs
                                         # (objective, contexts, files) and outputs, where the I/O nodes sit, a revision.
                                         'usage': "TEXT NOT NULL DEFAULT ''", 'inputs': "TEXT NOT NULL DEFAULT '[]'",
                                         'outputs': "TEXT NOT NULL DEFAULT '[]'", 'layout': "TEXT NOT NULL DEFAULT '{}'",
                                         'revision': 'INTEGER NOT NULL DEFAULT 0',
                                         # The conversation where you write the method with an AI (in a free workspace).
                                         'workshop': "TEXT NOT NULL DEFAULT ''",
                                         # Options of the method itself (invite the agents to propose improvements…).
                                         'options': "TEXT NOT NULL DEFAULT '{}'"}
        # A profile can also be summoned directly, outside any team: a specialist you call on.
        additions['conversations'].update({'profile_id': 'TEXT', 'profile_revision': 'INTEGER'})
        # What a conversation is for, when it is not an ordinary one: 'assistant' is the project's setup assistant.
        additions['conversations'].update({'purpose': "TEXT NOT NULL DEFAULT ''"})
        # How a message was written: 'voice' when it was dictated, '' otherwise.
        additions['messages'] = {'input': "TEXT NOT NULL DEFAULT ''"}
        for table, fields in additions.items():
            existing = {r[1] for r in self.db.execute(f'PRAGMA table_info({table})')}
            for column, declaration in fields.items():
                if column not in existing:
                    self.db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {declaration}')
        self.db.commit()
        schema = self.db.execute("SELECT sql FROM sqlite_master WHERE name='sessions'").fetchone()[0]
        if "UNIQUE(conversation_id,connector,model)" in schema:
            self.db.executescript("""
                ALTER TABLE sessions RENAME TO sessions_legacy;
                CREATE TABLE sessions(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    connector TEXT NOT NULL, model TEXT NOT NULL, native_id TEXT, last_seq INTEGER DEFAULT 0, created_at TEXT NOT NULL);
                INSERT INTO sessions SELECT * FROM sessions_legacy;
                DROP TABLE sessions_legacy;
            """)

        if 'purpose' not in {r[1] for r in self.db.execute('PRAGMA table_info(sessions)')}:
            self.db.execute("ALTER TABLE sessions ADD COLUMN purpose TEXT NOT NULL DEFAULT 'execution'")

    @contextmanager
    def transaction(self):
        with self.lock:
            with self.db:
                yield self.db

    def rows(self, sql, params=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, params)]

    def one(self, sql, params=()):
        rows = self.rows(sql, params)
        if not rows:
            raise ValueError("Élément introuvable.")
        return rows[0]

    def execute(self, sql, params=()):
        with self.transaction() as db:
            return db.execute(sql, params).rowcount

    def message(self, conversation_id, role, content, connector=None, model=None, source_id=None, db=None, created_at=None, input=''):
        id = uid()
        args = (id, conversation_id, role, connector, connector, model, content, created_at or now(), source_id, input)
        sql = "INSERT INTO messages(id,conversation_id,role,connector,provider,model,content,created_at,source_id,input) VALUES(?,?,?,?,?,?,?,?,?,?)"
        if db is not None:
            db.execute(sql, args)
        else:
            self.execute(sql, args)
        return id

    def event(self, mission_id, step_id, kind, data):
        self.execute("INSERT INTO events(mission_id,step_id,kind,data,created_at) VALUES(?,?,?,?,?)",
                     (mission_id, step_id, kind, json.dumps(data, ensure_ascii=False), now()))
        for listener in self.listeners:
            try:
                listener(mission_id, step_id, kind, data)
            except Exception:
                pass  # An observer (the voice) must never break the recording of an event.

    def log(self, level, operation, detail):
        with self.transaction() as db:
            db.execute('INSERT INTO app_logs(created_at,level,operation,detail) VALUES(?,?,?,?)', (now(),level,str(operation)[:200],str(detail)[:8000]))
            db.execute('DELETE FROM app_logs WHERE id <= (SELECT COALESCE(MAX(id),0)-5000 FROM app_logs)')

    def recover(self):
        with self.transaction() as db:
            missions=db.execute("SELECT id,status FROM missions WHERE status IN ('running','awaiting_approval','queued','pausing')").fetchall()
            for mission in missions:
                steps=[dict(r) for r in db.execute('SELECT id,position,name,status,attempts FROM steps WHERE mission_id=? ORDER BY position',(mission['id'],))]
                last=db.execute('SELECT seq,kind,created_at FROM events WHERE mission_id=? ORDER BY seq DESC LIMIT 1',(mission['id'],)).fetchone()
                report={'status':'interrupted','error':'Interruption du service détectée au redémarrage. La cause (crash, arrêt forcé ou extinction) reste à déterminer. Les agents externes peuvent encore travailler : vérifier leurs sessions avant de reprendre.', 'previous_status':mission['status'],'steps':steps,'last_event':dict(last) if last else None}
                db.execute('INSERT INTO events(mission_id,step_id,kind,data,created_at) VALUES(?,NULL,?,?,?)',(mission['id'],'recovery_required',json.dumps(report,ensure_ascii=False),now()))
            db.execute("UPDATE steps SET status='interrupted',error='Arrêt du service : vérifier les effets avant de réessayer.' WHERE status IN ('running','awaiting_approval')")
            db.execute("UPDATE missions SET status='interrupted',updated_at=? WHERE status IN ('running','awaiting_approval','queued','pausing')", (now(),))

    def backup(self, path):
        with self.lock, sqlite3.connect(path) as dest:
            self.db.backup(dest)

    def close(self):
        with self.lock:
            self.db.close()
