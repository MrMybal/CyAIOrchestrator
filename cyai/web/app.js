'use strict';
const failureNotices = new Set();
const failureQueue = [];
function errorExplanation(text) {
  if (/Interruption du service détectée/i.test(text)) return text;
  if (/réglage de vitesse/i.test(text)) return 'Un réglage Codex a été transmis à un autre connecteur. Le correctif empêche cet héritage incompatible ; reprenez après installation de la mise à jour.';
  if (/Durée maximale/i.test(text)) return 'La limite de temps configurée dans CyAI a été atteinte. Ce message ne signifie pas que le modèle était inactif. Vérifiez les effets déjà produits et choisissez une durée plus longue pour reprendre.';
  if (/is archived|session not found|thread not found|no rollout found/i.test(text)) return 'La session Codex est archivée ou introuvable. Reprenez : CyAI essaiera de la restaurer, puis ouvrira si nécessaire une nouvelle session avec le contexte conservé dans cette conversation.';
  if (/already has an active writer/i.test(text)) return 'Cette session Codex est déjà utilisée par une autre instance. Vérifiez si cet agent travaille encore avant de reprendre, afin de ne pas doubler ses actions.';
  return /apply deny-read ACLs|fs sandbox helper failed/i.test(text)
    ? 'Codex ne peut pas démarrer son environnement Windows : l’application des droits d’accès du sandbox a échoué. Aucune réponse n’a été produite. La protection des fichiers reste active.'
    : 'L’exécution a échoué. Consultez les détails avant de reprendre.';
}
function failureCard(f) {
  return `<article class="message execution-failure" role="alert"><div class="message-header"><strong>${f.data?.status==='interrupted'?'⚠ Travail interrompu — reprise à examiner':'⚠ Exécution échouée'}</strong><time class="message-time">${date(f.created_at)}</time></div><p class="operation-error">${esc(errorExplanation(f.content))}</p><details><summary>Détails techniques</summary><pre>${esc(f.content)}</pre></details><button class="secondary" data-retry="${esc(f.mission_id)}">Examiner et reprendre</button><button type="button" class="secondary" data-discuss-error="${esc(f.content)}">Diagnostiquer avec l’IA</button></article>`;
}
function showFailurePopup(text) {
  failureQueue.push(text);
  drainFailureQueue();
}
function drainFailureQueue() {
  if (!failureQueue.length || document.querySelector('dialog[open]')) return;
  const text = failureQueue.shift();
  const failure=state.detail?.failures?.findLast(f=>f.data.error===text);
  openDialog('Exécution échouée', `<button type="button" class="secondary" data-discuss-error="${esc(text)}">Diagnostiquer avec l’IA dans la conversation</button><p class="operation-error">${esc(errorExplanation(text))}</p><details open><summary>Détails techniques</summary><pre class="failure-details">${esc(text)}</pre></details><p>Votre conversation et ses messages sont conservés.</p>${failure?`<button class="primary" type="button" data-retry="${esc(failure.mission_id)}">Reprendre avec récupération de session</button>`:''}`, null);
}
function notifyFailures() {
  const failures=state.detail?.failures||[];
  const unseen=failures.filter(f=>!failureNotices.has(f.seq));
  for(const f of failures) failureNotices.add(f.seq);
  if(unseen.length) showFailurePopup(unseen[unseen.length-1].data.error||'Erreur inconnue.');
  drainFailureQueue();
}
const $ = id => document.getElementById(id);
const L = CYAI_LOCALES[CYAI_LOCALE];
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const active = status => ['queued','running','awaiting_approval','pausing'].includes(status);
const status = value => `<span class="status ${esc(value)}">${esc(L.states[value] || L.connections[value] || value)}</span>`;
const agentName = id => id==='local'?'CyAI · local':L.agents[id] || id;
const date = value => new Date(value).toLocaleString('fr-FR',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const state = {data:null,project:localStorage.getItem('cyai-project'),conversation:new URLSearchParams(location.search).get('conversation')||(sessionStorage.getItem('cyai-conversation')??localStorage.getItem('cyai-conversation')),view:'chat',detail:null,mission:null,missionId:null,archives:false,selected:new Set(),files:new Set(),polling:false,dialogSubmit:null};
state.collapsedProjects=new Set(storedJSON(localStorage,'cyai-collapsed-projects',[]).filter(id=>typeof id==='string'));
state.navigationVersion=0;state.conversationVersion=0;
// The right panel shows the members, the conversation details, or nothing. Clicking the selected icon closes it.
state.rightPanel=['members','details','none'].includes(localStorage.getItem('cyai-right-panel'))?localStorage.getItem('cyai-right-panel'):'members';
state.inspectorHidden=state.rightPanel!=='details';
function renderInspectorVisibility(){const hidden=state.rightPanel!=='details',label=hidden?'Détails de conversation':'Masquer les détails';state.inspectorHidden=hidden;$('workspace').classList.toggle('inspector-collapsed',hidden);$('toggle-inspector').title=label;$('toggle-inspector').setAttribute('aria-label',label);$('toggle-inspector').classList.toggle('active',!hidden);$('toggle-inspector').setAttribute('aria-expanded',String(!hidden));$('toggle-inspector').hidden=state.view!=='chat';}
function setRightPanel(panel){state.rightPanel=state.rightPanel===panel?'none':panel;localStorage.setItem('cyai-right-panel',state.rightPanel);renderInspectorVisibility();renderShell();}
$('toggle-inspector').onclick=()=>setRightPanel('details');
function htmlIfChanged(id,html){const el=$(id);if(el._rendered!==html){const top=el.scrollTop;el.innerHTML=html;el._rendered=html;if(id==='messages'&&state.followChat===false)el.scrollTop=top;}}
async function api(path, data) {
  const options={headers:{'Content-Type':'application/json','X-CyAI':'1'}, ...(data === undefined ? {} : {method:'POST',body:JSON.stringify(data)})};
  let response;
  try{response=await fetch('/api/'+path,options);if(response.status===403){await fetch('/');response=await fetch('/api/'+path,options);}}
  catch(error){error.connection=true;throw error;}
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Le service ne répond pas.');
  return result;
}
const action = (name,data={}) => api('action',{action:name,data});
function toast(message) { $('toast').textContent=message; $('toast').hidden=false; clearTimeout(toast.timer); toast.timer=setTimeout(()=>$('toast').hidden=true,5000); }
function fail(error) { showFailurePopup(error.message || String(error)); }
function contextOptions() { return {...(state.selected.size ? {message_ids:[...state.selected]} : {}), file_ids:[...state.files]}; }
function connectorOptions(value='codex') { return Object.entries({...L.agents,local:'CyAI · local'}).map(([id,name])=>`<option value="${id}" ${id===value?'selected':''}>${name}</option>`).join(''); }
function projectOptions(selected=state.project) { return state.data.projects.filter(p=>!p.free_chat).map(p=>`<option value="${p.id}" ${p.id===selected?'selected':''}>${esc(p.name)}</option>`).join(''); }
function openDialog(title,html,onSubmit,label='Enregistrer') {
  state.dialogVersion = (state.dialogVersion || 0) + 1;
  $('submit-dialog').disabled = false;
  $('dialog').classList.remove('web-plugin-dialog');
  $('dialog-title').classList.toggle('operation-error', title === 'Exécution échouée');
  $('dialog-title').textContent=title; $('dialog-content').innerHTML=html; $('dialog-error').textContent=''; $('submit-dialog').textContent=label;
  $('submit-dialog').hidden=!onSubmit; $('cancel-dialog').textContent=onSubmit?'Annuler':'Fermer'; state.dialogSubmit=onSubmit; $('dialog').showModal();
}
$('close-dialog').onclick=$('cancel-dialog').onclick=()=>$('dialog').close();
$('dialog').addEventListener('close',()=>setTimeout(drainFailureQueue,0));
$('dialog-form').onsubmit=async e=>{
 e.preventDefault();if(!state.dialogSubmit||$('submit-dialog').disabled)return;
 const version=state.dialogVersion,submit=state.dialogSubmit,b=$('submit-dialog'),label=b.textContent;
 b.disabled=true;b.textContent='Enregistrement…';
 try{await submit(new FormData(e.target));if(version===state.dialogVersion)$('dialog').close();await refresh(true);}
 catch(err){if(version===state.dialogVersion)$('dialog-error').textContent=err.message;else fail(err);}
 finally{if(version===state.dialogVersion){b.disabled=false;b.textContent=label;}}
};

function newProject() {
  appearanceDraft={current:'',fileLogo:'',name:''};
  openDialog('Ajouter un projet',`<p>Choisissez le dossier de votre projet ou saisissez son chemin. Aucun réglage de configuration n’est nécessaire.</p>${logoPreviewHTML()}<div class="fields"><label>Nom du projet<input name="name" placeholder="Mon application" required autofocus></label><label>Dossier de travail<input name="root" id="project-root-input" placeholder="D:\\Mes projets\\Mon application" required></label><button type="button" id="browse-project" class="secondary">Parcourir…</button><div class="field-help">Le dossier choisi sera enregistré pour ce projet. Son contenu reste local jusqu’à sa transmission à un agent.</div>${appearanceFieldsHTML({color:'#b6a1f4',icon:'',category:''})}<label class="assistant-option"><span><input type="checkbox" name="assistant" checked> Ouvrir l’assistant du projet : une conversation pour le mettre en place — reprise ou nouveau projet, présentation, consignes, équipe</span></label></div>`,async form=>{const category=String(form.get('category')||'').trim();const result=await action('create_project',{name:form.get('name'),root:form.get('root'),color:form.get('color'),icon:appearanceValue(form),category,assistant:!!form.get('assistant')});state.project=result.id;state.home=false;state.conversation=null;state.detail=null;localStorage.setItem('cyai-project',state.project);sessionStorage.setItem('cyai-conversation','');toast('Projet ajouté.');if(result.assistant_conversation_id)setTimeout(async()=>{try{for(let i=0;i<40&&!state.data.projects.some(p=>p.id===result.id);i++)await new Promise(r=>setTimeout(r,100));await selectConversation(result.assistant_conversation_id);}catch(err){fail(err);}},0);},'Créer le projet');
  paintLogoPreview();
  $('browse-project').onclick=async()=>{const button=$('browse-project');button.disabled=true;button.textContent='Sélectionnez un dossier dans Windows…';try{const result=await action('choose_project_folder');if(result.root){$('project-root-input').value=result.root;const name=$('dialog-form').elements.namedItem('name');if(!name.value)name.value=result.name;paintLogoPreview();}}catch(err){$('dialog-error').textContent=err.message;}finally{button.disabled=false;button.textContent='Parcourir…';}};
}
function newConversation(projectId) {
  if (!state.data.projects.some(p=>!p.free_chat)) return newProject();
  openDialog('Nouvelle conversation',`<div class="fields"><label>Projet<select name="project_id">${projectOptions(typeof projectId==='string'?projectId:state.project)}</select></label><label>Type de conversation<select name="mode"><option value="chat">Normal · un agent à la fois, mémoire du projet</option><option value="orchestrator">Orchestrateur multi-modèles · plan à autoriser</option></select></label><label>Titre<input name="title" placeholder="Sur quoi travaillons-nous ?" required autofocus></label></div>`,async form=>{const values=Object.fromEntries(form);const result=await action('create_conversation',values);state.project=values.project_id;await selectConversation(result.id);},'Créer la conversation');
}
function newFreeConversation(){
 openDialog('Nouvelle discussion libre','<p>Discutez avec un agent sans choisir de projet. Cette discussion conserve son propre historique et ses pièces jointes.</p><label>Titre<input name="title" placeholder="Discussion libre" autofocus></label>',async form=>{const r=await action('create_free_conversation',{title:form.get('title')});await refresh(true);await selectConversation(r.id);},'Créer la discussion');
}
$('new-project').onclick=newProject;
$('toggle-archives').onclick=()=>{state.archives=!state.archives;$('toggle-archives').title=state.archives?'Masquer les archives':'Afficher les archives';renderSidebar();};
function renderSidebar() {
  renderConversationTabs();
  renderShell();paintProjectColors();
  $('project-name').textContent=state.data.projects.find(p=>p.id===state.project)?.name||'Aucun projet';
  document.querySelectorAll('.nav[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===state.view));
}
async function selectConversation(id) {
  rememberDraft();const request=++state.conversationVersion;
  state.conversation=id;state.loadingConversation=id;state.conversationLoadError='';state.pinnedMission=null;state.selected.clear();state.missionId=null;state.mission=null;state.detail=null;
  restoreDraft();sessionStorage.setItem('cyai-conversation',id);showView('chat');
  const navigation=state.navigationVersion;
  try{
    const detail=await api('conversation/'+id);
    if(request!==state.conversationVersion||state.conversation!==id)return;
    state.loadingConversation=null;
    // Returning to this chat is an explicit navigation, never a side effect of a late read.
    if(navigation!==state.navigationVersion||state.view!=='chat')return;
    state.detail=detail;state.project=detail.project_id;
    if(detail.agent_id){$('agent').value=detail.agent_id;$('model').value=detail.agent_model||'';renderRuntimeOptions();}
    state.collapsedProjects.delete(state.project);localStorage.setItem('cyai-collapsed-projects',JSON.stringify([...state.collapsedProjects]));localStorage.setItem('cyai-project',state.project);
    renderMessages();await refresh(true);
  }catch(error){
    if(request!==state.conversationVersion||state.conversation!==id||navigation!==state.navigationVersion)return;
    state.loadingConversation=null;state.conversationLoadError=error.message;renderMessages();
  }finally{renderComposerPending();}
}
function showView(view) {
  const navigation=++state.navigationVersion;
  if(view==='connectors'){view='settings';state.settingsTab='connectors';}
  if(state.view!==view)$('page')._rendered=null;
  state.view=view; renderInspectorVisibility();$('page-title').textContent=view==='chat'&&state.detail?state.detail.title:view==='project'?(state.data.projects.find(p=>p.id===state.project)?.name||'Projets'):(view==='logs'?'Logs':L.views[view]);
  $('workspace').hidden=view!=='chat'; $('page').hidden=view==='chat';renderSidebar();
  if(view==='chat'){renderMessages();renderInspector();}else renderPage().catch(error=>{if(navigation===state.navigationVersion)fail(error);});
}
document.addEventListener('click',async e=>{
  const button=e.target.closest('button');if(!button)return;
  if(button.dataset.pluginAction)return;
  try {
    if(button.id==='new-free-conversation')newFreeConversation();
    if(button.dataset.view)showView(button.dataset.view);
    if(button.dataset.project){rememberDraft();state.project=button.dataset.project;state.collapsedProjects.delete(state.project);state.conversation=null;state.detail=null;state.mission=null;state.missionId=null;state.projectTab='overview';localStorage.setItem('cyai-project',state.project);sessionStorage.setItem('cyai-conversation','');showView('project');}
    if(button.dataset.newConversation)newConversation(button.dataset.newConversation);
    if(button.dataset.collapseProject){const id=button.dataset.collapseProject;state.collapsedProjects.has(id)?state.collapsedProjects.delete(id):state.collapsedProjects.add(id);localStorage.setItem('cyai-collapsed-projects',JSON.stringify([...state.collapsedProjects]));renderSidebar();}
    if(button.dataset.projectTab){state.projectTab=button.dataset.projectTab;if(state.view!=='project')showView('project');else await renderPage();}
    if(button.dataset.projectNew)newConversation(state.project);
    if(button.dataset.projectMission)await newMission();
    if(button.dataset.approvePlan)openPlanAdjustment(state.detail.plans.find(p=>p.id===button.dataset.approvePlan));
    if(button.dataset.revisePlan){$('instruction').value='Le résultat doit être réévalué. Analyse les étapes et les erreurs précédentes, puis propose un plan corrigé. Change d’agent ou de modèle si cela améliore le résultat.';$('instruction').focus();}
    if(button.dataset.conversation)await selectConversation(button.dataset.conversation);
    if(button.dataset.branch){const r=await action('branch',{conversation_id:state.conversation,message_id:button.dataset.branch});await selectConversation(r.id);toast(r.notice);}
    if(button.dataset.pin){const msg=state.detail.messages.find(m=>m.id===button.dataset.pin);editMemory({content:msg.content,source_ids:JSON.stringify([msg.id]),validated:0});}
    if(button.dataset.mission){state.missionId=button.dataset.mission;const m=await api('mission/'+state.missionId);await selectConversation(m.conversation_id);state.missionId=m.id;state.pinnedMission=m.id;state.mission=m;renderInspector();if(innerWidth<851)openDialog(m.title,missionHTML(m),null);}
    if(button.dataset.pauseChain){await action('pause_mission',{mission_id:button.dataset.pauseChain});toast('Pause demandée : les étapes actives vont se terminer.');await refresh(true);}
    if(button.dataset.resumeChain){await action('resume_mission',{mission_id:button.dataset.resumeChain});state.missionId=button.dataset.resumeChain;await refresh(true);}
    if(button.dataset.cancel){await action('cancel_mission',{mission_id:button.dataset.cancel});toast('Annulation transmise au connecteur.');await refresh(true);}
    if(button.dataset.discussError){if($('dialog').open)$('dialog').close();$('instruction').value='Aide-moi à résoudre le problème suivant dans cette conversation. Analyse les éléments disponibles, distingue ce qui est confirmé de ce qui reste à vérifier et propose une solution concrète. Ne relance pas la mission et ne répète pas ses actions pendant le diagnostic.\n\nErreur enregistrée :\n'+button.dataset.discussError;rememberDraft();$('instruction').focus();toast('Demande préparée : vous pouvez la compléter et choisir votre IA avant de l’envoyer.');}
    if(button.dataset.retry){const recovery=await api('mission/'+encodeURIComponent(button.dataset.retry));if($('dialog').open)$('dialog').close();openDialog(isTaskChain(recovery)?'Reprendre la mission':'Reprendre la réponse',`<button type="button" class="secondary" data-discuss-error="${esc(recovery.steps.filter(s=>s.error).map(s=>s.name+' : '+s.error).join('\n')||'Mission '+recovery.title+' : '+recovery.status)}">Diagnostiquer avec l’IA</button><p>${recovery.status==='interrupted'?'Une interruption a été détectée. La cause exacte n’est pas confirmée. Vérifiez aussi que les agents externes ne travaillent plus.':''}</p><ul>${recovery.steps.map(s=>`<li>${esc(s.name)} : ${esc(L.states[s.status]||s.status)}${s.error?' — '+esc(s.error):''}</li>`).join('')}</ul><details><summary>Derniers événements enregistrés</summary><pre>${esc(recovery.events.slice(-12).map(e=>e.created_at+' · '+e.kind+' · '+JSON.stringify(e.data)).join('\n'))}</pre></details><p>Vérifiez les effets de la dernière tentative dans le projet. La reprise réexécutera uniquement les étapes non réussies. Elle ne restaure aucun fichier.</p><label ${isTaskChain(recovery)?'':'hidden'}>Agents simultanés<input name="concurrency" type="number" min="1" max="32" value="${recovery.spec.concurrency||1}" required></label><p class="field-help" ${isTaskChain(recovery)?'':'hidden'}>Augmentez cette valeur pour lancer les étapes indépendantes en parallèle. Les étapes réussies restent conservées.</p><label>Durée maximale pour cette reprise (minutes, 0 = sans limite)<input name="timeout_minutes" type="number" min="0" value="0" required></label><label class="field"><span><input type="checkbox" name="ack" required> J’ai vérifié les effets déjà produits.</span></label>`,async form=>action('retry_mission',{mission_id:button.dataset.retry,acknowledged:true,timeout_seconds:Number(form.get('timeout_minutes'))*60,concurrency:Number(form.get('concurrency'))}),'Reprendre');}
    if(button.dataset.approve){await action('approve',{id:button.dataset.approve,accepted:button.dataset.accepted==='true'});await refresh(true);}
    if(button.dataset.context){const step=state.mission.steps.find(s=>s.id===button.dataset.context);openDialog('Contexte effectivement transmis',`<p>${step.context.chars.toLocaleString('fr-FR')} caractères · ${step.context.native_resume?'Session native reprise, avec son historique propre.':'Nouvelle session / reconstruction du contexte.'}</p><pre class="context-pre">${esc(step.context.text)}</pre><p>${esc(step.context.notice)}</p>`,null);}
    if(button.dataset.configure)configureConnector(button.dataset.configure);
    if(button.dataset.connect){button.disabled=true;try{const result=await action('connect_claude');if(result.status==='connected'){toast(result.detail);await refresh(true);return;}state.claudeLoginPending=true;openDialog('Connexion Claude Code',`<p>${esc(result.detail)}</p><p>Vos identifiants restent gérés par Claude Code.</p>`,async()=>{const r=await action('test_connector',{id:'claude-code'});if(r.status!=='connected')throw new Error(r.detail);toast(r.detail);},'Vérifier la connexion');}finally{button.disabled=false;}}
    if(button.dataset.test){button.disabled=true;const r=await action('test_connector',{id:button.dataset.test});toast(r.detail);await refresh(true);}
    if(button.dataset.models){button.disabled=true;const r=await action('list_models',{id:button.dataset.models});openDialog('Modèles disponibles',`<pre class="context-pre">${esc(r.models.map(m=>m.id).join('\n')||'Ce connecteur ne fournit pas de catalogue. Saisissez un identifiant de modèle dans sa configuration.')}</pre>`,null);}
    if(button.dataset.memoryEdit){editMemory(state.detail?.memory.find(m=>m.id===button.dataset.memoryEdit)||state.memory?.find(m=>m.id===button.dataset.memoryEdit));}
    if(button.dataset.memoryDelete){await action('delete_memory',{id:button.dataset.memoryDelete,project_id:state.project});await refresh(true);}
    if(button.dataset.fileDelete){const conversation=state.conversation;await action('delete_file',{id:button.dataset.fileDelete,conversation_id:conversation});removeDraftFiles(conversation,[button.dataset.fileDelete]);await refresh(true);}
    if(button.dataset.fileView){const result=await action('export',{conversation_id:state.conversation});const f=result.files.find(f=>f.id===button.dataset.fileView);openDialog(f.name,`<pre class="context-pre">${esc(f.content)}</pre>`,null);}
    if(button.id==='welcome-project')newProject();
    if(button.id==='welcome-conversation')newConversation();
    if(button.id==='add-memory')editMemory();
    if(button.id==='backup'){const backup=await action('backup');download('cyai-sauvegarde-'+new Date().toISOString().slice(0,10)+'.json',backup);}
    if(button.id==='restore')restoreDialog();
  }catch(err){fail(err);}finally{button.disabled=false;}
});
document.addEventListener('change',e=>{
  if(e.target.dataset.select){e.target.checked?state.selected.add(e.target.dataset.select):state.selected.delete(e.target.dataset.select);updateContextLabel();}
  if(e.target.dataset.file){e.target.checked?state.files.add(e.target.dataset.file):state.files.delete(e.target.dataset.file);updateContextLabel();rememberDraft();}
});
function updateContextLabel(){const label=state.selected.size?`${state.selected.size} message(s) sélectionné(s)`:'Contexte automatique';$('context-selection').innerHTML=`<span class="dot"></span> ${label}${state.files.size?' · '+state.files.size+' fichier(s)':''}<button type="button" id="preview-context" class="text-button">Inspecter le contexte ↗</button>`;$('preview-context').onclick=previewContext;}
function renderMessages(){
  if(state.scrollConversation!==state.conversation){state.scrollConversation=state.conversation;state.followChat=true;}
  $('instruction').placeholder=state.data.projects.find(p=>p.id===state.project)?.free_chat?'Discutez librement avec votre IA…':'Discutez avec votre IA et la mémoire partagée du projet…';
  renderPlan();
  renderPluginButtons();renderMediaDrafts();
  $('agent').disabled=false;$('model').disabled=false;
  $('conversation-toolbar').hidden=!state.detail; $('instruction').disabled=Boolean(state.detail?.archived);
  $('page-title').textContent=state.detail?.title||state.data.conversations.find(c=>c.id===state.conversation)?.title||L.views.chat;
  const messages=[...(state.detail?.messages||[]),...(state.detail?.failures||[]).map(f=>({...f,role:'failure',content:f.data.error||'Erreur inconnue.'}))].sort((a,b)=>a.created_at.localeCompare(b.created_at));
  if(!messages.length)$('messages')._rendered=null;
  if(!state.detail&&state.conversation){htmlIfChanged('messages',state.conversationLoadError?`<div class="empty-state" role="alert"><p>Impossible de charger cette conversation : ${esc(state.conversationLoadError)}</p><button type="button" class="secondary" data-conversation="${esc(state.conversation)}">Réessayer</button></div>`:'<div class="empty-state" role="status">Chargement de la conversation…</div>');} else if(!messages.length&&state.detail?.purpose==='assistant'){$('messages').innerHTML=assistantWelcomeHTML();} else if(!messages.length&&state.detail){$('messages').innerHTML=taskBannerHTML()+`<div class="welcome"><div class="welcome-logo"><img src="/cyai-logo.png" width="64" height="64" alt="CyAI Orchestrator"></div><div class="eyebrow">${state.detail.mode==='orchestrator'?'ORCHESTRATEUR DU PROJET':(state.data.projects.find(p=>p.id===state.project)?.free_chat?'DISCUSSION LIBRE':'DISCUSSION DU PROJET')}</div><h2>${state.detail.mode==='orchestrator'?'Quel travail souhaitez-vous organiser ?':'De quoi souhaitez-vous discuter ?'}</h2><p>${state.detail.mode==='orchestrator'?'Discutez de votre objectif. Votre orchestrateur proposera un graphe de tâches avec les agents et modèles choisis. Vous autoriserez ensuite son exécution.':(state.data.projects.find(p=>p.id===state.project)?.free_chat?'Une discussion indépendante, avec son propre historique et ses pièces jointes. Choisissez votre IA.':'Cette conversation utilise la mémoire validée du projet. Choisissez votre IA et écrivez votre premier message.')}</p></div>`;} else if(!messages.length){$('messages').innerHTML=`<div class="welcome"><div class="welcome-logo"><img src="/cyai-logo.png" width="64" height="64" alt="CyAI Orchestrator"></div><div class="eyebrow">VOTRE ESPACE D’INTELLIGENCE</div><h2>Plusieurs agents.<br><em>Un même fil de travail.</em></h2><p>Imaginez, construisez et vérifiez avec les agents de votre choix. Votre contexte, vos décisions et vos résultats restent réunis.</p><div class="welcome-cards"><button class="welcome-card" id="${state.data.projects.length?'welcome-conversation':'welcome-project'}"><span>＋</span>${state.data.projects.length?'Ouvrir une conversation':'Créer votre premier projet'}<small>Un dossier local, un historique durable.</small></button><button class="welcome-card" data-view="connectors"><span>⊞</span>Connecter vos agents<small>Codex, Claude Code, OpenCode et API.</small></button></div><p class="welcome-note">Aucune donnée de démonstration. Votre espace est prêt pour votre premier travail.</p></div>`;
  } else {
    const panel=$('messages');
    htmlIfChanged('messages',taskBannerHTML()+messages.map((m,i)=>m.role==='failure'?failureCard(m):`<article class="message ${m.role} role-${messageAuthor(m).role} ${messageGrouped(messages,i)?'grouped':''} ${state.selected.has(m.id)?'in-context':''}"><div class="message-header"><span class="avatar ${m.role==='user'?'user':''}">${esc(messageAuthor(m).initial)}</span><span class="agent-name">${esc(messageAuthor(m).name)}</span>${m.input==='voice'?'<span class="voice-tag" title="Message dicté">🎙 voix</span>':''}${m.model?`<span class="model-tag">${esc(m.model)}</span>`:''}<time class="message-time">${date(m.created_at)}</time></div><div class="message-body">${richText(m.role==='assistant'?displayMessage(m.content):m.content)}${messageMedia(m.id,m.source_id)}</div><div class="message-tools" role="toolbar" aria-label="Actions du message"><button type="button" class="tool-icon" data-msg-reply="${m.id}" title="Répondre : citer ce message dans la saisie" aria-label="Répondre">↩</button><button type="button" class="tool-icon" data-msg-copy="${m.id}" title="Copier le texte" aria-label="Copier">⧉</button>${m.role==='assistant'?`<button type="button" class="tool-icon" data-msg-speak="${m.id}" title="Lire ce message à voix haute" aria-label="Lire à voix haute">🔈</button>`:''}<button type="button" class="tool-icon" data-msg-pin="${m.id}" title="Épingler dans le projet (à valider avant d’être transmis aux agents)" aria-label="Épingler">📌</button><button type="button" class="tool-icon" data-pin="${m.id}" title="Proposer en mémoire, avec relecture" aria-label="Proposer en mémoire">◇</button><button type="button" class="tool-icon" data-branch="${m.id}" title="Créer une branche à partir de ce message" aria-label="Créer une branche">⑂</button><label class="tool-check" title="Joindre ce message au contexte de la prochaine demande"><input type="checkbox" data-select="${m.id}" ${state.selected.has(m.id)?'checked':''}> Contexte</label></div>${planRequestHTML(m)}</article>`).join('')+'<div id="live-output"></div>');
    scheduleChatScroll();
  }
  if(state.detail){$('archive').textContent=state.detail.archived?'Désarchiver':'Archiver';$('conversation-subtitle').textContent=`${state.detail.mode==='orchestrator'?'Orchestrateur multi-modèles':state.detail.mode==='team'?'Équipe · révision figée du profil':(state.data.projects.find(p=>p.id===state.project)?.free_chat?'Discussion libre':'Normal')} · ${state.detail.messages.length} messages · ${state.detail.sessions.length} sessions natives${state.detail.parent_id?' · Branche de conversation':''}`;renderApprovalButton();}
  updateContextLabel();renderLive();renderRuntimeOptions();scheduleChatScroll();
}
function renderLive(){
  renderWorkStatus();
  renderThinking();
  syncPlanActivity();
  const container=$('live-output');if(!container)return;
  if(!$('live-answer'))container.innerHTML='<div id="live-answer"></div><div id="live-approvals"></div>';
  const target=$('live-answer');
  if(state.mission&&active(state.mission.status)){
    const currents=state.mission.steps.filter(s=>['running','awaiting_approval'].includes(s.status));
    htmlIfChanged('live-answer',currents.map(current=>{
      const text=state.mission.events.filter(e=>e.kind==='delta'&&e.step_id===current.id).map(e=>e.data.text).join('').replace(/<cyai-continuity>[\s\S]*?(<\/cyai-continuity>|$)/g,'');
      return `<article class="message"><div class="message-header"><span class="avatar">${esc(agentName(current.connector)[0])}</span><b>${esc(agentName(current.connector))} · ${esc(current.name)}</b>${status(current.status)}<small data-step-clock="${esc(current.id)}">${esc(taskTimeLabel(state.mission,current))}</small></div><div class="message-body">${richText(text||'En attente du prochain événement du fournisseur…')}</div></article>`;
    }).join('')||`<p>${isTaskChain(state.mission)?'Préparation des prochaines étapes…':'En attente du démarrage de la réponse…'}</p>`);
  }else htmlIfChanged('live-answer','');
  renderApprovalCards();
}
function missionHTML(m){
  const approvals=state.data.approvals.filter(a=>a.mission_id===m.id);
  return `<div class="mission-title">${esc(m.title)}</div>${status(m.status)}<div class="steps">${m.steps.map((s,i)=>`<div class="step ${s.status}"><div class="step-number">${s.status==='succeeded'?'✓':isTaskChain(m)?i+1:'•'}</div><div class="step-main"><h4>${esc(s.name)}</h4><small>${esc(agentName(s.connector))}${s.model?' · '+esc(s.model):''}</small>${status(s.status)}<small class="task-clock" data-step-clock="${esc(s.id)}">${esc(taskTimeLabel(m,s))}</small>${s.error?`<p class="error">${esc(s.error)}</p>`:''}${s.context?`<button class="text-button" data-context="${s.id}">Voir le contexte ↗</button>`:''}</div></div>`).join('')}</div>
    ${approvals.length?'<p>Les autorisations sont affichées dans la conversation.</p>':''}
    ${active(m.status)?`<button class="secondary danger" data-cancel="${m.id}">${isTaskChain(m)?'Annuler la mission':'Arrêter la réponse'}</button>`:''}${['failed','interrupted','cancelled'].includes(m.status)?`<button class="secondary" data-retry="${m.id}">Examiner et reprendre</button>`:''}
    <div class="inspector-section"><h3>OUTILS & VALIDATIONS</h3>${m.events.filter(e=>['tool','tool_result','validation','usage','error','permission_denied'].includes(e.kind)).slice(-30).map(e=>`<details class="event"><summary>${esc({tool:'↳ Outil exécuté',tool_result:'↳ Résultat d’outil',validation:'✓ Contrôle du résultat',usage:'◷ Usage fourni',error:'! Erreur',permission_denied:'! Permission refusée'}[e.kind])}</summary><pre>${esc(JSON.stringify(e.data,null,2))}</pre></details>`).join('')||'<p class="context-info">Les appels d’outils et les contrôles apparaîtront ici.</p>'}</div>`;
}
function renderInspectorBody(){
  const opened=new Set([...$('mission-panel').querySelectorAll('details[open]')].map(el=>el.dataset.event));
  const scroll=$('inspector').scrollTop;
  let html=state.mission?missionHTML(state.mission):`<div class="inspector-empty"><div class="orbit">◎</div>Aucune réponse en cours<br>Le suivi de votre conversation apparaîtra ici.</div>`;
  html+=`<div class="inspector-section"><h3>CONTEXTE PARTAGÉ</h3><div class="context-row"><span>Messages enregistrés</span><b>${state.detail?.messages.length||0}</b></div><div class="context-row"><span>Mémoires validées</span><b>${state.detail?.memory.filter(m=>m.validated).length||0}</b></div><div class="context-row"><span>Sessions d’agents</span><b>${state.detail?.sessions.length||0}</b></div><p class="context-info">Chaque agent reçoit le contexte utile. Ses états internes restent propres à sa session.</p></div>`;
  html+=`<div class="inspector-section"><h3>FICHIERS & PIÈCES JOINTES</h3>${state.detail?.files.map(f=>`<div class="event"><label><input type="checkbox" data-file="${f.id}" ${state.files.has(f.id)?'checked':''}> <button class="text-button" data-file-view="${f.id}">${esc(f.name)}</button></label><small class="muted">${f.kind==='produced'?'Produit':'Joint'}</small><button class="text-button danger" data-file-delete="${f.id}">Retirer</button></div>`).join('')||'<p class="context-info">Joignez un fichier texte du projet avec le bouton + de la conversation.</p>'}</div>`;
  if($('mission-panel')._rendered===html)return;
  htmlIfChanged('mission-panel',html);
  $('mission-panel').querySelectorAll('details').forEach((el,i)=>{el.dataset.event=String(i);el.open=opened.has(String(i));});
  $('inspector').scrollTop=scroll;
}
async function previewContext(){
  if(!state.conversation)return toast('Créez d’abord une conversation.');
  try{const result=await action('context_preview',{conversation_id:state.conversation,instruction:$('instruction').value,context:contextOptions()});openDialog('Aperçu du contexte',`<p>${result.chars.toLocaleString('fr-FR')} / ${result.budget_chars.toLocaleString('fr-FR')} caractères · ${result.source_ids.length} messages · ${result.omitted_ids.length} omis</p><pre class="context-pre">${esc(result.text)}</pre><p>Aperçu avant envoi. Le contexte exact de chaque étape sera conservé dans son suivi. ${esc(result.notice)}</p>`,null);}catch(e){fail(e);}
}
$('preview-context').onclick=previewContext;
$('composer').onsubmit=async e=>{
  e.preventDefault();const text=$('instruction').value,instruction=text.trim(),files=[...state.files],project=state.project,key=draftKey();
  if(!instruction&&!files.length)return;
  if(composerRequests.has(key))return;
  if(state.conversation&&(state.loadingConversation||!state.detail))return toast('Attendez le chargement de la conversation.');
  if([...mediaUploads.values()].some(upload=>upload.conversation===state.conversation))return toast('Attendez la fin des transferts de cette conversation.');
  if(!project)return newProject();
  const navigation=state.navigationVersion,request={connector:$('agent').value,model:$('model').value,effort:$('model-effort').value,service_tier:$('model-tier').value,instruction:instruction||'Consulte les pièces jointes.',context:contextOptions(),request_key:crypto.randomUUID(),input:voiceUI.fromVoice?'voice':''};
  let conversation=state.conversation,targetKey=key;
  voiceUI.fromVoice=false;rememberDraft();composerRequests.add(key);renderComposerPending();
  try{
    if(!conversation){
      const r=await action('create_conversation',{project_id:project,title:instruction.slice(0,70)||'Pièces jointes'});conversation=r.id;targetKey=draftKey(conversation);composerRequests.add(targetKey);
      if(!state.conversation&&state.project===project&&state.navigationVersion===navigation){
        rememberDraft();conversationDrafts[targetKey]=conversationDrafts[key];conversationFileDrafts[targetKey]=draftFiles(key);delete conversationDrafts[key];delete conversationFileDrafts[key];state.conversation=conversation;sessionStorage.setItem('cyai-conversation',conversation);
      }else{conversationDrafts[targetKey]=text;conversationFileDrafts[targetKey]=files;}
      persistDrafts();
    }
    const result=await action('continue_conversation',{...request,conversation_id:conversation});
    consumeDraft(targetKey,text,files);
    if(state.conversation===conversation){state.pinnedMission=null;if(!result.queued)state.missionId=result.mission_id;}
    if(result.queued)toast('Message mis en attente.');
    await refresh(true);
  }catch(err){fail(err);}finally{composerRequests.delete(key);composerRequests.delete(targetKey);renderComposerPending();}
};
$('instruction').onkeydown=e=>{if(e.key!=='Enter'||e.isComposing||e.keyCode===229||e.shiftKey)return;if(e.ctrlKey||e.metaKey||state.data?.settings?.send_on_enter!==false){e.preventDefault();if(!e.repeat&&!$('composer').querySelector('[type=submit]').disabled)$('composer').requestSubmit();}};
$('agent').onchange=()=>{const c=state.data.connectors.find(c=>c.id===$('agent').value);$('model').value=c?.model||'';renderRuntimeOptions(true);};
$('refresh-catalog').onclick=async()=>{const button=$('refresh-catalog');button.disabled=true;button.textContent='Lecture des catalogues…';try{const items=await Promise.all(state.data.connectors.filter(c=>c.enabled).map(async c=>{try{const r=await action('list_models',{id:c.id});return {c,models:r.models};}catch(e){return {c,models:[],error:e.message};}}));openDialog('IA disponibles pour l’orchestrateur',items.map(({c,models,error})=>`<h3>${esc(agentName(c.id))}</h3>${status(c.status)}<p>${esc(models.map(m=>m.id).join(', ')||c.model||'Modèle par défaut du fournisseur')}${error?'<br>'+esc(error):''}</p>`).join(''),null);const selected=items.find(x=>x.c.id===$('agent').value);$('model-list').innerHTML=(selected?.models||[]).map(m=>`<option value="${esc(m.id)}"></option>`).join('');}catch(e){fail(e);}finally{button.disabled=false;button.textContent='Voir les IA disponibles';}};
$('attach').onclick=chooseAttachments;
$('rename').onclick=()=>openDialog('Renommer la conversation',`<div class="fields"><label>Titre<input name="title" value="${esc(state.detail.title)}" required autofocus></label></div>`,form=>action('rename_conversation',{id:state.conversation,title:form.get('title')}));
$('archive').onclick=async()=>{try{await action('archive_conversation',{id:state.conversation,archived:!state.detail.archived});await refresh(true);}catch(e){fail(e);}};
$('delete').onclick=()=>openDialog('Supprimer cette conversation',`<p>Les messages, missions, pièces jointes et correspondances de sessions de « ${esc(state.detail.title)} » seront supprimés de CyAI. Les sessions conservées chez les agents et les fichiers du projet restent gérés séparément.</p>`,async()=>{await action('delete_conversation',{id:state.conversation});state.conversation=null;state.detail=null;state.mission=null;state.missionId=null;},'Supprimer');
function download(name,value){const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),2000);}
$('export').onclick=async()=>{try{download('cyai-conversation.json',await action('export',{conversation_id:state.conversation}));}catch(e){fail(e);}};
async function newMission(){
  if(!state.project)return newProject();
  if(!state.conversation){const c=await action('create_conversation',{project_id:state.project,title:'Nouvelle mission',mode:'chat'});await selectConversation(c.id);}
  openDialog('Composer une mission',`<p>Les étapes s’exécutent dans l’ordre. Chacune dépend des précédentes et reçoit leurs résultats. Les rôles et agents sont interchangeables.</p><div class="fields"><label>Titre<input name="title" placeholder="Implémenter et vérifier une fonctionnalité" required></label><div class="two-fields"><label>Durée maximale (secondes, 0 = sans limite)<input name="timeout" type="number" min="0" value="0"></label></div></div><div id="mission-editors"></div><button type="button" id="add-step" class="secondary">＋ Ajouter une étape</button>`,async form=>{
    const steps=[...document.querySelectorAll('.mission-step-editor')].map((el,i)=>({name:el.querySelector('[data-name]').value,connector:el.querySelector('[data-agent]').value,model:el.querySelector('[data-model]').value,effort:el.querySelector('[data-effort]').value,service_tier:el.querySelector('[data-tier]').value,instruction:el.querySelector('[data-instruction]').value,depends_on:Array.from({length:i},(_,j)=>j),...(el.querySelector('[data-validation]').value?{validation:{type:el.querySelector('[data-validation]').value,value:el.querySelector('[data-value]').value}}:{})}));
    const result=await action('create_mission',{conversation_id:state.conversation,title:form.get('title'),timeout_seconds:Number(form.get('timeout')),steps,context:contextOptions(),request_key:crypto.randomUUID()});state.missionId=result.mission_id;showView('chat');
  },'Lancer la mission');
  const add=()=>{const i=document.querySelectorAll('.mission-step-editor').length; const section=document.createElement('div');section.className='mission-step-editor';section.innerHTML=`<h3>ÉTAPE ${i+1}</h3><div class="two-fields"><label class="field">Rôle<input data-name value="${['Préparer le plan','Réaliser','Vérifier','Compte rendu'][i]||'Étape '+(i+1)}" required></label><label class="field">Agent<select data-agent>${connectorOptions($('agent').value)}</select></label></div><label class="field">Modèle (optionnel)<input data-model placeholder="Modèle configuré"></label><div class="two-fields"><label>Effort (Codex / Claude Code)<select data-effort><option value="">Défaut</option>${Object.entries(effortLabels).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label><label>Vitesse (Codex)<select data-tier><option value="">Défaut</option><option value="default">Standard</option><option value="priority">Fast · usage accru</option></select></label></div><label class="field">Instruction<textarea data-instruction placeholder="Instruction précise pour cette étape…" required></textarea></label><div class="two-fields"><label class="field">Contrôle<select data-validation><option value="">Réponse non vide</option><option value="contains">Texte attendu</option><option value="file_exists">Fichier présent</option><option value="json">JSON valide</option></select></label><label class="field">Valeur du contrôle<input data-value placeholder="Texte ou chemin relatif"></label></div><button type="button" class="text-button danger" data-remove-step>Retirer cette étape</button>`;section.querySelector('[data-remove-step]').onclick=()=>section.remove();$('mission-editors').append(section);};
  $('add-step').onclick=add;add();
}

