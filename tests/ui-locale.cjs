// Load the production catalogue/runtime in lightweight browser-handler fixtures.
const fs=require('node:fs'),vm=require('node:vm');
module.exports=(context,language='fr')=>{
 if(context.ui)return context;
 const oldWindow=context.window||{};Object.assign(context,oldWindow);context.window=context;
 context.document??={};context.document.documentElement??={};
 context.CYAI_LANGUAGE=language;
 context.CYAI_SYSTEM_MESSAGES=JSON.parse(fs.readFileSync('cyai/locales/system.en.json','utf8'));
 context.CYAI_MESSAGES={...context.CYAI_SYSTEM_MESSAGES,...JSON.parse(fs.readFileSync('cyai/locales/en.json','utf8'))};
 vm.runInContext(fs.readFileSync('cyai/web/i18n.js','utf8'),context);
 return context;
};
