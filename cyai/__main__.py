import argparse
import json
import os
from pathlib import Path
import sys
import webbrowser

from .connectors import registry
from .engine import Engine
from .security import PathPolicy, SecretStore
from .server import make_server
from .service import Service
from .store import Store


class InstanceLock:
    """OS lock released on crash; prevents a second scheduler on the same database."""
    def __init__(self, path):
        self.file = open(path, "a+b")
        self.file.seek(0)
        self.file.write(b"0")
        self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise ValueError("Un service CyAI utilise déjà ce dossier de données.")

    def close(self):
        self.file.close()


def main():
    parser = argparse.ArgumentParser(description="CyAI Orchestrator · service local")
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "mcp"])
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--data-dir")
    parser.add_argument("--port", type=int)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--project", action="append", default=[])
    parser.add_argument("--allow-write", action="store_true", help="Autoriser les modifications MCP dans les projets explicitement sélectionnés.")
    parser.add_argument("--allow-global", action="store_true", help="Autoriser en plus les écritures de la bibliothèque globale de profils et de modèles d’équipe.")
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.exists() else {
        "port": 8766, "allowed_roots": [str(Path.cwd())], "context_chars": 48000, "connectors": {}}
    from .storage import apply_pending, default_data_dir
    if args.command == "serve" and not args.data_dir:
        apply_pending(config, config_path)
    data_dir = Path(args.data_dir or config_path.parent / config.get("data_dir", str(default_data_dir()))).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    # Optional project-local SDK installation, also usable without activating a venv.
    if (data_dir / "deps").exists():
        import site
        site.addsitedir(str(data_dir / "deps"))
    port = args.port if args.port is not None else int(config.get("port", 8766))
    if args.command == "mcp":
        from .mcp import serve_stdio
        serve_stdio(data_dir, f"http://127.0.0.1:{port}", args.project, args.allow_write, args.allow_global)
        return
    lock = InstanceLock(data_dir / "service.lock")
    secrets = SecretStore(data_dir)
    store = Store(data_dir / "cyai.sqlite3")
    engine = Engine(store, registry(config.get("connectors", {}), secrets), PathPolicy(config["allowed_roots"], [data_dir]), secrets, config.get("context_chars", 48000))
    service = Service(store, engine, config, config_path)
    from .agent_evaluation import ensure_installed
    ensure_installed(service)
    server, token = make_server(service, port)
    if os.name == "nt":
        secrets.set("local_token", token)
    else:
        # Linux users can supply a keychain/env token; no plaintext fallback for secrets.
        os.environ["CYAI_LOCAL_TOKEN"] = token
    print(f"CyAI Orchestrator : http://127.0.0.1:{server.server_port}", flush=True)
    print(f"Données : {data_dir}", flush=True)
    if not args.no_browser:
        webbrowser.open(f"http://127.0.0.1:{server.server_port}")
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        engine.shutdown()
        if not engine.worker.is_alive():
            store.close()
        lock.close()


if __name__ == "__main__":
    main()