function configureConnector(id){const c=state.data.connectors.find(c=>c.id===id);openDialog('Configurer '+agentName(id),`<div class="fields"><p>${esc(c.detail)}</p><label>Identifiant du modèle<input name="model" value="${esc(c.model)}" placeholder="Vide : modèle par défaut de l’agent"></label><label>État<select name="enabled"><option value="true" ${c.enabled?'selected':''}>Activé</option><option value="false" ${!c.enabled?'selected':''}>Désactivé</option></select></label>${['claude-code','codex','opencode','command-code','codebuddy','antigravity','devin'].includes(id)?`<label>Exécutable natif (.exe, facultatif)<input name="executable" value="${esc(c.executable||'')}" placeholder="Détection locale, puis CLI intégré"></label>`:''}${['anthropic','openrouter'].includes(id)?'<label>Clé API (laisser vide pour conserver)<input name="api_key" type="password" autocomplete="new-password" placeholder="Stockage chiffré avec Windows DPAPI"></label>':''}${['command-code','codebuddy','antigravity','devin'].includes(id)?`<label><input type="checkbox" name="native_auto_approve" ${c.native_auto_approve?'checked':''}> Autoriser automatiquement les outils natifs (écritures et commandes)</label><p>Authentifiez le CLI dans son terminal. Sans cette option, sa politique native peut refuser des outils ; les demandes natives ne sont pas relayées individuellement ici.</p>`:''}<p>Activez ce connecteur pour le tester au démarrage. Les abonnements aux applications et les clés API sont distincts.</p></div>`,async form=>{const data={id,model:form.get('model'),enabled:form.get('enabled')==='true'};if(['command-code','codebuddy','antigravity','devin'].includes(id))data.native_auto_approve=form.has('native_auto_approve');if(form.has('executable'))data.executable=form.get('executable').trim();if(form.get('api_key'))data.api_key=form.get('api_key');await action('save_connector',data);});}
function editMemory(memory={}){
  if(!state.project)return newProject();
  const sourceIds=JSON.parse(memory.source_ids||'[]');openDialog(memory.id?'Modifier la mémoire':'Ajouter une mémoire',`<div class="fields"><label>Catégorie<input name="category" list="memory-categories" value="${esc(memory.category||'Général')}"></label><datalist id="memory-categories">${memoryCategories().map(c=>`<option value="${esc(c)}">`).join('')}</datalist><label>Instruction, décision ou résumé de reprise<textarea name="content" rows="7" required>${esc(memory.content||'')}</textarea></label><label>Statut<select name="validated"><option value="false" ${!memory.validated?'selected':''}>Proposition · non transmise</option><option value="true" ${memory.validated?'selected':''}>Validée par moi · transmise aux agents</option></select></label><p>${sourceIds.length?sourceIds.length+' message(s) source conservé(s).':'Mémoire saisie manuellement.'} Une proposition ne devient permanente qu’après votre validation.</p></div>`,form=>action('save_memory',{...(memory.id?{id:memory.id}:{}),project_id:state.project,content:form.get('content'),category:form.get('category'),validated:form.get('validated')==='true',source_ids:sourceIds}));
}
function restoreDialog(){openDialog('Restaurer une sauvegarde',`<div class="fields"><label>Sauvegarde CyAI (.json)<input type="file" id="restore-file" accept="application/json,.json" required></label><p>La restauration remplace l’historique local. Une copie préalable est conservée dans le dossier de données. Les fichiers des projets et les sessions natives des fournisseurs ne sont pas restaurés.</p><label><span><input type="checkbox" required> Je confirme le remplacement des données locales.</span></label></div>`,async()=>{const file=$('restore-file').files[0];if(file.size>24000000)throw new Error('Sauvegarde limitée à 24 Mo dans cette interface.');const result=await action('restore',{backup:JSON.parse(await file.text()),acknowledged:true});state.detail=null;state.conversation=null;state.mission=null;state.missionId=null;toast(result.notice);},'Restaurer');}
async function renderPage(){
  const page=$('page');
  if(state.view==='project'){await renderProjectPage();return;}
  if(state.view==='agents'){await renderAgentsPage();return;}
  if(state.view==='home'){await renderHomePage();return;}
  if(state.view==='method'){await renderMethodEditor();return;}
  if(state.view==='space'){await renderSpace();return;}
  if(state.view==='plugins'){state.settingsTab='plugins';state.view='settings';renderSettings();return;}
  if(state.view==='logs'){await renderLogs();return;}
  if(state.view==='connectors'){
    const detail={'command-code':'CLI Command Code. Reprise de session ; configuration MCP native.','codebuddy':'CLI Tencent CodeBuddy. Streaming et MCP CyAI temporaire.','antigravity':'CLI Google Antigravity (agy). Tchat et exécution ; préparation de plan non prise en charge.','devin':'CLI Cognition Devin. Sortie texte et export de session ; préparation de plan non prise en charge.','openrouter':'API donnant accès à plusieurs fournisseurs. Clé API et modèle requis ; facturation OpenRouter.',codex:'Agent · App Server officiel. Fichiers, commandes sous sandbox, sessions et approbations.', 'claude-code':'Claude Code local · CLI / SDK. L’application Claude Desktop et ce CLI ont des sessions distinctes. Vérifiez sa connexion avant de discuter.',opencode:'Serveur local officiel. Outils de fichiers avec approbation ; shell et délégation désactivés.',anthropic:'API Messages avec streaming. Boucle d’outils de lecture et écriture fournie par CyAI.',ollama:'Modèle local via API Ollama. Conversation en streaming ; aucun outil de fichiers.'};
    page.innerHTML=`<div class="page-intro"><h2>Vos agents, votre choix.</h2><p>Une intégration installée n’est pas une connexion vérifiée. Configurez vos fournisseurs, puis lancez une conversation pour vérifier l’exécution réelle.</p></div><div class="card-grid">${state.data.connectors.map(c=>`<article class="card"><div class="card-icon">${esc(agentName(c.id)[0])}</div><div class="card-header"><h3>${esc(agentName(c.id))}</h3>${status(c.enabled?c.status:'Désactivé')}</div><p>${esc(detail[c.id]||c.detail)}</p><small>${esc(c.detail)}</small><p>Modèle : <b>${esc(c.model||'Défaut du fournisseur')}</b></p><div class="row-actions">${c.id==='claude-code'?'<button class="primary" data-connect="claude-code">Utiliser le CLI local</button>':''}<button class="secondary" data-configure="${c.id}">Configurer</button><button class="secondary" data-test="${c.id}">${c.id==='claude-code'?'Vérifier la connexion':'Tester'}</button><button class="text-button" data-models="${c.id}">Modèles ↗</button></div></article>`).join('')}</div><p class="context-info">Les réponses d’approbation natives non prises en charge sont refusées et signalées. Les coûts restent inconnus lorsqu’ils ne sont pas transmis par le fournisseur.</p>`;
  }else if(state.view==='missions'){
    const missions=state.data.missions.filter(m=>!state.project||state.data.conversations.find(c=>c.id===m.conversation_id)?.project_id===state.project);
    page.innerHTML=`<div class="page-intro"><h2>Du plan au résultat.</h2><p>Des étapes configurables, une exécution séquentielle et un historique durable. Après une interruption, vérifiez les effets avant de reprendre.</p></div>${missions.map(m=>`<div class="mission-row"><div class="title">${esc(m.title)}<small>${date(m.created_at)}</small></div>${status(m.status)}<button class="secondary" data-mission="${m.id}">Ouvrir ↗</button></div>`).join('')||'<div class="empty-state">Aucune mission. Ouvrez une conversation et composez votre première mission.</div>'}`;
  }else if(state.view==='memory'){
    const memoryProject=state.project?await api('project/'+state.project):null;const memory=memoryProject?.memory||[];state.memory=memory;
    page.innerHTML=`<div class="page-intro"><h2>Mémoire du projet</h2></div>${memoryHTML(memory,memoryProject)}`;
  }else if(state.view==='search'){
    page.innerHTML=`<div class="page-intro"><h2>Retrouvez le fil.</h2><p>Recherchez dans les messages enregistrés, y compris les conversations archivées.</p></div><form id="search-form"><div class="search-filters"><input name="text" aria-label="Rechercher dans l’historique" placeholder="Rechercher une décision, un résultat…"><select name="project_id" aria-label="Filtrer par projet"><option value="">Tous les projets</option>${projectOptions('')}</select><select name="connector" aria-label="Filtrer par agent"><option value="">Tous les agents</option>${connectorOptions('')}</select><input name="date_from" type="date" aria-label="À partir du"><input name="date_to" type="date" aria-label="Jusqu’au"><select name="status" aria-label="Filtrer par statut"><option value="">Tous les statuts</option>${Object.entries(L.states).map(([id,label])=>`<option value="${id}">${label}</option>`).join('')}</select></div><button class="primary">Rechercher</button></form><div id="search-results"></div>`;
    $('search-form').onsubmit=async e=>{e.preventDefault();try{const results=await api('search?'+new URLSearchParams(new FormData(e.target)));$('search-results').innerHTML=results.map(m=>`<article class="search-result"><button data-conversation="${m.conversation_id}">${esc(m.title)} ↗</button><small>${esc(m.connector?agentName(m.connector):'Vous')} · ${date(m.created_at)}</small><p>${esc(m.content)}</p></article>`).join('')||'<div class="empty-state">Aucun résultat pour ces filtres.</div>';}catch(err){fail(err);}};
  }else if(state.view==='settings'){
    renderSettings();
  }
}
async function refresh(force=false){
  if(state.polling){if(force)state.refreshAgain=true;return;}state.polling=true;
  const navigation=state.navigationVersion,selection=state.conversationVersion,conversation=state.conversation,project=state.project,pinned=state.pinnedMission;
  const stale=()=>navigation!==state.navigationVersion||selection!==state.conversationVersion||conversation!==state.conversation||project!==state.project||pinned!==state.pinnedMission;
  try{
    state.data=await api('state');
    if(stale()){state.refreshAgain=true;return;}
    applyAppearance();renderConnectorStatus();$('notice').hidden=true;
    if(!state.data.projects.some(p=>p.id===state.project))state.project=state.data.projects[0]?.id||null;
    if(conversation&&!state.loadingConversation&&!state.data.conversations.some(c=>c.id===conversation)){rememberDraft();state.conversation=null;state.detail=null;restoreDraft();}
    if(!state.conversation){state.mission=null;state.missionId=null;}
    if(state.conversation&&!state.loadingConversation){
      const detail=await api('conversation/'+conversation);
      if(stale()){state.refreshAgain=true;return;}
      const changed=JSON.stringify(detail)!==JSON.stringify(state.detail);
      const summary=state.data.missions.find(m=>m.id===pinned&&m.conversation_id===conversation)||state.data.missions.find(m=>m.conversation_id===conversation&&active(m.status))||state.data.missions.find(m=>m.conversation_id===conversation);
      let mission=null;
      if(summary){
        const previous=state.mission?.id===summary.id?state.mission.events:[],after=previous.at(-1)?.seq||0;
        let page=await api('mission/'+summary.id+'?after='+after);const events=[...previous,...page.events];
        while(page.events.length===1000){if(stale()){state.refreshAgain=true;return;}page=await api('mission/'+summary.id+'?after='+events.at(-1).seq);events.push(...page.events);}
        mission={...page,events};
      }
      if(stale()){state.refreshAgain=true;return;}
      state.detail=detail;state.project=detail.project_id;state.conversationLoadError='';state.mission=mission;state.missionId=mission?.id||null;
      if(state.view==='chat'&&(changed||force))renderMessages();
    }
    document.querySelectorAll('.version').forEach(el=>el.textContent='v'+state.data.version);renderSidebar();renderRuntimeOptions();
    if(state.view==='chat'){if(force&&!state.conversation)renderMessages();renderInspector();renderLive();notifyFailures();}
    if((force||state.view==='agents'||state.view==='project'&&state.projectTab!=='settings')&&state.view!=='chat')await renderPage();
  }catch(err){
    if(navigation!==state.navigationVersion||selection!==state.conversationVersion)return;
    $('notice').textContent=(err.connection?'Connexion au service interrompue. Votre historique reste enregistré. ':'Impossible d’actualiser cet écran. ')+err.message;$('notice').hidden=false;
  }finally{state.polling=false;if(state.refreshAgain){state.refreshAgain=false;setTimeout(()=>refresh(true),0);}}
}
(async()=>{restoreDraft();await refresh(true);if(state.data){showView(state.conversation?'chat':'project');if(state.detail?.agent_id){$('agent').value=state.detail.agent_id;$('model').value=state.detail.agent_model||'';}else $('model').value=state.data.connectors.find(c=>c.id===$('agent').value)?.model||'';renderRuntimeOptions();}setInterval(()=>refresh(),1600);})();


