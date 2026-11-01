"""Versioned, per-user installation. Application payload never contains user data."""
import hashlib,json,os,shutil,subprocess,uuid,zipfile
from pathlib import Path,PurePosixPath

APP='CyAIOrchestrator'
EXE='CyAIOrchestrator.exe'

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temp,path)

def read_install(root):
    p=Path(root)/'installation.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}

def safe_file(root,relative):
    rel=PurePosixPath(relative)
    if rel.is_absolute() or '..' in rel.parts or '\\' in relative or ':' in relative:
        raise ValueError('Chemin de paquet invalide : '+relative)
    p=(Path(root)/relative).resolve()
    if not p.is_relative_to(Path(root).resolve()):raise ValueError('Chemin hors installation.')
    return p

def install_package(payload,manifest,root,config,user_home,launcher,shortcuts=None):
    root=Path(root).resolve();config=Path(config).resolve();user_home=Path(user_home).resolve()
    if not config.is_file():raise ValueError('Sélectionnez une configuration existante ou créez une nouvelle installation.')
    json.loads(config.read_text(encoding='utf-8-sig'))
    manifest=json.loads(Path(manifest).read_text(encoding='utf-8'))
    version=manifest['version']
    if not version or any(c not in '0123456789.-abcdefghijklmnopqrstuvwxyz' for c in version):raise ValueError('Version invalide.')
    files=manifest['files']
    if EXE not in files or 'config.json' in files:raise ValueError('Paquet application invalide.')
    root.mkdir(parents=True,exist_ok=True)
    stage=root/('staging-'+uuid.uuid4().hex);stage.mkdir()
    previous=read_install(root)
    destination=root/'versions'/(version+'-'+uuid.uuid4().hex[:8])
    try:
        with zipfile.ZipFile(payload) as z:
            members={i.filename:i for i in z.infolist() if not i.is_dir()}
            if len(members)!=len([i for i in z.infolist() if not i.is_dir()]) or set(members)!=set(files):raise ValueError('Contenu du paquet différent du manifeste.')
            for name,entry in files.items():
                target=safe_file(stage,name);info=members[name]
                if (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Lien symbolique interdit dans le paquet.')
                if info.file_size!=entry['bytes']:raise ValueError('Taille invalide : '+name)
                target.parent.mkdir(parents=True,exist_ok=True);digest=hashlib.sha256()
                with z.open(info) as source,target.open('wb') as out:
                    while chunk:=source.read(1024*1024):out.write(chunk);digest.update(chunk)
                if digest.hexdigest()!=entry['sha256']:raise ValueError('SHA-256 invalide : '+name)
        destination.parent.mkdir(exist_ok=True);stage.rename(destination)
        # Copy the stable launcher only after validating the entire release.
        launcher_path=root/EXE
        if not launcher_path.exists() or hashlib.sha256(launcher_path.read_bytes()).digest()!=hashlib.sha256(Path(launcher).read_bytes()).digest():
            tmp=root/'launcher.new';shutil.copy2(launcher,tmp);os.replace(tmp,launcher_path)
        backup=user_home/'config-backups'/('config-'+uuid.uuid4().hex+'.json');backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(config,backup)
        state={'version':version,'current':destination.relative_to(root).as_posix(),'previous':previous.get('current'),'previous_version':previous.get('version'),'config_path':str(config)}
        if shortcuts:shortcuts(root,config)
        atomic_json(root/'installation.json',state)
        atomic_json(user_home/'installation.json',{'install_root':str(root),'config_path':str(config)})
        return state
    finally:
        # Only this newly created staging directory can be removed.
        if stage.exists() and stage.parent==root and stage.name.startswith('staging-'):shutil.rmtree(stage)

def rollback(root):
    root=Path(root).resolve();state=read_install(root)
    old=state.get('previous')
    if not old or not safe_file(root,old+'/'+EXE).is_file():raise ValueError('Aucune version précédente disponible.')
    state['current'],state['previous']=old,state['current']
    state['version'],state['previous_version']=state.get('previous_version'),state.get('version')
    atomic_json(root/'installation.json',state);return state

def create_shortcuts(root,config):
    # Pass paths as JSON through stdin; never interpolate them into shell code.
    desktop_script='''$v = [Console]::In.ReadToEnd() | ConvertFrom-Json
$s = New-Object -ComObject WScript.Shell
foreach ($folder in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('Programs'))) {
 $link=$s.CreateShortcut((Join-Path $folder 'CyAI Orchestrator.lnk'))
 $link.TargetPath=$v.target
 $link.WorkingDirectory=$v.root
 $link.Description='CyAI Orchestrator'
 $link.Save()
}'''
    p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',desktop_script],input=json.dumps({'target':str(Path(root)/EXE),'root':str(root)}),text=True,capture_output=True,creationflags=0x08000000)
    if p.returncode:raise RuntimeError('Création du raccourci impossible : '+p.stderr)
