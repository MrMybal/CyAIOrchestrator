"""Project organization and explicit local workspace settings."""
import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from .security import PathPolicy, scoped_path
from .store import uid, now

UNHANDLED = object()

def git_status(root):
    command = shutil.which('git')
    if not command:
        return {'installed': False, 'repository': False}
    def run(*args):
        return subprocess.run([command, '-C', root, *args], capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=10,
                              creationflags=0x08000000 if os.name == 'nt' else 0)
    result = run('rev-parse', '--show-toplevel')
    if result.returncode:
        return {'installed': True, 'repository': False}
    return {'installed': True, 'repository': True, 'root': result.stdout.strip(),
            'branch': run('branch', '--show-current').stdout.strip() or 'HEAD détachée',
            'changes': len(run('status', '--porcelain').stdout.splitlines())}

def persist(service):
    service.config_path.write_text(json.dumps(service.config, ensure_ascii=False, indent=2), encoding='utf-8')

def workspace_action(s, action, d):
    if action in {'annotation_save','annotation_list','annotation_open'}:
        project=s.project_for_conversation(d['conversation_id'])
        s.plugins.plugin('cyannota',project['id'])
        if action=='annotation_list':
            return {'items':s.store.rows("SELECT id,name FROM files WHERE conversation_id=? AND kind='cyannota'",(d['conversation_id'],))}
        if action=='annotation_open':
            row=s.store.one("SELECT * FROM files WHERE id=? AND conversation_id=? AND kind='cyannota'",(d['id'],d['conversation_id']))
            value=json.loads(row['content'])
            path=scoped_path(project['root'],value['image_path'])
            return {'id':row['id'],'name':row['name'],'document':value['document'],'image':'data:'+value['mime']+';base64,'+base64.b64encode(path.read_bytes()).decode()}
        image=d.get('image','')
        match=re.fullmatch(r'data:(image/(png|jpeg|webp));base64,([A-Za-z0-9+/=]+)',image)
        if not match: raise ValueError('Image PNG, JPEG ou WebP requise.')
        raw=base64.b64decode(match[3],validate=True)
        if len(raw)>10000000: raise ValueError('Image limitée à 10 Mo.')
        document=d.get('document')
        if not isinstance(document,dict) or not isinstance(document.get('annotations'),list): raise ValueError('Document CyAnnota invalide.')
        if len(json.dumps(document))>10000000: raise ValueError('Annotations trop volumineuses.')
        id=d.get('id') or uid()
        if d.get('id'): s.store.one("SELECT id FROM files WHERE id=? AND conversation_id=? AND kind='cyannota'",(id,d['conversation_id']))
        target=scoped_path(project['root'],'.cyai-annotations/'+id+'.'+match[2],must_exist=False)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        value={'instructions':'Corrections CyAnnota : consulter l’image source et appliquer les annotations numérotées. Les coordonnées sont exprimées dans le repère de l’image.', 'image_path':str(target),'mime':match[1],'document':document}
        content=json.dumps(value,ensure_ascii=False)
        if d.get('id'): s.store.execute('UPDATE files SET content=? WHERE id=?',(content,id))
        else: s.store.execute('INSERT INTO files VALUES(?,?,?,?,?,?)',(id,d['conversation_id'],str(d.get('name','Image'))[:200],content,'cyannota',now()))
        return {'id':id}
    if action == 'organize':
        table = {'project':'projects', 'conversation':'conversations'}.get(d.get('kind'))
        if not table: raise ValueError('Type inconnu.')
        row = s.store.one(f'SELECT * FROM {table} WHERE id=?', (d['id'],))
        values = {}
        for key in ('favorite', 'archived'):
            if key in d: values[key] = int(bool(d[key]))
        if table == 'projects':
            for key in ('category','color','icon'):
                if key in d: values[key] = str(d[key])
            if 'color' in values and not re.fullmatch(r'#[0-9a-fA-F]{6}', values['color']): raise ValueError('Couleur invalide.')
            if 'icon' in values:
                icon = values['icon']
                if len(icon)>400000 or (len(icon)>8 and not re.fullmatch(r'data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+',icon)):
                    raise ValueError('Logo PNG, JPEG ou WebP limité à 300 Ko, ou emoji.')
            if values.get('category') and values['category'] not in s.config.get('categories',[]): raise ValueError('Catégorie inconnue.')
        with s.engine.lock:
            if d.get('delete') or 'archived' in d:
                if table == 'projects':
                    for c in s.store.rows('SELECT id FROM conversations WHERE project_id=?',(row['id'],)): s._idle(c['id'])
                else: s._idle(row['id'])
            if d.get('delete'):
                s.store.execute(f'DELETE FROM {table} WHERE id=?',(row['id'],))
            elif values:
                s.store.execute(f'UPDATE {table} SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),row['id']))
        return {'ok':True}
    if action == 'category':
        name = str(d.get('name','')).strip()[:80]
        old = d.get('old')
        categories = s.config.setdefault('categories',[])
        if old:
            if old not in categories: raise ValueError('Catégorie inconnue.')
            if name and name != old and name in categories: raise ValueError('Catégorie existante.')
            categories[categories.index(old):categories.index(old)+1] = [name] if name else []
            s.store.execute('UPDATE projects SET category=? WHERE category=?',(name,old))
        elif name and name not in categories: categories.append(name)
        persist(s)
        return {'ok':True}
    if action == 'reorder':
        table = {'project':'projects','conversation':'conversations'}.get(d.get('kind'))
        if not table: raise ValueError('Type inconnu.')
        rows = s.store.rows(f'SELECT id FROM {table}' + (' WHERE project_id=?' if table=='conversations' else ''), (d['project_id'],) if table=='conversations' else ())
        ids=d['ids']
        if len(ids)!=len(set(ids)) or set(ids)!={r['id'] for r in rows}: raise ValueError('La liste a changé. Réessayez.')
        with s.store.transaction() as db:
            for i,id in enumerate(ids): db.execute(f'UPDATE {table} SET position=? WHERE id=?',(i,id))
        return {'ok':True}
    if action == 'conversation_workdirs':
        project=s.project_for_conversation(d['id'])
        roots=d.get('workdirs',[])
        if not isinstance(roots,list) or len(roots)>12: raise ValueError('12 dossiers supplémentaires maximum.')
        roots=list(dict.fromkeys(str(Path(r).resolve(strict=True)) for r in roots))
        policy=PathPolicy([*s.engine.policy.roots,*roots],s.engine.policy.protected_roots)
        for root in roots: policy.project(root)
        with s.engine.lock:
            s._idle(d['id'])
            s.config['allowed_roots']=list(dict.fromkeys(str(r) for r in policy.roots));persist(s);s.engine.policy=policy
            s.store.execute('UPDATE conversations SET workdirs=? WHERE id=?',(json.dumps(roots),d['id']))
            s.store.execute('UPDATE sessions SET native_id=NULL,last_seq=0 WHERE conversation_id=?',(d['id'],))
        return {'ok':True}
    if action == 'git_init':
        project=s.store.one('SELECT * FROM projects WHERE id=?',(d['project_id'],))
        root=s.engine.policy.project(project['root'])
        with s.engine.lock:
            for c in s.store.rows('SELECT id FROM conversations WHERE project_id=?',(project['id'],)): s._idle(c['id'])
            status=git_status(root)
            if not status['installed']: raise ValueError('Git n’est pas installé sur Windows. Installez Git pour Windows puis réessayez.')
            if not status['repository']:
                result=subprocess.run([shutil.which('git'),'-C',root,'init'],capture_output=True,text=True,timeout=20,creationflags=0x08000000 if os.name=='nt' else 0)
                if result.returncode: raise ValueError(result.stderr)
        return git_status(root)
    if action == 'save_theme':
        settings=s.config.setdefault('settings',{})
        name=str(d.get('name','')).strip()[:80]
        if not name: raise ValueError('Nom de thème requis.')
        theme={'name':name}
        for key in ('bg','panel','text','muted','accent','line'):
            if not re.fullmatch(r'#[0-9a-fA-F]{6}',str(d.get(key,''))): raise ValueError('Couleur invalide.')
            theme[key]=d[key]
        id='custom-'+uid()[:12]
        settings.setdefault('custom_themes',{})[id]=theme
        settings['theme']=id
        persist(s)
        return {'ok':True}
    if action == 'save_settings':
        settings=s.config.setdefault('settings',{})
        theme=d.get('theme',settings.get('theme','dark'))
        if theme not in {'dark','light','system','ocean','forest',*settings.get('custom_themes',{})}: raise ValueError('Thème invalide.')
        settings['theme']=theme
        if 'send_on_enter' in d:settings['send_on_enter']=d['send_on_enter'] in (True,'true','1','on')
        if 'backup_dir' in d:
            folder=Path(d['backup_dir']).resolve(strict=True)
            if not folder.is_dir(): raise ValueError('Choisissez un dossier existant.')
            settings['backup_dir']=str(folder)
        if 'context_chars' in d:
            budget=int(d['context_chars'])
            if budget<1: raise ValueError('La cible de contexte doit être positive.')
            s.engine.context_chars=budget;s.config['context_chars']=budget
        persist(s)
        return {'ok':True}
    if action == 'backup_to_folder':
        folder=s.config.get('settings',{}).get('backup_dir')
        if not folder: raise ValueError('Choisissez d’abord le dossier de sauvegarde.')
        target=Path(folder).resolve(strict=True)/('cyai-'+now().replace(':','-')+'-'+uid()[:6]+'.json')
        target.write_text(json.dumps(s.action('backup',{}),ensure_ascii=False),encoding='utf-8')
        return {'path':str(target)}
    return UNHANDLED
