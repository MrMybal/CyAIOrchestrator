'use strict';
let localModelsPoll=null;
async function renderLocalModels(){
 const info=await action('local_state');if(state.view!=='settings'||state.settingsTab!=='local')return;
 const panel=document.querySelector('.settings-content');if(!panel)return;
 panel.innerHTML=`<h3>Modèles locaux · moteur CyAI</h3><p>llama.cpp exécute les fichiers GGUF sur cet ordinateur. Ollama reste disponible dans Connecteurs. Ce moteur propose des conversations et du raisonnement ; il n’exécute pas d’outils de fichiers.</p>
 <div class="row-actions"><button class="secondary" data-show-downloads>Voir les téléchargements</button><button class="secondary" data-local-stop>Décharger le modèle · libérer la VRAM</button></div><h4>Moteur</h4><p>${esc(info.runtime||'Pas encore installé')}</p><div class="row-actions"><button class="secondary" data-runtime="cpu">Installer CPU</button><button class="secondary" data-runtime="vulkan">Installer GPU Vulkan</button><button class="secondary" data-runtime="cuda">Installer NVIDIA CUDA 12.4</button></div>
 <p>PrismML (Bonsai 2) : ${esc(info.prism_runtime || 'Non installé')}</p><div class="row-actions"><button class="secondary" data-runtime="prism-cuda">Installer PrismML CUDA</button><button class="secondary" data-runtime="prism-vulkan">Installer PrismML Vulkan</button><button class="secondary" data-runtime="prism-cpu">Installer PrismML CPU</button></div><form id="local-settings" class="fields"><h4>Réglages globaux par défaut</h4><p>Chaque modèle hérite de ces valeurs sauf pour ses réglages personnalisés.</p><label>Exécution<select name="device">${[['cpu','CPU uniquement'],['gpu','GPU · toutes les couches possibles'],['hybrid','GPU + CPU · nombre de couches choisi']].map(([id,n])=>`<option value="${id}" ${info.settings.device===id?'selected':''}>${n}</option>`).join('')}</select></label><div class="two-fields"><label>Couches GPU (hybride)<input type="number" name="gpu_layers" min="0" max="999" value="${info.settings.gpu_layers}"></label><label>Threads CPU<input type="number" name="threads" min="1" max="256" value="${info.settings.threads}"></label></div><label>Contexte (tokens)<input name="context" type="number" min="512" value="${info.settings.context}"></label><p>La mémoire nécessaire dépend du modèle, de sa quantification et du contexte. Réduisez les couches GPU pour laisser de la VRAM aux autres applications. Les journaux du moteur indiquent les périphériques et couches réellement utilisés.</p><label>Dossier des prochains modèles<input id="local-model-dir" name="models_dir" value="${esc(info.models_dir)}"></label><button type="button" class="secondary" data-local-folder>Parcourir…</button><button class="primary">Enregistrer le calcul et le dossier</button></form>
 <h4>Installer un modèle</h4><div class="row-actions"><button class="primary" data-gguf-download>Télécharger depuis Hugging Face</button><button class="secondary" data-gguf-import>Importer un GGUF</button></div><div id="local-jobs"></div>
 <h4>Modèles installés</h4>${info.models.map(m=>`<article class="card"><strong>${esc(m.name)}</strong><p class="${m.memory?.warning ? 'memory-warning' : ''}">${esc(m.memory?.label || '')} ${esc(m.memory?.warning || '')}</p><p>Moteur : ${m.runtime_family==='prism' ? 'PrismML requis (sélection automatique)' : 'llama.cpp'}</p><p>${(m.bytes/1024**3).toFixed(2)} Go · ${esc(m.path)}</p><button class="secondary" data-local-start="${m.id}" ${m.exists?'':'disabled'}>Charger</button><p>Calcul : ${esc(m.effective_settings.device)} · contexte ${m.effective_settings.context} · ${Object.keys(m.settings||{}).length?'réglages personnalisés':'valeurs globales'}</p><button class="secondary" data-model-config="${m.id}">Configurer ce modèle</button><button class="primary" data-local-use="${m.id}">Utiliser dans les conversations</button></article>`).join('')||'<p>Aucun modèle. Téléchargez ou importez un fichier GGUF.</p>'}
 <h4>État du moteur</h4><div id="local-running"></div><button class="secondary" data-local-stop>Arrêter et libérer la mémoire</button><details><summary>Journaux CPU/GPU</summary><pre id="local-logs" class="context-pre"></pre></details>`;
 $('local-settings').onsubmit=async e=>{e.preventDefault();try{await action('local_settings',Object.fromEntries(new FormData(e.target)));toast('Réglages enregistrés.');}catch(error){fail(error);}};
 paintLocalJobs(info);
 startLocalPolling();
}
const notifiedLocalJobs=new Set();
function openDownloads(){state.settingsTab='downloads';showView('settings');}
async function renderDownloads(){
 const panel=document.querySelector('.settings-content');if(!panel)return;
 panel.innerHTML='<h3>Téléchargements & installations</h3><p>Les opérations sont exécutées dans l’ordre. Gardez CyAI ouvert jusqu’à leur fin.</p><button class="primary" data-gguf-download>Ajouter un modèle</button><p id="download-summary" role="status">Lecture des opérations…</p><div id="local-jobs"></div><section id="optional-components"></section>';
 try{const info=await action('local_state');if(state.view!=='settings'||state.settingsTab!=='downloads')return;paintLocalJobs(info);startLocalPolling();}catch(e){settingsLoadError('downloads',e);}
}
function startLocalPolling(){
 clearInterval(localModelsPoll);localModelsPoll=setInterval(async()=>{if(state.view!=='settings'||!['local','downloads'].includes(state.settingsTab)){clearInterval(localModelsPoll);return;}try{paintLocalJobs(await action('local_state'));}catch(e){clearInterval(localModelsPoll);if($('download-summary'))$('download-summary').textContent='Suivi interrompu : '+e.message;else fail(e);}},1500);
}
function paintLocalJobs(info){
 if($('optional-components'))htmlIfChanged('optional-components','<h4>Composants à la demande</h4>'+ (info.components||[]).map(item=>{
  const job=info.jobs.find(j=>j.name==='Composant · '+item.id&&['queued','running'].includes(j.status));
  return `<article class="card"><h4>${esc(item.name)}</h4><p>${esc(item.description)}${item.bytes?' · '+(item.bytes/1024**2).toFixed(1)+' Mo':''}</p><button type="button" class="secondary" data-component-install="${esc(item.id)}" ${item.installed||job?'disabled':''}>${item.installed?'Installé':job?'Téléchargement en cours…':'Télécharger'}</button></article>`;
 }).join(''));
 if(!$('local-jobs'))return;
 const labels={queued:'En attente',running:'En cours',succeeded:'Terminé',failed:'Échec'};
 const size=n=>n>=1024**3?(n/1024**3).toFixed(2)+' Go':(n/1024**2).toFixed(1)+' Mo';
 htmlIfChanged('local-jobs',info.jobs.map(j=>`<article class="card"><strong>${esc(j.name)}</strong><p class="${j.status==='failed'?'operation-error':''}">${labels[j.status]||esc(j.status)}${j.status==='queued'?' · démarrera après les opérations précédentes':''}</p>${j.status==='running'?`<progress aria-label="Progression" class="job-progress" ${j.total?`max="${j.total}" value="${j.received}"`:''}></progress>`:''}<p>${j.total?size(j.received)+' / '+size(j.total)+' · '+Math.round(j.received/j.total*100)+' %':j.received?size(j.received)+' reçus':j.status==='running'?'Préparation ou installation en cours…':''}</p>${j.detail&&j.status==='running'?`<p class="field-help">${esc(j.detail)}</p>`:''}${j.error?`<pre class="error context-pre">${esc(j.error)}</pre>`:''}</article>`).join('')||'<p>Aucun téléchargement pour cette session.</p>');
 if($('download-summary'))$('download-summary').classList.toggle('operation-error',info.jobs.some(j=>j.status==='failed'));
 if($('download-summary'))$('download-summary').textContent=info.jobs.filter(j=>j.status==='running').length+' en cours · '+info.jobs.filter(j=>j.status==='queued').length+' en attente · '+info.jobs.filter(j=>j.status==='failed').length+' en échec';
 if($('local-running'))$('local-running').textContent=info.running?'Chargé : '+(info.models.find(m=>m.id===info.loaded)?.name||info.loaded):'Moteur arrêté';
 if($('local-logs'))$('local-logs').textContent=info.logs.join('\n');
 for(const j of info.jobs)if(['succeeded','failed'].includes(j.status)&&!notifiedLocalJobs.has(j.id)){notifiedLocalJobs.add(j.id);if(j.status==='failed')fail(new Error(j.error));else toast(j.name+' terminé.');}
}
async function submitLocalJob(button,name,data){
 if(button.disabled)return;
 const label=button.textContent;button.disabled=true;button.textContent='Demande en cours…';button.setAttribute('aria-busy','true');
 try{const result=await action(name,data);if(result.cancelled)return;if(result.job_id){toast('Demande enregistrée. Suivi dans Téléchargements.');if($('dialog')?.open)$('dialog').close();openDownloads();}}
 finally{button.disabled=false;button.textContent=label;button.removeAttribute('aria-busy');}
}

