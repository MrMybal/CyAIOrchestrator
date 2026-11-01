// Run real browser handlers with deferred service responses to exercise navigation races.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=name=>fs.readFileSync('cyai/web/'+name+'.js','utf8');
const block=(text,start,end)=>text.slice(text.indexOf(start),text.indexOf(end,text.indexOf(start)));
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const tests=[];
function context(stored={}){
 const elements=new Map(),listeners={};
 const el=id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',disabled:false,hidden:false,dataset:{},setAttribute(k,v){this[k]=v;},querySelector:()=>el('send'),querySelectorAll:()=>[],addEventListener(){}});return elements.get(id);};
 const storage=()=>({getItem:key=>stored[key]??null,setItem:(key,value)=>{stored[key]=value;}});
 const state={project:'p',conversation:'a',conversationVersion:0,navigationVersion:0,view:'chat',detail:{id:'a'},files:new Set(),selected:new Set(),collapsedProjects:new Set(),data:{projects:[{id:'p'}],conversations:[{id:'a'},{id:'b'},{id:'c'}],missions:[],settings:{}}};
 const c=vm.createContext({console,URLSearchParams,Set,Map,crypto:require('node:crypto').webcrypto,sessionStorage:storage(),localStorage:storage(),window:{addEventListener(){}},document:{addEventListener:(event,fn)=>{(listeners[event]??=[]).push(fn);},querySelectorAll:()=>[]},$:el,state,esc:s=>String(s??''),toast:()=>{},fail:error=>{throw error;},setTimeout:()=>{},setInterval:()=>{},voiceUI:{fromVoice:false},mediaUploads:new Map(),renderRuntimeOptions(){},renderMessages(){},renderInspector(){},renderLive(){},renderSidebar(){},renderPage:async()=>{},renderConnectorStatus(){},applyAppearance(){},notifyFailures(){},active:s=>s==='running',L:{views:{chat:'Chat'}},refresh:async()=>{}});
 vm.runInContext(source('tabs'),c);
 c.showView=view=>{state.view=view;state.navigationVersion++;};
 c.contextOptions=()=>({file_ids:[...state.files]});
 return {c,state,el,stored,listeners,run:code=>vm.runInContext(code,c)};
}
function test(name,fn){tests.push([name,fn]);}
const app=source('app');
const sendHandler=block(app,"$('composer').onsubmit=async","$('instruction').onkeydown");
const selectHandler=block(app,'async function selectConversation(id)','\nfunction showView');
const refreshHandler=block(app,'async function refresh(force=false)','\n(async()=>{restoreDraft();');
function sendFixture(){const f=context();f.run(sendHandler);return f;}
const submit=f=>f.el('composer').onsubmit({preventDefault(){},target:f.el('composer')});
test('malformed or wrong-shaped browser draft storage does not stop startup',()=>{
 for(const value of ['{broken','[]','null','true']){const f=context({'cyai-drafts':value,'cyai-file-drafts':value});f.run('restoreDraft()');assert.equal(f.el('instruction').value,'');assert.equal(f.state.files.size,0);}
});
test('text and selected attachments follow their own conversation',()=>{
 const f=context();f.el('instruction').value='draft A';f.state.files.add('file-a');f.run('rememberDraft()');
 f.state.conversation='b';f.run('restoreDraft()');assert.equal(f.el('instruction').value,'');assert.equal(f.state.files.size,0);
 f.el('instruction').value='draft B';f.run('rememberDraft();addDraftFiles("a",["uploaded-a"])');
 assert.equal(f.el('instruction').value,'draft B');assert.equal(f.state.files.size,0);
 f.state.conversation='a';f.run('restoreDraft()');assert.equal(f.el('instruction').value,'draft A');assert.deepEqual([...f.state.files],['file-a','uploaded-a']);
});
test('acknowledgment preserves newer typing and only consumes submitted files',async()=>{
 const f=sendFixture(),response=deferred();f.c.action=()=>response.promise;
 f.el('instruction').value='first';f.state.files.add('old');const sending=submit(f);assert.equal(f.el('send').disabled,true);assert.equal(f.el('send')['aria-busy'],'true');
 f.el('instruction').value='next draft';f.state.files.add('new');f.run('rememberDraft()');
 response.resolve({mission_id:'m'});await sending;assert.equal(f.el('instruction').value,'next draft');assert.deepEqual([...f.state.files],['new']);assert.equal(f.el('send').disabled,false);
});
test('acknowledgment never clears a different conversation, even after a second send',async()=>{
 const f=sendFixture(),a=deferred(),b=deferred();f.c.action=(name,data)=>data.conversation_id==='a'?a.promise:b.promise;
 f.el('instruction').value='first';const sendingA=submit(f);f.run('rememberDraft()');
 f.state.conversation='b';f.state.detail={id:'b'};f.run('restoreDraft();renderComposerPending()');f.el('instruction').value='second';const sendingB=submit(f);
 a.resolve({mission_id:'ma'});await sendingA;assert.equal(f.el('instruction').value,'second');assert.equal(f.el('send').disabled,true);
 b.resolve({mission_id:'mb'});await sendingB;assert.equal(f.el('instruction').value,'');assert.equal(f.el('send').disabled,false);
 f.state.conversation='a';f.run('restoreDraft()');assert.equal(f.el('instruction').value,'');
});
test('failed send retains text and attachments and prevents duplicate pending submissions',async()=>{
 const f=sendFixture(),response=deferred();let calls=0,failures=0;f.c.action=()=>{calls++;return response.promise;};f.c.fail=()=>failures++;
 f.el('instruction').value='keep me';f.state.files.add('keep-file');const sending=submit(f);await submit(f);assert.equal(calls,1);
 response.reject(Error('offline'));await sending;assert.equal(f.el('instruction').value,'keep me');assert.deepEqual([...f.state.files],['keep-file']);assert.equal(failures,1);assert.equal(f.el('send').disabled,false);
});
test('a transfer completed after navigation remains selected in its original draft',async()=>{
 const f=context();let xhr;f.c.XMLHttpRequest=class{constructor(){xhr=this;this.upload={};}open(){}setRequestHeader(){}send(){} };
 f.c.renderMediaDrafts=()=>{};f.run(block(source('media'),'async function uploadMedia(files)','\nfunction chooseAttachments'));
 f.el('instruction').value='A draft';f.run('rememberDraft()');const transfer=f.run('uploadMedia([{name:"image.png",size:50}])');
 f.state.conversation='b';f.run('restoreDraft()');f.el('instruction').value='B draft';
 xhr.upload.onprogress({lengthComputable:true,loaded:40,total:50});xhr.status=200;xhr.responseText='{"id":"uploaded-a"}';xhr.onload();await transfer;
 assert.equal(f.el('instruction').value,'B draft');assert.equal(f.state.files.size,0);
 f.state.conversation='a';f.run('restoreDraft()');assert.equal(f.el('instruction').value,'A draft');assert.deepEqual([...f.state.files],['uploaded-a']);
});
test('an upload in another conversation does not block sending here',async()=>{
 const f=sendFixture();f.c.mediaUploads.set('upload',{conversation:'b'});let sent=false;f.c.action=async()=>{sent=true;return {};};f.el('instruction').value='ok';await submit(f);assert(sent);
 f.c.mediaUploads.set('upload',{conversation:'a'});sent=false;f.el('instruction').value='wait';await submit(f);assert(!sent);assert.equal(f.el('instruction').value,'wait');
});
test('conversation creation captures project and request settings before navigation',async()=>{
 const f=sendFixture(),created=deferred(),response=deferred(),calls=[];f.state.conversation=null;f.state.detail=null;f.el('instruction').value='new chat';f.el('agent').value='alpha';
 f.c.action=(name,data)=>{calls.push({name,data});return name==='create_conversation'?created.promise:response.promise;};const sending=submit(f);
 f.state.conversation='b';f.state.project='other';f.state.detail={id:'b'};f.state.navigationVersion++;f.el('instruction').value='B draft';f.el('agent').value='beta';
 created.resolve({id:'created'});await tick();assert.equal(calls[1].data.conversation_id,'created');assert.equal(calls[1].data.connector,'alpha');assert.equal(calls[0].data.project_id,'p');
 response.resolve({mission_id:'m'});await sending;assert.equal(f.state.conversation,'b');assert.equal(f.el('instruction').value,'B draft');
});
test('rapid conversation selection keeps the latest detail and restores its draft immediately',async()=>{
 const f=context(),b=deferred(),c=deferred();f.run(selectHandler);f.c.api=path=>path.endsWith('/b')?b.promise:c.promise;
 f.el('instruction').value='A draft';f.run('rememberDraft();conversationDrafts.b="B draft";conversationDrafts.c="C draft";');
 const first=f.run('selectConversation("b")');assert.equal(f.el('instruction').value,'B draft');const second=f.run('selectConversation("c")');assert.equal(f.el('instruction').value,'C draft');
 f.el('instruction').value='new C';c.resolve({id:'c',project_id:'p'});await second;b.resolve({id:'b',project_id:'p'});await first;
 assert.equal(f.state.detail.id,'c');assert.equal(f.state.conversation,'c');assert.equal(f.el('instruction').value,'new C');assert.equal(f.state.loadingConversation,null);
});
test('a delayed selection cannot navigate back from logs',async()=>{
 const f=context(),response=deferred();f.run(selectHandler);f.c.api=()=>response.promise;const loading=f.run('selectConversation("b")');f.c.showView('logs');response.resolve({id:'b',project_id:'p'});await loading;assert.equal(f.state.view,'logs');assert.equal(f.state.detail,null);
});
test('polling cannot replace a newly selected conversation with stale detail',async()=>{
 const f=context(),response=deferred();f.run(refreshHandler);f.c.api=async path=>path==='state'?f.state.data:response.promise;
 const polling=f.run('refresh()');await tick();f.state.conversation='b';f.state.conversationVersion++;f.state.detail={id:'b'};response.resolve({id:'a',project_id:'p'});await polling;assert.equal(f.state.detail.id,'b');assert.equal(f.state.polling,false);
});
test('a late mission response cannot replace another conversation mission',async()=>{
 const f=context(),response=deferred();f.state.data.missions=[{id:'ma',conversation_id:'a',status:'running'}];f.run(refreshHandler);
 f.c.api=async path=>path==='state'?f.state.data:path.startsWith('conversation/')?{id:'a',project_id:'p'}:response.promise;
 const polling=f.run('refresh()');await tick();f.state.conversation='b';f.state.conversationVersion++;f.state.detail={id:'b'};f.state.mission={id:'mb'};
 response.resolve({id:'ma',events:[]});await polling;assert.equal(f.state.mission.id,'mb');assert.equal(f.state.detail.id,'b');
});
test('a forced refresh is retained while another poll is running',async()=>{
 const f=context(),response=deferred(),timers=[];f.c.setTimeout=callback=>timers.push(callback);f.run(refreshHandler);f.state.conversation=null;f.c.api=()=>response.promise;
 const first=f.run('refresh()');await f.run('refresh(true)');response.resolve(f.state.data);await first;assert.equal(timers.length,1);assert.equal(f.state.refreshAgain,false);
});
test('rendering errors are not mislabeled as connection interruptions',async()=>{
 const f=context();f.state.conversation=null;f.run(refreshHandler);f.c.api=async()=>f.state.data;f.c.renderSidebar=()=>{throw Error('render failure');};await f.run('refresh()');assert.match(f.el('notice').textContent,/Impossible/);assert.doesNotMatch(f.el('notice').textContent,/Connexion/);
});
test('RAW can load while Journal is pending; a late Journal response never paints',async()=>{
 const f=context(),journal=deferred(),raw=deferred();f.state.view='logs';f.c.api=()=>f.state.logsTab==='raw'?raw.promise:journal.promise;
 const workspace=source('workspace');f.run(block(workspace,'async function renderStandardLogs(',"\ndocument.addEventListener('click',e=>{if(e.target.closest('[data-theme-create]'))"));
 f.run(block(workspace,'let logsRendering=','\nfunction resourceHistoryHTML'));
 f.c.htmlIfChanged=(id,html)=>f.el(id).innerHTML=html;
 const first=f.run('renderLogs()');assert.match(f.el('page').innerHTML,/Chargement/);f.state.logsTab='raw';const second=f.run('renderLogs()');
 raw.resolve({entries:[{operation:'raw-result'}]});await second;assert.match(f.el('page').innerHTML,/raw-result/);
 journal.resolve({entries:[],notice:'old journal'});await first;assert.match(f.el('page').innerHTML,/raw-result/);assert.doesNotMatch(f.el('page').innerHTML,/old journal/);
});
test('a delayed project statistics request cannot overwrite another project tab',async()=>{
 const f=context(),statistics=deferred(),p={id:'p',name:'Project',root:'root',usage:[]};f.state.view='project';f.state.projectTab='statistics';
 f.c.projectMemoryPlugins=()=>[];f.c.api=async()=>p;f.c.action=()=>statistics.promise;f.c.analyticsHTML=()=>'<div>old statistics</div>';f.c.usageHTML=()=>'<div>latest usage</div>';f.c.htmlIfChanged=(id,html)=>f.el(id).innerHTML=html;
 f.run(block(source('project'),'let projectRendering=','\nlet planAdjustment'));
 const first=f.run('renderProjectPage()');await tick();f.state.projectTab='usage';await f.run('renderProjectPage()');statistics.resolve({});await first;assert.match(f.el('page').innerHTML,/latest usage/);assert.doesNotMatch(f.el('page').innerHTML,/old statistics/);
});
test('returning to cached project content replaces its loading placeholder',async()=>{
 const f=context(),statistics=deferred(),p={id:'p',name:'Project',root:'root',usage:[]};f.state.view='project';f.state.projectTab='usage';f.c.projectMemoryPlugins=()=>[];
 f.c.api=async()=>p;f.c.action=()=>statistics.promise;f.c.analyticsHTML=()=>'<div>statistics</div>';f.c.usageHTML=()=>'<div>usage</div>';
 f.run(block(app,'function htmlIfChanged(id,html)','\nasync function api('));f.run(block(source('project'),'let projectRendering=','\nlet planAdjustment'));
 await f.run('renderProjectPage()');assert(f.el('page')._rendered);f.state.projectTab='statistics';const pending=f.run('renderProjectPage()');await tick();assert.equal(f.el('page')._rendered,null);
 f.state.projectTab='usage';await f.run('renderProjectPage()');assert.match(f.el('page')._rendered,/<div>usage/);statistics.resolve({});await pending;
});
test('project errors keep retry visible and suppress stale failures after navigation',async()=>{
 const f=context(),response=deferred();f.state.view='project';f.state.projectTab='usage';f.c.api=()=>response.promise;f.c.htmlIfChanged=(id,html)=>f.el(id).innerHTML=html;
 f.run(block(source('project'),'let projectRendering=','\nlet planAdjustment'));const loading=f.run('renderProjectPage()');response.reject(Error('read failed'));await loading;assert.match(f.el('send').innerHTML,/Réessayer/);
 const stale=deferred();f.c.api=()=>stale.promise;const old=f.run('renderProjectPage()');f.state.view='logs';f.state.navigationVersion++;f.el('send').innerHTML='new view';stale.reject(Error('old failure'));await old;assert.equal(f.el('send').innerHTML,'new view');
});
(async()=>{for(const [name,fn] of tests){await fn();console.log('PASS: '+name);}console.log(tests.length+' asynchronous UI regressions passed.');})().catch(error=>{console.error(error);process.exitCode=1;});
