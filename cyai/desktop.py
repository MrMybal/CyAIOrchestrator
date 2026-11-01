"""Windows desktop window and ownership-aware local service lifecycle."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import threading
from urllib.error import URLError
from urllib.request import Request, urlopen

from .__main__ import InstanceLock
from .connectors import registry
from .engine import Engine
from .security import PathPolicy, SecretStore
from .server import make_server
from .service import Service
from .store import Store


class DesktopWindows:
    def __init__(self, url):
        self.url = url

    def open_window(self, conversation_id=''):
        import re
        import webview
        if conversation_id and not re.fullmatch(r'[a-f0-9]{32}', conversation_id):
            raise ValueError('Conversation invalide.')
        window=webview.create_window('CyAI Orchestrator', self.url+'/?conversation='+conversation_id,
            width=1280,height=900,min_size=(1000,680),text_select=True,js_api=self)
        def set_icon():
            from System import Action
            from System.Drawing import Icon
            window.native.Invoke(Action(lambda:setattr(window.native,'Icon',Icon(str(Path(__file__).parent/'web'/'cyai-logo.ico')))))
        window.events.shown += set_icon
        return {'opened':True}


def application_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def service_available(url, secrets):
    token = secrets.get("local_token")
    if not token:
        return False
    try:
        request = Request(url + "/api/state", headers={"Authorization": "Bearer " + token})
        with urlopen(request, timeout=2) as response:
            state = json.load(response)
            return isinstance(state, dict) and "projects" in state
    except (URLError, OSError, ValueError):
        return False


class DesktopService:
    def __init__(self, config_path):
        self.server = self.engine = self.store = self.lock = self.thread = None
        self.config_path = Path(config_path).resolve()
        self.config = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        from .storage import apply_pending, default_data_dir
        try:
            apply_pending(self.config, self.config_path)
        except Exception as exc:
            self.config.pop('pending_data_dir', None)
            self.config['storage_error'] = str(exc)
            self.config_path.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding='utf-8')
        self.data_dir = (self.config_path.parent / self.config.get("data_dir", str(default_data_dir()))).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if (self.data_dir / "deps").exists():
            import site
            site.addsitedir(str(self.data_dir / "deps"))
        self.secrets = SecretStore(self.data_dir)
        self.url = "http://127.0.0.1:" + str(int(self.config.get("port", 8766)))

    def start(self):
        if service_available(self.url, self.secrets):
            return self.url
        try:
            self.lock = InstanceLock(self.data_dir / "service.lock")
            self.store = Store(self.data_dir / "cyai.sqlite3")
            self.engine = Engine(self.store, registry(self.config.get("connectors", {}), self.secrets),
                                 PathPolicy(self.config["allowed_roots"], [self.data_dir]),
                                 self.secrets, self.config.get("context_chars", 48000))
            service = Service(self.store, self.engine, self.config, self.config_path)
            from .agent_evaluation import ensure_installed
            ensure_installed(service)
            self.server, token = make_server(service, int(self.config.get("port", 8766)))
            self.secrets.set("local_token", token)
            self.url = f"http://127.0.0.1:{self.server.server_port}"
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            return self.url
        except Exception:
            self.close()
            raise

    def close(self):
        if self.server:
            if self.thread and self.thread.is_alive():
                self.server.shutdown()
                self.thread.join(timeout=5)
            self.server.server_close()
            self.server = None
        if self.engine:
            self.engine.shutdown()
        if self.store and (not self.engine or not self.engine.worker.is_alive()):
            self.store.close()
            self.store = None
        if self.lock:
            self.lock.close()
            self.lock = None


def main():
    parser = argparse.ArgumentParser(description="CyAI Orchestrator · application Windows")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--verify-ui", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    runtime = None
    try:
        from .launch_config import resolve_config
        args.config = resolve_config(application_root(), args.config)
        if not args.config.exists():
            args.config.parent.mkdir(parents=True, exist_ok=True)
            from .storage import default_data_dir
            args.config.write_text(json.dumps({"port": 8766, "data_dir": str(default_data_dir()),
                "allowed_roots": [str(args.config.parent.resolve())], "context_chars": 48000,
                "connectors": {}}, indent=2), encoding="utf-8")
        if os.name == "nt":
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CyAI.Orchestrator.Desktop")
        import webview
        runtime = DesktopService(args.config)
        url = runtime.start()
        window = webview.create_window("CyAI Orchestrator", url, width=1440, height=960,
                              min_size=(1000, 680), background_color="#0b0f16",
                              confirm_close=False, text_select=True, js_api=DesktopWindows(url))
        from .tray import WindowsTray
        tray = WindowsTray(window, runtime)
        if args.verify_ui:
            def verify():
                import time
                time.sleep(3)  # Allow the initial asynchronous state request to finish.
                result = window.evaluate_js("JSON.stringify({title:document.title, ready:document.readyState, app:!!document.getElementById('workspace'), projects:document.querySelectorAll('[data-project]').length})")
                from System import Action
                report = json.loads(result)
                def verify_tray():
                    report['tray_visible'] = bool(tray.icon and tray.icon.Visible)
                    if not report['tray_visible']:
                        return
                    window.native.Close()
                    report['close_hides_window'] = not window.native.Visible
                    tray.open()
                    report['tray_reopens_window'] = bool(window.native.Visible)
                window.native.Invoke(Action(verify_tray))
                window.evaluate_js("state.settingsTab='connectors';showView('settings')")
                time.sleep(2)
                report['connectors_settings'] = window.evaluate_js("!!document.querySelector('[data-enable-connector]')")
                window.evaluate_js("state.settingsTab='models';showView('settings')")
                time.sleep(2)
                report['settings_scroll'] = window.evaluate_js("JSON.stringify({nav:getComputedStyle(document.querySelector('.settings-layout>nav')).overflowY,content:getComputedStyle(document.querySelector('.settings-content')).overflowY,page:getComputedStyle(document.getElementById('page')).overflowY})")
                window.evaluate_js("state.settingsTab='local';showView('settings')")
                time.sleep(2)
                report['local_settings'] = window.evaluate_js("!!document.getElementById('local-settings')")
                window.evaluate_js("state.settingsTab='downloads';showView('settings')")
                time.sleep(2)
                report['operations_tab'] = window.evaluate_js("!!document.getElementById('download-summary') && !!document.getElementById('local-jobs')")
                window.evaluate_js("state.settingsTab='voice';showView('settings')")
                time.sleep(4)
                # The voice: its settings, its catalogue, the Windows voices, and a microphone that stays closed.
                report['voice'] = window.evaluate_js("JSON.stringify({form:!!document.getElementById('voice-form'),models:document.querySelectorAll('.voice-item').length,voices:document.querySelectorAll('#voice-form [name=voice] option').length-1,buttons:!!document.getElementById('voice-mic')&&!!document.getElementById('voice-direct')&&!!document.getElementById('voice-read'),microphone_closed:!document.getElementById('voice-mic').classList.contains('listening')})")
                report['chat_media'] = window.evaluate_js("typeof uploadMedia==='function' && typeof chooseAttachments==='function' && richText('**image**').includes('<strong>') && mediaCard({id:'abc',name:'video.mp4',content:JSON.stringify({mime:'video/mp4',bytes:42})}).includes('<video')")
                report['free_chats'] = window.evaluate_js("!!document.querySelector('[data-shell-action=\"new-dm\"]') && typeof newFreeConversation==='function'")
                report['compact_chrome'] = window.evaluate_js("JSON.stringify({footnote:!!document.querySelector('.composer-footnote'),resources:!!document.getElementById('resource-usage'),details:/détails/i.test(document.getElementById('toggle-inspector').getAttribute('aria-label')||'')})")
                report['project_setup'] = window.evaluate_js("typeof resizeLogo==='function' && typeof appearanceFieldsHTML==='function' && typeof assistantWelcomeHTML==='function' && !!document.querySelector('#project-channels .assistant-channel')")
                report['team_lead'] = window.evaluate_js("typeof teamScorecardHTML==='function' && typeof cursorFieldsHTML==='function' && typeof renderCapabilities==='function' && typeof capabilityLine==='function'")
                report['tabs'] = window.evaluate_js("!document.getElementById('conversation-tabs') && !!document.querySelector('#server-rail [data-new-window]')")
                window.evaluate_js("ggufDownloadDialog()")
                time.sleep(2)
                report['catalog_choices'] = window.evaluate_js("document.querySelectorAll('#gguf-catalog option').length-1")
                window.evaluate_js("document.getElementById('dialog').close()")
                window.evaluate_js("showView('agents')")
                time.sleep(2)
                report['agent_library'] = window.evaluate_js("JSON.stringify({page:!!document.querySelector('[data-profile-new]'),cards:document.querySelectorAll('[data-profile-edit]').length,methods:document.querySelectorAll('[data-profile-methods]').length})")
                report['project_team_tab'] = window.evaluate_js("typeof teamTabHTML==='function' && typeof openAddMemberDialog==='function'")
                window.evaluate_js("state.projectTab='team';showView('project')")
                time.sleep(2)
                report['team_tab'] = window.evaluate_js("JSON.stringify({tab:[...document.querySelectorAll('[data-project-tab]')].map(b=>b.dataset.projectTab).includes('team'),panel:!!document.querySelector('.team-panel')||!!document.querySelector('[data-team-create]')})")
                window.evaluate_js("state.projectTab='board';showView('project')")
                time.sleep(2)
                report['board_tab'] = window.evaluate_js("JSON.stringify({columns:document.querySelectorAll('.board-column').length,create:!!document.querySelector('[data-task-new]')||!!document.querySelector('[data-project-tab=\"team\"]')})")
                window.evaluate_js("openMethodGraph(null)")
                time.sleep(2)
                report['method_editor'] = window.evaluate_js("JSON.stringify({nodes:document.querySelectorAll('.me-node').length,ports:document.querySelectorAll('[data-port-out]').length,inspector:!!document.getElementById('me-inspector'),io:document.querySelectorAll('.me-io').length,pins:document.querySelectorAll('[data-pin-out]').length,menu:!!document.getElementById('me-menu')&&typeof openMenu==='function',writer:typeof openWriter==='function'&&typeof prepareMethodInputs==='function',lab:typeof openLab==='function'&&typeof labStepHTML==='function'&&!!document.querySelector('[data-lab-open]'),proposals:typeof reviewDialog==='function'&&typeof proposalItemHTML==='function'})")
                window.evaluate_js("methodEditor.dirty=false;showView('project')")
                time.sleep(1)
                report['whiteboard'] = window.evaluate_js("typeof renderSpace==='function' && typeof renderGraphSpace==='function' && typeof taskBannerHTML==='function' && typeof renderPluginSpace==='function' && !!document.querySelector('[data-shell-action=\"new-space\"]')")
                report['discord_shell'] = window.evaluate_js("JSON.stringify({rail:document.querySelectorAll('#server-rail [data-project]').length,channels:document.querySelectorAll('#project-channels [data-channel]').length,members:!!document.getElementById('member-list')})")
                report['stable_live_dom'] = window.evaluate_js("(()=>{const old=state.mission,oldApprovals=state.data.approvals,host=document.getElementById('messages'),saved=host.innerHTML;host.innerHTML='<div id=\"live-output\"></div>';state.mission={id:'ui-check',status:'running',steps:[{id:'step',status:'running',connector:'codex'}],events:[]};state.data.approvals=[];renderLive();const before=document.querySelector('#live-answer article');renderLive();const stable=before===document.querySelector('#live-answer article');state.mission=old;state.data.approvals=oldApprovals;host.innerHTML=saved;host._rendered=null;return stable})()")

                DesktopWindows(url).open_window()
                time.sleep(3)
                report['multiple_windows'] = len(webview.windows) > 1
                for child in list(webview.windows):
                    if child is not window: child.destroy()
                window.evaluate_js("state.settingsTab='local';showView('settings')")
                args.verify_ui.write_text(json.dumps(report), encoding="utf-8")
            window.events.loaded += verify
        webview.start(tray.install, gui="edgechromium", private_mode=False, storage_path=str(runtime.data_dir / "window-state"), localization={
            "global.quitConfirmation": "Fermer CyAI Orchestrator ? Les missions du service démarré par cette fenêtre seront interrompues.",
            "global.ok": "Oui", "global.cancel": "Annuler"})
    except Exception as exc:
        message = f"Impossible d’ouvrir CyAI Orchestrator.\n\n{exc}\n\nConfiguration : {args.config}"
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(None, message, "CyAI Orchestrator", 0x10)
        else:
            raise
    finally:
        if runtime:
            runtime.close()


if __name__ == "__main__":
    main()