async function ggufDownloadDialog(){
 const catalog=await action('local_catalog');
 openDialog('Télécharger un modèle GGUF',`<label>Catalogue de modèles<select id="gguf-catalog"><option value="">Choisir un modèle…</option>${catalog.models.map(m=>`<option value="${esc(m.repo)}">${esc(m.name)} · ${esc(m.use)}</option>`).join('')}</select></label><div id="gguf-catalog-info"></div><details><summary>Autre dépôt / choix avancé</summary><p>Choisissez le dépôt du créateur ou d’un quantificateur de confiance. Consultez sa licence sur Hugging Face.</p><label>Dépôt<input id="gguf-repo" value="Qwen/Qwen3-0.6B-GGUF" placeholder="auteur/modèle"></label><button type="button" id="gguf-search" class="secondary">Lister les fichiers et tailles</button></details><div id="gguf-files"></div>`,null);
 $('gguf-catalog').onchange=()=>{const model=catalog.models.find(m=>m.repo===$('gguf-catalog').value);if(!model)return;$('gguf-repo').value=model.repo;$('gguf-catalog-info').innerHTML=`<p>${esc(model.use)} · <a href="${esc(model.source)}" target="_blank" rel="noopener">Fiche et licence</a></p><p>Q4_K_M : compromis taille/qualité. Q8_0 : plus volumineux. La taille du fichier ne représente pas toute la mémoire nécessaire à l’exécution.</p>`;$('gguf-search').click();};
 $('gguf-search').onclick=async()=>{try{const repo=$('gguf-repo').value.trim();$('gguf-files').textContent='Recherche des fichiers disponibles…';const r=await action('local_model_files',{repo});if(!$('gguf-repo')||$('gguf-repo').value.trim()!==repo)return;$('gguf-files').innerHTML=r.files.map(f=>`<p>${esc(f.name)} · ${(f.bytes/1024**3).toFixed(2)} Go <button type="button" class="primary" data-download-file="${esc(f.name)}">Télécharger</button></p>`).join('')||'<p>Aucun GGUF disponible.</p>';$('gguf-files').querySelectorAll('button').forEach(b=>b.onclick=async()=>{try{await submitLocalJob(b,'local_model_install',{repo:r.repo,filename:b.dataset.downloadFile});}catch(e){$('dialog-error').textContent=e.message;}});}catch(e){$('dialog-error').textContent=e.message;}};
}
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;try{
 if(b.dataset.componentInstall)await submitLocalJob(b,'component_install',{id:b.dataset.componentInstall});
 if(b.hasAttribute('data-show-downloads'))openDownloads();
 if(b.dataset.runtime)await submitLocalJob(b,'local_runtime_install',{backend:b.dataset.runtime});
 if(b.hasAttribute('data-gguf-download'))await ggufDownloadDialog();
 if(b.dataset.modelConfig)await localModelSettingsDialog(b.dataset.modelConfig);
 if(b.hasAttribute('data-gguf-import'))await submitLocalJob(b,'local_model_import',{});
 if(b.hasAttribute('data-local-folder')){const r=await action('choose_project_folder');if(r.root)$('local-model-dir').value=r.root;}
 if(b.dataset.localStart)await submitLocalJob(b,'local_start',{id:b.dataset.localStart});
 if(b.hasAttribute('data-local-stop'))await unloadLocalModel(b);
 if(b.dataset.localUse){await action('save_connector',{id:'local',enabled:true,model:b.dataset.localUse});await refresh(true);toast('Moteur local activé. Choisissez CyAI · local dans une nouvelle conversation.');}
 if(b.dataset.enableConnector){const c=state.data.connectors.find(c=>c.id===b.dataset.enableConnector);await action('save_connector',{id:c.id,enabled:!c.enabled});await refresh(true);}
 if(b.hasAttribute('data-update-benchmarks')){b.disabled=true;try{await action('refresh_benchmarks');await renderModelSettings();}finally{b.disabled=false;}}
}catch(error){fail(error);}});
function connectorsSettingsHTML(){
 return `<h3>Connecteurs</h3><p>Activez les connecteurs à utiliser. CyAI teste leur connexion au lancement et après activation. Les autres restent disponibles ici.</p><div class="card-grid">${state.data.connectors.map(c=>`<article class="card"><h3>${esc(agentName(c.id))}</h3>${status(c.enabled?c.status:'Désactivé')}<p>${esc(c.detail)}</p><div class="row-actions"><button class="${c.enabled?'secondary':'primary'}" data-enable-connector="${c.id}">${c.enabled?'Désactiver':'Activer'}</button><button class="secondary" data-configure="${c.id}">Configurer</button><button class="secondary" data-test="${c.id}" ${c.enabled?'':'disabled'}>Tester</button><button class="secondary" data-models="${c.id}">Modèles</button></div>${c.id==='local'?'<button class="secondary" data-local-stop>Décharger le modèle · libérer la VRAM</button><button class="text-button" data-workspace-action="settings-tab" data-tab="local">Gérer les modèles GGUF</button>':''}${c.id==='claude-code'?'<button class="text-button" data-connect="claude-code">Se connecter au compte Claude</button>':''}</article>`).join('')}</div>`;
}