function renderInspector(){hydrateLocalImages();
 renderInspectorBody();
 if(!$('inspector-tabs')){
  const nav=document.createElement('nav');nav.id='inspector-tabs';nav.className='inspector-tabs';nav.setAttribute('aria-label','Conversation');
  nav.innerHTML=Object.entries({tracking:'Suivi',details:'Détails',actions:'Actions',config:'Configuration',summary:'Résumé'}).map(([id,name])=>`<button type="button" data-inspector-tab="${id}">${name}</button>`).join('');
  $('inspector').prepend(nav);
  const tools=document.createElement('div');tools.id='conversation-actions';$('inspector').append(tools);
 }
 const selected=state.inspectorTab||'tracking';
 $('inspector-tabs').querySelectorAll('button').forEach(b=>b.classList.toggle('selected',b.dataset.inspectorTab===selected));
 const panel=$('mission-panel');panel.hidden=!['tracking','details'].includes(selected);
 [...panel.children].forEach(el=>{const heading=el.querySelector('h3')?.textContent||'';const detail=/CONTEXTE PARTAGÉ|FICHIERS & PIÈCES JOINTES/.test(heading);el.hidden=selected==='details'?!detail:detail;});
 const holder=$('conversation-actions');holder.hidden=!['actions','config','summary'].includes(selected);
 // Rebuild from the toolbar template, preserving delegated action handlers.
 renderPluginButtons();
 const buttons=[...$('plugin-toolbar').children];holder.replaceChildren();
 for(const b of buttons){if(b.classList.contains('cyannota-button'))continue;holder.append(b);const category=b.dataset.intelligence==='summary'?'summary':b.dataset.intelligence==='conversation'||b.dataset.workspaceAction==='workdirs'?'config':'actions';b.hidden=category!==selected;}
 if(selected==='summary'){const summary=document.createElement('pre');summary.className='context-pre';summary.textContent=state.detail?.summary||'Aucun résumé enregistré.';holder.append(summary);}
 $('plugin-toolbar')._rendered=null;
}
document.addEventListener('click',e=>{const b=e.target.closest('[data-inspector-tab]');if(b){state.inspectorTab=b.dataset.inspectorTab;renderInspector();}});
function renderConnectorStatus(){
 if(state.claudeLoginPending&&state.data?.connectors.some(c=>c.id==='claude-code'&&c.status==='connected')){state.claudeLoginPending=false;if($('dialog').open&&$('dialog-title').textContent==='Connexion Claude Code')$('dialog').close();toast('Claude Code connecté.');}
 let target=$('connector-status');if(!target){target=document.createElement('div');target.id='connector-status';target.className='connector-status';const stack=document.createElement('div');stack.className='connector-summary';document.querySelector('.sidebar-footer').prepend(stack);stack.append(target);const stats=document.createElement('div');stats.id='resource-usage';stack.append(stats);}
 const r=state.data?.resources||{},fmt=n=>n==null?'n/d':n>=1024**3?(n/1024**3).toFixed(2)+' Go':Math.round(n/1024**2)+' Mo';
 $('resource-usage').innerHTML=`<div>RAM CyAI : ${fmt(r.ram_bytes)}</div><div>VRAM CyAI : ${fmt(r.vram_bytes)}</div><div>VRAM modèle : ${fmt(r.local_model_vram_bytes)}</div>`;
 let meters=$('system-meters');if(!meters){meters=document.createElement('div');meters.id='system-meters';document.querySelector('.local-status').before(meters);}
 const gauge=(label,icon,value,detail)=>{const known=typeof value==='number'&&Number.isFinite(value),n=known?Math.max(0,Math.min(100,value)):0,color=!known?'#777b8d':n>=90?'#f07079':n>=75?'#e8b65d':'#79ceb4';return `<div class="system-meter" data-tone="${!known?'unknown':n>=90?'high':n>=75?'medium':'normal'}" title="${esc(detail)}" aria-label="${esc(label+': '+(known?Math.round(n)+' %':'non disponible')+'. '+detail)}"><span class="meter-ring"><svg viewBox="0 0 32 32" aria-hidden="true"><circle class="meter-track" cx="16" cy="16" r="13"/><circle class="meter-fill" cx="16" cy="16" r="13" stroke-dasharray="81.681" stroke-dashoffset="${81.681*(1-n/100)}" transform="rotate(-90 16 16)"/></svg><span>${icon}</span></span><span>${label}</span><small>${known?Math.round(n)+' %':'n/d'}</small></div>`;};
 meters.innerHTML=gauge('CPU','⚙',r.cpu_percent,'CPU total de la machine')+gauge('RAM','▤',r.system_ram_percent,fmt(r.system_ram_used_bytes)+' / '+fmt(r.system_ram_total_bytes)+' · machine entière')+gauge('GPU','▧',r.gpu_util_percent,'Activité du GPU NVIDIA mesuré · toutes applications')+gauge('VRAM','▦',r.gpu_total_bytes?100*r.gpu_used_bytes/r.gpu_total_bytes:null,fmt(r.gpu_used_bytes)+' / '+fmt(r.gpu_total_bytes)+' · toutes applications')+gauge('Disque','◉',r.disk_percent,fmt(r.disk_used_bytes)+' / '+fmt(r.disk_total_bytes)+' · volume contenant les données CyAI');
 $('resource-usage').title=(r.scope||'Mesure en cours…')+' '+(r.vram_source||'');

 target.innerHTML=(state.data?.connectors||[]).filter(c=>c.enabled).map(c=>`<button data-view="connectors" class="text-button" title="${esc(agentName(c.id))} : ${esc(L.connections[c.status]||c.status)}"><span class="connector-dot ${esc(c.status)}">●</span> ${esc(agentName(c.id))}</button>`).join('');
}

