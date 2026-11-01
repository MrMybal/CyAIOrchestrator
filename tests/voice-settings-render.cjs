const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = new Map();
function el(key) {
  if (['voice-mic','voice-direct','voice-read','voice-bar'].includes(key)) return null;
  if (!elements.has(key)) elements.set(key, {value:'', innerHTML:'', dataset:{}, addEventListener:()=>{}, elements:{voice:{value:'pocket:french_24l:clone:ref'},stt_engine:{value:'whisper'},stt_model:{closest:()=>({})},device:{closest:()=>({})}}, querySelector:s=>el(key+s), querySelectorAll:()=>[]});
  return elements.get(key);
}
const settings = {stt:{},tts:{voice:'pocket:french_24l:clone:ref'},connector_voices:{},samples:[]};
let reject = false;
const context = vm.createContext({console, setInterval, clearInterval, state:{view:'settings',settingsTab:'voice'}, $:el, esc:s=>String(s??'').replaceAll('<','&lt;'), date:s=>s, agentName:s=>s,
 action:async name=>{if(reject)throw Error('Discovery failed');return name==='voice_catalog'?{items:[],jobs:[],folder:'test',runtimes_folder:'test'}:{settings,voices:[],inputs:[],outputs:[],connectors:[],stt:{ready:true},engines:{pocket:true},samples:settings.samples};}});
require('./ui-locale.cjs')(context);vm.runInContext(fs.readFileSync('cyai/web/voice.js','utf8'), context);
(async()=>{
 for (const samples of [[],[{id:'ref',name:'Ma voix',seconds:12,created_at:'2026-09-20'}],[{id:'ref',name:'<script>',seconds:12,created_at:'today'},{id:'ref2',name:'Autre voix',seconds:8,created_at:'today'}]]) {
  settings.samples=samples;
  await vm.runInContext('renderVoiceSettings()',context);
  const html=el('voice-settings').innerHTML;
  assert(html.includes('id="voice-form"'),html);
  assert(!html.includes('Impossible d’afficher'),html);
  assert.equal((html.match(/class="card voice-sample"/g)||[]).length,samples.length);
  assert(!html.includes('<script>'));
 }
 const button = {}, status = {};
 const card = {dataset:{voiceItem:'fish'}, querySelector:selector=>selector==='[data-voice-job]'?status:button};
 el('voice-settings').querySelectorAll = ()=>[card];
 context.catalog = {items:[{id:'fish',name:'Fish',installed:false}],jobs:[{name:'Voix · Fish',status:'queued'}]};
 vm.runInContext('paintVoiceJobs(catalog)',context);
 assert.equal(button.disabled,true); assert.equal(button.textContent,'En attente…');
 context.catalog.jobs[0]={name:'Voix · Fish',status:'running',received:25,total:100,detail:'Poids du modèle'};
 vm.runInContext('paintVoiceJobs(catalog)',context);
 assert(button.textContent.includes('25 %')); assert(status.textContent.includes('Poids du modèle'));
 context.catalog.jobs[0]={name:'Voix · Fish',status:'failed',error:'Disque plein'};
 vm.runInContext('paintVoiceJobs(catalog)',context);
 assert.equal(button.disabled,false); assert.equal(button.textContent,'Réessayer'); assert(status.textContent.includes('Disque plein'));
 context.catalog.items[0].installed=true; context.catalog.jobs[0].status='succeeded';
 vm.runInContext('paintVoiceJobs(catalog)',context);
 assert.equal(button.textContent,'✓ Installé');
 el('voice-settings').querySelectorAll = ()=>[];
 reject=true;
 await vm.runInContext('renderVoiceSettings()',context);
 assert(el('voice-settings').innerHTML.includes('role="alert"'));
 assert(el('voice-settings').innerHTML.includes('Discovery failed'));
 reject=false;
 await el('voice-settings[data-voice-retry]').onclick();
 assert(el('voice-settings').innerHTML.includes('id="voice-form"'));
 console.log('PASS: empty, one and multiple cloned voices; escaped labels; visible failure; retry.');
})().catch(e=>{console.error(e);process.exitCode=1});
