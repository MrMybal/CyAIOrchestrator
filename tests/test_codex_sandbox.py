import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyai.connectors import Codex, Control, ROOT_READ_REQUIRED


class RPC:
    def __init__(self, refusal, events=()):
        self.refusal, self.calls, self.sent, self.events = refusal, [], [], list(events)

    def request(self, method, params):
        self.calls.append((method, copy.deepcopy(params)))
        if method == 'thread/start':
            if self.refusal and len([c for c in self.calls if c[0] == 'thread/start']) == 1:
                raise RuntimeError(self.refusal)
            return {'thread': {'id': 'thread-1'}}
        if method == 'turn/start':
            return {'turn': {'id': 'turn-1'}}
        return {}

    def send(self, value):
        self.sent.append(value)

    def next(self):
        if self.events:
            return self.events.pop(0)
        return {'method': 'turn/completed', 'params': {'turn': {'id': 'turn-1', 'status': 'completed'}}}

    def close(self):
        pass


class CodexSandboxTests(unittest.TestCase):
    """Codex's elevated Windows sandbox refuses a profile that forbids reading the disk: CyAI keeps the strict profile
    whenever Codex accepts it, and otherwise opens reading while keeping secrets closed and writing in the project."""

    def run_codex(self, refusal, protected=(), access='project', approve=False, requests=(), planning=False):
        rpc, events = RPC(refusal, requests), []
        self.asked = []
        control = Control(20, lambda data: self.asked.append(data) or approve, lambda kind, data: events.append((kind, data)))
        control.protected_roots, control.access, control.planning = list(protected), access, planning
        self.rpc = rpc
        root = tempfile.mkdtemp()
        with patch('cyai.connectors.JsonProcess', return_value=rpc), patch('cyai.connectors.executable', return_value=['codex']):
            codex = Codex('codex', {}, None)
            with patch.object(codex, 'configuration', return_value={'mcp_servers': {}}):
                try:
                    codex.run('Bonjour', root, '', None, control)
                except Exception:
                    pass
        starts = [params for method, params in rpc.calls if method == 'thread/start']
        return starts, events, root

    def test_the_strict_profile_stays_when_codex_accepts_it(self):
        starts, events, _ = self.run_codex(None)
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0]['config']['permissions.cyai-project']['filesystem'][':root'], 'deny')
        self.assertNotIn('sandbox_adjusted', [kind for kind, _ in events])

    def test_reading_opens_but_secrets_stay_closed_when_the_elevated_sandbox_requires_it(self):
        data = tempfile.mkdtemp()
        refusal = 'Fatal error: windows sandbox failed: elevated Windows sandbox ' + ROOT_READ_REQUIRED
        starts, events, root = self.run_codex(refusal, [data])
        self.assertEqual(len(starts), 2, 'une seule nouvelle tentative')
        filesystem = starts[1]['config']['permissions.cyai-project']['filesystem']
        self.assertEqual(filesystem[':root'], 'read')
        self.assertEqual(filesystem[':workspace_roots']['.'], 'write', 'l’écriture reste limitée au projet')
        for secret in (Path.home() / '.ssh', Path.home() / '.codex' / 'auth.json', Path(data)):
            self.assertEqual(filesystem[str(secret)], 'deny', secret)
        self.assertNotIn(str(Path.home() / '.codex' / 'AGENTS.md'), filesystem, 'vos consignes globales restent lisibles')
        adjusted = [data for kind, data in events if kind == 'sandbox_adjusted']
        self.assertEqual(len(adjusted), 1, 'le changement est dit dans le suivi')

    def test_a_free_discussion_inside_the_data_folder_keeps_its_workspace(self):
        data = Path(tempfile.mkdtemp())
        refusal = ROOT_READ_REQUIRED
        with patch('tempfile.mkdtemp', return_value=str(data / 'discussion-workspaces' / 'x')):
            (data / 'discussion-workspaces' / 'x').mkdir(parents=True)
            starts, _, root = self.run_codex(refusal, [str(data)])
        filesystem = starts[1]['config']['permissions.cyai-project']['filesystem']
        self.assertNotIn(str(data), filesystem, 'le dossier de travail de la discussion n’est pas fermé')
        self.assertEqual(filesystem[str(data / 'secrets.dpapi')], 'deny')

    def test_other_errors_are_not_retried(self):
        starts, events, _ = self.run_codex('network failed')
        self.assertEqual(len(starts), 1)


    def answer(self, identifier):
        return next(message['result'] for message in self.rpc.sent if message.get('id') == identifier)

    def filesystem(self, starts, index=0):
        return starts[index]['config']['permissions.cyai-project']

    def test_the_access_chosen_in_cyai_is_given_to_codex_from_the_start(self):
        data = tempfile.mkdtemp()
        starts, events, _ = self.run_codex(None, [data], access='read')
        profile = self.filesystem(starts)
        self.assertEqual((len(starts), profile['filesystem'][':root'], profile['network']), (1, 'read', {'enabled': False}))
        self.assertEqual(profile['filesystem'][str(Path.home() / '.ssh')], 'deny')
        self.assertIn('sandbox_access', [kind for kind, _ in events], 'le niveau d’accès est écrit dans le suivi')
        profile = self.filesystem(self.run_codex(None, [data], access='read_network')[0])
        self.assertEqual((profile['filesystem'][':root'], profile['network']), ('read', {'enabled': True}))
        full = self.run_codex(None, [data], access='full')[0][0]
        self.assertEqual(full['sandbox'], 'danger-full-access', 'l’accès complet est le mode sans bac à sable de Codex')
        self.assertNotIn('permissions.cyai-project', full['config'])
        profile = self.filesystem(self.run_codex(None, [data], access='full', planning=True)[0])
        self.assertEqual(profile['filesystem'][':root'], 'deny', 'un plan d’orchestrateur reste en lecture du projet')
        profile = self.filesystem(self.run_codex(None, [data], access='tout')[0])
        self.assertEqual(profile['filesystem'][':root'], 'deny', 'un niveau inconnu vaut « projet »')

    def test_a_permission_request_is_yours_to_grant(self):
        wanted = {'fileSystem': {'read': ['D:/Autre']}, 'network': {'enabled': True}}
        request = {'id': 9, 'method': 'item/permissions/requestApproval', 'params': {'permissions': wanted, 'reason': 'Lire la doc'}}
        self.run_codex(None, requests=[dict(request)], approve=False)
        self.assertEqual(self.asked[0]['summary'], 'lecture : D:/Autre · accès à Internet')
        self.assertEqual(self.answer(9), {'permissions': {}, 'scope': 'session'}, 'refusé : rien n’est accordé')
        self.run_codex(None, requests=[dict(request)], approve=True)
        self.assertEqual(self.answer(9), {'permissions': wanted, 'scope': 'session'}, 'accordé pour la conversation')


