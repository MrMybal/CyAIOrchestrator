"""Cached process RAM and NVIDIA per-process VRAM, sampled off the UI path."""
import os,shutil,subprocess,threading,time,json,re
from collections import deque

def process_tree(root):
 if os.name!='nt':return {root}
 import ctypes
 from ctypes import wintypes
 class Entry(ctypes.Structure):
  _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),('exe',wintypes.WCHAR*260)]
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD];k.CreateToolhelp32Snapshot.restype=wintypes.HANDLE;k.CloseHandle.argtypes=[wintypes.HANDLE]
 for name in ('Process32FirstW','Process32NextW'):getattr(k,name).argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
 handle=k.CreateToolhelp32Snapshot(2,0)
 if handle==ctypes.c_void_p(-1).value:return {root}
 try:
  e=Entry();e.size=ctypes.sizeof(e);edges=[];ok=k.Process32FirstW(handle,ctypes.byref(e))
  while ok:edges.append((e.pid,e.parent));ok=k.Process32NextW(handle,ctypes.byref(e))
  result={root}
  while True:
   more={pid for pid,parent in edges if parent in result}-result
   if not more:return result
   result.update(more)
 finally:k.CloseHandle(handle)

def ram_bytes(pid):
 if os.name!='nt':return None
 import ctypes
 from ctypes import wintypes
 class Counters(ctypes.Structure):
  _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('peak','working','pagedPeak','paged','nonpagedPeak','nonpaged','pagefile','pagefilePeak')]
 kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
 kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
 kernel.CloseHandle.argtypes=[wintypes.HANDLE];psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
 handle=kernel.OpenProcess(0x410,False,pid)
 if not handle:return None
 try:
  c=Counters();c.cb=ctypes.sizeof(c)
  return int(c.working) if psapi.GetProcessMemoryInfo(handle,ctypes.byref(c),c.cb) else None
 finally:kernel.CloseHandle(handle)

def windows_gpu_memory():
 """WDDM dedicated bytes per process (nvidia-smi returns N/A on many Windows drivers)."""
 command = "Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory -ErrorAction Stop | Select-Object Name,DedicatedUsage | ConvertTo-Json -Compress"
 result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=12,creationflags=0x08000000)
 if result.returncode:raise OSError('Compteurs GPU Windows indisponibles')
 return parse_windows_gpu(json.loads(result.stdout or 'null'))

def parse_windows_gpu(rows):
 if rows is None:raise ValueError('Aucun compteur GPU Windows')
 if isinstance(rows,dict):rows=[rows]
 usage={}
 for row in rows:
  match=re.match(r'pid_(\d+)_',row.get('Name',''))
  if match:
   pid=int(match[1]);usage[pid]=usage.get(pid,0)+int(row['DedicatedUsage'])
 return usage

def system_memory_cpu(previous=None):
 if os.name!='nt':return {},None
 import ctypes
 from ctypes import wintypes
 class Memory(ctypes.Structure):
  _fields_=[('length',wintypes.DWORD),('load',wintypes.DWORD)]+[(n,ctypes.c_ulonglong) for n in ('total','available','pageTotal','pageAvailable','virtualTotal','virtualAvailable','extended')]
 kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 mem=Memory();mem.length=ctypes.sizeof(mem);result={}
 if kernel.GlobalMemoryStatusEx(ctypes.byref(mem)):
  result.update(system_ram_percent=mem.load,system_ram_total_bytes=mem.total,system_ram_used_bytes=mem.total-mem.available)
 idle,kern,user=(wintypes.FILETIME() for _ in range(3))
 current=None
 if kernel.GetSystemTimes(ctypes.byref(idle),ctypes.byref(kern),ctypes.byref(user)):
  ticks=lambda x:(x.dwHighDateTime<<32)+x.dwLowDateTime
  current=(ticks(idle),ticks(kern)+ticks(user))
  if previous and current[1]>previous[1]:result['cpu_percent']=max(0,min(100,100*(1-(current[0]-previous[0])/(current[1]-previous[1]))))
 return result,current

class ResourceUsage:
 def __init__(self,service):self.service=service;self.history=deque(maxlen=720);self.cpu_previous=None;self.value={'ram_bytes':None,'vram_bytes':None};self.next=0;self.busy=False;self.lock=threading.Lock()
 def get(self):
  with self.lock:
   if not self.busy and time.monotonic()>=self.next:
    self.busy=True;threading.Thread(target=self.sample,daemon=True).start()
   return dict(self.value)
 def sample(self):
  try:
   pids=process_tree(os.getpid());manager=getattr(self.service,'local_models',None)
   if manager and manager.proc and manager.proc.poll() is None:pids.add(manager.proc.pid)
   values=[ram_bytes(pid) for pid in pids];ram=sum(v for v in values if v is not None) if any(v is not None for v in values) else None
   vram=None;model_vram=None;source='indisponible';command=shutil.which('nvidia-smi')
   if os.name=='nt':
    try:
     gpu=windows_gpu_memory();vram=sum(gpu.get(pid,0) for pid in pids);source='Windows WDDM · mémoire dédiée'
     model_vram=gpu.get(manager.proc.pid,0) if manager and manager.proc and manager.proc.poll() is None else 0
    except (OSError,ValueError,subprocess.TimeoutExpired):pass
   if command and vram is None:
    r=subprocess.run([command,'--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3,creationflags=0x08000000 if os.name=='nt' else 0)
    if r.returncode==0:
     vram=0;source='NVIDIA · processus de calcul'
     for line in r.stdout.splitlines():
      parts=line.split(',')
      if len(parts)==2 and parts[0].strip().isdigit() and int(parts[0]) in pids:
       if parts[1].strip().isdigit():vram+=int(parts[1])*1024**2
       else:vram=None;break
   from .model_memory import hardware
   hw=hardware();total=hw.get('gpu_total_gib');free=hw.get('gpu_free_gib')
   system,self.cpu_previous=system_memory_cpu(self.cpu_previous)
   try:
    disk=shutil.disk_usage(self.service.store.path.parent);system.update(disk_total_bytes=disk.total,disk_used_bytes=disk.used,disk_percent=100*disk.used/disk.total)
   except OSError:pass
   self.value={**system,'gpu_util_percent':hw.get('gpu_util_percent'),'local_model_ram_bytes':ram_bytes(manager.proc.pid) if manager and manager.proc and manager.proc.poll() is None else None,'ram_bytes':ram,'vram_bytes':vram,'local_model_vram_bytes':model_vram,'gpu_used_bytes':int((total-free)*1024**3) if total is not None and free is not None else None,'gpu_total_bytes':int(total*1024**3) if total is not None else None,'vram_source':source,'sampled_at':time.time(),'scope':'CyAI et ses processus enfants, dont WebView et le moteur local. RAM : somme des ensembles de travail. VRAM dédiée par processus, via Windows WDDM ou NVIDIA. GPU total inclut les autres applications.'}
   with self.lock:self.history.append(dict(self.value))
  except Exception:self.value={**self.value,'vram_bytes':None}
  finally:
   with self.lock:self.next=time.monotonic()+5;self.busy=False
