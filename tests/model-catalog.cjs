const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('cyai/web/analytics.js','utf8');const code=src.slice(0,src.indexOf("document.addEventListener('change'"));
const nodes={'agent':{value:'local'},model:{value:'old'},'model-list':{},'model-effort':{},'model-tier':{}};
const c={state:{data:{connectors:[],models_cache:{local:[{id:'old',name:'Old'}]}}},$:id=>nodes[id],esc:x=>x,active:()=>false};vm.createContext(c);require('./ui-locale.cjs')(c);vm.runInContext(code,c);
c.renderRuntimeOptions();assert(!nodes['model-list'].innerHTML.includes('new'));
c.state.data.models_cache.local.push({id:'new',name:'Qwen3.8'});c.renderRuntimeOptions();assert(nodes['model-list'].innerHTML.includes('Qwen3.8'));assert.equal(nodes.model.value,'old');
c.state.data.models_cache.local=[];c.renderRuntimeOptions();assert.equal(nodes['model-list'].innerHTML,'');
console.log('Catalogue updates without changing selected model; removed entries disappear.');