function isTaskChain(m){return !!m&&!m.spec?.planning&&(m.steps?.length>1||state.detail?.mode==='orchestrator');}
function renderWorkStatus(){
 renderComposerUsage();
 let queue=$('conversation-outbox');if(!queue){queue=document.createElement('div');queue.id='conversation-outbox';$('composer').before(queue);}
 htmlIfChanged('conversation-outbox',(state.detail?.outbox||[]).map(q=>`<article class="queued-message"><strong>${q.status==='pending'?'Message en attente':'Envoi à reprendre'}</strong><p>${esc(q.instruction)}</p>${q.error?`<p class="error">${esc(q.error)}</p>`:''}<button type="button" class="secondary" data-outbox="${esc(q.id)}" data-op="outbox_send_now" title="Interrompt la réponse actuelle puis transmet ce message dans la même conversation">Envoyer maintenant</button> <button type="button" class="text-button" data-outbox="${esc(q.id)}" data-op="outbox_cancel">Retirer</button><small>Envoyé automatiquement au prochain tour. « Envoyer maintenant » interrompt la réponse en cours.</small></article>`).join('')+backgroundWorkHTML());

 let stop=$('stop-inference');if(!stop){stop=document.createElement('button');stop.id='stop-inference';stop.type='button';stop.className='secondary danger';stop.textContent='✕';stop.setAttribute('aria-label','Arrêter la réponse');stop.title='Arrêter la réponse en cours (le moteur local sera déchargé)';$('composer').querySelector('.composer-actions').append(stop);}
 const current=state.mission,working=current&&current.conversation_id===state.conversation&&active(current.status);
 stop.hidden=!working;if(working)stop.dataset.cancel=current.id;
 const send=$('composer').querySelector('[type=submit]');send.title=state.data?.settings?.send_on_enter===false?'Envoyer (Ctrl+Entrée)':'Envoyer (Entrée ; Maj+Entrée pour un saut de ligne)';send.setAttribute('aria-label',send.title);renderComposerPending();

 let bar=$('work-status');if(!bar){bar=document.createElement('div');bar.id='work-status';bar.setAttribute('role','status');$('conversation-toolbar').after(bar);}
 const m=state.mission;bar.dataset.status=m?.status||'';bar.dataset.busy=String(['running','queued','pausing'].includes(m?.status));bar.hidden=!m||m.conversation_id!==state.conversation;
 if(bar.hidden)return;
 const chain=isTaskChain(m);
 const activeSteps=m.steps.filter(s=>['running','awaiting_approval'].includes(s.status));
 const step=activeSteps[0];
 const done=m.steps.filter(s=>s.status==='succeeded').length;
 const event=m.events.at(-1),age=event?Math.max(0,Math.floor((Date.now()-Date.parse(event.created_at))/1000)):null;
 const awaitingPlan=state.detail?.plans?.[0]&&!state.detail.plans[0].execution&&m.spec?.planning&&m.status==='succeeded';
 const tokenSteps=m.steps.filter(x=>['local','ollama'].includes(x.connector));let tokensIn=0,tokensOut=0,known=false;for(const step of tokenSteps){try{const u=typeof step.usage==='string'?JSON.parse(step.usage||'null'):step.usage;if(u){const a=u.input_tokens??u.prompt_tokens,b=u.output_tokens??u.completion_tokens;if(a!=null&&b!=null){known=true;tokensIn+=a;tokensOut+=b;}}}catch(_){}}
 const tokenLabel=known?`Tokens locaux : ${tokensIn.toLocaleString('fr-FR')} entrée · ${tokensOut.toLocaleString('fr-FR')} sortie`:(tokenSteps.length?'Tokens locaux : disponibles à la fin de la génération':'');
 const label=!chain&&!m.spec?.planning?({running:'Réponse en cours',queued:'Réponse en attente de démarrage',succeeded:'Réponse terminée',failed:'Réponse échouée',cancelled:'Réponse arrêtée',interrupted:'Réponse interrompue — reprise possible',awaiting_approval:'Votre autorisation est nécessaire',paused:'Réponse en pause',pausing:'Pause demandée'}[m.status]||m.status):awaitingPlan?'Plan prêt — en attente de votre validation':{pausing:'Pause demandée — fin des étapes actives',paused:'Chaîne en pause — mise à jour possible',running:'Travail en cours',queued:'En attente de démarrage',awaiting_approval:'Votre autorisation est nécessaire',succeeded:'Travail terminé',failed:'Exécution échouée',cancelled:'Exécution annulée',interrupted:'Exécution interrompue — reprise nécessaire'}[m.status]||m.status;
 htmlIfChanged('work-status',`<strong>${esc(label)}</strong><span>${esc(tokenLabel)}</span>${(state.data.approvals||[]).some(a=>a.mission_id===m.id)?'<button type="button" class="primary" data-show-approvals>Voir la demande et répondre</button>':''}<span>${awaitingPlan?'Aucune tâche du plan lancée':chain?`${done}/${m.steps.length} étapes terminées`:''}${activeSteps.length?' · '+activeSteps.map(s=>esc(s.name)+' ('+esc(s.model||agentName(s.connector))+')').join(' · '):''}</span><small>${active(m.status)?age===null?'En attente du premier événement':`Dernier événement reçu il y a ${age} s${age>60?' · aucun nouvel événement reçu, traitement non confirmé depuis cette date':''}`:''}</small>${chain&&['running','queued','awaiting_approval'].includes(m.status)?`<button class="secondary" data-pause-chain="${esc(m.id)}">Mettre la chaîne en pause</button>`:''}${m.status==='paused'?`<button class="primary" data-resume-chain="${esc(m.id)}">${chain?'Reprendre la chaîne':'Reprendre la réponse'}</button>`:''}${['interrupted','failed','cancelled'].includes(m.status)?`<button class="primary" data-retry="${esc(m.id)}">Examiner et reprendre</button>`:''}${active(m.status)?`<button class="secondary" data-cancel="${esc(m.id)}">Arrêter</button>`:''}`);
}

