import {createInterface} from 'node:readline';
for await (const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
  let request;
  try {
    request=JSON.parse(line);
    const response=await fetch(process.env.CYAI_PLUGIN_URL,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+process.env.CYAI_PLUGIN_TOKEN},body:JSON.stringify(request)});
    const body=await response.json();
    if(!response.ok)throw new Error(body.error||'Plugin indisponible');
    if(request.id!==undefined)process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:request.id,result:body})+'\n');
  } catch(error) {
    if(request?.id!==undefined)process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:request.id,error:{code:-32000,message:String(error.message)}})+'\n');
  }
}
