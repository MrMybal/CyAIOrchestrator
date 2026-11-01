'use strict';
// Translate only application-owned literals. Interpolated values are opaque and
// inserted after translation, so messages, paths and names are never rewritten.
(()=>{
 const supported={en:'English',fr:'Français'};
 window.CYAI_LOCALE=Object.hasOwn(supported,window.CYAI_LANGUAGE)?window.CYAI_LANGUAGE:'en';
 window.CYAI_FORMAT_LOCALE=CYAI_LOCALE==='fr'?'fr-FR':'en-US';
 window.CYAI_LANGUAGES=supported;
 // Bundled editors use this same origin and already support English/French.
 try{localStorage.setItem('cymd.language',CYAI_LOCALE);localStorage.setItem('cyannota.locale',CYAI_LOCALE);}catch{}
 const catalogue=window.CYAI_MESSAGES||{};
 function text(value){
  if(CYAI_LOCALE==='fr'||typeof value!=='string')return value;
  const key=value.trim(),translated=catalogue[key];
  return translated===undefined?value:value.slice(0,value.length-value.trimStart().length)+translated+value.slice(value.trimEnd().length);
 }
 function marked(value){
  const slots=[];
  const key=value.replace(/⟪(\d+)⟫/g,token=>'{'+(slots.push(token)-1)+'}');
  return text(key).replace(/\{(\d+)\}/g,(token,n)=>slots[n]??token);
 }
 function html(value){
  return value.replace(/<[^>]*>|[^<]+/gs,token=>token.startsWith('<')?
   token.replace(/(\b(?:title|placeholder|aria-label|alt)\s*=\s*)(["'])(.*?)\2/gs,(_,prefix,quote,value)=>prefix+quote+marked(value)+quote):marked(token));
 }
 window.ui=function(source,...values){
  if(typeof source==='string')return /<\/?[a-z][\w-]*(?:\s|>|\/)/i.test(source)?html(source):text(source);
  if(!Array.isArray(source)||!Object.hasOwn(source,'raw'))throw new TypeError('Expected an application message or template.');
  const skeleton=source.map((part,index)=>part+(index<values.length?'⟪'+index+'⟫':'')).join('');
  const translated=/<\/?[a-z][\w-]*(?:\s|>|\/)/i.test(skeleton)?html(skeleton):marked(skeleton);
  return translated.replace(/⟪(\d+)⟫/g,(_,index)=>String(values[index]));
 };
 const patterns=Object.entries(window.CYAI_SYSTEM_MESSAGES||{}).filter(([key])=>/\{\d+\}/.test(key)).map(([key,value])=>{
  const slots=[];
  const pattern=key.split(/(\{\d+\})/).map(part=>{
   if(/^\{\d+\}$/.test(part)){slots.push(part.slice(1,-1));return '(.*?)';}
   return part.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  }).join('');
  return {pattern:new RegExp('^'+pattern+'$','s'),value,slots};
 });
 ui.system=value=>{
  if(CYAI_LOCALE==='fr'||typeof value!=='string')return value;
  const exact=text(value);if(exact!==value)return exact;
  for(const item of patterns){const match=item.pattern.exec(value);if(match){const args={};item.slots.forEach((slot,i)=>args[slot]=match[i+1]);return item.value.replace(/\{(\d+)\}/g,(_,slot)=>args[slot]);}}
  return value;
 };
 const fr={
  states:{pausing:'Pause demandée',paused:'En pause',pending:'En attente',queued:'En file',running:'En cours',awaiting_approval:'Approbation requise',succeeded:'Réussie',failed:'Échouée',cancelled:'Annulée',interrupted:'Interrompue'},
  connections:{ready:'Prêt · démarrage à la demande',running:'En cours d’exécution',checking:'Vérification en cours',connected:'Connecté',disconnected:'Non connecté',operational:'Opérationnel',installed:'Installé · à vérifier',configured:'Configuré · à tester',unconfigured:'Non configuré',error:'Erreur'},
  views:{agents:'Bibliothèque d’agents',plugins:'Plugins',chat:'Conversation',missions:'Missions',search:'Historique',memory:'Mémoire partagée',connectors:'Connecteurs',settings:'Données & paramètres'},
  agents:{'command-code':'Command Code','codebuddy':'CodeBuddy · Tencent','antigravity':'Antigravity','devin':'Devin CLI','openrouter':'OpenRouter','codex':'Codex','claude-code':'Claude Code','opencode':'OpenCode','anthropic':'Claude · API','ollama':'Ollama'}
 };
 const en={
  states:{pausing:'Pause requested',paused:'Paused',pending:'Pending',queued:'Queued',running:'Running',awaiting_approval:'Approval required',succeeded:'Succeeded',failed:'Failed',cancelled:'Cancelled',interrupted:'Interrupted'},
  connections:{ready:'Ready · starts on demand',running:'Running',checking:'Checking',connected:'Connected',disconnected:'Disconnected',operational:'Operational',installed:'Installed · not verified',configured:'Configured · not verified',unconfigured:'Not configured',error:'Error'},
  views:{agents:'Agent library',plugins:'Plugins',chat:'Conversation',missions:'Missions',search:'History',memory:'Shared memory',connectors:'Connectors',settings:'Data & settings'},
  agents:fr.agents
 };
 window.CYAI_LOCALES={en,fr};
 if(typeof document!=='undefined'){document.documentElement.lang=CYAI_LOCALE;document.documentElement.style?.setProperty('--settings-heading',JSON.stringify(ui('PARAMÈTRES')));document.documentElement.style?.setProperty('--library-heading',JSON.stringify(ui('BIBLIOTHÈQUE')));}
})();
