'use strict';
function displayMessage(text){text=text.replace(/<cyai-continuity>[\s\S]*?<\/cyai-continuity>/g,'').trim();try{const r=JSON.parse(text.replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,''));return typeof r.reply==='string'?r.reply:text;}catch{return text;}}
function planHTML(proposal, controls=true){
  const plan=proposal.plan, steps=plan.steps;
  const depths=steps.map((s,i)=>s.depends_on.length?1+Math.max(...s.depends_on.map(d=>depthsSafe(d))):0);
  function depthsSafe(i){const s=steps[i];return s.depends_on.length?1+Math.max(...s.depends_on.map(depthsSafe)):0;}
  const levels=Math.max(...depths)+1, counts=Array.from({length:levels},(_,d)=>depths.filter(v=>v===d).length);
  const width=Math.max(650,Math.max(...counts)*235), slots={};
  const points=steps.map((s,i)=>{const d=depths[i], slot=slots[d]||0;slots[d]=slot+1;return {x:(width-counts[d]*225)/2+slot*225+8,y:d*105+12};});
  const edges=steps.flatMap((s,i)=>s.depends_on.map(d=>{const a=points[d],b=points[i];return `<path d="M${a.x+103} ${a.y+66} C${a.x+103} ${a.y+89},${b.x+103} ${b.y-18},${b.x+103} ${b.y}" fill="none" stroke="#9f8ada" stroke-width="2"/><path d="M${b.x+99} ${b.y-6} L${b.x+103} ${b.y} L${b.x+107} ${b.y-6}" fill="none" stroke="#9f8ada"/>`;})).join('');
  const nodes=steps.map((s,i)=>{const p=points[i],run=proposal.execution?.steps?.find(x=>x.position===i);return `<g data-graph-node="${i}"><title>${esc(s.name)} · ${esc(agentName(s.connector))} · ${esc(s.model||'Modèle par défaut')}</title><rect x="${p.x}" y="${p.y}" width="206" height="66" rx="9" fill="#242333" stroke="${nodeAppearance(run?.status).color}" stroke-width="3"/><text x="${p.x+12}" y="${p.y+24}" fill="#eee8ff" font-size="12">${i+1}. ${esc(s.name.slice(0,24))}</text><text x="${p.x+12}" y="${p.y+46}" fill="#bbb3cd" font-size="10">${esc(agentName(s.connector))} · ${esc((s.model||'Modèle par défaut').slice(0,23))}</text><text data-node-status x="${p.x+12}" y="${p.y+60}" fill="${nodeAppearance(run?.status).color}" font-size="10">${esc(nodeAppearance(run?.status).label)}</text></g>`;}).join('');
  return `<div class="plan-card"><div class="page-heading"><div><small>PLAN DE L’ORCHESTRATEUR</small><h3>${esc(plan.title)}</h3></div>${proposal.execution?status(proposal.execution.status):'<span class="status configured">À autoriser</span>'}</div>${controls?`<div class="row-actions">${!proposal.execution?`<button class="primary" data-approve-plan="${proposal.id}">Régler et autoriser</button>`:`<button class="secondary" data-mission="${proposal.execution.id}">Voir l’exécution</button>`}<button class="text-button" data-revise-plan="${proposal.id}">Demander une révision</button></div>`:''}<div class="plan-viewer" data-plan-viewer="${esc(proposal.id)}"><div class="row-actions graph-toolbar" aria-label="Navigation du graphe"><button type="button" class="secondary" data-graph-action="out" aria-label="Réduire le graphe">−</button><output class="graph-scale">125 %</output><button type="button" class="secondary" data-graph-action="in" aria-label="Agrandir le graphe">＋</button><button type="button" class="secondary" data-graph-action="reset">100 %</button><button type="button" class="secondary" data-graph-action="fit">Tout voir</button><button type="button" class="secondary" data-graph-action="expand">Vue agrandie</button></div><div class="plan-graph" tabindex="0" aria-label="Graphe défilant : Ctrl et molette pour zoomer, glisser pour déplacer" data-zoom="1.25"><svg style="width:${width*1.25}px;height:${levels*105*1.25}px" role="img" aria-label="Graphe des tâches et de leurs dépendances" viewBox="0 0 ${width} ${levels*105}" xmlns="http://www.w3.org/2000/svg">${edges}${nodes}</svg></div><small>Ctrl + molette : zoom · Glisser : déplacer · Survoler une tâche : intitulé complet</small></div><p class="field-help">Les flèches indiquent les dépendances. Les branches indépendantes peuvent travailler en parallèle ; une tâche attend la réussite de ses dépendances.</p>${steps.map((s,i)=>`<details class="event"><summary>${i+1}. ${esc(s.name)} · ${esc(agentName(s.connector))}</summary><p>${esc(s.instruction)}</p><small>Modèle : ${esc(s.model||'défaut du connecteur')} · Effort : ${esc(s.effort||'défaut')} · Vitesse : ${esc(s.service_tier||'défaut')} · Dépend de : ${s.depends_on.map(d=>d+1).join(', ')||'aucune tâche'}<br>Contrôle : ${esc(s.validation?.type||'réponse non vide')}${s.validation?.value?' · '+esc(s.validation.value):''}</small></details>`).join('')}</div>`;
}
function renderPlan(){
  const planning=state.detail?.mode==='orchestrator';
  $('conversation-subtitle').textContent=planning?'Orchestrateur · plan soumis à votre autorisation':state.detail?.mode==='team'?'Équipe · agent du projet, consignes de sa révision figée':'Normal · un seul agent, mémoire du projet';
  $('instruction').placeholder=planning?'Discutez de votre objectif. L’orchestrateur proposera un plan à autoriser…':'Discutez avec votre IA et la mémoire partagée du projet…';
  const proposal=state.detail?.plans?.[0];
  let choices=[];
  const last=state.detail?.messages?.filter(m=>m.role==='assistant').at(-1);
  try{choices=JSON.parse(last?.content.replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,'')).choices||[];}catch{}
  const choicesHTML=planning&&choices.length?`<div class="plan-card"><strong>Votre choix</strong><div class="row-actions">${choices.slice(0,4).map((c,i)=>`<button type="button" class="secondary" data-proposal-choice="${esc(c)}">${esc(c)}${i===0?' · Recommandé':''}</button>`).join('')}</div><small>Le choix prépare votre réponse ; vous pouvez la modifier avant envoi.</small></div>`:'';
  $('plan-panel').hidden=!proposal&&!choicesHTML;
  const previousGraph=$('plan-panel').querySelector('.plan-viewer');
  const view=previousGraph?graphSnapshot(previousGraph):null;
  const planContent=proposal?`<div class="plan-fold-header"><strong>${esc(proposal.plan.title)}</strong>${proposal.execution?status(proposal.execution.status):'<span>En attente de votre validation</span>'}<button type="button" class="secondary" data-open-plan="${esc(proposal.id)}">Ouvrir le plan en grand</button><button type="button" class="secondary" data-agent-sessions>Sessions des agents</button></div>`:'';
  htmlIfChanged('plan-panel',planContent+choicesHTML);
  const nextGraph=$('plan-panel').querySelector('.plan-viewer');
  if(view&&nextGraph?.dataset.planViewer===view.id)restoreGraph(nextGraph,view);
  $('orchestrator-tools').hidden=!planning;
  syncPlanActivity();
}
function usageHTML(rows){
  const groups={};
  for(const row of rows){const key=row.connector+' / '+(row.model||'défaut');const g=groups[key]||(groups[key]={calls:0,input:0,output:0,known:0,cost:0,costKnown:0});g.calls++;
    try{const u=JSON.parse(row.usage||'null');if(!u)continue;const t=u.last||u.tokens||u;const input=t.input_tokens??t.inputTokens??t.input??t.prompt_tokens,output=t.output_tokens??t.outputTokens??t.output??t.completion_tokens;if(typeof input==='number'&&typeof output==='number'){g.input+=input;g.output+=output;g.known++;}if(typeof u.cost_usd==='number'){g.cost+=u.cost_usd;g.costKnown++;}}catch{}
  }
  return `<div class="table-scroll"><table class="project-table"><thead><tr><th>Agent / modèle</th><th>Tâches</th><th>Tokens entrée / sortie</th><th>Coût fourni</th></tr></thead><tbody>${Object.entries(groups).map(([key,g])=>`<tr><td>${esc(key)}</td><td>${g.calls}</td><td>${g.known?`${g.input.toLocaleString()} / ${g.output.toLocaleString()} (${g.known}/${g.calls} renseignées)`:'Non fourni'}</td><td>${g.costKnown?'$'+g.cost.toFixed(4)+' (partiel si usage absent)':'Non fourni'}</td></tr>`).join('')||'<tr><td colspan="4">Aucune utilisation enregistrée.</td></tr>'}</tbody></table></div>`;
}
let projectRendering=0;
async function renderProjectPage(){
  const request=++projectRendering,navigation=state.navigationVersion,requestedTab=state.projectTab;
  if(!state.project){htmlIfChanged('page','<div class="page-intro"><h2>Vos projets</h2><p>Choisissez un dossier pour commencer.</p><button id="welcome-project" class="primary">Créer un projet</button></div>');return;}
  const id=state.project,page=$('page');
  const current=()=>request===projectRendering&&navigation===state.navigationVersion&&state.view==='project'&&state.project===id;
  if(page.dataset.projectId!==id||!page.querySelector('.project-content'))htmlIfChanged('page','<p class="empty-state" role="status">Chargement du projet…</p>');
  else if(page.dataset.projectTab!==(requestedTab||'overview')){
    const section=page.querySelector('.project-content');if(section){section.innerHTML='<p role="status">Chargement de cette section…</p>';page._rendered=null;}
    page.querySelectorAll('[data-project-tab]').forEach(button=>{const selected=button.dataset.projectTab===(requestedTab||'overview');button.classList.toggle('selected',selected);button.setAttribute('aria-current',selected?'page':'false');});
  }
  try{
  const p=await api('project/'+id);if(request!==projectRendering||navigation!==state.navigationVersion||state.view!=='project'||state.project!==id||requestedTab!==state.projectTab)return;
  state.projectDetail=p;state.projectTab=state.projectTab||'overview';
  $('page-title').textContent=p.name;
  if(state.projectTab.startsWith('plugin:')&&!projectMemoryPlugins().some(plugin=>'plugin:'+plugin.id===state.projectTab))state.projectTab='overview';
  const tab=state.projectTab;
  const tabs={overview:'Projet',team:'Équipe'+(p.team?.exists?(p.team.ready?' ✓':' · brouillon'):''),board:'Board',memory:'Mémoire partagée',skills:'Skills & contexte',plugins:'Plugins'};
  const projectSection=['overview','usage','history','statistics','settings'].includes(tab);
  const subnav=projectSection?`<nav class="project-subtabs">${Object.entries({overview:'Vue d’ensemble',usage:'Utilisation IA',history:'Historique',statistics:'Statistiques & stockage',settings:'Configuration'}).map(([k,v])=>`<button class="${tab===k?'selected':''}" data-project-tab="${k}">${v}</button>`).join('')}</nav>`:'';
  for(const plugin of projectMemoryPlugins())tabs['plugin:'+plugin.id]=plugin.name;
  let content='';
  if(tab.startsWith('plugin:'))content=memoryPluginHTML(tab.slice(7));
  if(tab==='overview')content=`<div class="project-stats"><div><b>${p.conversations.filter(c=>!c.archived).length}</b> conversations</div><div><b>${p.missions.filter(m=>active(m.status)).length}</b> actions en cours</div><div><b>${p.memory.filter(m=>m.validated).length}</b> mémoires validées</div></div><h3>Conversations</h3><div class="project-conversation-grid">${p.conversations.filter(c=>!c.archived).map(c=>`<button class="project-conversation-card" data-conversation="${c.id}"><span>${c.mode==='orchestrator'?'⌘ Orchestrateur multi-modèles':'◌ Normal'}</span><strong>${esc(c.title)}</strong><small>${date(c.created_at)}</small></button>`).join('')||'<p class="muted">Créez une discussion ou un orchestrateur pour ce projet.</p>'}</div><h3>Activité récente</h3>${p.missions.slice(0,15).map(m=>`<article class="mission-row"><button class="title" data-mission="${m.id}">${esc(m.title)}<small>${m.planning?'Discussion / planification':'Exécution'} · ${date(m.created_at)}</small></button>${status(m.status)}</article>`).join('')||'<p class="muted">Aucune action pour le moment.</p>'}`;
  if(tab==='statistics')content=analyticsHTML(await action('analytics',{project_id:id}));
  if(tab==='usage')content=usageHTML(p.usage);
  if(tab==='history')content=p.history.map(h=>`<article class="mission-row"><button data-conversation="${h.conversation_id}" class="title">${esc(h.title)}<small>${h.role==='user'?'Vous':esc(agentName(h.connector))} ${esc(h.model||'')} · ${date(h.created_at)}</small></button></article>`).join('')||'<p>Aucun historique.</p>';
  if(tab==='memory'){state.memory=p.memory;content=memoryHTML(p.memory,p);}
  if(tab==='team')content=await teamTabHTML(id);
  if(tab==='team'&&content.includes('<div id="team-learning"></div>'))content=content.replace('<div id="team-learning"></div>',await teamLearningHTML(id));
  if(tab==='team'&&content.includes('<div id="team-scorecard"></div>'))content=content.replace('<div id="team-scorecard"></div>',await teamScorecardHTML(id));
  if(tab==='board')content=await boardTabHTML(p);
  if(tab==='pins')content=await pinsHTML(id);
  if(tab==='media')content=await mediaHTML(id);
  if(tab==='skills')content=agentSettingsPanel('project',p);
  if(tab==='plugins')content=projectPluginsHTML();
  if(tab==='settings')content=`<button type="button" class="secondary" data-workspace-action="appearance">Logo, couleur et catégorie</button><form id="project-settings"><div class="fields"><label>Nom du projet<input name="name" value="${esc(p.name)}" required></label><label>Dossier de travail<input name="root" id="settings-root" value="${esc(p.root)}" required></label><button type="button" id="settings-browse" class="secondary">Parcourir…</button><p class="field-help">Changer de dossier conserve les messages et réinitialise les sessions natives pour le nouveau dossier.</p></div><button class="primary">Enregistrer le projet</button></form>${gitPanelHTML(p.git)}`;
  if(request!==projectRendering||navigation!==state.navigationVersion||state.view!=='project'||state.project!==id||state.projectTab!==tab)return;
  htmlIfChanged('page',`<div class="page-intro project-intro"><div><small>PROJET</small><h2>${esc(p.name)}</h2><p>${esc(p.root)}</p></div><div class="row-actions"><button class="primary" data-project-new="true">＋ Nouvelle conversation</button><button class="secondary" data-project-mission="true">Nouvelle mission</button></div></div><nav class="project-tabs" aria-label="Sections du projet">${Object.entries(tabs).map(([key,label])=>`<button class="${tab===key||(key==='overview'&&projectSection)?'selected':''}" data-project-tab="${key}">${label}</button>`).join('')}</nav>${subnav}<div class="project-content">${content}</div>`);
  page.dataset.projectId=id;page.dataset.projectTab=tab;
  if(tab==='settings'){
    $('settings-browse').onclick=async()=>{try{const r=await action('choose_project_folder');if(r.root&&state.view==='project'&&state.project===id&&state.projectTab==='settings'&&$('settings-root'))$('settings-root').value=r.root;}catch(e){fail(e);}};
    $('project-settings').onsubmit=async e=>{e.preventDefault();try{await action('update_project',{id,...Object.fromEntries(new FormData(e.target))});toast('Projet enregistré.');await refresh(true);}catch(e){fail(e);}};
  }
  }catch(error){if(!current())return;const message=`<p class="error" role="alert">Impossible de charger cette section : ${esc(error.message)}</p><button type="button" class="secondary" data-project-tab="${esc(requestedTab||'overview')}">Réessayer</button>`;const section=page.querySelector('.project-content');if(section){section.innerHTML=message;page._rendered=null;}else htmlIfChanged('page',message);}
}
let planAdjustment=null;
function planAssignmentHTML(step,i){
 const connectors=state.data.connectors.filter(c=>c.enabled),models=state.data.models_cache?.[step.connector]||[];
 const current=models.find(m=>m.id===step.model),efforts=['',...(current?.efforts||[]).map(e=>e.reasoningEffort)];
 if(step.effort&&!efforts.includes(step.effort))efforts.push(step.effort);
 if(step.connector!=='codex')step.service_tier='';
 const tiers=[{id:'',name:'Défaut'},...(step.connector==='codex'?(current?.service_tiers||[]):[])];
 if(step.service_tier&&!tiers.some(t=>t.id===step.service_tier))tiers.push({id:step.service_tier,name:step.service_tier});
 return `<fieldset class="fields" data-plan-step="${i}"><legend>${i+1}. ${esc(step.name)}</legend><div class="two-fields"><label>Agent<select data-plan-field="connector">${connectors.map(c=>`<option value="${esc(c.id)}" ${c.id===step.connector?'selected':''}>${esc(agentName(c.id))}</option>`).join('')}</select></label><label>Modèle<select data-plan-field="model"><option value="">Défaut du connecteur</option>${[...models,...(step.model&&!current?[{id:step.model}]:[])].map(m=>`<option value="${esc(m.id)}" ${m.id===step.model?'selected':''}>${esc(m.name||m.id)}</option>`).join('')}</select></label></div><label>Effort : <output>${esc(step.effort||'Défaut')}</output><input type="range" data-plan-field="effort" data-values="${esc(JSON.stringify(efforts))}" min="0" max="${efforts.length-1}" step="1" value="${Math.max(0,efforts.indexOf(step.effort||''))}" ${efforts.length===1?'disabled':''}></label><label ${step.connector!=='codex'?'hidden':''}>Vitesse<select data-plan-field="service_tier">${tiers.map(t=>`<option value="${esc(t.id)}" ${t.id===(step.service_tier||'')?'selected':''}>${esc(t.name||t.id)}</option>`).join('')}</select></label></fieldset>`;
}
async function openPlanAdjustment(proposal){
 const ids=[...new Set(proposal.plan.steps.map(s=>s.connector))];
 for(const id of ids){if(!(state.data.models_cache?.[id]||[]).length){try{const r=await action('list_models',{id});state.data.models_cache[id]=r.models;}catch(err){toast(err.message);}}}
 if($('dialog').open)$('dialog').close();
 planAdjustment={proposal,steps:structuredClone(proposal.plan.steps)};
 openDialog('Réglages de la proposition',`<p>Les affectations ci-dessous seront utilisées après votre autorisation. Aucun changement automatique de modèle pendant ce plan.</p><details><summary>Demander une autre répartition</summary><div class="row-actions">${['Économique','Équilibré','Qualité maximale'].map(x=>`<button type="button" class="secondary" data-plan-preset="${x}">${x}</button>`).join('')}</div><label>Priorité <output id="plan-priority-label">Équilibre</output><input id="plan-priority" type="range" min="0" max="2" value="1" step="1"></label><label><input id="plan-local-only" type="checkbox"> Uniquement des modèles locaux</label><label>Contraintes et budget souhaité<textarea id="plan-constraints" placeholder="Ex. privilégier la rapidité ; demander avant une dépense supplémentaire"></textarea></label><p class="field-help">Ces préférences servent à refaire le plan. Un budget écrit ici n’est pas un plafond de facturation garanti.</p><button type="button" class="secondary" data-plan-rethink>Préparer la demande de révision</button></details><label>Agents simultanés<input id="plan-concurrency" type="number" min="1" max="32" value="3" required></label><label>Durée maximale de la mission (minutes, 0 = sans limite)<input id="plan-timeout" type="number" min="0" value="0" required></label><div id="plan-assignments">${planAdjustment.steps.map(planAssignmentHTML).join('')}</div><p class="field-help">Le curseur utilise seulement les efforts annoncés par le catalogue. La vitesse et l’effort peuvent augmenter la consommation. Les instructions et dépendances du plan sont conservées.</p>`,async()=>{const r=await action('approve_plan',{id:proposal.id,acknowledged:true,timeout_seconds:Number($('plan-timeout').value)*60,concurrency:Number($('plan-concurrency').value),assignments:planAdjustment.steps.map(({connector,model,effort,service_tier})=>({connector,model,effort:effort||'',service_tier:service_tier||''}))});state.missionId=r.mission_id;},'Autoriser ces réglages et exécuter');
}
document.addEventListener('input',e=>{
 if(e.target.id==='plan-priority')$('plan-priority-label').textContent=['Économie','Équilibre','Qualité'][+e.target.value];
 if(e.target.dataset.planField==='effort'){
  const step=planAdjustment.steps[+e.target.closest('[data-plan-step]').dataset.planStep];
  step.effort=JSON.parse(e.target.dataset.values)[+e.target.value];e.target.parentElement.querySelector('output').textContent=step.effort||'Défaut';
 }
});
document.addEventListener('change',async e=>{
 const field=e.target.dataset.planField;if(!field||field==='effort')return;
 const step=planAdjustment.steps[+e.target.closest('[data-plan-step]').dataset.planStep];step[field]=e.target.value;
 if(field==='connector'){step.model='';if(!(state.data.models_cache?.[step.connector]||[]).length){e.target.disabled=true;toast('Chargement des modèles…');try{const r=await action('list_models',{id:step.connector});state.data.models_cache[step.connector]=r.models;}catch(err){toast(err.message);}finally{e.target.disabled=false;}}}
 if(field==='connector'||field==='model'){step.effort='';step.service_tier='';$('plan-assignments').innerHTML=planAdjustment.steps.map(planAssignmentHTML).join('');}
});
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b)return;
 if(b.dataset.proposalChoice){$('instruction').value=b.dataset.proposalChoice;$('instruction').focus();}
 if(b.dataset.planPreset){$('plan-priority').value={'Économique':0,'Équilibré':1,'Qualité maximale':2}[b.dataset.planPreset];$('plan-priority').dispatchEvent(new Event('input',{bubbles:true}));}
 if(b.hasAttribute('data-plan-rethink')){
  $('instruction').value=`Propose une nouvelle répartition du plan « ${planAdjustment.proposal.plan.title} ». Priorité : ${$('plan-priority-label').textContent}. ${$('plan-local-only').checked?'Utilise uniquement des modèles locaux. ':''}${$('plan-constraints').value}\nExplique tes choix et présente des alternatives si tu hésites. Ne commence pas l’exécution.`;
  $('dialog').close();$('instruction').focus();toast('Demande préparée : modifiez-la ou envoyez-la à l’orchestrateur.');
 }
});

