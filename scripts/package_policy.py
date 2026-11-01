"""Rules shared by the desktop build and its package validation."""
from pathlib import PurePosixPath

MODEL_SUFFIXES = {'.gguf', '.safetensors', '.onnx', '.onnx_data', '.pt', '.pth', '.ckpt', '.fermion'}
LOCAL_DIRS = {'.git', '.data', '.env', '.venv', '.desktop-venv', 'node_modules', 'test-results', 'experiments'}


def payload_problem(name):
    path = PurePosixPath(name.replace(chr(92), '/'))
    lower = path.as_posix().lower()
    if path.is_absolute() or '..' in path.parts or ':' in lower:
        return 'Chemin de paquet invalide'
    if any(part.lower() in LOCAL_DIRS for part in path.parts):
        return 'Données locales dans le paquet'
    if path.name.lower() in {'config.json', '.env', 'secrets.dpapi'} or path.suffix.lower() in {'.sqlite3', '.db', '.dpapi'}:
        return 'Configuration ou base locale dans le paquet'
    if path.suffix.lower() in MODEL_SUFFIXES:
        return 'Modèle à télécharger séparément'
    if 'claude_agent_sdk/_bundled/' in lower or path.name.lower().startswith('ffmpeg-core.wasm') and not path.name.endswith('.json'):
        return 'Composant optionnel à télécharger séparément'
    if any(part.lower() in {'torch', 'tensorflow', 'transformers', 'onnxruntime', 'nvidia'} for part in path.parts):
        return 'Environnement ML à installer séparément'
    return None


def validate_payload(names):
    failures = [(name, payload_problem(name)) for name in names if payload_problem(name)]
    if failures:
        raise ValueError('Paquet refusé : ' + '; '.join(reason + ' : ' + name for name, reason in failures[:20]))
