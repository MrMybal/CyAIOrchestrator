'use strict';
function storedJSON(storage,key,fallback){
 try{const value=JSON.parse(storage.getItem(key));return value&&typeof value===typeof fallback&&Array.isArray(value)===Array.isArray(fallback)?value:fallback;}catch{return fallback;}
}
const conversationDrafts=storedJSON(sessionStorage,'cyai-drafts',{});
const conversationFileDrafts=storedJSON(sessionStorage,'cyai-file-drafts',{});
const composerRequests=new Set();
function draftKey(conversation=state.conversation,project=state.project){return conversation||'project:'+project;}
function persistDrafts(){
 try{sessionStorage.setItem('cyai-drafts',JSON.stringify(conversationDrafts));sessionStorage.setItem('cyai-file-drafts',JSON.stringify(conversationFileDrafts));}catch{/* An unavailable browser store must not interrupt editing or sending. */}
}
function rememberDraft(){
 if(!$('instruction'))return;
 const key=draftKey();conversationDrafts[key]=$('instruction').value;conversationFileDrafts[key]=[...state.files];persistDrafts();
}
function draftFiles(key){return Array.isArray(conversationFileDrafts[key])?conversationFileDrafts[key].filter(id=>typeof id==='string'):[];}
function restoreDraft(){
 const key=draftKey();$('instruction').value=typeof conversationDrafts[key]==='string'?conversationDrafts[key]:'';state.files=new Set(draftFiles(key));
}
function addDraftFiles(conversation,ids){
 const key=draftKey(conversation);if(state.conversation===conversation)rememberDraft();
 conversationFileDrafts[key]=[...new Set([...draftFiles(key),...ids])];persistDrafts();
 if(state.conversation===conversation)state.files=new Set(conversationFileDrafts[key]);
}
function removeDraftFiles(conversation,ids){
 const key=draftKey(conversation);if(state.conversation===conversation)rememberDraft();
 const removed=new Set(ids);conversationFileDrafts[key]=draftFiles(key).filter(id=>!removed.has(id));persistDrafts();
 if(state.conversation===conversation)state.files=new Set(conversationFileDrafts[key]);
}
function consumeDraft(key,text,ids){
 const current=key===draftKey();if(current)rememberDraft();
 if(conversationDrafts[key]===text)conversationDrafts[key]='';
 const sent=new Set(ids);conversationFileDrafts[key]=draftFiles(key).filter(id=>!sent.has(id));persistDrafts();
 if(current){if($('instruction').value===text)$('instruction').value='';state.files=new Set(conversationFileDrafts[key]);}
}
function renderComposerPending(){
 const send=$('composer')?.querySelector('[type=submit]');if(!send)return;
 const pending=composerRequests.has(draftKey()),loading=Boolean(state.conversation&&(state.loadingConversation||!state.detail));
 send.disabled=pending||loading||Boolean(state.detail?.archived);send.setAttribute('aria-busy',String(pending));
 send.textContent=pending?'…':'↑';
 if(pending||loading){send.title=pending?'Envoi en cours…':'Chargement de la conversation…';send.setAttribute('aria-label',send.title);}
}
// The conversation tabs were replaced by the channels of the project; a new window is opened from the rail.
function renderConversationTabs(){$('conversation-tabs')?.remove();}
document.addEventListener('input',e=>{if(e.target.id==='instruction')rememberDraft();});
window.addEventListener('beforeunload',rememberDraft);
document.addEventListener('click',async e=>{
 const b=e.target.closest('button');if(!b)return;
 try{
  if(b.hasAttribute('data-new-window')){
   rememberDraft();const id=state.conversation||'';
   if(window.pywebview?.api?.open_window)await window.pywebview.api.open_window(id);
   else window.open('/?conversation='+encodeURIComponent(id),'_blank','noopener');
  }
 }catch(error){fail(error);}
});