function graphSnapshot(viewer){const g=viewer.querySelector('.plan-graph');return {id:viewer.dataset.planViewer,zoom:+g.dataset.zoom,x:g.scrollLeft,y:g.scrollTop};}
function restoreGraph(viewer,v){setGraphZoom(viewer,v.zoom);const g=viewer.querySelector('.plan-graph');g.scrollLeft=v.x;g.scrollTop=v.y;}
function setGraphZoom(viewer,zoom,anchor){
 const g=viewer.querySelector('.plan-graph'),svg=g.querySelector('svg'),box=svg.viewBox.baseVal;
 const old=+g.dataset.zoom||1, z=Math.max(.2,Math.min(4,zoom));
 const a=anchor||{x:g.clientWidth/2,y:g.clientHeight/2},x=(g.scrollLeft+a.x)/old,y=(g.scrollTop+a.y)/old;
 svg.style.width=box.width*z+'px';svg.style.height=box.height*z+'px';g.dataset.zoom=z;
 viewer.querySelector('.graph-scale').textContent=Math.round(z*100)+' %';
 g.scrollLeft=x*z-a.x;g.scrollTop=y*z-a.y;
}
document.addEventListener('click',e=>{
 const b=e.target.closest('[data-graph-action]');if(!b)return;
 const viewer=b.closest('.plan-viewer'),g=viewer.querySelector('.plan-graph'),action=b.dataset.graphAction;
 if(action==='expand'){
  const v=graphSnapshot(viewer);openDialog('Graphe du plan',viewer.outerHTML,null);
  $('dialog').classList.add('graph-dialog');const large=$('dialog-content').querySelector('.plan-viewer');
  large.querySelector('[data-graph-action="expand"]').remove();restoreGraph(large,v);
  $('dialog').addEventListener('close',()=>$('dialog').classList.remove('graph-dialog'),{once:true});return;
 }
 const box=g.querySelector('svg').viewBox.baseVal;
 setGraphZoom(viewer,action==='fit'?Math.min((g.clientWidth-20)/box.width,(g.clientHeight-20)/box.height):action==='reset'?1:(+g.dataset.zoom)*(action==='in'?1.25:.8));
 if(action==='fit'||action==='reset'){g.scrollLeft=0;g.scrollTop=0;}
});
document.addEventListener('wheel',e=>{
 const g=e.target.closest('.plan-graph');if(!g||!e.ctrlKey)return;
 e.preventDefault();const r=g.getBoundingClientRect();setGraphZoom(g.closest('.plan-viewer'),(+g.dataset.zoom)*Math.exp(-e.deltaY*.002),{x:e.clientX-r.left,y:e.clientY-r.top});
},{passive:false});
let graphDrag=null;
document.addEventListener('pointerdown',e=>{
 const g=e.target.closest('.plan-graph');if(!g||e.button!==0||e.pointerType==='touch')return;
 const rect=g.getBoundingClientRect();if(e.clientX-rect.left>=g.clientWidth||e.clientY-rect.top>=g.clientHeight)return;
 graphDrag={g,id:e.pointerId,x:e.clientX,y:e.clientY,left:g.scrollLeft,top:g.scrollTop};g.setPointerCapture(e.pointerId);g.classList.add('dragging');e.preventDefault();
});
document.addEventListener('pointermove',e=>{if(!graphDrag||graphDrag.id!==e.pointerId)return;const d=graphDrag;d.g.scrollLeft=d.left+d.x-e.clientX;d.g.scrollTop=d.top+d.y-e.clientY;});
function stopGraphDrag(e){if(!graphDrag||graphDrag.id!==e.pointerId)return;graphDrag.g.classList.remove('dragging');graphDrag=null;}
document.addEventListener('pointerup',stopGraphDrag);
document.addEventListener('pointercancel',stopGraphDrag);

