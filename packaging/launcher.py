"""Stable launcher: never derive user configuration from the current directory."""
import ctypes,json,subprocess,sys
from pathlib import Path

def main():
    try:
        root=Path(sys.executable).resolve().parent
        state=json.loads((root/'installation.json').read_text(encoding='utf-8'))
        folder=(root/state['current']).resolve();config=Path(state['config_path'])
        if not folder.is_relative_to(root/'versions') or not config.is_file():raise ValueError('Installation ou configuration inaccessible. Relancez l’installateur.')
        subprocess.Popen([str(folder/'CyAIOrchestrator.exe'),'--config',str(config)],cwd=str(config.parent),creationflags=0x08000000)
    except Exception as e:ctypes.windll.user32.MessageBoxW(None,str(e),'CyAI Orchestrator',0x10)
if __name__=='__main__':main()
