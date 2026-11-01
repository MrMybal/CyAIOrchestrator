import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from cyai.connectors import Anthropic, Cancelled, Codex, Control, Ollama


class Secrets:
    def get(self, name):
        return "test-not-a-real-secret"


def sse(events):
    return io.BytesIO(b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events))


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.events = []
        self.control = Control(10, lambda data: False, lambda kind, data: self.events.append((kind, data)))
    def tearDown(self):
        self.temp.cleanup()
    def text_events(self, text="Bonjour"):
        return [{"type": "message_start", "message": {"usage": {"input_tokens": 5}}},
                {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
                {"type": "message_delta", "usage": {"output_tokens": 2}, "delta": {"stop_reason": "end_turn"}}, {"type": "message_stop"}]
    def test_anthropic_stream_and_actual_usage(self):
        with patch("urllib.request.urlopen", return_value=sse(self.text_events())):
            result = Anthropic("anthropic", {}, Secrets()).run("Hello", self.root, "test-model", None, self.control)
        self.assertEqual(result, "Bonjour")
        self.assertIn(("usage", {"input_tokens": 5, "output_tokens": 2}), self.events)
        self.assertNotIn("cost", str(self.events))
    def test_anthropic_missing_final_event_is_failure(self):
        with patch("urllib.request.urlopen", return_value=sse(self.text_events()[:-1])):
            with self.assertRaisesRegex(RuntimeError, "interrompu"):
                Anthropic("anthropic", {}, Secrets()).run("Hello", self.root, "test-model", None, self.control)
    def test_anthropic_write_requires_approval(self):
        events = [{"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "t1", "name": "write_file", "input": {}}},
                  {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": json.dumps({"path": "output.txt", "content": "safe"})}},
                  {"type": "message_delta", "delta": {"stop_reason": "tool_use"}}, {"type": "message_stop"}]
        with patch("urllib.request.urlopen", side_effect=[sse(events), sse(self.text_events())]) as mock:
            Anthropic("anthropic", {}, Secrets()).run("Hello", self.root, "test-model", None, self.control)
        self.assertFalse((Path(self.root) / "output.txt").exists())
        second = json.loads(mock.call_args_list[1].args[0].data)
        self.assertTrue(second["messages"][-1]["content"][0]["is_error"])
    def test_ollama_stream_and_cancellation(self):
        response = io.BytesIO(b'{"message":{"content":"Hello"},"done":false}\n{"message":{"content":"!"},"done":true,"eval_count":2}\n')
        with patch("urllib.request.urlopen", return_value=response):
            result = Ollama("ollama", {}, Secrets()).run("Hello", self.root, "local-model", None, self.control)
        self.assertEqual(result, "Hello!")
        self.control.cancelled.set()
        with self.assertRaises(Cancelled):
            self.control.check()
    def test_timeout_is_distinct_from_cancellation(self):
        self.control.deadline = time.monotonic() - 1
        with self.assertRaises(TimeoutError):
            self.control.check()
    def test_ollama_rejects_nonlocal_endpoint(self):
        with self.assertRaises(ValueError):
            Ollama("ollama", {"base_url": "https://example.com"}, Secrets()).base()
    def test_codex_protocol_approval_resume_and_final(self):
        recorder = []
        class RPC:
            def __init__(self, *args):
                self.events = iter([
                    {"id": 42, "method": "item/commandExecution/requestApproval", "params": {"command": "test"}},
                    {"method": "item/agentMessage/delta", "params": {"delta": "OK"}},
                    {"method": "item/completed", "params": {"item": {"type": "agentMessage", "text": "OK"}}},
                    {"method": "turn/completed", "params": {"turn": {"status": "completed"}}}])
            def request(self, method, params):
                recorder.append((method, params))
                return {"thread": {"id": "native-session"}, "turn": {"id": "turn"}}
            def send(self, value):
                recorder.append(value)
            def next(self):
                return next(self.events)
            def close(self):
                pass
        with patch("cyai.connectors.JsonProcess", RPC), patch("cyai.connectors.executable", return_value=["codex"]):
            result = Codex("codex", {}, Secrets()).run("Hello", self.root, "", "native-session", self.control)
        self.assertEqual(result, "OK")
        self.assertTrue(any(isinstance(r, tuple) and r[0] == "thread/resume" for r in recorder))
        self.assertIn({"id": 42, "result": {"decision": "decline"}}, recorder)
        self.assertIn(("session", {"native_id": "native-session"}), self.events)


if __name__ == "__main__":
    unittest.main()
