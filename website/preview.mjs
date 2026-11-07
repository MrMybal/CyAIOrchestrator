import {createServer} from 'node:http';
import {readFile,stat,realpath} from 'node:fs/promises';
import {resolve,relative,isAbsolute,extname} from 'node:path';
import {buildShowcase} from './build.mjs';
const args=process.argv.slice(2);if(args.some(a=>!/^--(?:port|base)=/.test(a)))throw Error('Usage: node website/preview.mjs [--port=0] [--base=/cyai/]');
const port=Number(args.find(a=>a.startsWith('--port='))?.slice(7)||0);
const base=args.find(a=>a.startsWith('--base='))?.slice(7)||'/cyai/';
if(!Number.isInteger(port)||port<0||port>65535||!/^\/(?:[a-z0-9_-]+\/)*$/.test(base))throw Error('Invalid port or static base path.');
const result=await buildShowcase();const root=await realpath(result.output);
const types={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml','.txt':'text/plain; charset=utf-8','.md':'text/plain; charset=utf-8'};
const server=createServer(async(req,res)=>{
 try{
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405).end();return;}
  const owned=new Set(Object.keys(JSON.parse(await readFile(resolve(root,'.cyai-showcase.json'),'utf8')).files));
  const path=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  if(path==='/'&&base!=='/'){res.writeHead(302,{Location:base}).end();return;}
  if(!path.startsWith(base)){res.writeHead(404).end();return;}
  let name=path.slice(base.length);if(!name||name.endsWith('/'))name+='index.html';
  const target=resolve(root,name);const delta=relative(root,target);
  if(delta.startsWith('..')||isAbsolute(delta)||!owned.has(delta.replaceAll('\\','/'))){res.writeHead(404).end();return;}
  const real=await realpath(target);const check=relative(root,real);if(check.startsWith('..')||isAbsolute(check)||!(await stat(real)).isFile()){res.writeHead(404).end();return;}
  const bytes=await readFile(real);res.writeHead(200,{'Content-Type':types[extname(target)]||'text/plain; charset=utf-8','Content-Length':bytes.length,'X-Content-Type-Options':'nosniff','Cache-Control':/\.[a-f0-9]{12}\./.test(name)?'public, max-age=31536000, immutable':'no-cache'});res.end(req.method==='HEAD'?undefined:bytes);
 }catch{res.writeHead(404).end();}
});
await new Promise((ok,no)=>{server.once('error',no);server.listen(port,'127.0.0.1',ok);});
console.log('CyAI showcase: http://127.0.0.1:'+server.address().port+base);
console.log('Generated entry: '+resolve(root,'index.html'));
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>server.close(()=>process.exit(0)));
process.stdin.on('data',bytes=>{if(bytes.includes(3))server.close(()=>process.exit(0));});
