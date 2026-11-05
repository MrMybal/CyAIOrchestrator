const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('cyai/web/help.js','utf8');
const docs=JSON.parse(fs.readFileSync('cyai/web/help/en.json','utf8'));
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
function fixture(fetch){
 const page={innerHTML:'',querySelector:()=>null};
 const state={view:'help',navigationVersion:1,data:{version:'test'}};
 const context=vm.createContext({console,fetch,state,CYAI_LOCALE:'en',document:{addEventListener(){},getElementById(){return null;}},$:()=>page,ui:s=>s,esc:v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),htmlIfChanged:(_,html)=>{page.innerHTML=html;},rememberDraft(){},showView(){}});
 vm.runInContext(source,context);return {context,page,state,run:s=>vm.runInContext(s,context)};
}
(async()=>{
 const f=fixture(()=>{});f.context.doc=docs;
 assert(f.run('helpSearch(doc,"KV").some(c=>c.id==="local-models")'));
 const fr=JSON.parse(fs.readFileSync('cyai/web/help/fr.json','utf8'));f.context.fr=fr;
 assert(f.run('helpSearch(fr,"memoire").some(c=>c.id==="context")'));
 assert.equal(f.run('helpSearch(doc,"definitely-no-such-topic").length'),0);
 for(const name of ['../config.png','a/b.png','" onerror="bad.png','image.svg']){f.context.name=name;assert.equal(f.run('helpAsset(name)'),'');}
 assert.equal(f.run('helpAsset("conversation-en.png")'),'/help/images/conversation-en.png');
 f.context.block={type:'paragraph',text:'<script>bad()</script>'};
 assert.equal(f.run('helpBlock(block,0,doc.chapters[0],doc)'),'<p>&lt;script&gt;bad()&lt;/script&gt;</p>');
 const diagram=f.run('helpDiagram(doc.chapters.find(c=>c.id==="orchestration").blocks.find(b=>b.type==="diagram"),"test")');
 assert.equal((diagram.match(/<rect /g)||[]).length,6);assert(diagram.includes('aria-labelledby="test-title test-desc"'));
 const response=deferred();let calls=0;const late=fixture(()=>{calls++;return response.promise;});
 const first=late.run('renderHelp()');const second=late.run('renderHelp()');
 late.state.view='settings';late.state.navigationVersion++;
 late.page.innerHTML='Current settings';response.resolve({ok:true,json:async()=>docs});
 await Promise.all([first,second]);assert.equal(calls,1);assert.equal(late.page.innerHTML,'Current settings');
 const error=deferred();const staleError=fixture(()=>error.promise);const loading=staleError.run('renderHelp()');
 staleError.state.view='chat';staleError.state.navigationVersion++;staleError.page.innerHTML='Current chat';error.reject(Error('offline failure'));
 await loading;assert.equal(staleError.page.innerHTML,'Current chat');
 let attempts=0;const retry=fixture(async()=>{if(!attempts++)throw Error('temporary failure');return {ok:true,json:async()=>docs};});
 await retry.run('renderHelp()');assert(retry.page.innerHTML.includes('data-help-retry'));
 await retry.run('renderHelp()');assert.equal(attempts,2);assert(retry.page.innerHTML.includes('help-layout'));
 console.log('PASS: full-text/accent search, asset validation, escaped content, accessible diagram, shared load, stale success/error isolation and retry.');
})().catch(error=>{console.error(error);process.exitCode=1;});
