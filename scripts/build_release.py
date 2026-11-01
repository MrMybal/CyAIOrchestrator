"""Build a reproducible manifest and offline installer from a staged desktop build."""
import argparse,hashlib,json,subprocess,sys,zipfile
from pathlib import Path
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
from cyai import __version__
sys.path.insert(0,str(root/'scripts'))
from package_policy import validate_payload
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--stage',type=Path,default=root/'dist-next'/'CyAIOrchestrator',help='Directory containing the staged desktop application')
args=parser.parse_args()
stage=args.stage.resolve();out=root/'releases';work=root/'build-release';out.mkdir(exist_ok=True);work.mkdir(exist_ok=True)
if not (stage/'CyAIOrchestrator.exe').is_file():raise ValueError('Build desktop absent.')
validate_payload(p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file())
files={}
with zipfile.ZipFile(work/'payload.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in stage.rglob('*'):
  if not p.is_file():continue
  name=p.relative_to(stage).as_posix()
  if name=='config.json' or name.endswith('.sqlite3') or '.data/' in name:raise ValueError('Données utilisateur dans le paquet : '+name)
  files[name]={'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()};z.write(p,name)
(work/'release.json').write_text(json.dumps({'version':__version__,'files':files},indent=2),encoding='utf-8')
def build(name,entry,data=[]):
 command=[sys.executable,'-m','PyInstaller','--noconfirm','--onefile','--windowed','--name',name,'--distpath',str(out),'--workpath',str(work),'--specpath',str(work),'--paths',str(root/'packaging'),'--icon',str(root/'cyai/web/cyai-logo.ico')]
 for path in data:command+=['--add-data',str(path)+';.']
 if entry=='packaging/installer.py':command+=['--add-data',str(root/'cyai'/'locales')+';cyai/locales']
 subprocess.run(command+[str(root/entry)],check=True)
build('CyAILauncher','packaging/launcher.py')
build('CyAIOrchestrator-Setup-'+__version__,'packaging/installer.py',[work/'payload.zip',work/'release.json',out/'CyAILauncher.exe'])
setup=out/('CyAIOrchestrator-Setup-'+__version__+'.exe');(out/(setup.name+'.sha256')).write_text(hashlib.file_digest(setup.open('rb'),'sha256').hexdigest()+'  '+setup.name+'\n')
print(setup)
