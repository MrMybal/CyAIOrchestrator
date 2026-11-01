"""Official Piper manifest, bundled for offline use and explicitly refreshable."""
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

REPO = 'https://huggingface.co/rhasspy/piper-voices'
BUNDLED = Path(__file__).with_suffix('.json')


def parse(document):
    revision = document['revision']
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Révision Piper invalide.')
    items = []
    for key, voice in document['voices'].items():
        if not re.fullmatch(r'[\w-]+', key):
            raise ValueError('Identifiant Piper invalide.')
        files = voice['files']
        model = next(p for p in files if p.endswith('.onnx'))
        config = model + '.json'
        for path in (model, config):
            if path.startswith('/') or '..' in PurePosixPath(path).parts or '\\' in path:
                raise ValueError('Chemin Piper invalide.')
            if not re.fullmatch(r'[a-f0-9]{32}', files[path]['md5_digest']):
                raise ValueError('Empreinte Piper absente.')
        language = voice['language']['code']
        count = int(voice['num_speakers'])
        if count < 1: raise ValueError('Nombre de locuteurs invalide.')
        speakers = {str(name): int(number) for name, number in voice.get('speaker_id_map', {}).items()}
        if any(n < 0 or n >= count for n in speakers.values()):
            raise ValueError('Locuteur Piper invalide.')
        for number in range(count):
            if number not in speakers.values(): speakers['Voix ' + str(number)] = number
        label = voice['name'].replace('_', ' ').title() + ' · ' + voice['language']['name_native'] + ' · ' + voice['quality']
        if count > 1: label += ' · ' + str(count) + ' voix'
        items.append({'id': key, 'kind': 'tts_voice', 'name': label, 'language': language,
                      'quality': voice['quality'], 'num_speakers': count, 'speakers': speakers,
                      'file': model, 'bytes': files[model]['size_bytes'], 'sha256': None,
                      'md5': files[model]['md5_digest'], 'config_md5': files[config]['md5_digest'],
                      'revision': revision, 'source': REPO + '/blob/' + revision + '/' + str(PurePosixPath(model).parent) + '/MODEL_CARD',
                      'license': 'Voir la fiche de cette voix', 'note': 'Piper sur processeur · aucun modèle chargé en VRAM.'})
    if not items: raise ValueError('Catalogue Piper vide.')
    return sorted(items, key=lambda i: (not i['language'].startswith('fr'), i['language'], i['id']))


def load(cache=None):
    if cache and cache.is_file():
        try: return parse(json.loads(cache.read_text(encoding='utf8')))
        except (ValueError, KeyError, TypeError, StopIteration): pass
    return parse(json.loads(BUNDLED.read_text(encoding='utf8')))


def refresh(cache):
    from .connectors import request_json
    revision = request_json('https://huggingface.co/api/models/rhasspy/piper-voices')['sha']
    if not re.fullmatch(r'[a-f0-9]{40}', revision): raise ValueError('Révision Piper invalide.')
    document = {'revision': revision, 'voices': request_json(REPO + '/resolve/' + revision + '/voices.json')}
    items = parse(document)
    cache.parent.mkdir(parents=True, exist_ok=True)
    import uuid
    temporary = cache.with_name(cache.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(document, ensure_ascii=False), encoding='utf8')
        temporary.replace(cache)
    finally:
        temporary.unlink(missing_ok=True)
    return items


def verify_md5(path, expected):
    digest = hashlib.md5()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError('Le fichier Piper ne correspond pas à l’empreinte officielle : ' + Path(path).name)
