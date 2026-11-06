import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import crypto from 'node:crypto';
import {build} from 'esbuild';
const base=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(base),output=path.resolve(root,'Documentation');
if(Number(process.versions.node.split('.')[0])<22)throw Error('CyDoc generation requires Node.js 22+.');
const config=JSON.parse(fs.readFileSync(path.join(base,'cydoc.config.json'),'utf8'));
if(path.resolve(base,config.out)!==output||path.dirname(output)!==root)throw Error('Invalid documentation output');
// Remove only a previously generated, owned export; unrelated files must survive.
if(fs.existsSync(output)){
 const marker=path.join(output,'DocData/build-info.json');
 if(!fs.existsSync(marker))throw Error('Unrecognized Documentation directory; refusing to replace it.');
 const previous=JSON.parse(fs.readFileSync(marker,'utf8'));
 const known=new Set([...Object.keys(previous.outputs),'DocData/build-info.json']);
 function guard(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,entry.name);if(entry.isSymbolicLink())throw Error('Symlink in export');if(entry.isDirectory())guard(p);else if(!known.has(path.relative(output,p).replaceAll('\\','/')))throw Error('Unrecognized export file: '+p);}}
 guard(output);fs.rmSync(output,{recursive:true,force:true});
}
const result=spawnSync(process.execPath,[path.join(base,'node_modules/cydoc/tools/cli.mjs'),'check',path.join(base,'cydoc.config.json')],{cwd:root,stdio:'inherit'});
if(result.error)throw result.error;if(result.status!==0)throw Error('CyDoc check failed');
// Keep CyDoc's actual exporter, module providers and viewer. Only add the native bridge.
await build({entryPoints:[path.join(base,'host/adapter.mjs')],bundle:true,format:'iife',target:'es2020',minify:true,outfile:path.join(output,'DocData/cyai-host.js'),legalComments:'eof'});
fs.copyFileSync(path.join(base,'host/Documentation.html'),path.join(output,'Documentation.html'));
fs.copyFileSync(path.join(base,'vendor/CyDoc-LICENSE.txt'),path.join(output,'DocData/CyDoc-LICENSE.txt'));
fs.copyFileSync(path.join(root,'LICENSE'),path.join(output,'DocData/CyAI-LICENSE.txt'));
const manifest=JSON.parse(fs.readFileSync(path.join(output,'DocData/manifest.json'),'utf8'));
if(manifest.pages.some(p=>p.kind==='source')||manifest.defaultLocale!=='en')throw Error('Invalid public content');
for(const locale of ['en','fr'])if(!manifest.locales.some(x=>x.code===locale))throw Error('Incomplete mandatory locale');
const modules=fs.readdirSync(path.join(output,'DocData')).filter(x=>/^media-.*\.js$/.test(x));
if(modules.join()!=='media-image.js')throw Error('Unexpected media dependency');
const digest=file=>{let data=fs.readFileSync(file);if(path.basename(file)==='.gitignore'||/\.(?:md|json|mjs|cjs|js|py|toml|html|css|txt)$/.test(file))data=Buffer.from(data.toString('utf8').replaceAll('\r\n','\n'));return crypto.createHash('sha256').update(data).digest('hex');};
const inputs={},outputs={};
function collect(dir,relativeTo,map,skip=[]){for(const e of fs.readdirSync(dir,{withFileTypes:true})){if(skip.includes(e.name))continue;const p=path.join(dir,e.name);if(e.isDirectory())collect(p,relativeTo,map,skip);else map[path.relative(relativeTo,p).replaceAll('\\','/')]=digest(p);}}
collect(base,root,inputs,['node_modules','.generated','internal']);
for(const name of ['pyproject.toml','cyai/documentation.py','cyai/mcp.py','cyai/app_mcp.py'])inputs[name]=digest(path.join(root,name));
collect(output,output,outputs);
fs.writeFileSync(path.join(output,'DocData/build-info.json'),JSON.stringify({version:config.version,cydoc:'0.1.0',upstream:'6ddf9a582defb2f11fbb3f992afef6f98dcadc93',modules:config.modules,defaultLocale:config.defaultLocale,locales:['en','fr'],inputs,outputs},null,2)+'\n');
console.log('CyAI: '+manifest.pages.length+' localized pages → '+output+'; image only; stock CyDoc file reader.');
