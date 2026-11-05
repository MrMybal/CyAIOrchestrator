"""@doc api-help-links
@locale en
@title Local documentation routes
@section API
@symbol cyai.documentation
Build and open validated local CyDoc routes without starting an HTTP documentation server.

## Route contract {#parameters}
`documentation_url(page_id, locale, anchor, state, theme)` returns an encoded file URL.
Page IDs, anchors and media IDs are checked against the bundled manifest. English is the
fallback language. Unknown pages fall back to `start`; invalid explicit anchors are rejected.

## Native integration {#native}
`DocumentationWindows.open()` reuses a dedicated WebView2 window. Windows navigation uses
an explicit file:// URL; filesystem paths must not be passed as HTTP-served relative paths.
The browser-mode launcher sends routes over a local control file and never sends documentation over HTTP.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import quote, urlencode

__doc_fr__ = """@doc api-help-links
@locale fr
@title Adresses de documentation locale
@section API
@symbol cyai.documentation
Construire et ouvrir des adresses CyDoc locales validées, sans serveur HTTP de documentation.

## Contrat des adresses {#parameters}
`documentation_url(page_id, locale, anchor, state, theme)` renvoie une URL file encodée.
Pages, ancres et médias sont vérifiés dans le manifeste livré. L'anglais est la langue de repli.
Une page inconnue revient à `start` ; une ancre explicite invalide est refusée.

