"""Official Cy* repositories and explicit, verified per-user downloads."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import threading
import urllib.request
import uuid
import zipfile

from .local_models import download

CATALOG = [
    {'id':'audiostudio','name':'CyTools AudioStudio','repo':'CyTools_AudioStudio','kind':'tool','tool_id':'cy.tool.audiostudio','description':'Éditeur audio, effets, musique, voix et transcription.'},
    {'id':'audiolibrary','name':'CyTools AudioLibrary','repo':'CyTools_AudioLibrary','kind':'tool','tool_id':'cy.tool.audiolibrary','description':'Bibliothèque audio locale, analyse et recherche de sons.'},
    {'id':'aichat','name':'CyTools AIChat','repo':'CyTools_AIChat','kind':'tool','tool_id':'cy.tool.aichat','description':'Conversations IA, modèles locaux et distants, voix.'},
    {'id':'personarp','name':'CyTools PersonaRP','repo':'CyTools_PersonaRP','kind':'tool','tool_id':'cy.tool.personarp','description':'Personnages persistants, jeu de rôle et voix.'},
    {'id':'storyboard','name':'CyTools Storyboard','repo':'CyTools_Storyboard','kind':'tool','tool_id':'cy.tool.storyboard','description':'Storyboard, prévisualisation et génération d’images.'},
    {'id':'meshstudio','name':'CyTools MeshStudio','repo':'CyTools_MeshStudio','kind':'tool','tool_id':'cy.tool.meshstudio','description':'Modélisation 3D, reconstruction, remeshing, UV et textures.'},
    {'id':'cyannota','name':'CyAnnota','repo':'CyAnnota','kind':'editor','description':'Annotations d’images, de vidéos et de modèles 3D.'},
    {'id':'cymd','name':'CyMD','repo':'CyMD','kind':'editor','description':'Éditeur Markdown et documents CyMD.'},
    {'id':'cytask','name':'CyTask','repo':'CyTask','kind':'service','description':'Projets, tâches, agents et appels durables via MCP.'},
    {'id':'cyaicodex','name':'CyAICodex','repo':'CyAICodex','kind':'service','description':'Bibliothèque de skills et de références visuelles via MCP.'},
]
LEGACY = {
    'audiostudio':['acestep15','acestep','audiogen','fishspeechs2pro','pipertts','qwen3tts'],
    'meshstudio':['autoremesher','localmesh','meshconstruct','quadwild','spar3d','trellis2texture','triposr','unirig','viewgenerator','wham','xatlas'],
    'storyboard':['flux1'],
    'aichat':['qwen34bnymphaea'],
    'retired':['hunyuanvideo15','ltx2'],
}


def legacy_replacement(plugin):
    if plugin.get('id') == 'cyprojectcodex': return 'legacy'
    if not plugin.get('cytools'): return ''
    values = [re.sub('[^a-z0-9]','',str(plugin.get(k,'')).lower()) for k in ('name','cytools_id')]
    for target, names in LEGACY.items():
        for value in values:
            value = re.sub(r'^cytools?', '', value)
            if value in names or any(len(n)>7 and value.startswith(n) for n in names): return target
    return ''


def extract_archive(archive, destination):
    """Validate the entire portable archive before writing within a new directory."""
    destination=Path(destination).resolve()
    with zipfile.ZipFile(archive) as package:
        entries=package.infolist()
        if sum(e.file_size for e in entries)>2*1024**3: raise ValueError('Archive d’extension trop volumineuse.')
        seen=set()
        for entry in entries:
            name=entry.orig_filename
            path=PurePosixPath(name)
            if not name or chr(92) in name or ':' in name or path.is_absolute() or '..' in path.parts or chr(0) in name:
                raise ValueError('Chemin invalide dans l’archive d’extension.')
            key=path.as_posix().casefold().rstrip('/')
            if key in seen: raise ValueError('Chemin en double dans l’archive d’extension.')
            seen.add(key)
            if (entry.external_attr>>16)&0o170000==0o120000: raise ValueError('Lien symbolique dans l’archive d’extension.')
            if not (destination/path.as_posix()).resolve().is_relative_to(destination): raise ValueError('Chemin hors extension.')
        for entry in entries:
            target=destination/entry.filename
            if entry.is_dir(): target.mkdir(parents=True,exist_ok=True);continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with package.open(entry) as source, target.open('xb') as output: shutil.copyfileobj(source,output)


class ExtensionCatalog:
    def __init__(self,service):
        self.service=service
        self.lock=threading.RLock()

    def entry(self,identifier):
        for entry in CATALOG:
            if entry['id']==identifier:return entry
        raise ValueError('Extension inconnue.')

    def folder(self):
        return self.service.store.path.parent/'extensions'

    def state(self):
        # Reading settings never calls GitHub or downloads software.
        cache=self.service.config.get('extension_releases',{})
        downloads=self.service.config.get('extension_downloads',{})
        plugins=self.service.config.get('plugins',{})
        manager=getattr(self.service,'local_models',None)
        jobs=list(manager.jobs.values()) if manager else []
        checks={j['name'] for j in jobs if j['status'] in {'queued','running'} and j['name'].startswith('Extensions · GitHub')}
        items=[]
        for entry in CATALOG:
            plugin=next((p for p in plugins.values() if (entry.get('tool_id') and p.get('cytools_id')==entry['tool_id']) or (entry['kind']!='tool' and p.get('id')==entry['id'])),None)
            saved=downloads.get(entry['id'],{})
            job=next((j for j in reversed(jobs) if j['name']=='Extension · '+entry['id']),None)
            items.append({**entry,'repository':'https://github.com/MrMybal/'+entry['repo'],
                          'release':cache.get(entry['id']), 'plugin_id':plugin.get('id') if plugin else None,
                          'installed_version':plugin.get('version','') if plugin else '',
                          'downloaded':bool(saved.get('path') and Path(saved['path']).is_file()),
                          'job':job,'checking':'Extensions · GitHub' in checks or 'Extensions · GitHub · '+entry['id'] in checks,
                          'check_error':self.service.config.get('extension_errors',{}).get(entry['id'],'')})
        return items

    def check_one(self,identifier):
        entry=self.entry(identifier)
        url='https://api.github.com/repos/MrMybal/'+entry['repo']+'/releases/latest'
        request=urllib.request.Request(url,headers={'User-Agent':'CyAI-Orchestrator','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=25) as response:
            raw=response.read(3*1024**2+1)
        if len(raw)>3*1024**2:raise ValueError('Métadonnées GitHub trop volumineuses.')
        release=json.loads(raw)
        if release.get('draft') or release.get('prerelease'):raise ValueError('Release stable requise.')
        version=release.get('tag_name','')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',version):raise ValueError('Version GitHub invalide.')
        def suitable(asset):
            name=asset.get('name','').lower()
            if entry['kind']=='tool':return name.endswith('.zip') and ('windows-x64' in name or 'win64' in name)
            return name.endswith('.exe') and ('setup' in name or 'portable' in name)
        assets=[a for a in release.get('assets',[]) if suitable(a)]
        assets.sort(key=lambda a:('setup' not in a['name'].lower(),a['name']))
        asset=assets[0] if assets else None
        if asset:
            address=asset.get('browser_download_url','')
            prefix='https://github.com/MrMybal/'+entry['repo']+'/releases/download/'
            if not address.startswith(prefix):raise ValueError('Adresse d’asset GitHub inattendue.')
            name=asset['name']
            if Path(name).name!=name or any(c in name for c in ('/',chr(92),':')):raise ValueError('Nom d’asset invalide.')
            digest=asset.get('digest','') or ''
            if not re.fullmatch('sha256:[a-f0-9]{64}',digest):asset=None
            else:asset={k:asset[k] for k in ('name','browser_download_url','size','digest')}
        info={'version':version,'url':'https://github.com/MrMybal/'+entry['repo']+'/releases/tag/'+version,'asset':asset}
        with self.lock:
            self.service.config.setdefault('extension_releases',{})[identifier]=info
            self.service.config.setdefault('extension_errors',{}).pop(identifier,None)
            self.service.plugins.persist()
        return info

    def check(self,identifier=None):
        identifiers=[self.entry(identifier)['id']] if identifier else [e['id'] for e in CATALOG]
        def work(progress):
            errors=[]
            for i,key in enumerate(identifiers):
                progress(0,0,'GitHub · '+self.entry(key)['name'])
                try:self.check_one(key)
                except Exception as exc:
                    errors.append(self.entry(key)['name']+': '+str(exc))
                    with self.lock:
                        self.service.config.setdefault('extension_errors',{})[key]=str(exc)
                        self.service.plugins.persist()
            if errors:raise ValueError(chr(10).join(errors))
            progress(0,0,'Catalogue actualisé')
        return self.service.local_models.job('Extensions · GitHub'+(' · '+identifier if identifier else ''),work)

    def install(self,identifier):
        entry=self.entry(identifier)
        return self.service.local_models.job('Extension · '+identifier,lambda progress:self._install(entry,progress))

    def _install(self,entry,progress):
        info=self.service.config.get('extension_releases',{}).get(entry['id']) or self.check_one(entry['id'])
        asset=info.get('asset')
        if not asset:raise ValueError('Aucun téléchargement Windows vérifiable dans cette release. Consultez le dépôt officiel.')
        folder=self.folder()/entry['id'];folder.mkdir(parents=True,exist_ok=True)
        archive=folder/(asset['digest'][7:19]+'-'+asset['name'])
        if archive.is_file():
            with archive.open('rb') as source:valid=hashlib.file_digest(source,'sha256').hexdigest()==asset['digest'][7:]
            if not valid:raise ValueError('Téléchargement local modifié. Choisissez le téléchargement officiel dans le dépôt.')
        else:download(asset['browser_download_url'],archive,progress,asset['digest'])
        if archive.stat().st_size!=asset['size']:raise ValueError('Taille de téléchargement incorrecte.')
        if entry['kind']=='tool':
            destination=folder/(info['version']+'-'+asset['digest'][7:19])
            if not destination.exists():
                stage=folder/('staging-'+uuid.uuid4().hex);stage.mkdir()
                try:
                    extract_archive(archive,stage)
                    # A release may wrap its portable folder in a single directory.
                    roots=[stage]+[p for p in stage.iterdir() if p.is_dir()]
                    base=next((p for p in roots if (p/'app/CyTool.json').is_file() or (p/'CyTool.json').is_file()),None)
                    if base is None:raise ValueError('CyTool.json absent du paquet Windows.')
                    manifest=json.loads(next(p for p in (base/'app/CyTool.json',base/'CyTool.json') if p.is_file()).read_text('utf-8-sig'))
                    if manifest.get('id')!=entry['tool_id']:raise ValueError('Identifiant CyTool inattendu dans la release.')
                    base.rename(destination)
                finally:
                    if stage.exists() and stage.parent.resolve()==folder.resolve() and stage.name.startswith('staging-'):shutil.rmtree(stage)
            from .cytool_discovery import discover
            detected=discover(str(destination))
            if detected['manifest'].get('id')!=entry['tool_id']:raise ValueError('Identifiant CyTool inattendu.')
            with self.service.engine.lock:
                self.service.plugins.import_cytool({**detected,'replace':True,'source_repo':entry['repo']})
        with self.lock:
            self.service.config.setdefault('extension_downloads',{})[entry['id']]={'path':str(archive),'version':info['version'],'digest':asset['digest']}
            self.service.plugins.persist()
        progress(asset['size'],asset['size'],'Extension installée' if entry['kind']=='tool' else 'Installeur téléchargé ; prêt à ouvrir')

    def open_download(self,identifier):
        entry=self.entry(identifier)
        if entry['kind']=='tool':raise ValueError('Ouvrez le dossier du CyTool depuis sa configuration.')
        saved=self.service.config.get('extension_downloads',{}).get(identifier,{})
        path=Path(saved.get('path','')).resolve()
        if not path.is_relative_to(self.folder().resolve()) or not path.is_file() or path.suffix.lower()!='.exe':raise ValueError('Installeur téléchargé introuvable.')
        with path.open('rb') as source:digest='sha256:'+hashlib.file_digest(source,'sha256').hexdigest()
        if digest!=saved.get('digest'):raise ValueError('Installeur modifié depuis son téléchargement.')
        if os.name!='nt':raise ValueError('Ouverture Windows requise.')
        os.startfile(str(path))
        return {'ok':True}
