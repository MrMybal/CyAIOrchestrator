"""Offline Windows installer and updater; retains previous application version."""
import argparse,ctypes,json,os,subprocess,sys,threading
from pathlib import Path
from release_install import install_package,read_install,rollback,create_shortcuts,atomic_json

def main():
    base=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
    parser=argparse.ArgumentParser();parser.add_argument('--install-dir',type=Path);parser.add_argument('--config',type=Path);parser.add_argument('--silent',action='store_true');args=parser.parse_args()
    home=Path(os.environ['LOCALAPPDATA'])/'CyAIOrchestrator'
    pointer=json.loads((home/'installation.json').read_text(encoding='utf-8')) if (home/'installation.json').exists() else {}
    root=args.install_dir or Path(pointer.get('install_root',Path(os.environ['LOCALAPPDATA'])/'Programs'/'CyAIOrchestrator'))
    config=args.config or Path(pointer.get('config_path',home/'config.json'))
    if not config.exists():
        for parent in Path(sys.executable).resolve().parents:
            if (parent/'pyproject.toml').exists() and (parent/'config.json').exists():config=parent/'config.json';break
    def apply(selected):
        selected=Path(selected).expanduser().resolve()
        return install_package(base/'payload.zip',base/'release.json',root,selected,home,base/'CyAILauncher.exe',create_shortcuts)
    if args.silent:
        apply(config);return
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    ui=tk.Tk();ui.title('Installer / mettre à jour CyAI Orchestrator');ui.geometry('710x400')
    version=json.loads((base/'release.json').read_text())['version'];choice=tk.StringVar(value=str(config));status=tk.StringVar(value='Les conversations et modèles restent dans leur dossier actuel.')
    panel=ttk.Frame(ui,padding=20);panel.pack(fill='both',expand=True)
    ttk.Label(panel,text='CyAI Orchestrator '+version,font=('Segoe UI',17,'bold')).pack(anchor='w',pady=8)
    ttk.Label(panel,text='Installation par utilisateur, sans droits administrateur.\nUne mise à jour conserve la version précédente et votre configuration.').pack(anchor='w',pady=8)
    ttk.Label(panel,text='Configuration à conserver :').pack(anchor='w')
    ttk.Entry(panel,textvariable=choice,width=90).pack(fill='x')
    def choose():
        result=filedialog.askopenfilename(title='Configuration CyAI existante',filetypes=[('Configuration JSON','*.json')]);
        if result:choice.set(result)
    def fresh():
        dest=home/'config.json'
        if not dest.exists():atomic_json(dest,{'port':8766,'data_dir':str(home/'data'),'allowed_roots':[str(Path.home())],'context_chars':48000,'connectors':{}})
        choice.set(str(dest))
    row=ttk.Frame(panel);row.pack(anchor='w',pady=6)
    ttk.Button(row,text='Choisir une configuration…',command=choose).pack(side='left')
    ttk.Button(row,text='Nouvelle installation',command=fresh).pack(side='left',padx=8)
    ttk.Label(panel,text='Application : '+str(root),wraplength=650).pack(anchor='w',pady=8)
    ttk.Label(panel,textvariable=status,wraplength=650).pack(anchor='w',pady=8)
    def work():
        selected=choice.get();button.config(state='disabled');status.set('Vérification du paquet et installation…')
        def run():
            try:
                apply(selected)
                ui.after(0,lambda:(status.set('Installation terminée. Raccourcis créés sur le Bureau et dans le menu Démarrer. Quittez l’ancienne version avant d’ouvrir la nouvelle.'),button.config(state='normal')))
            except Exception as exc:
                message=str(exc);ui.after(0,lambda:(messagebox.showerror('Installation impossible',message),button.config(state='normal')))
        threading.Thread(target=run,daemon=True).start()
    button=ttk.Button(panel,text='Installer / mettre à jour',command=work);button.pack(anchor='w',pady=8)
    def undo():
        try:rollback(root);status.set('Version précédente rétablie. Rouvrez CyAI avec son raccourci. Les données sont conservées.')
        except Exception as exc:messagebox.showerror('Retour arrière',str(exc))
    ttk.Button(panel,text='Revenir à la version précédente',command=undo).pack(anchor='w')
    ui.mainloop()
if __name__=='__main__':
    try:main()
    except Exception as e:
        if '--silent' in sys.argv:raise
        ctypes.windll.user32.MessageBoxW(None,str(e),'Installation CyAI',0x10)
