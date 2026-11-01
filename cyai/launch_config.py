"""Resolve the same configuration for direct EXE, shortcut and installed launches."""
import json
import os
from pathlib import Path

def user_home():
    return Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local'/'share'))/'CyAIOrchestrator'

def resolve_config(root, explicit=None):
    if explicit is not None:
        path=Path(explicit).expanduser().resolve()
        if not path.is_file():raise ValueError('Configuration indiquée introuvable : '+str(path))
        return path
    root=Path(root).resolve()
    # Development builds must keep the repository config, even if an earlier
    # direct launch accidentally created an empty config next to the EXE.
    for parent in (root,*root.parents):
        marker=parent/'pyproject.toml'
        if marker.is_file() and 'CyAIOrchestrator' in marker.read_text(encoding='utf-8') and (parent/'config.json').is_file():
            return parent/'config.json'
    pointer=user_home()/'installation.json'
    if pointer.is_file():
        target=Path(json.loads(pointer.read_text(encoding='utf-8'))['config_path'])
        if not target.is_file():raise ValueError('La configuration enregistrée est inaccessible : '+str(target))
        return target
    if (root/'config.json').is_file():return root/'config.json'
    return user_home()/'config.json'
