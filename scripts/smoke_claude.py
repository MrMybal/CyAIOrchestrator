"""Opt-in real Claude Code SDK smoke test; no file tools requested."""
import json
import site
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))
site.addsitedir(str(repo / ".data" / "deps"))
from cyai.connectors import ClaudeCode, Control
from cyai.security import SecretStore

root = repo / "test-results" / "live-project"
root.mkdir(parents=True, exist_ok=True)
events = []
connector = ClaudeCode("claude-code", {}, SecretStore(root))
def emit(kind, data):
    events.append((kind, data))
    if kind == "session":
        print("Session Claude reçue.", flush=True)
first = connector.run("Test technique de connexion : sans lire de fichiers ni utiliser d’outils, mémorise CYAI-CLAUDE-613 et réponds seulement OK.", str(root), "", None, Control(90, lambda data: False, emit))
native_id = next(data["native_id"] for kind, data in events if kind == "session")
second = connector.run("Sans outils, rappelle uniquement le mot technique du tour précédent.", str(root), "", native_id, Control(90, lambda data: False, emit))
assert "CYAI-CLAUDE-613" in second, second
report = {"first": first, "second": second, "resume_verified": True, "event_types": sorted({kind for kind, _ in events})}
(root.parent / "claude-smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False), flush=True)
