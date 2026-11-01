const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const load=(language)=>require('./ui-locale.cjs')(vm.createContext({}),language);
const en=load('en'),fr=load('fr'),fallback=load('unsupported');
const editorPrefs={};const editorContext=vm.createContext({localStorage:{setItem:(key,value)=>editorPrefs[key]=value}});require('./ui-locale.cjs')(editorContext,'en');assert.equal(editorPrefs['cymd.language'],'en');assert.equal(editorPrefs['cyannota.locale'],'en');
assert.equal(en.CYAI_LOCALE,'en');assert.equal(fr.CYAI_LOCALE,'fr');assert.equal(fallback.CYAI_LOCALE,'en');
assert.equal(en.document.documentElement.lang,'en');assert.equal(en.CYAI_FORMAT_LOCALE,'en-US');
assert.equal(fr.document.documentElement.lang,'fr');assert.equal(fr.CYAI_FORMAT_LOCALE,'fr-FR');
assert.equal(en.ui('Enregistrer'),'Save');assert.equal(fr.ui('Enregistrer'),'Enregistrer');
assert.equal(en.ui('  Enregistrer  '),'  Save  ');
assert.equal(en.ui('<button data-action="save" aria-label="Enregistrer">Enregistrer</button>'),'<button data-action="save" aria-label="Save">Save</button>');
assert.equal(en.ui('<input name="title" value="Paramètres" placeholder="Nom du projet">'),'<input name="title" value="Paramètres" placeholder="Project name">');
for(const context of [en,fr]){
 context.content='Paramètres <b>Enregistrer</b> ⟪1⟫ {0}';
 const value=vm.runInContext('ui`<p>${content}</p>`',context);assert.equal(value,'<p>'+context.content+'</p>');
 context.name='Nom du projet';assert.equal(vm.runInContext('ui`<button title="${name}">${name}</button>`',context),'<button title="Nom du projet">Nom du projet</button>');
}
assert.equal(vm.runInContext('ui`<p>${5} tâche(s)</p>`',en),'<p>5 task(s)</p>');
assert.equal(vm.runInContext('ui`<p>${5} tâche(s)</p>`',fr),'<p>5 tâche(s)</p>');
assert.equal(vm.runInContext('ui`<label>Entrée</label><p>${3} réussies / ${2} échouées</p>`',en),'<label>Input</label><p>3 succeeded / 2 failed</p>');
assert.equal(en.ui('Unexpected provider output: Paramètres'),'Unexpected provider output: Paramètres');
assert.equal(en.ui.system('Voix · Paramètres'), 'Voice · Paramètres');
assert.equal(fr.ui.system('Voix · Paramètres'), 'Voix · Paramètres');
assert.equal(en.ui.system('VRAM ≈ 20–24 Gio · RAM non mesurée'), 'VRAM ≈ 20–24 GiB · RAM not measured');
const catalog={...JSON.parse(fs.readFileSync('cyai/locales/system.en.json','utf8')),...JSON.parse(fs.readFileSync('cyai/locales/en.json','utf8'))};
for(const [key,value] of Object.entries(catalog))assert.deepEqual((key.match(/\{\d+\}/g)||[]).sort(),(value.match(/\{\d+\}/g)||[]).sort(),key);
console.log('PASS: English default/fallback, French, HTML and attributes, dynamic value isolation, plural templates and '+Object.keys(catalog).length+' catalogue entries.');