function renderThinking(){
 let box=$('thinking-stream');if(!box){box=document.createElement('details');box.id='thinking-stream';box.innerHTML='<summary>Activité et réflexion transmises par le fournisseur</summary><pre></pre>';const area=$('live-output');if(!area)return;area.prepend(box);}
 const m=state.mission,step=m?.steps?.find(s=>['running','awaiting_approval'].includes(s.status));box.hidden=!step;
 if(!step)return;
 const events=m.events.filter(e=>e.step_id===step.id&&['thinking','activity','tool'].includes(e.kind));
 const text=events.slice(-100).map(e=>e.kind==='thinking'?e.data.text:'['+e.kind+'] '+(e.data.name||e.data.type||'Outil')).join('');
 box.querySelector('pre').textContent=text||'Aucun détail de réflexion transmis pour le moment. L’indicateur animé signale une exécution en cours, pas une preuve d’activité du modèle.';
}

let chatScrollFrame=0,chatScrollAdjusting=false;
function scheduleChatScroll(){
 if(chatScrollFrame)return;
 chatScrollAdjusting=true;
 chatScrollFrame=requestAnimationFrame(()=>{
  chatScrollFrame=0;const panel=$('messages');
  if(state.followChat!==false&&state.view==='chat')panel.scrollTop=panel.scrollHeight;
  const jump=$('jump-latest');if(jump)jump.hidden=state.followChat!==false||state.view!=='chat';
  requestAnimationFrame(()=>{chatScrollAdjusting=false;});
 });
}
(()=>{
 const panel=$('messages'),jump=document.createElement('button');jump.id='jump-latest';jump.className='secondary';jump.type='button';jump.textContent='↓ Derniers messages';jump.hidden=true;
 $('composer-area').prepend(jump);
 jump.onclick=()=>{state.followChat=true;scheduleChatScroll();};
 panel.addEventListener('wheel',e=>{if(e.deltaY<0){state.followChat=false;jump.hidden=false;}},{passive:true});
 panel.addEventListener('touchmove',()=>{state.followChat=false;jump.hidden=false;},{passive:true});
 panel.addEventListener('scroll',()=>{
  if(chatScrollAdjusting)return;
  state.followChat=panel.scrollHeight-panel.scrollTop-panel.clientHeight<60;
  jump.hidden=state.followChat;
 },{passive:true});
 new MutationObserver(scheduleChatScroll).observe(panel,{childList:true,subtree:true,characterData:true});
 new ResizeObserver(scheduleChatScroll).observe(panel);
 panel.addEventListener('load',scheduleChatScroll,true);
})();

