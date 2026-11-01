"""Stored chat attachments and explicit desktop links."""
import base64,json,mimetypes,os,re,subprocess
from pathlib import Path
from .store import uid,now
from .security import scoped_workspace
MAX_BYTES=256*1024*1024
IMAGE_TYPES={'image/png','image/jpeg','image/webp','image/gif'}
def folder(store):return store.path.parent/'attachments'
def locate(store,id):
    if not re.fullmatch('[a-f0-9]{32}',id):raise ValueError('Pièce jointe invalide.')
    row=store.one("SELECT * FROM files WHERE id=? AND kind='media'",(id,));meta=json.loads(row['content'])
    path=folder(store)/id
    if not path.is_file():raise ValueError('Pièce jointe absente du stockage.')
    return row,meta,path

def upload(s,conversation,name,stream,length):
    s.project_for_conversation(conversation)
    if not 0<length<=MAX_BYTES:raise ValueError('Fichier vide ou supérieur à 256 Mo.')
    name=Path(name.replace('\\','/')).name[:240]
    if not name:raise ValueError('Nom de fichier requis.')
    id=uid();path=folder(s.store)/id;path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('xb') as out:
            left=length
            while left:
                chunk=stream.read(min(left,1024*1024))
                if not chunk:raise ValueError('Transfert interrompu.')
                out.write(chunk);left-=len(chunk)
        mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
        # Only known raster formats are embedded; HTML and SVG are downloads.
        meta={'mime':mime,'bytes':length,'message_ids':[]}
        s.store.execute('INSERT INTO files VALUES(?,?,?,?,?,?)',(id,conversation,name,json.dumps(meta),'media',now()))
        return {'id':id,'name':name,**meta}
    except Exception:path.unlink(missing_ok=True);raise

