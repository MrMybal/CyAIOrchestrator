import {readFile,writeFile,mkdir,readdir,lstat,copyFile,mkdtemp,rm,rename,realpath} from 'node:fs/promises';
import {resolve,dirname,relative,isAbsolute,extname,basename} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {Script} from 'node:vm';
import {renderPage} from './source/template.mjs';
export const ROOT=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const hash=data=>createHash('sha256').update(data).digest('hex');
const inside=(base,path)=>{const delta=relative(base,path);return !delta.startsWith('..')&&!isAbsolute(delta);};
const textSuffixes=new Set(['.md','.json','.mjs','.cjs','.js','.py','.toml','.html','.css','.txt']);
const canonical=(name,data)=>textSuffixes.has(extname(name))||basename(name)==='.gitignore'?Buffer.from(data.toString('utf8').replaceAll('\r\n','\n')):data;
async function sourceFile(name){const file=resolve(ROOT,name);if(!inside(ROOT,file)||(await lstat(file)).isSymbolicLink()||!inside(await realpath(ROOT),await realpath(file)))throw Error('Source outside project: '+name);if(!(await lstat(file)).isFile())throw Error('Not a source file: '+name);return file;}
async function filesIn(base,prefix=''){const files=[];for(const item of await readdir(resolve(base,prefix),{withFileTypes:true})){const name=prefix+item.name;if(item.isSymbolicLink())throw Error('Symbolic link in artifact: '+name);if(item.isDirectory())files.push(...await filesIn(base,name+'/'));else if(item.isFile())files.push(name);else throw Error('Unsupported artifact entry: '+name);}return files.sort();}
function validateCopy(copy){const keys=Object.keys(copy.en).sort();if(JSON.stringify(keys)!==JSON.stringify(Object.keys(copy.fr).sort()))throw Error('English/French translation keys differ.');for(const locale of ['en','fr'])for(const key of keys){const value=copy[locale][key];if(typeof value!=='string'||!value.trim())throw Error('Empty translation: '+locale+'/'+key);if(JSON.stringify(value.match(/\{\w+\}/g)||[])!==JSON.stringify(copy.en[key].match(/\{\w+\}/g)||[]))throw Error('Translation placeholders differ: '+key);}return keys.length;}
function imageSize(bytes){
 if(bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])))return [bytes.readUInt32BE(16),bytes.readUInt32BE(20)];
 if(bytes[0]===255&&bytes[1]===216){let offset=2;while(offset<bytes.length&&bytes[offset]===255){const marker=bytes[offset+1];offset+=2;if(marker===216||marker===217)continue;const length=bytes.readUInt16BE(offset);if([192,193,194].includes(marker))return [bytes.readUInt16BE(offset+5),bytes.readUInt16BE(offset+3)];offset+=length;}}
 throw Error('Unsupported screenshot dimensions; use PNG or JPEG.');
}
async function checkOldOutput(output){
 try{const info=await lstat(output);if(info.isSymbolicLink()||!info.isDirectory())throw Error('Output must be a generated showcase directory.');}catch(e){if(e.code==='ENOENT')return false;throw e;}
 let info;try{info=JSON.parse(await readFile(resolve(output,'.cyai-showcase.json'),'utf8'));}catch{throw Error('Refusing to replace an unowned output directory.');}
 const files=await filesIn(output);if(info.kind!=='cyai-showcase'||JSON.stringify(files)!==JSON.stringify([...Object.keys(info.files),'.cyai-showcase.json'].sort()))throw Error('Unexpected files in output; preserving the directory.');
 for(const [name,expected] of Object.entries(info.files))if(hash(await readFile(resolve(output,name)))!==expected)throw Error('Output file was modified; preserving '+name);
 return true;
}
export async function buildShowcase({output=resolve(ROOT,'dist/website')}={}){
 output=resolve(output);const allowed=[resolve(ROOT,'dist'),resolve(ROOT,'test-results')];
 if(!allowed.some(base=>inside(base,output)&&base!==output))throw Error('Output must be inside dist/ or test-results/.');
 await mkdir(dirname(output),{recursive:true});if(!inside(await realpath(ROOT),await realpath(dirname(output))))throw Error('Output parent escapes the project.');
 const replace=await checkOldOutput(output);
 const config=JSON.parse(await readFile(resolve(ROOT,'website/site.json'),'utf8'));
 const version=(await readFile(resolve(ROOT,'pyproject.toml'),'utf8')).match(/^version\s*=\s*"([^"]+)"/m)?.[1];if(!version)throw Error('Missing application version.');
 if(config.license!=='AGPL-3.0-only')throw Error('The showcase must retain the application license.');
 for(const key of ['repository','release','download'])if(config[key]){config[key]=config[key].replaceAll('{version}',version);if(new URL(config[key]).protocol!=='https:')throw Error('Expected a verified HTTPS destination.');}
 const copy={};for(const locale of ['en','fr'])copy[locale]=JSON.parse(await readFile(resolve(ROOT,'website/source',locale+'.json'),'utf8'));
 const translationKeys=validateCopy(copy);for(const locale of ['en','fr'])for(const key of Object.keys(copy[locale]))copy[locale][key]=copy[locale][key].replaceAll('{version}',version);
 if(config.stage!=='Alpha'||!copy.en['hero.status'].startsWith('Alpha'))throw Error('Review the product stage before changing its presentation.');
 const catalog=JSON.parse(await readFile(resolve(ROOT,'website/source/screens.json'),'utf8'));
 const manualInfo=JSON.parse(await readFile(resolve(ROOT,'Documentation/DocData/build-info.json'),'utf8'));
 const manifest=JSON.parse(await readFile(resolve(ROOT,'Documentation/DocData/manifest.json'),'utf8'));
 if(manualInfo.version!==version||manifest.version!==version||JSON.stringify(manualInfo.locales)!=='["en","fr"]'||JSON.stringify(manualInfo.modules)!=='["image"]')throw Error('Regenerate the current bilingual manual before building the showcase.');
 for(const [group,base] of [['inputs',ROOT],['outputs',resolve(ROOT,'Documentation')]])for(const [name,expected] of Object.entries(manualInfo[group])){const path=resolve(base,name);if(!inside(base,path))throw Error('Documentation path escape.');const source=await sourceFile(relative(ROOT,path));if(hash(canonical(name,await readFile(source)))!==expected)throw Error('Stale documentation '+group+': '+name);}
 const manualNames=[...Object.keys(manualInfo.outputs),'DocData/build-info.json'].sort();if(JSON.stringify(await filesIn(resolve(ROOT,'Documentation')))!==JSON.stringify(manualNames))throw Error('Unexpected files in the documentation export.');
 const temporary=await mkdtemp(resolve(dirname(output),'.cyai-showcase-'));
 try{
  await mkdir(resolve(temporary,'assets'),{recursive:true});
  async function asset(source,label){const file=await sourceFile(source);const bytes=await readFile(file);const suffix=extname(file).toLowerCase();if(!['.png','.jpg','.webp'].includes(suffix))throw Error('Unsupported screenshot asset.');const name=label+'.'+hash(bytes).slice(0,12)+suffix;await copyFile(file,resolve(temporary,'assets',name));return './assets/'+name;}
  const logo=await asset('cyai/web/cyai-logo.png','cyai-logo');
  const screens={};for(const [id,item] of Object.entries(catalog)){
   if(!/^[a-z-]+$/.test(id)||!Number.isInteger(item.width)||!Number.isInteger(item.height))throw Error('Invalid screenshot catalog.');
   if(!copy.en[item.alt]||!copy.fr[item.caption])throw Error('Missing screenshot copy.');
   screens[id]={alt:item.alt,caption:item.caption,doc:item.doc,width:item.width,height:item.height,assets:{}};
   for(const locale of ['en','fr']){if(!manifest.pages.some(p=>p.id===item.doc&&p.locale===locale))throw Error('Missing screenshot manual destination.');const size=imageSize(await readFile(await sourceFile(item.files[locale])));if(size[0]!==item.width||size[1]!==item.height)throw Error('Screenshot dimensions differ from catalog: '+id+'/'+locale);screens[id].assets[locale]={src:await asset(item.files[locale],id+'-'+locale)};}
  }
  const css=await readFile(resolve(ROOT,'website/source/styles.css'),'utf8');
  const runtime=await readFile(resolve(ROOT,'website/source/site.js'),'utf8');
  const js='/* CyAI Orchestrator showcase — AGPL-3.0-only. */\n(()=>{\nconst SHOWCASE='+JSON.stringify({copy,screens})+';\n'+runtime+'\n})();\n';new Script(js,{filename:'showcase.js'});
  const stylesheet='./assets/site.'+hash(css).slice(0,12)+'.css';const script='./assets/site.'+hash(js).slice(0,12)+'.js';
  await writeFile(resolve(temporary,stylesheet),css);await writeFile(resolve(temporary,script),js);
  const html=renderPage({copy:copy.en,screens,logo,stylesheet,script,config});
  for(const [,key] of html.matchAll(/data-i18n(?:-label|-alt)?="([^"]+)"/g))if(!copy.en[key]||!copy.fr[key])throw Error('Missing HTML translation: '+key);
  for(const [,page] of html.matchAll(/data-doc="([^"]+)"/g))for(const locale of ['en','fr']){const [id,anchor]=page.split('#');const item=manifest.pages.find(p=>p.id===id&&p.locale===locale);if(!item||anchor&&!item.html.includes('id="'+anchor+'"'))throw Error('Missing contextual manual target: '+locale+'/'+page);}
  await writeFile(resolve(temporary,'index.html'),html);await copyFile(await sourceFile('LICENSE'),resolve(temporary,'LICENSE'));
  for(const name of manualNames){const destination=resolve(temporary,'manual',name);await mkdir(dirname(destination),{recursive:true});await copyFile(resolve(ROOT,'Documentation',name),destination);}
  await copyFile(await sourceFile('.CyDocBuild/host/index.html'),resolve(temporary,'manual/index.html'));
  await copyFile(await sourceFile('.CyDocBuild/host/pages-entry.js'),resolve(temporary,'manual/DocData/pages-entry.js'));
  for(const [,target] of html.matchAll(/(?:href|src)="([^"]+)"/g)){
   if(/^https:/.test(target)){if(![config.repository,config.release,config.download].filter(Boolean).includes(target))throw Error('Unexpected external destination.');continue;}
   if(target.startsWith('#')){if(!html.includes('id="'+target.slice(1)+'"'))throw Error('Broken chapter link: '+target);continue;}
   const name=target.split(/[?#]/)[0];if(!name.startsWith('./')||!inside(temporary,resolve(temporary,name)))throw Error('Nonportable local reference: '+target);if(!(await lstat(resolve(temporary,name))).isFile())throw Error('Missing showcase reference: '+target);
  }
  const names=await filesIn(temporary);const hashes={};for(const name of names)hashes[name]=hash(await readFile(resolve(temporary,name)));
  await writeFile(resolve(temporary,'.cyai-showcase.json'),JSON.stringify({kind:'cyai-showcase',version,locales:['en','fr'],translationKeys,files:hashes},null,2)+'\n');
  if(replace)await rm(output,{recursive:true});await rename(temporary,output);
  return {output,version,translationKeys,files:names.length,screenshots:Object.keys(screens).length*2,stylesheet,script};
 }catch(error){await rm(temporary,{recursive:true,force:true});throw error;}
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const args=process.argv.slice(2);if(args.some(arg=>!arg.startsWith('--output=')))throw Error('Usage: node website/build.mjs [--output=dist/website]');
 console.log(JSON.stringify(await buildShowcase({output:args[0]?.slice(9)}),null,2));
}
