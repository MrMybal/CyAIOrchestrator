"""Probe explicitly enabled connectors without generating model output."""
import threading
from .store import now


def probe(service, identifier):
    connector=service.engine.connectors[identifier]
    if not connector.config.get('enabled',False):
        service.health.pop(identifier,None)
        return {'status':'disabled','detail':'Connecteur désactivé.'}
    service.health[identifier]={'status':'checking','detail':'Connexion en cours…'}
    try:
        if identifier=='claude-code': result=connector.auth_status()
        else:
            result=connector.check()
            if result['status']!='unconfigured':
                models=connector.models()
                result={**result,'status':'connected' if identifier not in {'local','openrouter'} and not getattr(connector,'native_cli',False) else result['status'],
                        'detail':'Connexion vérifiée ; catalogue reçu.' if identifier not in {'local','openrouter'} and not getattr(connector,'native_cli',False) else result['detail']}
                service.catalogs[identifier]=models
        result['checked_at']=now()
    except Exception as exc:
        result={'status':'error','detail':service.engine.secrets.redact(str(exc)),'checked_at':now()}
    if connector.config.get('enabled',False):service.health[identifier]=result
    return result


def start_probes(service, identifiers=None):
    for identifier in identifiers or list(service.engine.connectors):
        if service.engine.connectors[identifier].config.get('enabled',False):
            threading.Thread(target=probe,args=(service,identifier),daemon=True).start()