document.addEventListener('click',e=>{
 const b=e.target.closest('[data-open-plan]');if(!b)return;
 const proposal=state.detail?.plans?.find(p=>p.id===b.dataset.openPlan);if(!proposal)return;
 openDialog('Plan de la conversation',planHTML(proposal),null);
 $('dialog').classList.add('graph-dialog');$('cancel-dialog').textContent='Retour à la conversation';
 $('dialog').addEventListener('close',()=>$('dialog').classList.remove('graph-dialog'),{once:true});
 syncPlanActivity();
 const expand=$('dialog-content').querySelector('[data-graph-action="expand"]');if(expand)expand.remove();
});

function nodeAppearance(status){return {running:{color:'#71b7ff',label:'En cours'},awaiting_approval:{color:'#ffcd70',label:'Autorisation requise'},succeeded:{color:'#72d0b0',label:'Terminée'},failed:{color:'#ff838b',label:'Échec'},cancelled:{color:'#c0a0ba',label:'Annulée'},interrupted:{color:'#ff838b',label:'Interrompue'},skipped:{color:'#aaa',label:'Ignorée'}}[status]||{color:'#9690a5',label:'En attente'};}
function syncPlanActivity(){
 for(const viewer of document.querySelectorAll('.plan-viewer')){
  const p=state.detail?.plans?.find(p=>p.id===viewer.dataset.planViewer);if(!p)continue;
  const mission=state.mission?.id===p.execution?.id?state.mission:p.execution;
  for(const node of viewer.querySelectorAll('[data-graph-node]')){
   const step=mission?.steps?.find(s=>s.position===+node.dataset.graphNode),v=nodeAppearance(step?.status);
   node.querySelector('rect').setAttribute('stroke',v.color);node.querySelector('rect').setAttribute('fill',step?.status==='running'?'#20394f':'#242333');
   const text=node.querySelector('[data-node-status]');const timing=taskTiming(mission,step);text.textContent=v.label+(timing&&!timing.incomplete?' · '+durationText(timing.elapsed):'');node.querySelector('title').textContent=(step?.name||p.plan.steps[+node.dataset.graphNode]?.name||'')+' · '+taskTimeLabel(mission,step);text.setAttribute('fill',v.color);
  }
  let follow=viewer.querySelector('.graph-live-summary');if(!follow){follow=document.createElement('p');follow.className='graph-live-summary';follow.setAttribute('role','status');viewer.prepend(follow);}
  const currents=mission?.steps?.filter(s=>['running','awaiting_approval'].includes(s.status))||[];
  const current=currents[0];
  const name=current&&(current.name||p.plan.steps[current.position]?.name);
  follow.textContent=!mission?'Plan prêt : validez pour démarrer.':current?currents.map(s=>`${nodeAppearance(s.status).label} · Étape ${s.position+1} : ${s.name||p.plan.steps[s.position]?.name} · ${taskTimeLabel(mission,s)}`).join(' | '):`${mission.steps?.filter(s=>s.status==='succeeded').length||0}/${p.plan.steps.length} étapes terminées · ${mission.status}`;
 }
}
document.addEventListener('click',e=>{
 if(e.target.closest('[data-show-approvals]')){if($('dialog').open)$('dialog').close();$('live-approvals')?.scrollIntoView({block:'center',behavior:'smooth'});}
});

