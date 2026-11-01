'use strict';
async function openAnnotationEditor(){
 const conversation=state.conversation;if(!conversation)throw new Error('Ouvrez une conversation.');
 const saved=await action('annotation_list',{conversation_id:conversation});
 const archives=(state.detail?.files||[]).filter(f=>f.kind==='media'&&/\.cyannota(?:\.zip)?$/i.test(f.name));
 const modal=document.createElement('dialog');modal.className='annotation-modal';
 modal.innerHTML=`<header><h2><img src="/cyannota/cyannota-logo.png" alt=""> CyAnnota</h2><span class="annotation-status">Collez ou déposez vos médias, puis cliquez sur Envoyer.</span><button type="button" class="secondary annotation-close">Fermer</button></header><div class="annotation-existing">${archives.map(f=>`<button class="text-button" data-archive-open="${f.id}">Reprendre ${esc(f.name)}</button>`).join('')}${saved.items.map(f=>`<button class="text-button" data-annotation-open="${f.id}">Reprendre ${esc(f.name)}</button>`).join('')}</div><iframe title="Éditeur CyAnnota" allow="clipboard-read; clipboard-write; fullscreen"></iframe>`;
 document.body.append(modal);modal.showModal();
 const frame=modal.querySelector('iframe'),notice=modal.querySelector('.annotation-status'),close=modal.querySelector('.annotation-close');
 let session,attachment,file,documentValue,mediaKind='project',saving=false;
 function load(next,kind='project',doc){file=next;mediaKind=kind;documentValue=doc;session=crypto.randomUUID();attachment=crypto.randomUUID();frame.src='/cyannota/?'+new URLSearchParams({integration:'cyai',integrationName:'CyAI',session,attachmentId:attachment,parentOrigin:location.origin,display:'iframe'});}
 function reply(ok,error){frame.contentWindow.postMessage({source:'cyai',type:'send-result-ack',protocol:'cyannota.integration',protocolVersion:2,session,ok,error,revision:Date.now()},location.origin);}
 async function receive(event){
  const m=event.data;if(event.origin!==location.origin||event.source!==frame.contentWindow||m?.source!=='cyannota'||m.session!==session||m.protocol!=='cyannota.integration')return;
  if(m.type==='ready'){
   frame.contentWindow.postMessage({source:'cyai',type:file?'open-media':'open-workspace',protocol:'cyannota.integration',protocolVersion:2,session,attachmentId:attachment,title:file?.name,mediaKind,file:file||new File([],"workspace.cyannota",{type:"application/x-cyannota"}),document:documentValue,locale:'fr',exportAudience:'ai',exportContainer:'zip',includeOriginalVideos:false,resultMode:'archive',closeOnSend:false,maximumResultBytes:256*1024**2,maximumDocumentBytes:10000000},location.origin);frame.focus();
  }
  if(m.attachmentId!==attachment)return;
  if(m.type==='integration-closed'&&!saving)modal.close();
  if(m.type==='send-result'&&!saving){
   saving=true;close.disabled=true;let uploaded;
   try{
    if(!(m.archive instanceof Blob)||!m.archive.size)throw Error('CyAnnota n’a pas transmis d’archive.');
    if(m.archive.size>256*1024**2)throw Error('Archive limitée à 256 Mo.');
    notice.textContent='Transfert des annotations vers la conversation…';
    const name=String(m.archiveName||'annotations.cyannota.zip');
    const response=await fetch('/api/upload?conversation_id='+conversation+'&name='+encodeURIComponent(name),{method:'POST',headers:{'X-CyAI':'1','Content-Type':'application/octet-stream'},body:m.archive});
    const result=await response.json();if(!response.ok)throw Error(result.error||'Transfert refusé.');uploaded=result.id;
    const delivery=await action('annotation_receive',{conversation_id:conversation,id:uploaded});
    addDraftFiles(conversation,delivery.ids);if(state.conversation===conversation)await refresh(true);
    reply(true);toast(`CyAnnota : annotations, ${delivery.images} image(s) et ${delivery.models||0} modèle(s) 3D jointes au prochain message.`);modal.close();
   }catch(err){if(uploaded)await action('delete_file',{conversation_id:conversation,id:uploaded}).catch(()=>{});notice.textContent=err.message;reply(false,err.message);}
   finally{saving=false;close.disabled=false;}
  }
 }
 window.addEventListener('message',receive);modal.addEventListener('close',()=>{window.removeEventListener('message',receive);modal.remove();});
 modal.addEventListener('cancel',e=>{if(saving)e.preventDefault();});close.onclick=()=>modal.close();
 modal.querySelectorAll('[data-archive-open]').forEach(b=>b.onclick=async()=>{try{const row=archives.find(f=>f.id===b.dataset.archiveOpen);const r=await fetch('/media/'+row.id);if(!r.ok)throw Error('Archive indisponible.');load(new File([await r.blob()],row.name,{type:'application/zip'}));}catch(e){notice.textContent=e.message;}});
 modal.querySelectorAll('[data-annotation-open]').forEach(b=>b.onclick=async()=>{try{const r=await action('annotation_open',{conversation_id:conversation,id:b.dataset.annotationOpen});const blob=await (await fetch(r.image)).blob();load(new File([blob],r.name,{type:blob.type}),'image',r.document);}catch(e){notice.textContent=e.message;}});
 load();
}
