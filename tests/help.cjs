const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('cyai/web/help.js','utf8');
function fixture(native=false){
 const listeners={},calls=[],errors=[];
 const state={view:'chat',settingsTab:'models',data:{settings:{theme:'dark'}}};
 let drafts=0;
 const context=vm.createContext({console,state,CYAI_LOCALE:'fr',window:{pywebview:native?{api:{open_documentation:async route=>{calls.push(route);return {opened:true};}}}:null},document:{addEventListener:(event,fn)=>listeners[event]=fn,querySelector:()=>null},ui:v=>v,esc:v=>v,toast(){},rememberDraft(){drafts++;},action:async(name,route)=>{calls.push({name,...route});return {opened:true};},openDialog:(...args)=>errors.push(args),URLSearchParams});
 vm.runInContext(source,context);
 return {context,state,calls,listeners,errors,get drafts(){return drafts;},run:s=>vm.runInContext(s,context)};
}
(async()=>{
 for(const native of [false,true]){
  const f=fixture(native);await f.run('openHelp("start","help-part-1","conversation",{zoom:1.5})');
  const route=f.calls[0];assert.equal(route.page_id,'start');assert.equal(route.locale,'fr');assert.equal(route.anchor,'help-part-1');assert.equal(route.state.media,'conversation');assert.equal(route.state.zoom,1.5);assert.equal(f.drafts,1);assert.equal(f.state.view,'chat');
  if(!native)assert.equal(route.name,'open_documentation');
 }
 const f=fixture();await f.run('openLegacyHelp(new URLSearchParams("help=start&media=conversation&zoom=2"),"#help-part-1")');
 assert.equal(f.calls[0].anchor,'help-part-1');assert.equal(f.calls[0].state.zoom,'2');
 for(const [view,tab,expected] of [['settings','voice','voice'],['settings','local','local-models'],['logs','','diagnostics'],['agents','','agents'],['method','','methods'],['space','','spaces'],['project','board','board'],['project','media','files'],['missions','','orchestration'],['home','','start']]){
  f.state.view=view;f.state.settingsTab=tab;f.state.projectTab=tab;assert.equal(f.run('contextHelpTopic()'),expected);
 }
 let prevented=false;f.state.view='settings';f.state.settingsTab='mcp';f.listeners.keydown({key:'F1',preventDefault(){prevented=true;}});await Promise.resolve();assert(prevented);assert.equal(f.calls.at(-1).page_id,'mcp');
 const failure=fixture();failure.context.action=async()=>{throw Error('Unavailable');};await failure.run('openHelp()');assert.equal(failure.errors.length,1);assert(failure.errors[0][1].includes('data-context-help'));
 const app=fs.readFileSync('cyai/web/app.js','utf8'),shell=fs.readFileSync('cyai/web/channels.js','utf8');
 assert(/if\s*\(view\s*===\s*'help'\)\s*\{\s*openHelp\(\);\s*return;\s*\}/.test(app));
 assert(app.includes('openLegacyHelp(query,location.hash)'));assert.equal((app.match(/openLegacyHelp\(/g)||[]).length,1);assert(!shell.match(/OVERLAY_VIEWS\s*=.*'help'/));
 console.log('PASS: native/browser help actions, workspace and draft preservation, F1 context, legacy section/media routes, retry and rail integration.');
})().catch(error=>{console.error(error);process.exitCode=1;});
