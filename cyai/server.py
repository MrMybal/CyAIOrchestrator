"""Loopback-only HTTP transport, same-origin browser session and bearer MCP access."""
import json
import mimetypes
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote


def make_server(service, port=8766, token=None):
    token = token or secrets.token_urlsafe(40)
    webroot = Path(__file__).parent / "web"
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Request bodies, prompts and credentials are never logged.

        def send(self, status, body, content_type="application/json; charset=utf-8", cookie=False, embedded=False):
            if status >= 400 and isinstance(body, dict) and isinstance(body.get('error'), str):
                from .i18n import language, translate
                body = {**body, 'error': translate(body['error'], language(service.config))}
            payload = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, (dict, list)) else body
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self' data:; connect-src 'self' blob:; worker-src 'self' blob:; frame-ancestors 'self'; base-uri 'self'" if embedded else "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' blob:; frame-src 'self' http://127.0.0.1:* http://localhost:* https:; img-src 'self' data: blob: https:; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.send_header("Referrer-Policy", "no-referrer")
            if cookie:
                self.send_header("Set-Cookie", f"cyai={token}; HttpOnly; SameSite=Strict; Path=/")
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def authorized(self):
            expected_host = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in expected_host:
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + h for h in expected_host}:
                return False
            bearer = self.headers.get("Authorization", "")
            if bearer and secrets.compare_digest(bearer, "Bearer " + token):
                return True
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            return "cyai" in cookie and secrets.compare_digest(cookie["cyai"].value, token) and self.headers.get("X-CyAI") == "1"

        def do_GET(self):
            try:
                path = urlparse(self.path).path
                if path.startswith('/media/') or path.startswith('/method-asset/'):
                    cookie=SimpleCookie(self.headers.get('Cookie',''))
                    if self.headers.get('Host') not in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'} or 'cyai' not in cookie or not secrets.compare_digest(cookie['cyai'].value,token) or self.headers.get('Sec-Fetch-Site')=='cross-site':return self.send(403,{'error':'Accès refusé.'})
                    from .media import locate,IMAGE_TYPES
                    if path.startswith('/method-asset/'):
                        from .methods import locate_asset
                        row,meta,file=locate_asset(service,path.split('/')[-1])
                    else:row,meta,file=locate(service.store,path.split('/')[-1])
                    size=file.stat().st_size
                    start,end=0,size-1;partial=False
                    import re
                    value=self.headers.get('Range','')
                    if value:
                        m=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
                        if not m:return self.send(416,{'error':'Plage invalide.'})
                        if not m[1] and not m[2]:return self.send(416,{'error':'Plage invalide.'})
                        if m[1]:start=int(m[1]);end=min(int(m[2]) if m[2] else end,end)
                        else:start=max(0,size-int(m[2]))
                        partial=True
                        if start>end:return self.send(416,{'error':'Plage invalide.'})
                    self.send_response(206 if partial else 200)
                    inline=meta['mime'] in IMAGE_TYPES or meta['mime'] in {'video/mp4','video/webm','audio/mpeg','audio/wav','audio/ogg'}
                    self.send_header('Content-Type',meta['mime'] if inline else 'application/octet-stream')
                    from urllib.parse import quote
                    self.send_header('Content-Disposition',('inline' if inline and 'download' not in self.path else 'attachment')+"; filename*=UTF-8''"+quote(row['name']))
                    self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
                    if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
                    self.end_headers()
                    with file.open('rb') as f:
                        f.seek(start);left=end-start+1
                        while left:
                            chunk=f.read(min(left,1024*1024))
                            if not chunk:break
                            try:self.wfile.write(chunk)
                            except (BrokenPipeError,ConnectionResetError):break
                            left-=len(chunk)
                    return
                if not path.startswith("/api/"):
                    if self.headers.get("Host") not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
                        return self.send(403, {"error": "Hôte refusé."})
                    if self.headers.get("Sec-Fetch-Site") == "cross-site":
                        return self.send(403, {"error": "Origine refusée."})
                    if path == '/cyannota-logo.png':
                        return self.send(200,(webroot/'cyannota/cyannota-logo.png').read_bytes(),'image/png')
                    if path in {'/cyai-logo.png', '/cyai-logo.ico', '/favicon.ico'}:
                        name = 'cyai-logo.png' if path.endswith('.png') else 'cyai-logo.ico'
                        return self.send(200, (webroot/name).read_bytes(), 'image/png' if name.endswith('.png') else 'image/x-icon')
                    if path.startswith('/three/'):
                        root=(webroot/'three').resolve(); file=(root/unquote(path[len('/three/'):])).resolve()
                        if not file.is_relative_to(root) or not file.is_file() or file.suffix not in {'.js','.txt'}:return self.send(404,{'error':'Module absent.'})
                        return self.send(200,file.read_bytes(),'text/javascript' if file.suffix=='.js' else 'text/plain')
                    if path.startswith('/cymd/'):
                        root = (webroot/'cymd').resolve()
                        file = (root/(unquote(path[len('/cymd/'):]) or 'index.html')).resolve()
                        if not file.is_relative_to(root) or not file.is_file() or file.suffix not in {'.js','.css','.html','.png','.txt','.zip','.json'}:
                            return self.send(404, {'error':'Fichier CyMD absent.'})
                        return self.send(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream',embedded=True)
                    if path.startswith('/cyannota/'):
                        if path.startswith('/cyannota/ffmpeg/') and (path.endswith('.wasm') or any(path.endswith('.part'+str(i)) for i in range(4))):
                            try: content = service.components.ffmpeg_asset(path.rsplit('/',1)[-1])
                            except ValueError as error: return self.send(424, {'error':str(error)})
                            return self.send(200,content,'application/wasm' if path.endswith('.wasm') else 'application/octet-stream',embedded=True)
                        relative = path[len('/cyannota/'):] or 'index.html'
                        root = (webroot/'cyannota').resolve()
                        file = (root/relative).resolve()
                        if not file.is_relative_to(root) or not file.is_file() or file.suffix not in {'.js','.css','.html','.png','.txt','.zip','.wasm','.json','.part0','.part1','.part2','.part3'}:
                            return self.send(404, {'error':'Fichier CyAnnota absent.'})
                        return self.send(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream',embedded=True)
                    name = "index.html" if path == "/" else path.lstrip("/")
                    if name not in {"index.html", "app.js", "help.js", "project.js", "plugins.js", "workspace.js", "annotation.js", "intelligence.js", "analytics.js", "styles.css", "i18n.js", "tabs.js", "teams.js", "board.js", "methods.js", "channels.js", "method-editor.js", "method-writer.js", "method-lab.js", "team-lead.js", "spaces.js", "voice.js", "local-models.js", "media.js", "mesh-viewer.js", "cymd-editor.js"}:
                        return self.send(404, {"error": "Introuvable."})
                    file = webroot / name
                    mime = {".js": "text/javascript", ".html": "text/html", ".css": "text/css"}[file.suffix]
                    content = file.read_bytes()
                    if name in {'index.html', 'i18n.js'}:
                        from .i18n import bootstrap, language, translate_html
                        if name == 'i18n.js':
                            content = bootstrap(service.config).encode('utf-8') + content
                        else:
                            source = translate_html(content.decode('utf-8'), language(service.config))
                            source = source.replace('<html lang="fr">', '<html lang="' + language(service.config) + '">')
                            content = source.encode('utf-8')
                    return self.send(200, content, mime + "; charset=utf-8", cookie=name == "index.html")
                if not self.authorized():
                    return self.send(403, {"error": "Accès local non autorisé."})
                query = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                if path == "/api/logs":
                    result = service.logs(query)
                elif path == "/api/state":
                    result = service.state()
                elif path == "/api/search":
                    result = service.search(query)
                elif path.startswith("/api/memory/"):
                    result = service.memory(path.split("/")[-1])
                elif path.startswith('/api/project/'):
                    result = service.project(path.split('/')[-1])
                elif path.startswith("/api/conversation/"):
                    result = service.conversation(path.split("/")[-1])
                elif path.startswith("/api/mission/"):
                    result = service.mission(path.split("/")[-1], query.get("after", 0))
                else:
                    return self.send(404, {"error": "Introuvable."})
                self.send(200, result)
            except (ValueError, KeyError, OSError) as e:
                self.send(400, {"error": service.engine.secrets.redact(str(e))})

        def do_POST(self):
            plugin_request = self.path == '/api/plugin-mcp' and self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            if not plugin_request and not self.authorized():
                return self.send(403, {"error": "Accès local non autorisé."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if self.path.startswith('/api/upload?'):
                    from .media import upload
                    q=parse_qs(urlparse(self.path).query)
                    if 'method_id' in q:
                        from .methods import upload_asset
                        return self.send(200,upload_asset(service,q['method_id'][0],q['name'][0],self.rfile,length))
                    return self.send(200,upload(service,q['conversation_id'][0],q['name'][0],self.rfile,length))
                if not 0 < length <= 25000000:
                    return self.send(413, {"error": "Requête trop volumineuse ou vide (25 Mo maximum)."})
                if self.headers.get_content_type() != "application/json":
                    return self.send(415, {"error": "JSON requis."})
                data = json.loads(self.rfile.read(length))
                if plugin_request:
                    result=service.plugins.gateway(self.headers.get('Authorization','').removeprefix('Bearer '),data)
                elif self.path == "/api/action":
                    result = service.action(data["action"], data.get("data", {}))
                    if data['action'] not in {'voice_state', 'voice_catalog', 'local_state', 'project_channels', 'resource_history'}:
                        service.store.log("info",data["action"],"Action terminée.")
                elif self.path == "/api/mcp":
                    from .mcp import call_tool
                    from .app_mcp import resources, resource_read
                    if data.get('method')=='resources/list':result={'resources':resources(service,data.get('project_ids',[]))}
                    elif data.get('method')=='resources/read':result=resource_read(service,data.get('project_ids',[]),data['params']['uri'])
                    else:result = call_tool(service, data["name"], data.get("arguments", {}), data.get("project_ids", []),bool(data.get('allow_write',False)),bool(data.get('allow_global',False)))
                else:
                    return self.send(404, {"error": "Introuvable."})
                self.send(200, result)
            except Exception as e:
                service.store.log("error","http.post",service.engine.secrets.redact(str(e)))
                self.send(400, {"error": service.engine.secrets.redact(str(e))})
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server, token
