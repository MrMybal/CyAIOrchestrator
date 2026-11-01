"""Optional native tools and video codecs, installed only after a user request."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import urllib.request

from .local_models import download

FFMPEG_VERSION = '0.12.10'
FFMPEG_BYTES = 32232419
FFMPEG_SHA256 = '9f57947a5bd530d8f00c5b3f2cb2a3492faa7e5d823315342d6a8656d0a6b7b7'
FFMPEG_URL = 'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.10/dist/esm/ffmpeg-core.wasm'
CLAUDE_BASE = 'https://downloads.claude.ai/claude-code-releases'
CHUNK_BYTES = 8 * 1024 * 1024


def read_text(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'CyAI-Orchestrator'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(1024 * 1024).decode('utf-8').strip()


class OptionalComponents:
    def __init__(self, service):
        self.service = service
        self.verified_ffmpeg = None

    def folder(self):
        return self.service.store.path.parent / 'runtimes' / 'optional'

    def ffmpeg_path(self):
        return self.folder() / 'ffmpeg' / FFMPEG_VERSION / 'ffmpeg-core.wasm'

    def ffmpeg_ready(self):
        path = self.ffmpeg_path()
        try:
            stat = path.stat()
            identity = (stat.st_size, stat.st_mtime_ns)
            if self.verified_ffmpeg == identity: return True
            if stat.st_size != FFMPEG_BYTES: return False
            with path.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != FFMPEG_SHA256: return False
            self.verified_ffmpeg = identity
            return True
        except OSError:
            return False

    def state(self):
        cli = ''
        connector = self.service.engine.connectors.get('claude-code')
        if connector:
            try: cli = connector.auth_cli()
            except (ValueError, ImportError, OSError): pass
        return [
            {'id': 'ffmpeg', 'name': 'FFmpeg · vidéo CyAnnota', 'bytes': FFMPEG_BYTES,
             'installed': self.ffmpeg_ready(),
             'description': 'Nécessaire pour extraire et encoder la vidéo dans CyAnnota. Téléchargé séparément, puis utilisable hors ligne.'},
            {'id': 'claude-code', 'name': 'CLI Claude Code', 'bytes': None, 'installed': bool(cli),
             'description': 'CLI natif officiel, réutilisé si déjà installé. Taille selon la version. La connexion au compte reste une étape séparée.'}]

    def install(self, identifier):
        if identifier not in {'ffmpeg', 'claude-code'}:
            raise ValueError('Composant inconnu.')
        manager = getattr(self.service, 'local_models', None)
        if manager is None:
            raise ValueError('Le gestionnaire de téléchargements est indisponible.')
        return manager.job('Composant · ' + identifier,
                           self.install_ffmpeg if identifier == 'ffmpeg' else self.install_claude)

    def install_ffmpeg(self, progress):
        path = self.ffmpeg_path()
        if path.is_file():
            with path.open('rb') as stream: valid = hashlib.file_digest(stream, 'sha256').hexdigest() == FFMPEG_SHA256
            if valid:
                progress(FFMPEG_BYTES, FFMPEG_BYTES, 'FFmpeg déjà installé')
                return
        staged = path.with_name('ffmpeg-download.wasm')
        staged.unlink(missing_ok=True)
        try:
            download(FFMPEG_URL, staged, progress, FFMPEG_SHA256)
            if staged.stat().st_size != FFMPEG_BYTES:
                raise ValueError('Taille FFmpeg inattendue.')
            staged.replace(path)
            self.verified_ffmpeg = None
        finally:
            staged.unlink(missing_ok=True)

    def ffmpeg_asset(self, name):
        # Reads never initiate a download. The renderer uses four chunks of the same verified WASM.
        if name not in {'ffmpeg-core.wasm', *(f'ffmpeg-core.wasm.part{i}' for i in range(4))}:
            raise ValueError('Ressource vidéo inconnue.')
        path = self.ffmpeg_path()
        if not path.is_file():
            raise ValueError('Installez FFmpeg dans Paramètres > Téléchargements pour utiliser la vidéo CyAnnota.')
        if not self.ffmpeg_ready():
            raise ValueError('FFmpeg modifié ou incomplet. Réinstallez-le depuis Téléchargements.')
        with path.open('rb') as stream:
            if name.endswith('.wasm'): return stream.read()
            stream.seek(int(name[-1]) * CHUNK_BYTES)
            return stream.read(CHUNK_BYTES)

    def install_claude(self, progress):
        if platform.system() != 'Windows':
            raise ValueError('Ce téléchargement du CLI natif concerne Windows.')
        version = read_text(CLAUDE_BASE + '/latest')
        if not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?', version):
            raise ValueError('Version Claude invalide.')
        architecture = 'win32-arm64' if platform.machine().lower() in {'arm64', 'aarch64'} else 'win32-x64'
        manifest = json.loads(read_text(CLAUDE_BASE + '/' + version + '/manifest.json'))
        digest = manifest.get('platforms', {}).get(architecture, {}).get('checksum', '')
        if not re.fullmatch('[a-fA-F0-9]{64}', digest):
            raise ValueError('Empreinte officielle Claude absente du manifeste.')
        path = self.folder() / 'claude-code' / version / architecture / 'claude.exe'
        valid = False
        if path.is_file():
            with path.open('rb') as stream: valid = hashlib.file_digest(stream, 'sha256').hexdigest() == digest.lower()
        if not valid:
            staged = path.with_name('claude-download.exe')
            staged.unlink(missing_ok=True)
            try:
                download(CLAUDE_BASE + '/' + version + '/' + architecture + '/claude.exe', staged, progress, digest.lower())
                staged.replace(path)
            finally:
                staged.unlink(missing_ok=True)
        connector = self.service.engine.connectors.get('claude-code')
        if connector is None: raise ValueError('Connecteur Claude Code absent.')
        connector.config['executable'] = str(path)
        self.service.config.setdefault('connectors', {})['claude-code'] = connector.config
        self.service.plugins.persist()
        self.service.health.pop('claude-code', None)
        progress(path.stat().st_size, path.stat().st_size, 'CLI installé ; connexion disponible dans Connecteurs')
