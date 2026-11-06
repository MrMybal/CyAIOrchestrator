import fs from 'node:fs';import path from 'node:path';import {pathToFileURL} from 'node:url';import assert from 'node:assert/strict';
// Run against an isolated Chromium DevTools endpoint: CYAI_DOCS_CDP=http://127.0.0.1:PORT
const folder=process.env.CYAI_DOCS_OUTPUT||'test-results/cydoc-browser';fs.mkdirSync(folder,{recursive:true});
const endpoint=process.env.CYAI_DOCS_CDP || 'http://127.0.0.1:'+Number(fs.readFileSync(folder+'/edge-profile/DevToolsActivePort','utf8').split('\n')[0]);
const target=await(await fetch(endpoint+'/json/new?about:blank',{method:'PUT'})).json();
const ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
let id=0;const pending=new Map(),errors=[],requests=[];
ws.onmessage=event=>{const data=JSON.parse(event.data);if(data.id){const p=pending.get(data.id);if(p){pending.delete(data.id);data.error?p.reject(Error(JSON.stringify(data.error))):p.resolve(data.result);}}else if(data.method==='Runtime.exceptionThrown')errors.push(data.params.exceptionDetails.exception?.description||data.params.exceptionDetails.text);else if(data.method==='Network.requestWillBeSent')requests.push(data.params.request.url);};
function send(method,params={}){return new Promise((resolve,reject)=>{const key=++id;pending.set(key,{resolve,reject});const t=setTimeout(()=>{if(pending.delete(key))reject(Error('Timeout '+method));},10000);t.unref?.();ws.send(JSON.stringify({id:key,method,params}));});}
const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result?.value;};
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(expression){const end=Date.now()+25000;while(Date.now()<end){try{if(await evaluate(expression))return;}catch{}await delay(100);}throw Error('Not ready: '+expression);}
async function screenshot(name){await evaluate('document.fonts.ready');await delay(350);const shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(folder+'/'+name+'.png',Buffer.from(shot.data,'base64'));}
const keep=setInterval(()=>{},1000);
try{
 await send('Runtime.enable');await send('Page.enable');await send('Network.enable');await send('Page.bringToFront');
 await send('Emulation.setFocusEmulationEnabled',{enabled:true});
 await send('Network.setBlockedURLs',{urls:['http://*','https://*']});
 await send('Emulation.setDeviceMetricsOverride',{width:1500,height:1000,deviceScaleFactor:1,mobile:false});
 const base=pathToFileURL(path.resolve('Documentation/Documentation.html')).href;
 await send('Page.navigate',{url:base+'#/en/start?theme=midnight'});
 await until('!!globalThis.CYAI_HELP && !!document.querySelector("#main-content h1")');
 assert.equal(await evaluate('location.protocol'),'file:');
 assert.equal(await evaluate('document.documentElement.lang'),'en');
 await until('document.querySelector(".cy-image img")?.complete');
 await screenshot('guide-en');
 const pages=await evaluate('CYDOC_DATA.pages.map(p=>({id:p.id,locale:p.locale}))');
 for(const page of pages){
  await evaluate('CYAI_HELP.navigate('+JSON.stringify({locale:page.locale,pageId:page.id})+')');
  await until('location.hash.includes('+JSON.stringify('/'+page.locale+'/'+page.id)+') && document.querySelector("#breadcrumb").textContent==='+JSON.stringify(JSON.parse(fs.readFileSync('Documentation/DocData/manifest.json','utf8')).pages.find(p=>p.id===page.id&&p.locale===page.locale).title));
 }
 await evaluate('CYAI_HELP.navigate({locale:"fr",pageId:"orchestration"})');
 await until('document.documentElement.lang==="fr" && document.querySelector("#main-content svg")');
 await screenshot('diagram-fr');
 await evaluate('CYAI_HELP.navigate({locale:"fr",pageId:"start"})');
 await until('document.querySelector(".cy-image img")?.complete');
 await screenshot('guide-fr');
 await evaluate('document.querySelector(".cy-image [data-action=in]").click()');
 assert.notEqual(await evaluate('document.querySelector(".zoom-value").textContent'),'100%');

 // Common deep anchors and a real language-selector change.
 await evaluate('CYAI_HELP.navigate({locale:"fr",pageId:"start",anchor:"help-part-4"})');
 await until('document.activeElement.id==="help-part-4"');
 await evaluate('(()=>{const s=document.querySelector(".locale-control select");s.value="en";s.dispatchEvent(new Event("change",{bubbles:true}));})()');
 await until('document.documentElement.lang==="en" && location.hash.includes("/en/start/help-part-4")');
 // Deep media state, keyboard zoom and in-window enlargement with Escape focus return.
 await evaluate('CYAI_HELP.navigate({locale:"en",pageId:"start",state:{media:"conversation",zoom:"2"}})');
 await until('document.querySelector(".cy-image img")?.naturalWidth>0 && document.querySelector(".zoom-value")?.textContent==="200%"');
 await evaluate('document.querySelector(".media-stage").dispatchEvent(new KeyboardEvent("keydown",{key:"0",bubbles:true}))');
 assert.equal(await evaluate('document.querySelector(".zoom-value").textContent'),'100%');
 await evaluate('document.querySelector(".cy-image [data-action=expand]").click()');
 assert(await evaluate('!!document.querySelector(".cy-image.media-expanded")'));
 const box=await evaluate('(()=>{const r=document.querySelector(".media-expanded").getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom};})()');
 assert(box.x>=0&&box.y>=0&&box.right<=1500&&box.bottom<=1000);
 await evaluate('document.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true}))');
 assert.equal(await evaluate('document.querySelectorAll(".media-expanded").length'),0);
 assert.equal(await evaluate('document.activeElement.dataset.action'),'expand');
 // Reading positions are restored while moving between guide pages.
 await evaluate('CYAI_HELP.navigate({locale:"en",pageId:"start"})');
 await until('location.hash==="#/en/start"');await delay(500);
 await evaluate('window.scrollTo({top:480,behavior:"instant"})');await delay(150);
 const position=await evaluate('scrollY');assert(position>100);
 await evaluate('CYAI_HELP.navigate({locale:"en",pageId:"connectors"})');
 await until('location.hash==="#/en/connectors" && document.querySelector("#breadcrumb").textContent==="Connectors & models"');await delay(150);
 await evaluate('CYAI_HELP.navigate({locale:"en",pageId:"start"})');
 await until('Math.abs(scrollY-'+position+')<3');
 // Search is keyboard-accessible and searches body text, including technical references.
 await evaluate('document.dispatchEvent(new KeyboardEvent("keydown",{key:"k",ctrlKey:true,bubbles:true}))');
 await until('!!document.querySelector("dialog[open] .search-form input")');
 await evaluate('(()=>{const i=document.querySelector(".search-form input");i.value="VRAM";i.dispatchEvent(new Event("input",{bubbles:true}));})()');
 await until('document.querySelectorAll(".search-result").length>0');
 assert(await evaluate('document.activeElement.matches(".search-form input")'));
 await evaluate('document.querySelector("dialog[open]").close()');
 // Settings return to the host only when its explicit bridge exists.
 await evaluate('CYAI_HELP.navigate({locale:"en",pageId:"start"})');
 await until('!!document.querySelector("a[href*=app-settings]")');
 await evaluate('globalThis.settingsCalled="";globalThis.pywebview={api:{open_settings:async tab=>{settingsCalled=tab;return {opened:true};}}};document.querySelector("a[href*=app-settings]").click()');
 await until('settingsCalled==="connectors"');
 assert.equal(await evaluate('location.hash'),'#/en/start');
 await evaluate('delete globalThis.pywebview;document.querySelector("a[href*=app-settings]").click()');
 await until('location.hash.includes("/en/connectors?")');
 // Stock-reader navigation, header search, tooltips and theme controls.
 await evaluate('CYAI_HELP.navigate({locale:"en",pageId:"start"})');
 await until('document.documentElement.lang==="en" && document.querySelector("#breadcrumb")?.textContent==="Start here" && !!document.querySelector("[data-header-search]")');
 assert.equal(await evaluate('getComputedStyle(document.querySelector(".sidebar")).width'),'330px');
 assert.equal(await evaluate('document.querySelectorAll(".mit-tag,.offline-card,.local-card").length'),0);
 assert(await evaluate('!!document.querySelector("[data-page=chat]")?.closest("[data-nav-key]")'));
 await delay(300);
 await evaluate('document.querySelector(".locale-control select").focus();document.querySelector("[data-page=start]").focus()');
 await until('!document.querySelector(".reader-tooltip").hidden');
 assert.equal(await evaluate('document.querySelector(".reader-tooltip strong").textContent'),'Start here');
 assert(await evaluate('document.querySelector(".reader-tooltip-description").textContent.includes("workspace")'));
 await evaluate('document.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true}))');
 await evaluate('(()=>{const i=document.querySelector("[data-header-search]");i.focus();i.value="VRAM";i.dispatchEvent(new Event("input",{bubbles:true}));})()');
 await until('!!document.querySelector(".search-popover[open] .search-result")');
 assert(await evaluate('[...document.querySelectorAll(".search-result")].every(a=>!a.textContent.includes("migration-inventory"))'));
 await evaluate('document.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true}))');
 for(const theme of ['light','dark','midnight','nord','paper','contrast']){
  await evaluate('document.querySelector("[data-set-theme='+theme+']").click()');
  assert.equal(await evaluate('document.querySelector("#app").dataset.theme'),theme);
 }
 await evaluate('document.querySelector("[data-set-theme=midnight]").click()');
 // Initial direct stale links and unsupported locales fall back safely.
 await send('Page.navigate',{url:'about:blank'});
 await until('location.href==="about:blank"');
 await send('Page.navigate',{url:base+'#/zz/obsolete-page'});
 await until('!!globalThis.CYAI_HELP && document.documentElement.lang==="en" && location.hash==="#/en/start"');
 const longName='CyAI Orchestrator — A deliberately long application name for multilingual workspace documentation';
 const init=await send('Page.addScriptToEvaluateOnNewDocument',{source:'Object.defineProperty(globalThis,"CYDOC_DATA",{configurable:true,set(value){value.name='+JSON.stringify(longName)+';Object.defineProperty(globalThis,"CYDOC_DATA",{configurable:true,writable:true,value});}});'});
 await send('Page.navigate',{url:'about:blank'});await until('location.href==="about:blank"');
 await send('Page.navigate',{url:base+'#/fr/start'});
 await until('document.querySelector(".brand-name")?.textContent==='+JSON.stringify(longName));
 await send('Page.removeScriptToEvaluateOnNewDocument',{identifier:init.identifier});
 await evaluate('document.querySelector(".brand").focus()');
 await until('!document.querySelector(".reader-tooltip").hidden');
 assert.equal(await evaluate('document.querySelector(".reader-tooltip strong").textContent'),longName);
 const brandBox=await evaluate('(()=>{const a=document.querySelector(".brand-name").getBoundingClientRect(),b=document.querySelector(".sidebar").getBoundingClientRect();return {right:a.right,sidebar:b.right};})()');
 assert(brandBox.right<=brandBox.sidebar);
 await screenshot('long-name');
 await evaluate('document.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true}))');
 await evaluate('CYAI_HELP.navigate({locale:"fr",pageId:"start"})');
 await until('document.querySelector(".cy-image img")?.naturalWidth>0');
 await send('Emulation.setDeviceMetricsOverride',{width:480,height:860,deviceScaleFactor:1,mobile:true});
 await send('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:2});
 await evaluate('document.querySelector(".cy-image .media-stage").scrollIntoView({block:"center",behavior:"instant"})');
 await delay(450);
 const touch=await evaluate('(()=>{const b=document.querySelector(".cy-image .media-stage").getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2};})()');
 const beforePan=await evaluate('document.querySelector(".cy-image img").style.transform');
 await send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{...touch,id:1}]});
 await send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:touch.x+35,y:touch.y+10,id:1}]});
 await send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
 assert.notEqual(await evaluate('document.querySelector(".cy-image img").style.transform'),beforePan);
 const beforePinch=await evaluate('document.querySelector(".zoom-value").textContent');
 for(const [type,distance] of [['touchStart',20],['touchMove',40],['touchMove',70]])await send('Input.dispatchTouchEvent',{type,touchPoints:[{x:touch.x-distance,y:touch.y,id:1},{x:touch.x+distance,y:touch.y,id:2}]});
 await send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
 assert.notEqual(await evaluate('document.querySelector(".zoom-value").textContent'),beforePinch);
 await evaluate('scrollTo(0,0)');
 await screenshot('mobile-fr');
 assert((await evaluate('document.documentElement.scrollWidth'))<=480);
 fs.writeFileSync(folder+'/report.json',JSON.stringify({pages:pages.length,errors,remoteHttpBlocked:true,requests:requests.filter(r=>!r.includes('kaspersky-labs.com')),checks:['all pages','topic tree','330px sidebar','header search','full tooltips','six themes','long application name','locale switch','anchors','media state','zoom','in-window expansion','keyboard','reading positions','search','settings bridge','fallback','mobile','emulated touch pan and pinch']},null,2));
 console.log('PASS file://: '+pages.length+' pages, language/anchors/media, keyboard, zoom, enlargement, reading positions, search, settings, fallback and mobile; remote HTTP blocked.');
 if(errors.length)throw Error(errors.join('\n'));
}catch(error){console.error('Browser errors:',JSON.stringify(errors));console.error(await evaluate('JSON.stringify({url:location.href,scroll:scrollY,height:document.documentElement.scrollHeight,focus:document.activeElement?.outerHTML.slice(0,200),tooltips:[...document.querySelectorAll(".reader-tooltip")].map(x=>x.outerHTML)})'));await screenshot('failure');throw error;}finally{clearInterval(keep);ws.close();}
