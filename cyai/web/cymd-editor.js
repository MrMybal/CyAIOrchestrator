'use strict';
function cymdEnabled(){return (state.data.plugins||[]).some(p=>p.id==='cymd'&&p.enabled&&p.projects?.[state.project]?.enabled!==false);}
async function openCymdEditor(id){
 const conversation=state.conversation;
 const info=await action('cymd_open',{conversation_id:conversation,id});
 let file=new Blob([''],{type:'text/markdown'});
 if(info.url){const response=await fetch(info.url);if(!response.ok)throw Error('Document indisponible.');file=await response.blob();}
 if(file.size>50*1024**2)throw Error('Document limité à 50 Mo.');
 const modal=document.createElement('dialog');modal.className='annotation-modal';
 modal.innerHTML='<header><h2>CyMD</h2><span class="annotation-status">Enregistrer ajoute une nouvelle pièce jointe à la conversation.</span><button type="button" class="secondary cymd-save">Enregistrer dans CyAI</button><button type="button" class="secondary cymd-close">Fermer</button></header><iframe title="Éditeur CyMD" allow="clipboard-read; clipboard-write"></iframe>';
 const frame=modal.querySelector('iframe'),notice=modal.querySelector('.annotation-status'),save=modal.querySelector('.cymd-save');
 const session=crypto.randomUUID();let dirty=false,saving=false,ready=false;
 const send=(type,payload={})=>frame.contentWindow.postMessage({protocol:'cymd.integration',version:1,session,source:'host',type,...payload},location.origin);
 const close=()=>{if(saving)return;if(dirty&&!confirm('Des modifications ne sont pas enregistrées. Les abandonner ?'))return;modal.close();};
 const receive=async event=>{
  const m=event.data;
  if(event.origin!==location.origin||event.source!==frame.contentWindow||m?.source!=='cymd'||m.protocol!=='cymd.integration'||m.version!==1||m.session!==session)return;
  if(m.type==='ready'&&!ready){ready=true;send('open',{name:info.name,file,locale:document.documentElement.lang?.startsWith('en')?'en':'fr'});save.disabled=false;}
  if(m.type==='state')dirty=m.dirty===true;
  if(m.type==='close-request')close();
  if(m.type==='error')notice.textContent=String(m.message);
  if(m.type==='save'){
   if(typeof m.requestId!=='string')return;
   if(saving){send('save-result',{requestId:m.requestId,ok:false,error:'Une sauvegarde est déjà en cours.'});return;}
   saving=true;save.disabled=true;
   try{
    if(!(m.file instanceof Blob)||!m.file.size||m.file.size>50*1024**2||typeof m.name!=='string'||! /\.(cymd|md|markdown)$/i.test(m.name))throw Error('Document invalide ou trop volumineux.');
    await action('cymd_open',{conversation_id:conversation});
    const response=await fetch('/api/upload?conversation_id='+encodeURIComponent(conversation)+'&name='+encodeURIComponent(m.name),{method:'POST',headers:{'X-CyAI':'1','Content-Type':'application/octet-stream'},body:m.file});
    const result=await response.json();if(!response.ok)throw Error(result.error||'Enregistrement refusé.');
    send('save-result',{requestId:m.requestId,ok:true});
    notice.textContent='Enregistré dans la conversation : '+result.name;
    addDraftFiles(conversation,[result.id]);if(state.conversation===conversation)await refresh(true);
   }catch(error){notice.textContent=error.message;send('save-result',{requestId:m.requestId,ok:false,error:error.message});}
   finally{saving=false;save.disabled=false;}
  }
 };
 window.addEventListener('message',receive);
 modal.addEventListener('close',()=>{window.removeEventListener('message',receive);modal.remove();});
 modal.addEventListener('cancel',event=>{event.preventDefault();close();});
 modal.addEventListener('keydown',event=>event.stopPropagation());
 modal.querySelector('.cymd-close').onclick=close;
 save.disabled=true;save.onclick=()=>send('command',{command:'save'});
 document.body.append(modal);modal.showModal();
 frame.src='/cymd/?'+new URLSearchParams({integration:'1',parentOrigin:location.origin,session});
}