function renderApprovalButton(){
 let b=$('conversation-permissions');if(!b){b=document.createElement('select');b.id='conversation-permissions';b.setAttribute('aria-label','Mode d’autorisation de la conversation');b.title='Automatique : autorise les demandes d’outils sans nouvelle confirmation. Les restrictions de fichiers restent actives.';$('conversation-toolbar').append(b);b.innerHTML='<option value="inherit">Autorisations : réglage global</option><option value="manual">Autorisations : manuelles</option><option value="auto">Autorisations : automatiques</option>';b.onchange=async()=>{b.disabled=true;try{await action('approval_settings',{conversation_id:state.conversation,mode:b.value});await refresh(true);toast('Mode d’autorisation enregistré.');}catch(e){fail(e);}finally{b.disabled=false;}};}
 const mode=JSON.parse(state.detail?.agent_settings||'{}').approval_mode||'inherit';
 if(document.activeElement!==b)b.value=mode;
 b.options[0].textContent='Global : '+(state.data.approval_default==='auto'?'automatique':'manuel');
 renderAccessButton();
}
// What Codex may reach beyond the project, for this conversation. Raised here by you, never by the agent.
const accessLabels={project:'projet seulement',read:'lecture du disque',read_network:'disque + Internet',full:'complet'};
function renderAccessButton(){
 let b=$('conversation-access');
 if(!b){b=document.createElement('select');b.id='conversation-access';b.setAttribute('aria-label','Accès de Codex dans cette conversation');
  b.title='Ce que Codex peut atteindre hors du projet. En lecture du disque, les dossiers de secrets (clés, jetons, profils de navigateur) et les données de CyAI restent fermés et l’écriture reste dans le projet. L’accès complet retire le bac à sable.';
  $('conversation-toolbar').append(b);
  b.innerHTML='<option value="inherit">Accès Codex : réglage global</option>'+Object.entries(accessLabels).map(([k,v])=>`<option value="${k}">Accès Codex : ${v}</option>`).join('');
  b.onchange=async()=>{const level=b.value;
   const save=async()=>{b.disabled=true;try{await action('access_settings',{conversation_id:state.conversation,level});await refresh(true);toast('Accès de Codex enregistré pour cette conversation.');}catch(e){fail(e);}finally{b.disabled=false;}};
   if(level==='full'){b.value=JSON.parse(state.detail?.agent_settings||'{}').agent_access||'inherit';openDialog('Accès complet pour Codex','<p>Dans cette conversation, Codex travaillera sans bac à sable : il pourra lire et écrire partout sur cet ordinateur, y compris dans les données de CyAI, et utiliser Internet. À réserver à une tâche qui en a vraiment besoin.</p>',async()=>{b.value='full';await save();},'Donner l’accès complet');return;}
   await save();};}
 const level=JSON.parse(state.detail?.agent_settings||'{}').agent_access||'inherit';
 if(document.activeElement!==b)b.value=level;
 b.options[0].textContent='Accès Codex : global ('+(accessLabels[state.data.access_default||'project'])+')';
}

