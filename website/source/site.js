/* Classic script; all copy and asset URLs are bundled by build.mjs. */
const viewer=document.querySelector('#image-viewer');
const image=document.querySelector('#viewer-image');
const stage=document.querySelector('.viewer-stage');
const menu=document.querySelector('.menu-button');
let language='en',openedBy=null,shots=[],shotIndex=0,zoom=1,previousScroll=0,previousOverflow='';
const text=key=>SHOWCASE.copy[language][key];
function docUrl(page){return './manual/Documentation.html#/'+language+'/'+page.split('#').map(encodeURIComponent).join('/');}
function closeMenu({focus=false}={}){menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label',text('nav.menu'));document.querySelector('#primary-nav').dataset.open='false';if(focus)menu.focus();}
function applyLanguage(){
 document.documentElement.lang=language;
 document.title=text('meta.title');
 for(const selector of ['meta[name="description"]','meta[property="og:description"]'])document.querySelector(selector).content=text('meta.description');
 document.querySelector('meta[property="og:title"]').content=text('meta.title');
 document.querySelector('meta[property="og:image"]').content=SHOWCASE.screens.conversation.assets[language].src;
 document.querySelectorAll('[data-i18n]').forEach(e=>{e.textContent=text(e.dataset.i18n);});
 document.querySelectorAll('[data-i18n-label]').forEach(e=>e.setAttribute('aria-label',text(e.dataset.i18nLabel)));
 document.querySelectorAll('[data-i18n-alt]').forEach(e=>{e.alt=text(e.dataset.i18nAlt);});
 document.querySelectorAll('[data-screen]').forEach(e=>{const s=SHOWCASE.screens[e.dataset.screen];e.src=s.assets[language].src;});
 document.querySelectorAll('[data-doc]').forEach(e=>{e.href=docUrl(e.dataset.doc);});
 document.querySelectorAll('button[data-lang]').forEach(e=>e.setAttribute('aria-pressed',String(e.dataset.lang===language)));
 document.querySelectorAll('[data-shot]').forEach(e=>e.setAttribute('aria-label',text('viewer.open')+': '+text(e.dataset.caption)));
 menu.setAttribute('aria-label',text(menu.getAttribute('aria-expanded')==='true'?'nav.closeMenu':'nav.menu'));
 if(viewer.open)showShot(shotIndex);
}
function localeFromUrl(){const value=new URL(location.href).searchParams.get('lang');return value==='fr'?'fr':'en';}
function setLanguage(value,{normalize=false}={}){
 language=value==='fr'?'fr':'en';
 const url=new URL(location.href);if(!normalize||url.searchParams.has('lang'))url.searchParams.set('lang',language);
 try{history.replaceState(null,'',url);}catch{}
 applyLanguage();
}
function chooseTab(id,{focus=false}={}){
 for(const button of document.querySelectorAll('[data-tab]')){const selected=button.dataset.tab===id;button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;document.querySelector('#'+button.getAttribute('aria-controls')).hidden=!selected;if(selected&&focus)button.focus();}
}
function fitPicture(){
 if(!viewer.open||!image.naturalWidth)return;
 const width=Math.max(1,Math.min(image.naturalWidth,stage.clientWidth-16,(stage.clientHeight-16)*image.naturalWidth/image.naturalHeight));
 image.style.width=Math.round(width*zoom)+'px';
 image.style.height='auto';
 document.querySelector('[data-zoom=fit]').textContent=Math.round(zoom*100)+'%';
}
function showShot(index){
 shotIndex=(index+shots.length)%shots.length;zoom=1;
 const target=shots[shotIndex];const screen=SHOWCASE.screens[target.dataset.shot];
 image.src=screen.assets[language].src;image.alt=text(screen.alt);
 document.querySelector('#viewer-caption').textContent=text(screen.caption);
 document.querySelector('#viewer-count').textContent=(shotIndex+1)+' / '+shots.length;
 stage.scrollTop=0;stage.scrollLeft=0;fitPicture();
}
function openShot(target){
 openedBy=target;previousScroll=scrollY;previousOverflow=document.body.style.overflow;
 shots=[...document.querySelectorAll('[data-shot]')].filter(e=>e.getClientRects().length);
 showShot(shots.indexOf(target));viewer.showModal();document.body.style.overflow='hidden';fitPicture();
 document.querySelector('[data-viewer-close]').focus({preventScroll:true});
}
function changeZoom(value){zoom=Math.max(1,Math.min(4,value));fitPicture();if(zoom===1){stage.scrollTop=0;stage.scrollLeft=0;}}
image.addEventListener('load',fitPicture);
viewer.addEventListener('close',()=>{document.body.style.overflow=previousOverflow;window.scrollTo({top:previousScroll,behavior:'instant'});openedBy?.focus({preventScroll:true});});
viewer.addEventListener('click',e=>{if(e.target===viewer)viewer.close();});
viewer.addEventListener('keydown',e=>{
 if(e.key==='Escape'){e.preventDefault();viewer.close();return;}
 if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();showShot(shotIndex+(e.key==='ArrowRight'?1:-1));}
 if(e.key==='+'||e.key==='='){e.preventDefault();changeZoom(zoom+.25);}
 if(e.key==='-'||e.key==='−'){e.preventDefault();changeZoom(zoom-.25);}
 if(e.key==='0'){e.preventDefault();changeZoom(1);}
 if(e.key==='Tab'){
  const controls=[...viewer.querySelectorAll('button,a[href],[tabindex="0"]')].filter(e=>!e.disabled&&e.getClientRects().length);
  const first=controls[0],last=controls[controls.length-1];
  if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
  else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
 }
});
document.addEventListener('click',e=>{
 const lang=e.target.closest('button[data-lang]');if(lang){setLanguage(lang.dataset.lang);return;}
 const shot=e.target.closest('[data-shot]');if(shot){openShot(shot);return;}
 const tab=e.target.closest('[data-tab]');if(tab){chooseTab(tab.dataset.tab);return;}
 if(e.target.closest('[data-viewer-close]'))viewer.close();
 if(e.target.closest('[data-viewer-prev]'))showShot(shotIndex-1);
 if(e.target.closest('[data-viewer-next]'))showShot(shotIndex+1);
 const zoomButton=e.target.closest('[data-zoom]');if(zoomButton)changeZoom(zoomButton.dataset.zoom==='fit'?1:zoom+(zoomButton.dataset.zoom==='in'?0.25:-0.25));
 if(e.target.closest('#primary-nav a'))closeMenu();
});
menu.addEventListener('click',()=>{const open=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(open));menu.setAttribute('aria-label',text(open?'nav.closeMenu':'nav.menu'));document.querySelector('#primary-nav').dataset.open=String(open);});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&menu.getAttribute('aria-expanded')==='true'){e.preventDefault();closeMenu({focus:true});}});
document.querySelector('[role=tablist]').addEventListener('keydown',e=>{
 const tabs=[...document.querySelectorAll('[data-tab]')];let index=tabs.indexOf(e.target);if(index<0)return;
 if(e.key==='ArrowRight'||e.key==='ArrowLeft')index=(index+(e.key==='ArrowRight'?1:tabs.length-1))%tabs.length;
 else if(e.key==='Home')index=0;else if(e.key==='End')index=tabs.length-1;else return;
 e.preventDefault();chooseTab(tabs[index].dataset.tab,{focus:true});
});
const links=[...document.querySelectorAll('[data-chapter]')];let chapterFrame=false;
function updateChapter(){chapterFrame=false;const top=document.querySelector('.site-header').offsetHeight+document.querySelector('.chapters').offsetHeight+25;let current;for(const link of links)if(document.getElementById(link.dataset.chapter).getBoundingClientRect().top<=top)current=link;links.forEach(link=>{if(link===current)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');});}
function queueChapter(){if(!chapterFrame){chapterFrame=true;requestAnimationFrame(updateChapter);}}
window.addEventListener('scroll',queueChapter,{passive:true});
window.addEventListener('resize',()=>{queueChapter();fitPicture();if(innerWidth>900)closeMenu();});
window.addEventListener('popstate',()=>{setLanguage(localeFromUrl(),{normalize:true});});
setLanguage(localeFromUrl(),{normalize:true});queueChapter();