document.addEventListener('click',async e=>{const b=e.target.closest('[data-outbox]');if(!b)return;b.disabled=true;try{state.pinnedMission=null;await action(b.dataset.op,{id:b.dataset.outbox});await refresh(true);}catch(err){fail(err);}finally{b.disabled=false;}});

function backgroundWorkHTML(){
 const jobs=state.detail?.background||[];if(!jobs.length)return '';
 const expanded=localStorage.getItem('cyai-background-expanded:'+state.conversation)==='true';
 const running=jobs.filter(b=>active(b.status)).length;
 const failed=jobs.filter(b=>['failed','interrupted'].includes(b.status)).length;
 return `<div class="background-summary"><span>Travaux · ${jobs.length} lots · ${running} actifs${failed?' · '+failed+' en échec':''}</span><button type="button" class="text-button" data-background-toggle aria-expanded="${expanded}">${expanded?'Masquer les travaux':'Afficher les travaux'}</button></div>`+(expanded?(state.detail?.background||[]).map(b=>`<article class="queued-message"><strong>Travail en arrière-plan · ${esc(b.title)}</strong> ${status(b.status)}<p>${b.completed}/${b.total} exercices terminés</p><details><summary>Voir les exercices</summary>${(b.steps||[]).map(step=>`<p>${esc(step.name)} · ${status(step.status)}${step.error?' · '+esc(step.error):''}</p>`).join('')}</details>${active(b.status)?`<button type="button" class="secondary" data-cancel="${esc(b.id)}">Arrêter le lot</button>`:''}</article>`).join(''):'');
}
document.addEventListener('click',e=>{if(!e.target.closest('[data-background-toggle]'))return;const key='cyai-background-expanded:'+state.conversation;localStorage.setItem(key,localStorage.getItem(key)==='true'?'false':'true');renderWorkStatus();});

