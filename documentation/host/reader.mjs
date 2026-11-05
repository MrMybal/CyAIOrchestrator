import {mountViewer} from 'cydoc/viewer';
import {createDocumentation, createLink, parseLink} from 'cydoc';
const data=globalThis.CYDOC_DATA, options=globalThis.CYDOC_OPTIONS||{};
const core=createDocumentation(data), pending=new Map();
// Same classic-script packed-resource contract as CyDoc's generated exporter.
function script(src){return new Promise((resolve,reject)=>{const element=document.createElement('script');element.src=src;element.onload=()=>resolve(element);element.onerror=()=>{element.remove();reject(Error('Local resource unavailable: '+src));};document.head.append(element);});}
function loadAsset(src){
 if(pending.has(src))return pending.get(src);
 const file=options.assets?.[src];if(!file)return Promise.reject(Error('Asset is not packaged: '+src));
 const promise=script(file).then(element=>{const asset=globalThis.CYDOC_ASSETS?.[src];if(globalThis.CYDOC_ASSETS)delete globalThis.CYDOC_ASSETS[src];element.remove();if(!asset)throw Error('Invalid local asset');return asset;}).finally(()=>pending.delete(src));
 pending.set(src,promise);return promise;
}
const modules=Object.fromEntries((options.modules||[]).map(name=>[name,()=>script('media-'+name+'.js').then(()=>globalThis['CyDocMedia_'+name].default)]));
const route=parseLink(location.hash,data.defaultLocale,options.homePage||'start');
if(!data.locales.some(item=>item.code===route.locale))route.locale=data.defaultLocale;
if(!core.resolve(route.pageId,route.locale)){route.pageId=options.homePage||'start';route.anchor=undefined;route.state=undefined;}
const theme=route.state?.theme || new URL(location.href).searchParams.get('theme');
// Theme belongs to the host bootstrap, not media state or reading-position routing.
if(route.state?.theme){delete route.state.theme;if(!Object.keys(route.state).length)route.state=undefined;}
history.replaceState(null,'',createLink(route,location.href));
const viewer=mountViewer(document.getElementById('app'),data,{homePage:options.homePage,initialLocale:data.defaultLocale,initialTheme:['light','dark','midnight','nord','paper','contrast'].includes(theme)?theme:undefined,storageId:'cyai-orchestrator-help',modules,loadAsset});
globalThis.CYAI_HELP={navigate(target){location.hash=createLink(target);},destroy(){viewer.destroy();}};
addEventListener('pagehide',()=>viewer.destroy(),{once:true});
const settings=new Set(['models','local','voice','downloads','connectors','appearance','mcp','plugins','cytools','backup','folders','context','desktop']);
document.addEventListener('click',event=>{
 const link=event.target.closest('a[href]');if(!link)return;
 const href=link.getAttribute('href');if(!href?.startsWith('#/'))return;
 const destination=parseLink(href,data.defaultLocale,options.homePage);
 const tab=destination.state?.['app-settings'];
 if(!settings.has(tab)||!globalThis.pywebview?.api?.open_settings)return;
 event.preventDefault();event.stopImmediatePropagation();
 globalThis.pywebview.api.open_settings(tab).then(result=>{if(!result.opened)location.hash=href;}).catch(()=>{location.hash=href;});
},true);
function branding(){
 const tag=document.querySelector('.mit-tag');if(tag)tag.textContent='CyDoc · MIT';
 const license=document.querySelector('.footer>div>span:last-child');if(license)license.textContent='CyDoc: MIT · CyAI: AGPL-3.0-only';
}
branding();addEventListener('hashchange',()=>setTimeout(branding,0));
