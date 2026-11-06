// Host-only routing and settings bridge; the visual reader is CyDoc's stock export.
import {createDocumentation,createLink,parseLink} from 'cydoc';
const data=globalThis.CYDOC_DATA,options=globalThis.CYDOC_OPTIONS||{},core=createDocumentation(data);
function normalize(route){
 if(!data.locales.some(x=>x.code===route.locale))route.locale=data.defaultLocale;
 route=core.canonicalRoute(route);
 if(!core.resolve(route.pageId,route.locale)){route.pageId=options.homePage||'start';delete route.anchor;delete route.state;}
 return route;
}
const initial=normalize(parseLink(location.hash,data.defaultLocale,options.homePage||'start'));
const theme=initial.state?.theme;
if(initial.state?.theme){delete initial.state.theme;if(!Object.keys(initial.state).length)delete initial.state;}
if(['light','dark','midnight','nord','paper','contrast'].includes(theme))try{localStorage.setItem('cydoc:theme',theme);}catch{}
history.replaceState(null,'',createLink(initial,location.href));
globalThis.CYAI_HELP={navigate(target){
 const route=normalize({...target});
 if(['light','dark','midnight','nord','paper','contrast'].includes(route.theme)){
  const root=document.getElementById('app');root.dataset.theme=route.theme;
  try{localStorage.setItem('cydoc:theme',route.theme);}catch{}
 }
 location.hash=createLink(route);
}};
const settings=new Set(['models','local','voice','downloads','connectors','appearance','mcp','plugins','cytools','backup','folders','context','desktop']);
document.addEventListener('click',event=>{
 const link=event.target.closest('a[href]'),href=link?.getAttribute('href');
 if(!href?.startsWith('#/'))return;
 const tab=parseLink(href,data.defaultLocale,options.homePage).state?.['app-settings'];
 if(!settings.has(tab)||!globalThis.pywebview?.api?.open_settings)return;
 event.preventDefault();event.stopImmediatePropagation();
 globalThis.pywebview.api.open_settings(tab).then(result=>{if(!result.opened)location.hash=href;}).catch(()=>{location.hash=href;});
},true);
