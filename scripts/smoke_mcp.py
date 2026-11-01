"""Read-only end-to-end MCP stdio validation against the running local service."""
import json
import subprocess
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))
from cyai.connectors import request_json
from cyai.security import SecretStore

config = json.loads((repo / "config.json").read_text(encoding="utf-8-sig"))
token = SecretStore(repo / config.get("data_dir", ".data")).get("local_token")
state = request_json(f"http://127.0.0.1:{config.get('port',8766)}/api/state", headers={"Authorization": "Bearer " + token})
project = state["projects"][-1]["id"]
requests = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "CyAI-validation", "version": "1"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_projects", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "search_history", "arguments": {"text": "CYAI"}}},
]
result = subprocess.run([sys.executable, str(repo / "scripts" / "mcp_bridge.py"), "--project", project], input="\n".join(json.dumps(r) for r in requests)+"\n", capture_output=True, text=True, encoding="utf-8", timeout=20)
if result.returncode:
    raise RuntimeError(result.stderr)
responses = [json.loads(line) for line in result.stdout.splitlines()]
assert len(responses) == 4
assert responses[0]["result"]["protocolVersion"] == "2025-06-18"
assert len(responses[1]["result"]["tools"]) == 8
assert all(not r["result"].get("isError") for r in responses)
projects = json.loads(responses[2]["result"]["content"][0]["text"])["projects"]
assert [p["id"] for p in projects] == [project]
report = {"initialize": "passed", "tools_list": 8, "scoped_projects": "passed", "history_search": "passed", "stdout_json_only": True}
(repo / "test-results" / "mcp-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
