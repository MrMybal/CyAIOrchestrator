"""UI translations shared by the web interface and Windows chrome.

French source messages are stable catalogue keys, never user content. Unknown
messages are preserved verbatim; English is the default independently of the OS.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

DEFAULT_LANGUAGE = 'en'
LANGUAGES = {'en': 'English', 'fr': 'Français'}


def language(config=None):
    value = (config or {}).get('settings', {}).get('language', DEFAULT_LANGUAGE)
    return value if isinstance(value, str) and value in LANGUAGES else DEFAULT_LANGUAGE


@lru_cache(maxsize=1)
def messages():
    return {**system_messages(), **json.loads((Path(__file__).parent / 'locales' / 'en.json').read_text(encoding='utf-8'))}


@lru_cache(maxsize=1)
def system_messages():
    return json.loads((Path(__file__).parent / 'locales' / 'system.en.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def system_patterns():
    result = []
    for source, target in system_messages().items():
        if not re.search(r'\{\d+\}', source):
            continue
        parts = re.split(r'(\{\d+\})', source)
        expression = ''.join('(?P<p' + part[1:-1] + '>.*?)' if re.fullmatch(r'\{\d+\}', part)
                             else re.escape(part) for part in parts)
        result.append((re.compile('^' + expression + '$', re.S), target))
    return result


def translate(text, locale=DEFAULT_LANGUAGE):
    if locale == 'fr' or not isinstance(text, str):
        return text
    key = text.strip()
    value = messages().get(key)
    if value is None:
        for pattern, target in system_patterns():
            match = pattern.fullmatch(key)
            if match:
                value = re.sub(r'\{(\d+)\}', lambda m: match.group('p' + m[1]), target)
                break
        if value is None:
            return text
    return text[:len(text)-len(text.lstrip())] + value + text[len(text.rstrip()):]


def translate_html(source, locale=DEFAULT_LANGUAGE):
    """Translate static application markup, before it contains any user data."""
    if locale == 'fr':
        return source
    def token(match):
        value = match.group(0)
        if value.startswith('<'):
            return re.sub(r'(\b(?:title|placeholder|aria-label|alt)\s*=\s*)([\"\'])(.*?)\2',
                lambda m: m[1] + m[2] + translate(m[3], locale) + m[2], value, flags=re.S)
        return translate(value, locale)
    return re.sub(r'<[^>]*>|[^<]+', token, source, flags=re.S)


def bootstrap(config):
    return ('window.CYAI_LANGUAGE=' + json.dumps(language(config)) + ';\n'
            'window.CYAI_MESSAGES=' + json.dumps(messages(), ensure_ascii=False) + ';\n'
            'window.CYAI_SYSTEM_MESSAGES=' + json.dumps(system_messages(), ensure_ascii=False) + ';\n')