class AccessSettingTests(unittest.TestCase):
    def test_the_access_is_set_per_conversation_or_by_default(self):
        import test_core
        fixture = test_core.CoreTests()
        fixture.setUp()
        try:
            service, seen = fixture.service, []
            original = fixture.connectors['alpha'].run
            fixture.connectors['alpha'].run = lambda prompt, root, model, native, control: seen.append(control.access) or original(prompt, root, model, native, control)
            conversation = fixture.conversation
            with self.assertRaises(ValueError):
                service.action('access_settings', {'conversation_id': conversation, 'level': 'tout'})
            service.action('access_settings', {'level': 'read'})
            self.assertEqual(service.state()['access_default'], 'read')
            fixture.wait(service.action('continue_conversation', {'conversation_id': conversation, 'connector': 'alpha', 'instruction': 'Un'})['mission_id'])
            service.action('access_settings', {'conversation_id': conversation, 'level': 'read_network'})
            fixture.wait(service.action('continue_conversation', {'conversation_id': conversation, 'connector': 'alpha', 'instruction': 'Deux'})['mission_id'])
            self.assertEqual(seen, ['read', 'read_network'])
            with self.assertRaises(ValueError):
                service.action('access_settings', {'level': 'inherit'})
        finally:
            fixture.tearDown()


if __name__ == '__main__':
    unittest.main()
