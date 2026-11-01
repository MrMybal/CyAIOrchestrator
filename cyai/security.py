"""Local path policy and Windows user-bound secret encryption."""
import base64
import ctypes
import json
import os
import re
from pathlib import Path


def scoped_path(root, value=".", *, must_exist=True):
    root = Path(root).resolve(strict=True)
    path = (root / value).resolve(strict=must_exist)
    if not path.is_relative_to(root):
        raise ValueError("Chemin hors du dossier autorisé.")
    if any(":" in part for part in path.relative_to(root).parts):
        raise ValueError("Flux de fichiers alternatifs interdits.")
    # Never attach application/agent credentials or control directories.
    if any(p.lower() in {".git", ".codex", ".claude", ".data", ".ssh", ".aws"} for p in path.relative_to(root).parts):
        raise ValueError("Dossier protégé.")
    if path.name.lower().startswith(".env") or path.name.lower() in {"auth.json", "credentials.json", "secrets.json", "secrets.dpapi", "cyai.sqlite3", "cyai.sqlite3-wal", "cyai.sqlite3-shm"}:
        raise ValueError("Fichier de secrets exclu.")
    return path


def scoped_workspace(root, value='.', additional=(), *, must_exist=True):
    candidate = (Path(root) / value).resolve(strict=must_exist)
    for directory in (root, *additional):
        base = Path(directory).resolve(strict=True)
        if candidate.is_relative_to(base):
            return scoped_path(base, str(candidate), must_exist=must_exist)
    raise ValueError('Chemin hors des dossiers de cette conversation.')


class PathPolicy:
    def __init__(self, roots, protected_roots=()):
        self.roots = [Path(p).resolve(strict=True) for p in roots]
        self.protected_roots = [Path(p).resolve() for p in protected_roots]

    def project(self, value):
        p = Path(value).resolve(strict=True)
        if any(p.is_relative_to(r) and not p.is_relative_to(r / 'discussion-workspaces') for r in self.protected_roots):
            raise ValueError("Le dossier de données CyAI ne peut pas servir de projet d’agent.")
        if not p.is_dir() or not any(p.is_relative_to(r) for r in self.roots):
            raise ValueError("Projet hors des racines autorisées dans config.json.")
        return str(p)


class SecretStore:
    def __init__(self, directory):
        self.path = Path(directory) / "secrets.dpapi"

    def _crypt(self, data, decrypt=False):
        if os.name != "nt":
            raise ValueError("Coffre DPAPI réservé à Windows ; utilisez ANTHROPIC_API_KEY sur ce système.")
        class Blob(ctypes.Structure):
            _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_byte))]
        buf = ctypes.create_string_buffer(data)
        src = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
        dst = Blob()
        fn = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
        if not fn(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(dst)):
            raise ValueError("Le coffre Windows n’est pas accessible pour cet utilisateur.")
        try:
            return ctypes.string_at(dst.data, dst.size)
        finally:
            ctypes.windll.kernel32.LocalFree(dst.data)

    def get(self, name):
        if name == "local_token" and os.environ.get("CYAI_LOCAL_TOKEN"):
            return os.environ["CYAI_LOCAL_TOKEN"]
        if name == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
            return os.environ["ANTHROPIC_API_KEY"]
        if not self.path.exists():
            return None
        return json.loads(self._crypt(self.path.read_bytes(), True)).get(name)

    def set(self, name, value):
        values = json.loads(self._crypt(self.path.read_bytes(), True)) if self.path.exists() else {}
        if value:
            values[name] = value
        else:
            values.pop(name, None)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(self._crypt(json.dumps(values).encode()))
        tmp.replace(self.path)

    def redact(self, value):
        text = json.dumps(value, ensure_ascii=False)
        for name in ("anthropic", "local_token", "huggingface"):
            try:
                secret = self.get(name)
                if secret:
                    text = text.replace(secret, "[SECRET MASQUÉ]")
            except ValueError:
                pass
        text = re.sub(r"sk-(?:ant-)?[A-Za-z0-9_-]{16,}", "[SECRET MASQUÉ]", text)
        return json.loads(text)
