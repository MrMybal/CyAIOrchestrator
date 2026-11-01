const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('cyai/web/app.js','utf8');let html='';const bar={dataset:{},querySelector(){return this;},setAttribute(){}};
const c={state:{conversation:'c',detail:{mode:'chat'},data:{approvals:[]},mission:{id:'m',conversation_id:'c',status:'queued',steps:[{id:'s',status:'pending'}],events:[],spec:{}}},$:()=>bar,esc:String,active:s=>s==='queued',htmlIfChanged:(id,v)=>html=v,agentName:String,renderComposerUsage(){},backgroundWorkHTML(){return "";},renderComposerPending(){}};
vm.createContext(c);require('./ui-locale.cjs')(c);vm.runInContext(src.slice(src.indexOf('function isTaskChain('),src.indexOf('function renderThinking(')),c);
c.renderWorkStatus();assert(html.includes('Réponse en attente'));assert(!html.includes('data-pause-chain'));assert(!html.includes('étapes terminées'));
c.state.detail.mode='orchestrator';c.renderWorkStatus();assert(html.includes('data-pause-chain'));assert(html.includes('0/1 étapes terminées'));
c.state.mission.spec.planning=true;c.renderWorkStatus();assert(!html.includes('data-pause-chain'));
console.log('Tchat normal, chaîne et planification : affichages vérifiés');