document.addEventListener('click',e=>{
 if(!e.target.closest('[data-agent-sessions]'))return;
 const sessions=(state.detail?.sessions||[]).filter(s=>s.native_id);
 const project=state.data.projects.find(p=>p.id===state.detail?.project_id);
 const nativeSettings=JSON.parse(state.detail?.agent_settings||'{}');
 const root=nativeSettings.native_directory||JSON.parse(project?.agent_settings||'{}').native_directory||project?.root||'';
 openDialog('Sessions des agents',`<p><strong>Projet CyAI : ${esc(project?.name||'Discussion libre')}</strong><br>Dossier transmis aux agents : <code>${esc(root)}</code></p><p>Le rattachement au dossier est automatique. L’enregistrement d’un projet dans la barre latérale de Codex ou Claude Desktop n’est pas confirmé par leurs connecteurs.</p><p>Le suivi en direct est dans CyAI. Claude Code utilise des sessions locales du CLI ; leur apparition dans Claude Desktop n’est pas automatique.</p><p>Attendez la fin de l’exécution CyAI avant de reprendre la même session dans un autre client.</p>${sessions.map(s=>`<section class="event"><strong>${esc(agentName(s.connector))} · ${esc(s.model||'Défaut')}</strong><p>Session : <code>${esc(s.native_id)}</code></p>${s.connector==='claude-code'&&/^[a-zA-Z0-9-]+$/.test(s.native_id)?`<p>Dans un terminal du dossier du projet :</p><pre>claude --resume ${esc(s.native_id)}</pre>`:''}</section>`).join('')||'<p>Aucune session native créée pour le moment. Le plan seul ne lance pas ses agents.</p>'}`,null);
});