function renderApprovalCards(){
 const target=$('live-approvals');if(!target)return;
 const approvals=(state.data?.approvals||[]).filter(a=>a.mission_id===state.mission?.id||(state.detail?.background||[]).some(b=>b.id===a.mission_id));
 htmlIfChanged('live-approvals',approvals.map(a=>{const request=a.data.request||a.data.input||{},reason=request.reason||request.message||a.data.reason||a.data.notice||'Cet outil demande votre autorisation pour continuer.',command=a.data.summary||request.command||request.commandLine||request._meta?.origin||a.data.tool||a.data.method||'Action de l’agent',session=a.data.method==='item/permissions/requestApproval';return `<article class="message approval" role="alert"><div class="message-header"><strong>Autorisation requise · ${esc(agentName(a.data.provider||''))}</strong></div><p>${esc(reason)}</p><pre>${esc(typeof command==='string'?command:JSON.stringify(command))}</pre><details><summary>Détails de la demande</summary><pre>${esc(JSON.stringify(a.data,null,2))}</pre></details><div class="row-actions"><button class="secondary" data-approve="${a.id}" data-accepted="false">Refuser</button><button class="primary" data-approve="${a.id}" data-accepted="true">${session?'Accorder pour cette conversation':'Autoriser une fois'}</button><button class="secondary" data-permission-conversation>Configurer l’approbation automatique</button></div></article>`;}).join('')+((state.data.mcp_jobs||[]).some(j=>j.conversation_id===state.conversation)?mcpJobsHTML(state.data.mcp_jobs.filter(j=>j.conversation_id===state.conversation)):''));
}
function permissionDialog(global=false){
 const own=JSON.parse(state.detail?.agent_settings||'{}'),mode=global?(state.data.approval_default||'manual'):(own.approval_mode||'inherit');
 openDialog(global?'Autorisations par défaut':'Autorisations de cette conversation',`<label>Approbation<select name="mode">${[...(!global?[['inherit','Utiliser le réglage global']]:[]),['manual','Demander à chaque fois'],['auto','Approuver automatiquement les demandes d’outils']].map(([id,label])=>`<option value="${id}" ${mode===id?'selected':''}>${label}</option>`).join('')}</select></label>${global?`<label>Accès de Codex par défaut<select name="access">${Object.entries(accessLabels).map(([id,label])=>`<option value="${id}" ${(state.data.access_default||'project')===id?'selected':''}>${label[0].toUpperCase()+label.slice(1)}</option>`).join('')}</select></label><p>En lecture du disque, les dossiers de secrets (clés SSH, jetons, profils de navigateur) et les données de CyAI restent fermés, et Codex n’écrit que dans le projet. L’accès complet retire le bac à sable de Codex. Chaque conversation peut choisir autrement dans sa barre.</p>`:''}<p>L’approbation automatique autorise aussi les demandes déjà en attente dans les conversations concernées. Les commandes et modifications peuvent alors s’exécuter sans nouvelle confirmation. Les restrictions de fichiers de CyAI restent appliquées ; les plans d’orchestration nécessitent toujours votre lancement.</p><p>Chaque décision automatique est enregistrée dans les événements de la mission.</p>`,async form=>{await action('approval_settings',{mode:form.get('mode'),...(!global?{conversation_id:state.conversation}:{})});if(global&&form.get('access'))await action('access_settings',{level:form.get('access')});await refresh(true);});
}
document.addEventListener('click',e=>{if(e.target.closest('[data-permission-conversation]'))permissionDialog(false);if(e.target.closest('[data-permission-global]'))permissionDialog(true);});

