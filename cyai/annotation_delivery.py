"""Receive a CyAnnota archive as stored chat media, including vision inputs."""
import io,zipfile
from pathlib import PurePosixPath
from .media import locate,upload,IMAGE_TYPES,folder

def receive(s,d):
 conversation=d['conversation_id'];project=s.project_for_conversation(conversation)
 s.plugins.plugin('cyannota',project['id'])
 row,meta,path=locate(s.store,d['id'])
 if row['conversation_id']!=conversation:raise ValueError('Archive hors conversation.')
 created=[]
 try:
  with zipfile.ZipFile(path) as z:
   entries=[i for i in z.infolist() if not i.is_dir()]
   if len(entries)>1000 or sum(i.file_size for i in entries)>256*1024**2:raise ValueError('Archive limitée à 256 Mo décompressés et 1 000 fichiers.')
   for item in entries:
    p=PurePosixPath(item.filename.replace('\\','/'))
    if p.is_absolute() or '..' in p.parts:raise ValueError('Chemin invalide dans l’archive.')
   prompts=[i for i in entries if PurePosixPath(i.filename).name=='prompt.md']
   if not prompts:raise ValueError('Exportez en mode IA pour transmettre les consignes à la conversation.')
   models=[i for i in entries if PurePosixPath(i.filename).suffix.lower() in {'.glb','.gltf','.obj','.stl','.ply','.fbx'}]
   selected=[i for i in entries if i in prompts or i in models or (PurePosixPath(i.filename).suffix.lower() in {'.png','.jpg','.jpeg','.webp'} and PurePosixPath(i.filename).name!='thumbnail.png')]
   image_entries=[i for i in selected if i not in prompts and i not in models]
   if len(image_entries)>8 or sum(i.file_size for i in image_entries)>32*1024**2:raise ValueError('L’envoi aux IA accepte 8 images et 32 Mo d’images. Réduisez les captures ou répartissez-les entre plusieurs envois.')
   for item in selected:
    if item in prompts and item.file_size>500000:raise ValueError('Consignes trop volumineuses.')
    if item in image_entries and item.file_size>20*1024**2:raise ValueError('Image limitée à 20 Mo pour les IA.')
    raw=z.read(item)
    result=upload(s,conversation,PurePosixPath(item.filename).name,io.BytesIO(raw),len(raw));created.append(result['id'])
  return {'ids':[d['id'],*created],'images':len(image_entries),'prompts':len(prompts),'models':len(models)}
 except Exception:
  for id in created:
   s.store.execute('DELETE FROM files WHERE id=?',(id,));(folder(s.store)/id).unlink(missing_ok=True)
  raise