## Intégration native {#native}
`DocumentationWindows.open()` réutilise une fenêtre WebView2 dédiée avec une URL file:// explicite.
Les chemins relatifs servis en HTTP ne sont pas utilisés. Le mode navigateur
transmet ses adresses par fichier de contrôle local, sans servir la documentation en HTTP.
"""

SETTINGS_TABS = {'models', 'local', 'voice', 'downloads', 'connectors', 'appearance', 'mcp', 'plugins', 'cytools', 'backup', 'folders', 'context', 'desktop'}
THEMES = {'dark': 'midnight', 'light': 'light', 'nord': 'nord', 'midnight': 'midnight', 'paper': 'paper', 'contrast': 'contrast'}

def help_root():
    return Path(__file__).resolve().parent / 'help'

def canonical_route(page_id='start', locale='en', anchor='', state=None, theme='dark'):
    manifest = json.loads((help_root()/'manifest.json').read_text('utf-8'))
    locale = locale if locale in {item['code'] for item in manifest['locales']} else manifest['defaultLocale']
    page_id = str(page_id or 'start')
    if '#' in page_id and not anchor:
        page_id, anchor = page_id.split('#', 1)
    aliases = manifest.get('aliases', {})
    seen = set()
    while page_id in aliases and page_id not in seen:
        seen.add(page_id); target = aliases[page_id]
        page_id, _, destination_anchor = target.partition('#')
        anchor = anchor or destination_anchor
    page = next((p for p in manifest['pages'] if p['id']==page_id and p['locale']==locale), None)
    page = page or next((p for p in manifest['pages'] if p['id']==page_id and p['locale']==manifest['defaultLocale']), None)
    if page is None:
        page_id='start';anchor='';state={}
        page=next(p for p in manifest['pages'] if p['id']==page_id and p['locale']==manifest['defaultLocale'])
    if anchor and anchor not in {h['id'] for h in page['headings']} | set(page.get('anchors', [])):
        raise ValueError('Unknown documentation section.')
    values = {}
    for key,value in (state or {}).items():
        if isinstance(key,str) and re.fullmatch(r'[a-zA-Z][\w-]{0,31}',key) and isinstance(value,(str,int,float)) and len(str(value))<=2000:
            values[key]=str(value)
    if values.get('media') and ('data-cydoc-id="'+values['media']+'"') not in page['html']:
        raise ValueError('Unknown documentation media.')
    return {'pageId':page_id,'locale':locale,'anchor':anchor or '', 'state':values,'theme':THEMES.get(theme,'midnight')}

def documentation_url(page_id='start', locale='en', anchor='', state=None, theme='dark'):
    route=canonical_route(page_id,locale,anchor,state,theme)
    base=(help_root()/'index.html').resolve().as_uri()
    address=base+'#/'+quote(route['locale'],safe='')+'/'+quote(route['pageId'],safe='')
    if route['anchor']:address+='/'+quote(route['anchor'],safe='')
    # .NET Uri treats an outer file query as part of its filename. Keep theme in the fragment.
    values={**route['state'],'theme':route['theme']}
    address+='?'+urlencode(sorted(values.items()),quote_via=quote)
    return address


class DocumentationActions:
    def __init__(self, open_settings=None):self._open_settings=open_settings
    def open_settings(self, tab):
        if tab not in SETTINGS_TABS:raise ValueError('Unknown settings page.')
        if self._open_settings:self._open_settings(tab);return {'opened':True}
        return {'opened':False}

class DocumentationWindows:
    """One dedicated reader per desktop process. The main workspace remains intact."""
    def __init__(self, open_settings=None):
        self.window=None;self.callback=open_settings
    def open(self, page_id='start', locale='en', anchor='', state=None, theme='dark'):
        address=documentation_url(page_id,locale,anchor,state,theme)
        if self.window is None:
            import webview
            window=webview.create_window('CyAI · Documentation',address,width=1320,height=920,min_size=(640,480),background_color='#101217',text_select=True,js_api=DocumentationActions(self.callback))
            self.window=window
            def closed():
                if self.window is window:self.window=None
            window.events.closed += closed
        else:
            window=self.window
            target=canonical_route(page_id,locale,anchor,state,theme)
            window.evaluate_js('CYAI_HELP.navigate('+json.dumps(target)+')')
            window.show()
        return {'opened':True,'url':address,'reader':'cydoc-file'}

class DocumentationLauncher:
    """Local control-file transport for opening/reusing help from browser mode."""
    def __init__(self, data_dir):self.directory=Path(data_dir);self.process=None;self.control=None
    def open(self, **route):
        address=documentation_url(**route)
        if importlib.util.find_spec('webview') is None:
            import webbrowser
            return {'opened':bool(webbrowser.open(address)),'url':address,'reader':'system-browser'}
        self.directory.mkdir(parents=True,exist_ok=True)
        if self.process is None or self.process.poll() is not None:
            handle=tempfile.NamedTemporaryFile(prefix='documentation-',suffix='.json',dir=self.directory,delete=False);handle.close();self.control=Path(handle.name)
        temporary=self.control.with_suffix('.tmp')
        temporary.write_text(json.dumps(route),encoding='utf-8');temporary.replace(self.control)
        if self.process is None or self.process.poll() is not None:
            args=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,'-m','cyai.documentation']
            args+=['--documentation-route',json.dumps(route),'--control',str(self.control)]
            self.process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000 if os.name=='nt' else 0)
        return {'opened':True,'url':address,'reader':'cydoc-file'}

def main(argv=None):
    parser=argparse.ArgumentParser(description='Open the bundled local CyDoc manual')
    parser.add_argument('--documentation-route',default='{}');parser.add_argument('--control',type=Path)
    parser.add_argument('--verify-documentation',type=Path);parser.add_argument('--storage',type=Path)
    args=parser.parse_args(argv);route=json.loads(args.documentation_route)
    import webview
    manager=DocumentationWindows();manager.open(**route)
    window=manager.window
    done=threading.Event();verify_lock=threading.Lock()
    def loaded():
        if not args.verify_documentation or done.is_set():return
        # about:blank has its own loaded event; it must not close the real reader.
        if not str(window.get_current_url() or '').startswith('file:'):return
        if not verify_lock.acquire(blocking=False):return
        try:
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                result=window.evaluate_js("JSON.stringify({url:location.href,ready:location.protocol==='file:' && !!globalThis.CYAI_HELP && !!document.querySelector('#main-content h1') && [...document.querySelectorAll('[data-cydoc-module=image]')].every(e=>e.querySelector('img')?.naturalWidth>0),language:document.documentElement.lang,images:document.querySelectorAll('[data-cydoc-module=image]').length,bridge:!!globalThis.pywebview?.api?.open_settings})")
                report=json.loads(result)
                if report['ready']:break
                time.sleep(.1)
            from webview import http
            report['webview_http_server']=http.global_server is not None
            if not report['ready']:
                report['error']=window.evaluate_js('document.body.innerText.slice(0,2000)')
            args.verify_documentation.parent.mkdir(parents=True,exist_ok=True)
            args.verify_documentation.write_text(json.dumps(report,indent=2),encoding='utf-8')
        except Exception as error:
            args.verify_documentation.write_text(json.dumps({'error':str(error)}),encoding='utf-8')
        finally:done.set();window.destroy()
    window.events.loaded += loaded
    def watch():
        if not args.control:return
        window.events.shown.wait(20)
        try:previous=args.control.stat().st_mtime_ns
        except OSError:previous=0
        while not done.wait(.3):
            try:
                timestamp=args.control.stat().st_mtime_ns
                if timestamp!=previous:
                    previous=timestamp;manager.open(**json.loads(args.control.read_text('utf-8')))
            except (OSError,ValueError):pass
    window.events.closed += done.set
    threading.Thread(target=watch,daemon=True).start()
    def timeout():
        if args.verify_documentation and not done.wait(30):
            args.verify_documentation.parent.mkdir(parents=True,exist_ok=True)
            args.verify_documentation.write_text(json.dumps({'error':'Reader did not become ready within 30 seconds.'}),encoding='utf-8')
            window.destroy()
    threading.Thread(target=timeout,daemon=True).start()
    if args.storage:storage=args.storage
    else:
        from .storage import default_data_dir
        storage=default_data_dir()/'documentation-window'
    storage=storage.resolve()
    storage.mkdir(parents=True,exist_ok=True)
    webview.start(gui='edgechromium' if os.name=='nt' else None,http_server=False,private_mode=False,storage_path=str(storage))

if __name__=='__main__':main()
