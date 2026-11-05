'use strict';
// Bundled documentation is application content, separate from user documents and provider output.
const helpState = {cache: {}, requests: {}, topic: 'start', query: '', version: 0};
const helpText = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
function helpSearch(doc, query) {
  const words = helpText(query).trim().split(/\s+/).filter(Boolean);
  return doc.chapters.filter(chapter => words.every(word => helpText(JSON.stringify(chapter)).includes(word)));
}
function helpAsset(name) {
  return /^[a-z0-9-]+\.png$/.test(name) ? '/help/images/' + name : '';
}
function openHelp(topic = 'start') {
  rememberDraft();
  helpState.topic = /^[a-z0-9-]+$/.test(topic || '') ? topic : 'start';
  helpState.query = '';
  showView('help');
}
async function helpDocument() {
  const lang = CYAI_LOCALE === 'fr' ? 'fr' : 'en';
  if (helpState.cache[lang]) return helpState.cache[lang];
  if (!helpState.requests[lang]) helpState.requests[lang] = (async () => {
    const response = await fetch('/help/' + lang + '.json');
    if (!response.ok) throw Error(ui('Impossible de charger la documentation.'));
    const doc = await response.json();
    if (!Array.isArray(doc.chapters) || !doc.chapters.length || doc.language !== lang) throw Error(ui('Documentation invalide.'));
    helpState.cache[lang] = doc;
    return doc;
  })().finally(() => { delete helpState.requests[lang]; });
  return helpState.requests[lang];
}
function helpDiagram(block, id) {
  const parallel = block.layout === 'parallel';
  const boxes = parallel ? [[5,85,130,64],[165,85,150,64],[365,5,165,64],[365,85,165,64],[365,165,165,64],[585,85,155,64]]
    : block.labels.map((_, i) => [i * 152 + 4,20,128,76]);
  const paths = parallel ? ['M135 117H165','M315 117H340V37H365','M340 117H365','M340 117V197H365','M530 37H555V117H585','M530 117H585','M530 197H555V117']
    : boxes.slice(1).map((b,i) => 'M'+(boxes[i][0]+128)+' 58H'+b[0]);
  const lines = value => {
    const result = [''];
    for (const word of value.split(' ')) {
      if ((result.at(-1) + ' ' + word).trim().length > 17) result.push(word);
      else result[result.length-1] = (result.at(-1)+' '+word).trim();
    }
    return result;
  };
  return `<figure class="help-diagram"><svg viewBox="0 0 ${parallel?750:boxes.length*152} ${parallel?240:118}" role="img" aria-labelledby="${id}-title ${id}-desc"><title id="${id}-title">${esc(block.title)}</title><desc id="${id}-desc">${esc(block.caption)}</desc><defs><marker id="${id}-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z"/></marker></defs>${paths.map(path=>`<path class="help-edge" d="${path}" marker-end="url(#${id}-arrow)"/>`).join('')}${boxes.map(([x,y,w,h],i)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12"/><text x="${x+w/2}" y="${y+h/2-(lines(block.labels[i]).length-1)*9+5}">${lines(block.labels[i]).map((line,j)=>`<tspan x="${x+w/2}" dy="${j?18:0}">${esc(line)}</tspan>`).join('')}</text>`).join('')}</svg><figcaption>${esc(block.caption)}</figcaption></figure>`;
}
function helpBlock(block, index, chapter, doc) {
  switch (block.type) {
    case 'paragraph': return `<p>${esc(block.text)}</p>`;
    case 'heading': return `<h3 id="help-part-${index}">${esc(block.text)}</h3>`;
    case 'list': case 'steps': {
      const tag = block.type === 'steps' ? 'ol' : 'ul';
      return `<${tag}>${block.items.map(item=>`<li>${esc(item)}</li>`).join('')}</${tag}>`;
    }
    case 'note': return `<aside class="help-note"><strong>${esc(doc.labels.note)}</strong><p>${esc(block.text)}</p></aside>`;
    case 'table': return `<div class="help-table"><table><thead><tr>${block.headers.map(value=>`<th scope="col">${esc(value)}</th>`).join('')}</tr></thead><tbody>${block.rows.map(row=>`<tr>${row.map(value=>`<td>${esc(value)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    case 'image': {
      const src = helpAsset(block.file);
      return src ? `<figure class="help-screenshot"><button type="button" data-help-image="${esc(block.file)}" aria-label="${esc(doc.labels.enlarge+': '+block.alt)}"><img src="${src}" alt="${esc(block.alt)}" loading="lazy" width="1600" height="1000"></button><figcaption>${esc(block.caption)} · ${esc(doc.labels.enlarge)}</figcaption></figure>` : '';
    }
    case 'diagram': return helpDiagram(block, chapter.id+'-'+index);
    case 'action': return `<p><button type="button" class="secondary" data-help-settings="${esc(block.tab)}">${esc(block.text)} ↗</button></p>`;
    case 'related': return `<nav class="help-related" aria-label="${esc(doc.labels.related)}">${block.topics.map(id=>{const topic=doc.chapters.find(c=>c.id===id);return topic?`<button type="button" class="text-button" data-help-topic="${id}">${esc(topic.title)} →</button>`:'';}).join('')}</nav>`;
    default: return '';
  }
}
function helpNavigation(doc) {
  const results = helpSearch(doc, helpState.query);
  const list = document.getElementById('help-topics');
  if (!list) return;
  list.innerHTML = Object.entries(doc.groups).map(([group,title])=>{
    const chapters = results.filter(c=>c.group===group);
    return chapters.length ? `<section><h3>${esc(title)}</h3>${chapters.map(chapter=>`<button type="button" class="help-topic ${chapter.id===helpState.topic?'selected':''}" data-help-topic="${chapter.id}" ${chapter.id===helpState.topic?'aria-current="page"':''}><span>${esc(chapter.title)}</span>${helpState.query?`<small>${esc(chapter.summary)}</small>`:''}</button>`).join('')}</section>` : '';
  }).join('') || `<p class="help-empty">${esc(doc.labels.noResults)}</p>`;
  document.getElementById('help-count').textContent = results.length+' / '+doc.chapters.length+' '+doc.labels.chapters;
}
function helpArticle(doc, focus=false) {
  const chapter = doc.chapters.find(c=>c.id===helpState.topic) || doc.chapters[0];
  helpState.topic = chapter.id;
  const article = document.getElementById('help-article');
  if (!article || article.dataset.topic === chapter.id) return;
  const index = doc.chapters.indexOf(chapter);
  article.innerHTML = `<header class="help-article-heading"><div class="help-eyebrow">${esc(doc.groups[chapter.group])} · ${index+1} / ${doc.chapters.length}</div><h2 tabindex="-1">${esc(chapter.title)}</h2><p class="help-summary">${esc(chapter.summary)}</p></header>${chapter.blocks.map((block,i)=>helpBlock(block,i,chapter,doc)).join('')}<nav class="help-pagination" aria-label="${esc(doc.labels.navigation)}">${index?`<button type="button" class="secondary" data-help-topic="${doc.chapters[index-1].id}">← ${esc(doc.chapters[index-1].title)}</button>`:'<span></span>'}${index+1<doc.chapters.length?`<button type="button" class="secondary" data-help-topic="${doc.chapters[index+1].id}">${esc(doc.chapters[index+1].title)} →</button>`:''}</nav><footer class="help-footer">CyAI Orchestrator ${esc(state.data?.version||'')} · ${esc(doc.labels.offline)}</footer>`;
  article.dataset.topic = chapter.id;
  article.scrollTop = 0;
  if (focus) article.querySelector('h2').focus({preventScroll:true});
}
async function renderHelp() {
  const request = ++helpState.version;
  const navigation = state.navigationVersion;
  const current = () => state.view==='help' && navigation===state.navigationVersion && request===helpState.version;
  const page = $('page');
  if (!page.querySelector('.help-layout')) htmlIfChanged('page',`<p class="empty-state" role="status">${esc(ui('Chargement de la documentation…'))}</p>`);
  try {
    const doc = await helpDocument();
    if (!current()) return;
    if (!page.querySelector('.help-layout')) {
      page.innerHTML = `<div class="help-layout"><aside class="help-sidebar"><div class="help-brand"><span aria-hidden="true">?</span><div><h2>${esc(doc.labels.title)}</h2><small>${esc(doc.labels.offline)}</small></div></div><button type="button" class="text-button help-back" data-help-back>← ${esc(doc.labels.back)}</button><label class="help-search-label" for="help-search">${esc(doc.labels.search)}</label><div class="help-search"><input id="help-search" type="search" value="${esc(helpState.query)}" placeholder="${esc(doc.labels.searchPlaceholder)}" autocomplete="off"><button type="button" data-help-clear aria-label="${esc(doc.labels.clear)}">×</button></div><p id="help-count" class="help-count" role="status" aria-live="polite"></p><nav id="help-topics" aria-label="${esc(doc.labels.contents)}"></nav><p class="help-language">${esc(doc.labels.language)}</p></aside><article id="help-article" class="help-article" aria-label="${esc(doc.labels.article)}"></article></div>`;
      page._rendered = null;
    }
    helpArticle(doc); helpNavigation(doc);
  } catch (error) {
    if (current()) { page.innerHTML = `<div class="empty-state" role="alert"><h2>${esc(ui('Documentation'))}</h2><p>${esc(error.message)}</p><button type="button" class="secondary" data-help-retry>${esc(ui('Réessayer'))}</button></div>`; page._rendered=null; }
  }
}
function helpImage(name) {
  const doc = helpState.cache[CYAI_LOCALE];
  const block = doc?.chapters.flatMap(c=>c.blocks).find(b=>b.type==='image' && b.file===name);
  const src = helpAsset(name);
  if (!block || !src) return;
  const dialog = document.createElement('dialog');
  dialog.className = 'help-image-dialog';
  dialog.setAttribute('aria-label',block.alt);
  dialog.innerHTML = `<header><strong>${esc(block.alt)}</strong><div><button type="button" data-help-zoom="-" aria-label="${esc(doc.labels.zoomOut)}">−</button><button type="button" data-help-zoom="reset">100 %</button><button type="button" data-help-zoom="+" aria-label="${esc(doc.labels.zoomIn)}">＋</button><button type="button" data-help-close aria-label="${esc(doc.labels.close)}">✕</button></div></header><div class="help-image-stage"><img src="${src}" alt="${esc(block.alt)}"></div>`;
  let zoom = 100;
  dialog.addEventListener('click',event=>{
    const button=event.target.closest('button'); if(!button)return;
    if(button.hasAttribute('data-help-close'))dialog.close();
    if(button.dataset.helpZoom){zoom=button.dataset.helpZoom==='reset'?100:Math.max(50,Math.min(300,zoom+(button.dataset.helpZoom==='+'?25:-25)));dialog.querySelector('img').style.width=zoom+'%';dialog.querySelector('[data-help-zoom="reset"]').textContent=zoom+' %';}
  });
  dialog.addEventListener('close',()=>dialog.remove(),{once:true});
  document.body.append(dialog);dialog.showModal();
}
document.addEventListener('input',event=>{
  if(event.target.id!=='help-search')return;
  helpState.query=event.target.value;
  const doc=helpState.cache[CYAI_LOCALE];if(doc)helpNavigation(doc);
});
document.addEventListener('click',event=>{
  const button=event.target.closest('button');if(!button)return;
  const doc=helpState.cache[CYAI_LOCALE];
  if(button.dataset.helpTopic && doc){helpState.topic=button.dataset.helpTopic;helpArticle(doc,true);helpNavigation(doc);}
  if(button.hasAttribute('data-help-clear') && doc){helpState.query='';$('help-search').value='';helpNavigation(doc);$('help-search').focus();}
  if(button.hasAttribute('data-help-retry'))renderHelp();
  if(button.hasAttribute('data-help-back'))closeOverlay();
  if(button.dataset.helpImage)helpImage(button.dataset.helpImage);
  if(button.dataset.helpSettings && ['connectors','appearance','mcp','plugins','cytools','local','voice','downloads','backup','folders','context','models','desktop'].includes(button.dataset.helpSettings)){
    state.settingsTab=button.dataset.helpSettings;showView('settings');
  }
});
