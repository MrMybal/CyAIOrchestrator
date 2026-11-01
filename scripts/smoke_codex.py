"""Opt-in real-provider test: two short requests, no file/tool work requested."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cyai.connectors import Codex, Control
from cyai.security import SecretStore

root = Path(__file__).resolve().parents[1] / "test-results" / "live-project"
root.mkdir(parents=True, exist_ok=True)
connector = Codex("codex", {}, SecretStore(root))
events = []
def emit(kind, data):
    events.append((kind, data))
    if kind == "session":
        print("Session native reçue.", flush=True)
def approve(data):
    print("Approbation inattendue : refus du test.", flush=True)
    return False
first = connector.run("Test technique d’intégration. Ne lis aucun fichier et n’utilise aucun outil. Mémorise le mot CYAI-REPRISE-742 puis réponds uniquement OK.", str(root), "", None, Control(90, approve, emit))
native_id = next(data["native_id"] for kind, data in events if kind == "session")
second = connector.run("Sans outil ni lecture de fichiers, quel mot de test ai-je donné au tour précédent ? Réponds seulement ce mot.", str(root), "", native_id, Control(90, approve, emit))
assert "CYAI-REPRISE-742" in second, second
report = {"first": first, "second": second, "resume_verified": True, "event_types": sorted({kind for kind, _ in events})}
(root.parent / "codex-smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False), flush=True)
