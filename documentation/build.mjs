import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import crypto from 'node:crypto';
import {build} from 'esbuild';
const base=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(base);
const python=process.env.CYAI_BUILD_PYTHON || (process.platform==='win32'?path.join(root,'.desktop-venv/Scripts/python.exe'):'python3');
function run(program,args){const result=spawnSync(program,args,{cwd:root,stdio:'inherit'});if(result.error)throw result.error;if(result.status!==0)throw Error('Documentation generation failed: '+program);}
if(Number(process.versions.node.split('.')[0])<22)throw Error('CyDoc generation requires Node.js 22+. Reading requires no Node.js.');
run(python,[path.join(base,'prepare.py')]);
const config=path.join(base,'cydoc.config.json');
// Use the installed package's CLI, not an invented cydoc/build export.
run(process.execPath,[path.join(base,'node_modules/cydoc/tools/cli.mjs'),'check',config]);
const output=path.join(base,'.generated/export');
await build({entryPoints:[path.join(base,'host/reader.mjs')],bundle:true,format:'iife',target:'es2020',minify:true,outfile:path.join(output,'cyai-reader.js'),legalComments:'eof'});
fs.copyFileSync(path.join(base,'host/index.html'),path.join(output,'index.html'));
fs.unlinkSync(path.join(output,'viewer.js')); // The host bootstrap uses the public viewer API above.
fs.copyFileSync(path.join(base,'vendor/CyDoc-LICENSE.txt'),path.join(output,'CyDoc-LICENSE.txt'));
fs.copyFileSync(path.join(root,'LICENSE'),path.join(output,'CyAI-LICENSE.txt'));
fs.copyFileSync(path.join(base,'.generated/inventory.json'),path.join(output,'migration-inventory.json'));
const manifest=JSON.parse(fs.readFileSync(path.join(output,'manifest.json'),'utf8'));
const originalGuides=fs.readdirSync(path.join(base,'manual/en')).filter(name=>name.endsWith('.md'));
for(const name of originalGuides){const id=name.slice(0,-3);for(const locale of ['en','fr'])if(!manifest.pages.some(page=>page.id===id&&page.locale===locale))throw Error('Missing translated guide '+id+'/'+locale);}
const modules=fs.readdirSync(output).filter(name=>/^media-.*\.js$/.test(name));
if(modules.length!==1||modules[0]!=='media-image.js')throw Error('Unexpected media dependency');
const inputs={};
const digest=file=>{let data=fs.readFileSync(file);if(/\.(?:md|json|mjs|cjs|js|py|toml|html|css|txt)$/.test(file))data=Buffer.from(data.toString('utf8').replaceAll('\r\n','\n'));return crypto.createHash('sha256').update(data).digest('hex');};
function collect(directory){for(const entry of fs.readdirSync(directory,{withFileTypes:true})){if(['node_modules','.generated'].includes(entry.name))continue;const file=path.join(directory,entry.name);if(entry.isDirectory())collect(file);else{const relative=path.relative(root,file).replaceAll('\\','/');inputs[relative]=digest(file);}}}
collect(base);
const inventory=JSON.parse(fs.readFileSync(path.join(output,'migration-inventory.json'),'utf8'));
for(const name of [...inventory.documents.map(item=>item.source),...inventory.sourceFiles,'pyproject.toml'])inputs[name]=digest(path.join(root,name));
const version=JSON.parse(fs.readFileSync(config,'utf8')).version;
const outputs={};
function outputFiles(directory){for(const entry of fs.readdirSync(directory,{withFileTypes:true})){const file=path.join(directory,entry.name);if(entry.isDirectory())outputFiles(file);else outputs[path.relative(output,file).replaceAll('\\','/')]=digest(file);}}
outputFiles(output);
fs.writeFileSync(path.join(output,'build-info.json'),JSON.stringify({version,cydoc:'0.1.0',modules:['image'],defaultLocale:'en',locales:['en','fr'],inputs,outputs},null,2)+'\n');
const target=path.resolve(root,'cyai/help');
if(path.dirname(target)!==path.join(root,'cyai')||path.basename(target)!=='help')throw Error('Invalid distribution directory');
fs.rmSync(target,{recursive:true,force:true});fs.cpSync(output,target,{recursive:true});
console.log('CyAI: '+manifest.pages.length+' localized pages exported to '+target+'; module=image; file:// reader.');