async function localModelSettingsDialog(id){
 const info=await action('local_state'),model=info.models.find(m=>m.id===id),own=model.settings||{};
 openDialog('Réglages · '+model.name,`<p>Laissez un champ vide pour hériter de la valeur globale. Les réglages seront utilisés lors du prochain chargement.</p><label>Moteur<select name="runtime_family">${[['','Automatique selon le modèle'],['standard','llama.cpp standard'],['prism','PrismML (Bonsai 2)']].map(([id,n])=>`<option value="${id}" ${(own.runtime_family||'')===id?'selected':''}>${n}</option>`).join('')}</select></label><label>Calcul<select name="device">${[['','Global ('+info.settings.device+')'],['cpu','CPU'],['gpu','GPU'],['hybrid','GPU + CPU']].map(([id,n])=>`<option value="${id}" ${(own.device||'')===id?'selected':''}>${n}</option>`).join('')}</select></label>${[['gpu_layers','Couches GPU',0,999],['threads','Threads CPU',1,256],['context','Contexte en tokens',512,null]].map(([k,label,min,max])=>`<label>${label}<input type="number" name="${k}" min="${min}" ${max==null?'':`max="${max}"`} value="${own[k]??''}" placeholder="Global : ${info.settings[k]}"></label>`).join('')}`,async form=>{await action('local_model_settings',{id,settings:Object.fromEntries(form)});renderLocalModels();});
}

