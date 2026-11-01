"""Application data relocation on restart, preserving the original."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
from contextlib import closing


def default_data_dir():
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share')) / 'CyAIOrchestrator' / 'data'


def validate_destination(source, destination):
    raw = Path(destination).expanduser()
    if not raw.is_absolute():
        raise ValueError('Choisissez un chemin absolu.')
    target, source = raw.resolve(), Path(source).resolve()
    if target == source or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError('Choisissez un dossier distinct, ni parent ni enfant du stockage actuel.')
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError('La destination doit être un dossier vide pour éviter tout écrasement.')
    return target


def apply_pending(config, config_path):
    if not config.get('pending_data_dir'):
        return
    from .__main__ import InstanceLock
    source = (Path(config_path).parent / config.get('data_dir', str(default_data_dir()))).resolve()
    target = validate_destination(source, config['pending_data_dir'])
    for entry in source.rglob('*'):
        if entry.is_symlink() or (hasattr(entry, 'is_junction') and entry.is_junction()):
            raise ValueError('Un lien dans le stockage empêche la migration automatique.')
    lock = InstanceLock(source / 'service.lock')
    try:
        target.mkdir(parents=True, exist_ok=True)
        for entry in source.iterdir():
            if entry.name in {'service.lock', 'window-state', 'cyai.sqlite3', 'cyai.sqlite3-wal', 'cyai.sqlite3-shm'}:
                continue
            if entry.is_symlink():
                raise ValueError('Un lien symbolique empêche la copie sûre du stockage.')
            if entry.is_dir():
                shutil.copytree(entry, target / entry.name)
            else:
                shutil.copy2(entry, target / entry.name)
        with closing(sqlite3.connect(source / 'cyai.sqlite3')) as src, closing(sqlite3.connect(target / 'cyai.sqlite3')) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('La base copiée ne passe pas le contrôle d’intégrité.')
        updated = {**config, 'data_dir': str(target)}
        updated = json.loads(json.dumps(updated))
        local = updated.get('connectors', {}).get('local', {})
        def relocated(value):
            path = Path(value).resolve()
            return str(target / path.relative_to(source)) if path.is_relative_to(source) else value
        for key in ('runtime', 'models_dir'):
            if local.get(key): local[key] = relocated(local[key])
        for model in local.get('models', []):
            model['path'] = relocated(model['path'])
        updated['allowed_roots']=[relocated(r) for r in updated.get('allowed_roots',[])]
        with closing(sqlite3.connect(target/'cyai.sqlite3')) as db:
            if 'free_chat' in [r[1] for r in db.execute('PRAGMA table_info(projects)')]:
                for id,root in db.execute('SELECT id,root FROM projects WHERE free_chat=1').fetchall():
                    db.execute('UPDATE projects SET root=? WHERE id=?',(relocated(root),id))
                    db.execute('UPDATE sessions SET native_id=NULL,last_seq=0 WHERE conversation_id IN (SELECT id FROM conversations WHERE project_id=?)',(id,))
                db.commit()
        updated.pop('pending_data_dir', None)
        temporary = Path(str(config_path) + '.storage-tmp')
        temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(config_path)
        config.clear()
        config.update(updated)
    finally:
        lock.close()