function renderComposerUsage(){
 const el=$('composer-usage');if(!el)return;
 const connector=$('agent').value,model=$('model').value;
 const steps=(state.mission?.conversation_id===state.conversation?state.mission.steps:[])||[];
 const step=[...steps].reverse().find(s=>s.connector===connector&&(!model||s.model===model));
 let usage={};try{usage=typeof step?.usage==='string'?JSON.parse(step.usage||'{}'):(step?.usage||{});}catch(_){}
 const latest=usage.last||usage;
 const input=latest.input_tokens??latest.prompt_tokens??latest.inputTokens;
 const output=latest.output_tokens??latest.completion_tokens??latest.outputTokens;
 const number=n=>n==null?'non fourni':Number(n).toLocaleString('fr-FR');
 const memory=n=>n==null?'non mesurée':(n/1024**3).toFixed(2)+' Go';
 const parts=[];
 if(connector==='local'){
  const local=state.data?.local_info||{};
  const selected=(local.models||[]).find(m=>m.id===model||m.name===model||(!model&&m.id===local.loaded));
  parts.push('Contexte configuré : '+number(selected?.context??local.context)+' tokens');
  const event=[...(state.mission?.events||[])].reverse().find(e=>e.kind==='usage'&&e.step_id===step?.id);
  const last=event?.data||{};
  parts.push('Dernière requête : '+number(last.input_tokens??last.prompt_tokens??input)+' tokens en entrée');
  parts.push('RAM moteur : '+memory(state.data?.resources?.local_model_ram_bytes));
  parts.push('RAM CyAI : '+memory(state.data?.resources?.ram_bytes));
 }else{
  const metadata=typeof runtimeModel==='function'?runtimeModel():null;
  const usageEvent=[...(state.mission?.events||[])].reverse().find(e=>e.kind==='usage'&&e.step_id===step?.id)?.data||{};
  const sessionCapacity=usageEvent.modelContextWindow??usage.modelContextWindow??latest.modelContextWindow;
  const capacity=sessionCapacity??metadata?.context_window??metadata?.contextWindow??metadata?.context_length;
  parts.push('Entrée : '+number(input)+(capacity!=null?' / '+number(capacity):'')+' tokens'+(capacity!=null?' · contexte annoncé par '+agentName(connector)+(sessionCapacity!=null?' pour cette session':' dans le catalogue'):' · limite de contexte non communiquée'),'Sortie : '+number(output)+' tokens');
  parts.push('Quota abonnement restant : non fourni par le connecteur');
 }
 el.innerHTML=parts.map(part=>esc(part).replace(/\d[\d\s\u202f\u00a0.,]*/g,value=>'<strong class="usage-number">'+value.trimEnd()+'</strong>'+value.slice(value.trimEnd().length))).join(' · ');
 el.title='Tokens rapportés par le fournisseur, pas une estimation en caractères. La dernière requête représente le contexte envoyé, pas une mesure en direct du cache mémoire. RAM CyAI inclut ses processus enfants ; RAM moteur concerne le modèle actuellement chargé.';
}
document.addEventListener('change',e=>{if(['agent','model'].includes(e.target.id))renderComposerUsage();});
