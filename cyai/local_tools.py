"""Function calling for local engines; all application actions use the MCP gateway."""
import json
import urllib.request
from .app_mcp import TOOLS


def normalized_usage(data):
    return {**data, 'input_tokens':data.get('input_tokens',data.get('prompt_tokens')),
            'output_tokens':data.get('output_tokens',data.get('completion_tokens'))}


def run(url, headers, prompt, control, model=None, ollama=False):
    messages=[{'role':'user','content':prompt}]
    if ollama and getattr(control,'images',[]):messages[0]['images']=[im['data'] for im in control.images]
    if not ollama and getattr(control,'images',[]):
        messages[0]['content']=[{'type':'text','text':prompt}]+[{'type':'image_url','image_url':{'url':'data:'+im['mime']+';base64,'+im['data']}} for im in control.images]
    tools=[{'type':'function','function':{'name':t['name'],'description':t['description'],'parameters':t['inputSchema']}} for t in TOOLS]
    if getattr(control,'benchmark',False): tools=[]
    output=''
    totals={'input_tokens':0,'output_tokens':0}
    while True:
        control.check()
        payload={'messages':messages,'tools':tools,'stream':True}
        if model:payload['model']=model
        if not ollama:payload.update(stream_options={'include_usage':True})
        request=urllib.request.Request(url,headers=headers,data=json.dumps(payload).encode())
        content='';calls={};finished=False;done=False;last_usage=None
        def record_usage(raw):
            nonlocal last_usage
            candidate=normalized_usage(raw)
            if not all(isinstance(candidate.get(k),(int,float)) for k in totals):return
            last_usage=candidate
            control.emit('usage',{k:totals[k]+(last_usage.get(k) or 0) for k in totals})
        with urllib.request.urlopen(request,timeout=120) as response:
            for line in response:
                control.check()
                if ollama:
                    if not line.strip():continue
                    event=json.loads(line)
                    delta=event.get('message',{})
                    for call in delta.get('tool_calls',[]):
                        index=len(calls);calls[index]={'id':'local_'+str(index),'function':call['function']}
                    text=delta.get('content') or ''
                    if event.get('done'):
                        finished=done=True
                        record_usage({'input_tokens':event.get('prompt_eval_count'),'output_tokens':event.get('eval_count')})
                else:
                    if not line.startswith(b'data:'):continue
                    raw=line[5:].strip()
                    if raw==b'[DONE]':done=True;break
                    event=json.loads(raw);text=''
                    if event.get('usage'):record_usage(event['usage'])
                    for choice in event.get('choices',[]):
                        delta=choice.get('delta',{});text+=delta.get('content') or ''
                        for fragment in delta.get('tool_calls',[]):
                            call=calls.setdefault(fragment['index'],{'id':'','function':{'name':'','arguments':''}})
                            if fragment.get('id'):call['id']=fragment['id']
                            for key in ('name','arguments'):call['function'][key]+=fragment.get('function',{}).get(key,'')
                        reason=choice.get('finish_reason')
                        if reason=='length':raise RuntimeError('Limite de sortie atteinte avant la fin de la réponse.')
                        if reason:finished=True
                if event.get('error'):raise RuntimeError(str(event['error']))
                if text:content+=text;output+=text;control.emit('delta',{'text':text})
                if ollama and done:break
        if not (done and finished):raise RuntimeError('Flux local interrompu avant confirmation finale.')
        if last_usage:
            for k in totals:totals[k]+=last_usage.get(k) or 0
        if not calls:return output
        if getattr(control,'benchmark',False): raise ValueError('Le candidat a demandé un outil dans un exercice sans outils.')
        normalized=[]
        for index in sorted(calls):
            call=calls[index];fn=call['function'];args=fn.get('arguments',{})
            if isinstance(args,str):args=json.loads(args)
            normalized.append({'id':call['id'] or 'local_'+str(index),'type':'function','function':{'name':fn['name'],'arguments':args if ollama else json.dumps(args)}})
        messages.append({'role':'assistant','content':content,'tool_calls':normalized})
        for call in normalized:
            control.check();fn=call['function'];args=fn['arguments']
            if isinstance(args,str):args=json.loads(args)
            if fn['name'] not in {t['name'] for t in TOOLS}:result={'isError':True,'error':'Outil inconnu.'}
            else:
                control.emit('tool',{'tool':fn['name'],'arguments':args})
                result=control.plugin_call(fn['name'],args)
            message={'role':'tool','content':json.dumps(result,ensure_ascii=False)}
            message.update({'tool_name':fn['name']} if ollama else {'tool_call_id':call['id']})
            messages.append(message)