def cymd_content(path):
    """Read the CyMD container in memory; never execute or extract its resources."""
    import zipfile
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if sum(m.file_size for m in members) > MAX_BYTES:
            raise ValueError("Archive CyMD trop volumineuse après décompression (256 Mo).")
        names = [m.filename for m in members if not m.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError("Archive CyMD ambiguë : fichiers internes en double.")
        manifest = {}
        if 'manifest.json' in names:
            try: manifest = json.loads(archive.read('manifest.json').decode('utf-8-sig'))
            except (ValueError, UnicodeError): pass
        if not isinstance(manifest,dict): manifest={}
        main = manifest.get('main')
        if not isinstance(main,str) or main not in names:
            main = 'document.md' if 'document.md' in names else next((n for n in names if '/' not in n and n.lower().endswith(('.md','.markdown'))), None)
        if not main: raise ValueError("Archive CyMD sans document Markdown.")
        text = archive.read(main).decode('utf-8-sig')
        pictures=[];other=[]
        for name in names:
            if name in (main,'manifest.json','mimetype','previews.json') or name.startswith('previews/'):continue
            mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
            if mime in IMAGE_TYPES:
                info=archive.getinfo(name)
                if info.file_size>20*1024*1024:raise ValueError("Image CyMD trop grande : "+name)
                pictures.append((name,mime,archive.read(name)))
            else: other.append(name)
        return text,pictures,other

def stage_originals(store, conversation, ids, root):
    """Give local agents byte-for-byte originals in their own workspace."""
    import shutil
    from .security import scoped_path
    originals=[]
    for id in ids:
        row=store.one('SELECT * FROM files WHERE id=? AND conversation_id=?',(id,conversation))
        if row['kind']!='media':continue
        row,meta,source=locate(store,id)
        name=Path(row['name'].replace('\\','/')).name
        target=scoped_path(root,str(Path('.cyai-attachments')/id/name),must_exist=False)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        originals.append({'id':id,'name':row['name'],'path':str(target),'bytes':meta['bytes']})
    return originals

def context_media(store,conversation,ids):
    images=[];notes=[];image_bytes=0
    for id in ids:
        row=store.one('SELECT * FROM files WHERE id=? AND conversation_id=?',(id,conversation))
        if row['kind']!='media':continue
        row,meta,path=locate(store,id)
        if row['name'].lower().endswith('.cymd'):
            import zipfile
            try: content,pictures,other=cymd_content(path)
            except (ValueError,UnicodeError,zipfile.BadZipFile,KeyError,RuntimeError) as exc:
                notes.append("Extraction automatique impossible pour "+row['name']+" : "+str(exc)+". Utiliser le fichier original fourni avec les outils locaux.")
                continue
            notes.append('Document CyMD '+row['name']+' — texte transmis (données du fichier joint) :\n'+content)
            for name,mime,payload in pictures:
                image_bytes+=len(payload)
                if len(images)>=8 or image_bytes>32*1024*1024:
                    raise ValueError('Les images CyMD et les autres images jointes dépassent les capacités de cet envoi (8 images / 32 Mo).')
                images.append({'mime':mime,'data':base64.b64encode(payload).decode()})
                notes.append('Image jointe n° '+str(len(images))+' : '+row['name']+' / '+name)
            if other:notes.append('Autres ressources présentes dans '+row['name']+' (contenu non transmis) : '+', '.join(other))
        elif meta['mime'] in IMAGE_TYPES:
            image_bytes+=meta['bytes']
            if len(images)>=8 or image_bytes>32*1024*1024:raise ValueError('Maximum 8 images et 32 Mo d’images par envoi.')
            if meta['bytes']>20*1024*1024:raise ValueError('Image trop grande pour l’IA (20 Mo maximum).')
            images.append({'mime':meta['mime'],'data':base64.b64encode(path.read_bytes()).decode()})
        else:
            try:
                if meta['bytes']>500000:raise ValueError()
                content=path.read_text(encoding='utf-8-sig')
                if '\x00' in content:raise ValueError()
                notes.append('Fichier '+row['name']+' :\n'+content)
            except (UnicodeError,ValueError):notes.append('Pièce jointe '+row['name']+' ('+meta['mime']+'). Contenu non extrait en texte ; utiliser le fichier original fourni avec les outils locaux pour l’analyser.')
    return images,notes

def local_path(s,conversation,raw):
    p=s.project_for_conversation(conversation);c=s.conversation(conversation)
    if raw.lower().startswith('file:'):
        from urllib.parse import urlparse,unquote
        parsed=urlparse(raw)
        if parsed.netloc not in {'','localhost'}:raise ValueError('Chemin réseau non pris en charge.')
        raw=unquote(parsed.path)
        if re.match(r'^/[A-Za-z]:',raw):raw=raw[1:]
    raw=re.sub(r':\d+(?::\d+)?$','',raw)
    try:return scoped_workspace(p['root'],raw,json.loads(c.get('workdirs','[]')))
    except ValueError:
        # Desktop media navigation is distinct from agent workspace access.
        from .security import scoped_path
        candidate=Path(raw)
        if not candidate.is_absolute() or str(candidate).startswith(('\\\\','//')):raise
        return scoped_path(candidate.anchor,str(candidate))

def reveal(s,data):
    if data.get('id'):
        row,meta,path=locate(s.store,data['id'])
        if row['conversation_id']!=data['conversation_id']:raise ValueError('Pièce jointe hors conversation.')
    else:path=local_path(s,data['conversation_id'],data['path'])
    if os.name!='nt':raise ValueError('Ouverture Windows indisponible.')
    # Explorer selection never executes an attached program or script.
    subprocess.Popen(['explorer.exe','/select,',str(path)],creationflags=subprocess.CREATE_NO_WINDOW)
    return {'ok':True}

def preview(s,data):
    path=local_path(s,data['conversation_id'],data['path'])
    mime=mimetypes.guess_type(path.name)[0] or ''
    if path.suffix.lower() not in {'.glb','.gltf','.obj','.stl','.ply'} and mime not in IMAGE_TYPES and mime not in {'video/mp4','video/webm','audio/mpeg','audio/wav'}:raise ValueError('Ce format ne possède pas d’aperçu intégré.')
    with path.open('rb') as stream:result=upload(s,data['conversation_id'],path.name,stream,path.stat().st_size)
    return {'url':'/media/'+result['id'],'mime':mime,'name':path.name}


def document_preview(service, data):
    row,meta,path=locate(service.store,data['id'])
    if row['conversation_id']!=data['conversation_id']:raise ValueError('Pièce jointe hors conversation.')
    if not row['name'].lower().endswith('.cymd'):raise ValueError('Document CyMD requis.')
    text,pictures,other=cymd_content(path)
    return {'name':row['name'],'text':text,'images':[{'name':name,'mime':mime,'data':base64.b64encode(payload).decode()} for name,mime,payload in pictures],'other':other}


def open_cymd(service,data):
    import shutil
    row,meta,source=locate(service.store,data['id'])
    if row['conversation_id']!=data['conversation_id'] or not row['name'].lower().endswith('.cymd'):
        raise ValueError('Document CyMD de cette conversation requis.')
    target=folder(service.store)/'windows-open'/data['id']/Path(row['name']).name
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
    try:os.startfile(str(target))
    except OSError as exc:raise ValueError('Windows ne peut pas ouvrir ce document. Associez .cymd à CyMD dans les applications par défaut. '+str(exc)) from exc
    return {'ok':True}


def open_local(service,data):
    import shutil
    if data.get('id'):
        row,meta,source=locate(service.store,data['id'])
        if row['conversation_id']!=data['conversation_id']:raise ValueError('Pièce jointe hors conversation.')
        path=folder(service.store)/'windows-open'/data['id']/Path(row['name']).name
        path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,path)
    else:path=local_path(service,data['conversation_id'],data['path'])
    if path.suffix.lower() not in {'.glb','.gltf','.obj','.stl','.ply','.fbx','.blend','.cymd','.png','.jpg','.jpeg','.webp','.gif','.mp4','.webm','.wav','.mp3','.pdf','.txt','.md'}:
        return reveal(service,data)
    try:os.startfile(str(path))
    except OSError as exc:raise ValueError('Windows ne dispose pas d’une application associée à ce fichier. Utilisez Afficher dans l’Explorateur puis Ouvrir avec. '+str(exc)) from exc
    return {'ok':True}