// Available outside conversations: closing a chat does not stop the shared engine.
let localUnloadBusy=false,localRuntimePolling=false;
function paintLocalUnload(info){
 let button=$('unload-local-model');
 if(!button){const host=document.querySelector('.top-actions')||$('resource-usage')?.parentElement;if(!host)return;button=document.createElement('button');button.id='unload-local-model';button.className='secondary';button.setAttribute('data-local-stop','');host.prepend(button);}
 const name=info.models.find(m=>m.id===info.loaded)?.name||info.loaded||'';
 button.hidden=!info.running&&!localUnloadBusy;
 button.disabled=localUnloadBusy;
 button.textContent=localUnloadBusy?'Arrêt…':'■ Arrêter / décharger le modèle';
 button.title=name?'Modèle chargé : '+name:'Moteur local arrêté';
 button.setAttribute('aria-busy',String(localUnloadBusy));
}
async function refreshLocalUnload(){
 if(localRuntimePolling||localUnloadBusy)return;
 localRuntimePolling=true;
 try{paintLocalUnload(await action('local_state'));}catch(_){/* Main connection indicator handles service outages. */}
 finally{localRuntimePolling=false;}
}
async function unloadLocalModel(button){
 if(localUnloadBusy)return;
 localUnloadBusy=true;const label=button.textContent;button.disabled=true;button.textContent='Déchargement…';button.setAttribute('aria-busy','true');
 try{
  await action('local_stop');
  const info=await action('local_state');
  if(info.running)throw new Error('Le moteur est encore actif. Le déchargement n’est pas confirmé.');
  toast('Modèle déchargé : mémoire du moteur libérée. Les fichiers GGUF sont conservés.');
  if(state.view==='settings'&&state.settingsTab==='local')await renderLocalModels();
 }finally{localUnloadBusy=false;button.disabled=false;button.textContent=label;button.removeAttribute('aria-busy');await refreshLocalUnload();}
}
setInterval(refreshLocalUnload,2500);
refreshLocalUnload();
