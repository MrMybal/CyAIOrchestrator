"""Advisory memory estimates, never an execution quota."""
import shutil, subprocess, os, time, threading
_lock=threading.Lock()
_cached={}
_until=0

def hardware():
 global _cached,_until
 with _lock:
  if time.monotonic()<_until:return dict(_cached)
  result={'gpu_total_gib':None,'gpu_free_gib':None,'gpu_name':None}
  command=shutil.which('nvidia-smi')
  if command:
   try:
    r=subprocess.run([command,'--query-gpu=name,memory.total,memory.free,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3,creationflags=0x08000000 if os.name=='nt' else 0)
    cards=[line.rsplit(',',3) for line in r.stdout.splitlines()]
    name,total,free,util=max(cards,key=lambda x:float(x[1]))
    result.update(gpu_name=name.strip(),gpu_total_gib=float(total)/1024,gpu_free_gib=float(free)/1024,gpu_util_percent=float(util) if util.strip().isdigit() else None)
   except (OSError,ValueError,IndexError,subprocess.TimeoutExpired):pass
  _cached,_until=result,time.monotonic()+10
  return dict(result)

def estimate(key,hw):
 engine=key.split(':')[0]
 ranges={'qwen':(4,6),'chatterbox':(3,5),'fish':(20,24)}
 if engine in ranges:
  low,high=ranges[engine]
  label=f'VRAM ≈ {low}–{high} Gio · RAM non mesurée'
  basis='Fish : essais courts autour de 20–21 Gio, marge jusqu’à 24 Gio.' if engine=='fish' else 'Ordre de grandeur à confirmer selon texte, référence et buffers.'
 else:
  low=high=0
  label={'pocket':'CPU · RAM ≈ 1–3 Gio · VRAM 0','piper':'CPU · RAM ≈ 0,1–1 Gio · VRAM 0','windows':'CPU · RAM gérée par Windows · VRAM 0'}.get(engine,'RAM/VRAM non mesurées')
  basis='Estimation indicative ; hors autres modèles et applications.'
 total,free=hw.get('gpu_total_gib'),hw.get('gpu_free_gib')
 severity = 'danger' if high and total is not None and low > total else 'warning' if high and (total is None or high > total or free is not None and high > free) else ''
 warning = ('VRAM totale inférieure au minimum estimé' if severity == 'danger' else 'Marge faible — chargement autorisé' if severity == 'warning' and total is not None else 'VRAM non mesurée — chargement autorisé' if severity else '')
 return {'label':label,'warning':warning,'severity':severity,'basis':basis,'vram_low_gib':low,'vram_high_gib':high}


def gguf_estimate(model,hw):
 size=model.get('bytes',0)/1024**3
 gpu=model.get('effective_settings',{}).get('device')=='gpu'
 limit=hw.get('gpu_free_gib')
 return {'label':f'Poids : {size:.2f} Gio · '+('VRAM' if gpu else 'RAM/VRAM')+' supplémentaire pour contexte et calcul (non mesurée)','warning':'Poids seuls supérieurs à la VRAM disponible' if gpu and limit is not None and size>limit else ''}
