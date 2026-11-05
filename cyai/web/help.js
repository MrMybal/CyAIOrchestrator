'use strict';
// Help opens the bundled CyDoc file reader; the application workspace stays mounted.
function contextHelpTopic() {
  if (document.querySelector('.mesh-viewer[open]')) return 'viewer-3d';
  if (state.view==='settings') return ({local:'local-models',voice:'voice',downloads:'downloads',connectors:'connectors',mcp:'mcp',plugins:'extensions',cytools:'extensions',backup:'backups',context:'context'})[state.settingsTab] || 'settings';
  if (state.view==='connectors') return 'connectors';
  if (state.view==='missions') return 'orchestration';
  if (state.view==='memory') return 'context';
  if (state.view==='home') return 'start';
  if (state.view==='logs') return 'diagnostics';
  if (state.view==='agents') return 'agents';
  if (state.view==='method') return 'methods';
  if (state.view==='space') return 'spaces';
  if (state.view==='project') return ({board:'board',team:'agents',memory:'context',media:'files',skills:'methods',plugins:'extensions',settings:'settings',usage:'context'})[state.projectTab] || 'projects';
  return 'chat';
}
async function openHelp(topic='start', anchor='', media='', viewState={}) {
  rememberDraft();
  const route={page_id:String(topic||'start'),locale:CYAI_LOCALE,anchor:String(anchor||''),state:{...viewState},theme:state.data?.settings?.theme||'dark'};
  if (media) route.state.media=String(media);
  toast(ui('Ouverture de la documentation locale…'));
  try {
    if (window.pywebview?.api?.open_documentation) return await window.pywebview.api.open_documentation(route);
    return await action('open_documentation',route);
  } catch (error) {
    openDialog(ui('Documentation'),`<p role="alert">${esc(ui('Impossible d’ouvrir la documentation.'))}</p><p>${esc(error.message)}</p><button type="button" class="secondary" data-context-help>${esc(ui('Réessayer'))}</button>`,null);
  }
}
function openLegacyHelp(query, hash='') {
  const anchor=query.get('section')||query.get('anchor')||(hash.startsWith('#help-part-')?hash.slice(1):'');
  const view={};
  for (const name of ['zoom','x','y','note','wipe']) if(query.has(name))view[name]=query.get(name);
  return openHelp(query.get('help')||'start',anchor,query.get('media')||'',view);
}
document.addEventListener('click',event=>{
  if(event.target.closest('[data-context-help]'))openHelp(contextHelpTopic());
});
document.addEventListener('keydown',event=>{
  if(event.key!=='F1')return;
  event.preventDefault();openHelp(contextHelpTopic());
});
