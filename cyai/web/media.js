'use strict';
const mediaUploads=new Map();
function richText(text){
 const input=String(text||'');let out='',last=0;
 const re=/```([^\n]*)\n([\s\S]*?)```|!\[([^\]]*)\]\(([^\n]+?)\)|\[([^\]]+)\]\(([^\n]+?)\)|https?:\/\/[^\s<>]+/g;let m;
 const plain=s=>s.split(/(`[^`\n]+`)/g).map(part=>part.startsWith('`')&&part.endsWith('`')?'<code>'+esc(part.slice(1,-1))+'</code>':esc(part.replace(/;[ \t]*(?!\n)/g,';\n')).replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>')).join('');
 const link=(label,url,picture=false)=>{
  url=url.replace(/^<|>$/g,'');
  if(/^https?:\/\//i.test(url)){
   if(picture)return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer"><img class="chat-image" src="${esc(url)}" alt="${esc(label)}" loading="lazy"></a>`;
   return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`;
  }
  if(/^(?:[A-Za-z]:[\\/]|file:\/\/|\/|\.\.?[\\/])/.test(url)||(!/^[a-z][a-z0-9+.-]*:/i.test(url)&&/[\\/]/.test(url))){if(picture)return `<img class="chat-image" data-local-preview="${esc(url)}" alt="${esc(label)}">`;return `<button class="text-button local-link" data-local-link="${esc(url)}">${esc(label)}</button>`;}
  return esc(label)+' ('+esc(url)+')';
 };
 while((m=re.exec(input))){out+=plain(input.slice(last,m.index));
  if(m[1]!==undefined)out+=`<pre class="chat-code"><code>${esc(m[2])}</code></pre>`;
  else if(m[3]!==undefined)out+=link(m[3],m[4],true);
  else if(m[5]!==undefined)out+=link(m[5],m[6]);
  else out+=link(m[0],m[0]);last=re.lastIndex;
 }
 return out+plain(input.slice(last));
}
function mediaCard(file,draft=false){
 let meta;try{meta=JSON.parse(file.content);}catch{return '';}
 const url='/media/'+file.id,mime=meta.mime||'';
 const preview=['image/png','image/jpeg','image/webp','image/gif'].includes(mime)?`<a href="${url}" target="_blank"><img class="chat-image" src="${url}" alt="${esc(file.name)}" loading="lazy"></a>`:mime.startsWith('video/')?ui`<video class="chat-video" controls preload="metadata" src="${url}">Vidéo non prise en charge. Téléchargez le fichier.</video>`:mime.startsWith('audio/')?`<audio controls preload="metadata" src="${url}"></audio>`:'';
 return ui`<div class="chat-attachment" data-file-id="${file.id}" data-file-conversation="${esc(file.conversation_id||state.conversation||'')}">${preview}<div><strong>${esc(file.name)}</strong> · ${(meta.bytes/1024**2).toFixed(2)} Mo</div><a href="${url}?download=1" download>Télécharger</a> <button type="button" class="text-button" data-reveal-file="${file.id}">Afficher dans l’Explorateur</button>${draft?ui` <button type="button" class="text-button" data-unselect-media="${file.id}">Retirer de l’envoi</button>`:''}${mime.startsWith('video/')?ui`<button type="button" class="secondary" data-media-video="${url}" data-media-name="${esc(file.name)}">Agrandir la vidéo</button>`:''}${/\.(glb|gltf|obj|stl|ply)$/i.test(file.name)?ui`<button type="button" class="secondary" data-mesh-id="${file.id}" data-mesh-name="${esc(file.name)}">Voir en 3D</button>`:''}${file.name.toLowerCase().endsWith('.cymd')?`<button type="button" class="secondary" data-media-document="${file.id}">${cymdEnabled()?ui('Ouvrir dans CyMD'):ui('Ouvrir avec Windows')}</button>`:''}${mime.startsWith('video/')?ui('<small>Lecture dans CyAI. Analyse vidéo non transmise aux agents actuels.</small>'):''}</div>`;
}
function messageMedia(id,sourceId){return (state.detail?.files||[]).filter(f=>f.kind==='media'&&(JSON.parse(f.content).message_ids||[]).some(x=>x===id||x===sourceId)).map(f=>mediaCard(f)).join('');}
function renderMediaDrafts(){
 let el=$('media-drafts');if(!el){el=document.createElement('div');el.id='media-drafts';$('composer-area').prepend(el);}
 htmlIfChanged('media-drafts',(state.detail?.files||[]).filter(f=>f.kind==='media'&&state.files.has(f.id)).map(f=>mediaCard(f,true)).join('')+[...mediaUploads.values()].filter(x=>x.conversation===state.conversation).map(x=>`<p role="status">${esc(x.name)} · ${esc(x.status)}</p>`).join(''));
}
async function uploadMedia(files){
 if(!state.conversation){toast(ui('Ouvrez une conversation dans un projet avant de joindre des fichiers.'));return;}
 const conversation=state.conversation;
 for(const file of files){
  const id=crypto.randomUUID();mediaUploads.set(id,{conversation,name:file.name,status:ui('Préparation…')});renderMediaDrafts();
  try{
   if(file.size>256*1024**2)throw Error(ui('Fichier limité à 256 Mo : ')+file.name);
   const r=await new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST','/api/upload?conversation_id='+conversation+'&name='+encodeURIComponent(file.name));xhr.setRequestHeader('X-CyAI','1');xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.upload.onprogress=e=>{mediaUploads.set(id,{conversation,name:file.name,status:e.lengthComputable?Math.round(e.loaded/e.total*100)+' %':ui('Transfert…')});renderMediaDrafts();};xhr.onerror=()=>reject(Error(ui('Transfert interrompu.')));xhr.onload=()=>{let r;try{r=JSON.parse(xhr.responseText);}catch{return reject(Error(ui('Réponse de transfert invalide.')));}xhr.status===200?resolve(r):reject(Error(r.error||ui('Échec du transfert')));};xhr.send(file);});
   addDraftFiles(conversation,[r.id]);if(state.conversation===conversation)await refresh(true);
  }catch(e){fail(e);}finally{mediaUploads.delete(id);renderMediaDrafts();}
 }
}
function chooseAttachments(){let el=$('chat-file-input');if(!el){el=document.createElement('input');el.id='chat-file-input';el.type='file';el.multiple=true;el.hidden=true;el.onchange=()=>{uploadMedia([...el.files]);el.value='';};document.body.append(el);}el.click();}
document.addEventListener('dragover',e=>{if(e.dataTransfer?.types.includes('Files')&&e.target.closest('#workspace')){e.preventDefault();$('composer-area').classList.add('file-drop-active');}});
document.addEventListener('dragleave',e=>{if(!e.relatedTarget||!e.relatedTarget.closest('#workspace'))$('composer-area').classList.remove('file-drop-active');});
document.addEventListener('drop',e=>{if(e.dataTransfer?.files.length&&e.target.closest('#workspace')){e.preventDefault();$('composer-area').classList.remove('file-drop-active');uploadMedia([...e.dataTransfer.files]);}});
document.addEventListener('paste',e=>{if(!e.target.closest('#composer'))return;const files=[...(e.clipboardData?.files||[])];if(files.length){e.preventDefault();uploadMedia(files);}});
document.addEventListener('click',async e=>{const b=e.target.closest('[data-local-link],[data-reveal-file],[data-unselect-media]');if(!b)return;try{
 if(b.dataset.unselectMedia){state.files.delete(b.dataset.unselectMedia);rememberDraft();renderMediaDrafts();return;}
 if(b.dataset.localLink){await openLocalAsset(b.dataset.localLink);return;}
 await action('reveal_local',{conversation_id:state.conversation,id:b.dataset.revealFile});toast(ui('Fichier affiché dans l’Explorateur.'));
}catch(err){fail(err);}});

const localPreviewCache=new Map();
async function hydrateLocalImages(){
 const conversation=state.conversation;
 for(const img of document.querySelectorAll('[data-local-preview]')){
  const path=img.dataset.localPreview,key=conversation+'|'+path;img.removeAttribute('data-local-preview');
  try{if(!localPreviewCache.has(key))localPreviewCache.set(key,action('preview_local',{conversation_id:conversation,path}));const r=await localPreviewCache.get(key);if(img.isConnected){img.src=r.url;img.dataset.originalLocalPath=path;}}
  catch(e){img.alt=ui('Aperçu indisponible : ')+e.message;localPreviewCache.delete(key);}
 }
}

document.addEventListener('error',e=>{if(e.target.matches?.('.chat-video,audio')){const host=e.target.closest('.chat-attachment');if(host&&!host.querySelector('.media-error')){const note=document.createElement('p');note.className='media-error';note.textContent=ui('Ce format ou codec ne peut pas être lu ici. Téléchargez le fichier pour l’ouvrir dans votre lecteur.');host.append(note);}}},true);


function openMediaViewer(url,kind,name,source){
 const dialog=document.createElement('dialog');dialog.className='media-viewer';
 dialog.innerHTML=ui`<header><strong></strong><div class="row-actions"><button type="button" data-zoom="out" aria-label="Réduire">−</button><button type="button" data-zoom="in" aria-label="Zoomer">+</button><button type="button" data-zoom="actual">100 %</button><button type="button" data-zoom="fit">Adapter</button><button type="button" data-close aria-label="Fermer l’aperçu">✕</button></div></header><div class="media-viewer-stage"></div><p class="field-help" aria-live="polite"></p>`;
 dialog.querySelector('strong').textContent=name||ui('Aperçu');
 const stage=dialog.querySelector('.media-viewer-stage'),status=dialog.querySelector('p');
 let scale=1,x=0,y=0,drag=null;
 const content=document.createElement(kind==='video'?'video':'img');
 content.src=url;content.alt=name||'';content.draggable=false;
 if(kind==='video'){content.controls=true;content.preload='metadata';dialog.querySelectorAll('[data-zoom]').forEach(b=>b.hidden=true);if(source){source.pause();content.onloadedmetadata=()=>{content.currentTime=source.currentTime;};}}
 stage.append(content);
 const paint=()=>{content.style.transform=`translate(${x}px,${y}px) scale(${scale})`;status.textContent=Math.round(scale*100)+ui(' % · Molette pour zoomer · Glisser pour déplacer');};
 const fit=()=>{if(kind==='video')return;scale=Math.min(stage.clientWidth/content.naturalWidth,stage.clientHeight/content.naturalHeight,1)||1;x=y=0;paint();};
 const zoom=(factor,px=0,py=0)=>{const next=Math.max(.02,Math.min(32,scale*factor));x=px-(px-x)*next/scale;y=py-(py-y)*next/scale;scale=next;paint();};
 content.onerror=()=>{status.textContent=ui('Impossible de lire ce média dans CyAI. Le fichier original reste téléchargeable.');status.className='voice-note error';};
 if(kind!=='video'){
   content.onload=fit;
   stage.addEventListener('wheel',e=>{e.preventDefault();const r=stage.getBoundingClientRect();zoom(Math.exp(-e.deltaY*.002),e.clientX-r.left-r.width/2,e.clientY-r.top-r.height/2);},{passive:false});
   stage.onpointerdown=e=>{if(e.button!==0)return;drag={px:e.clientX,py:e.clientY,x,y};stage.setPointerCapture(e.pointerId);};
   stage.onpointermove=e=>{if(drag){x=drag.x+e.clientX-drag.px;y=drag.y+e.clientY-drag.py;paint();}};
   stage.onpointerup=stage.onpointercancel=()=>{drag=null;};
   stage.ondblclick=fit;
 }
 dialog.querySelectorAll('[data-zoom]').forEach(b=>b.onclick=()=>{if(b.dataset.zoom==='fit')fit();else if(b.dataset.zoom==='actual'){scale=1;x=y=0;paint();}else zoom(b.dataset.zoom==='in'?1.25:.8);});
 const previous=document.activeElement;
 dialog.querySelector('[data-close]').onclick=()=>dialog.close();
 dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});
 dialog.addEventListener('close',()=>{if(kind==='video'){content.pause();if(source)source.currentTime=content.currentTime;content.removeAttribute('src');content.load();}dialog.remove();previous?.focus();},{once:true});
 dialog.addEventListener('keydown',e=>{e.stopPropagation();if(kind!=='video'&&['+','-','0'].includes(e.key)){e.preventDefault();e.key==='0'?fit():zoom(e.key==='+'?1.25:.8);}});
 document.body.append(dialog);dialog.showModal();return {dialog,stage,status};
}

document.addEventListener('click',async e=>{
 const image=e.target.closest('.chat-image,.cymd-preview img'),video=e.target.closest('[data-media-video]'),doc=e.target.closest('[data-media-document]');
 if(!image&&!video&&!doc)return;
 e.preventDefault();e.stopImmediatePropagation();
 if(image){if(image.currentSrc||image.src)openMediaViewer(image.currentSrc||image.src,'image',image.alt);return;}
 if(video){openMediaViewer(video.dataset.mediaVideo,'video',video.dataset.mediaName,video.closest('.chat-attachment')?.querySelector('video'));return;}
 const conversation=state.conversation;
 try{
  if(cymdEnabled()){await openCymdEditor(doc.dataset.mediaDocument);return;}
  await action('open_cymd',{conversation_id:conversation,id:doc.dataset.mediaDocument});
 }catch(error){fail(error);}
},true);

async function openLocalAsset(path){
 const conversation=state.conversation;
 if(/\.(glb|gltf|obj|stl|ply)$/i.test(path)){
  const module=await import('/mesh-viewer.js');return module.openMesh({path,conversation});
 }
 const dialog=document.createElement('dialog');dialog.className='media-viewer';
 dialog.innerHTML=ui('<header><strong></strong><button data-close>✕</button></header><div class="row-actions"><button data-open>Ouvrir avec Windows</button><button data-reveal>Afficher dans l’Explorateur</button></div><p role="status"></p>');
 dialog.querySelector('strong').textContent=path;
 for(const [selector,op] of [['[data-open]','open_local'],['[data-reveal]','reveal_local']])dialog.querySelector(selector).onclick=async()=>{try{await action(op,{conversation_id:conversation,path});}catch(e){dialog.querySelector('p').textContent=e.message;dialog.querySelector('p').className='media-error';}};
 dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.onclose=()=>dialog.remove();document.body.append(dialog);dialog.showModal();
}
document.addEventListener('click',async e=>{const b=e.target.closest('[data-mesh-id]');if(!b)return;try{const module=await import('/mesh-viewer.js');await module.openMesh({id:b.dataset.meshId,name:b.dataset.meshName,conversation:state.conversation});}catch(err){fail(err);}});

let activeFileMenu=null, fileMenuOrigin=null;
function closeFileMenu(restore=false){activeFileMenu?.remove();activeFileMenu=null;if(restore)fileMenuOrigin?.focus();fileMenuOrigin=null;}
document.addEventListener('contextmenu',e=>{
 const el=e.target.closest('[data-local-link],.chat-image,.chat-attachment a[href],.chat-video,[data-media-video],.chat-attachment');if(!el)return;
 let path=el.dataset.localLink||el.dataset.originalLocalPath||el.dataset.localPreview;
 const url=el.getAttribute('href')||el.getAttribute('src')||el.dataset.mediaVideo||'';
 const id=url.match(/^\/media\/([a-f0-9]{32})/)?.[1]||el.closest('.chat-attachment')?.dataset.fileId;if(!path&&!id)return;
 e.preventDefault();closeFileMenu();fileMenuOrigin=el;const menu=document.createElement('div');menu.className='file-menu';menu.setAttribute('role','menu');activeFileMenu=menu;
 const data={conversation_id:el.closest('.chat-attachment')?.dataset.fileConversation||state.conversation,...(path?{path}:{id})};
 const items=[[ui('Afficher dans l’Explorateur'),()=>action('reveal_local',data)],[ui('Ouvrir en externe'),()=>action('open_local',data)],[ui('Copier le lien du fichier'),()=>navigator.clipboard.writeText(path||new URL('/media/'+id,location.href).href)]];
 for(const [label,run] of items){const button=document.createElement('button');button.textContent=label;button.setAttribute('role','menuitem');button.onclick=async()=>{closeFileMenu();try{await run();}catch(error){fail(error);}};menu.append(button);}
 document.body.append(menu);menu.style.left=Math.max(0,Math.min(e.clientX,innerWidth-menu.offsetWidth-8))+'px';menu.style.top=Math.max(0,Math.min(e.clientY,innerHeight-menu.offsetHeight-8))+'px';menu.querySelector('button').focus();
});
document.addEventListener('pointerdown',e=>{if(activeFileMenu&&!activeFileMenu.contains(e.target))closeFileMenu();});
document.addEventListener('keydown',e=>{
 if(!activeFileMenu)return;
 if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeFileMenu(true);return;}
 const buttons=[...activeFileMenu.querySelectorAll('button')],index=buttons.indexOf(document.activeElement);
 if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();buttons[e.key==='Home'?0:e.key==='End'?buttons.length-1:(index+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length]?.focus();}
});window.addEventListener('blur',closeFileMenu);