function planRequestHTML(message){
 const p=state.detail?.plans?.[0];if(!p||message.role!=='assistant')return '';
 const matches=state.detail.messages.filter(m=>{if(m.role!=='assistant')return false;try{return JSON.parse(m.content.replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,'')).plan?.title===p.plan.title;}catch{return false;}});
 if(matches.at(-1)?.id!==message.id)return '';
 return `<section class="inline-plan-request" aria-label="Validation du plan"><strong>${p.execution?'Plan validé':'Votre validation est nécessaire pour démarrer'}</strong><p>${p.execution?'Suivez les étapes dans le graphe.':'L’IA a préparé ce plan. Aucune de ses tâches n’a encore été lancée.'}</p><div class="row-actions">${!p.execution?`<button type="button" class="primary" data-approve-plan="${esc(p.id)}">Valider et lancer le plan</button><button type="button" class="secondary" data-revise-plan="${esc(p.id)}">Demander des modifications</button>`:''}<button type="button" class="secondary" data-open-plan="${esc(p.id)}">Voir le plan</button></div></section>`;
}

// Durations derive from persisted events, including historical attempts.
function taskTiming(mission,step,now=Date.now()){
 if(!mission||!step)return null;
 let start=null,end=null,total=0,count=0;
 for(const e of mission.events||[]){
  if(e.step_id!==step.id)continue;
  const t=Date.parse(e.created_at);if(!Number.isFinite(t))continue;
  if(e.kind==='model_settings'){start=t;end=null;count++;}
  else if((e.kind==='step_completed'||e.kind==='error')&&start!==null&&end===null){end=t;total+=Math.max(0,end-start);}
 }
 if(start===null)return null;
 const running=['running','awaiting_approval'].includes(step.status);
 const elapsed=Math.max(0,(end??(running?now:start))-start);
 return {elapsed,total:total+(end===null&&running?elapsed:0),running,start,end,count,incomplete:end===null&&!running};
}
function durationText(ms){const s=Math.max(0,Math.floor(ms/1000)),h=Math.floor(s/3600),m=Math.floor(s%3600/60);return (h?h+' h ':'')+(m||h?m+' min ':'')+(s%60)+' s';}
function taskTimeLabel(m,s){const t=taskTiming(m,s);if(!t)return '';if(t.incomplete)return 'Durée non déterminée (arrêt sans événement de fin)';return (t.running?'En cours depuis ':'Durée : ')+durationText(t.elapsed)+(t.count>1?' · Cumul : '+durationText(t.total):'');}
function updateTaskClocks(){
 for(const el of document.querySelectorAll('[data-step-clock]')){
  const m=state.mission,s=m?.steps?.find(s=>s.id===el.dataset.stepClock);
  const value=taskTimeLabel(m,s);if(el.textContent!==value)el.textContent=value;
 }
 syncPlanActivity();
}
setInterval(updateTaskClocks,1000);
