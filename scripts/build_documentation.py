"""Generate or verify the self-contained CyDoc export used by every distribution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {'.md','.json','.mjs','.cjs','.js','.py','.toml','.html','.css','.txt'}

def digest(path):
    data = path.read_bytes()
    if path.suffix in TEXT_SUFFIXES:
        data = data.decode('utf-8').replace('\r\n','\n').encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def verify_export(root=ROOT, export=None, check_inputs=True):
    root = Path(root).resolve()
    export = Path(export or root/'cyai/help').resolve()
    info = json.loads((export/'build-info.json').read_text('utf-8'))
    config = json.loads((root/'documentation/cydoc.config.json').read_text('utf-8'))
    if config['version'] != tomllib.loads((root/'pyproject.toml').read_text('utf-8'))['project']['version'] or info['version'] != config['version'] or info['modules'] != ['image']:
        raise ValueError('Documentation version or modules differ; regenerate the export.')
    if not check_inputs and export != (root/'cyai/help').resolve():
        current = json.loads((root/'cyai/help/build-info.json').read_text('utf-8'))
        if info['outputs'] != current['outputs']:
            raise ValueError('The staged documentation differs from the current application export.')
    for group, base in [('outputs',export)] + ([('inputs',root)] if check_inputs else []):
        if not info.get(group):
            raise ValueError('Documentation build manifest is incomplete.')
        for name, expected in info[group].items():
            file = (base/name).resolve()
            if not file.is_relative_to(base) or not file.is_file() or digest(file) != expected:
                raise ValueError('Stale or missing documentation '+group+': '+name+'. Run python scripts/build_documentation.py --install')
    actual = {p.relative_to(export).as_posix() for p in export.rglob('*') if p.is_file()}
    if actual != set(info['outputs']) | {'build-info.json'}:
        raise ValueError('Unexpected or missing files in the documentation export.')
    if check_inputs:
        candidates = {p.relative_to(root).as_posix() for p in (root/'documentation').rglob('*') if p.is_file() and not {'node_modules','.generated'} & set(p.relative_to(root/'documentation').parts)}
        candidates |= {p.relative_to(root).as_posix() for folder in (root/'docs',root/'cyai/evaluation_kit') for p in folder.glob('*.md')}
        # New authoring files must not be silently omitted from the freshness check.
        if not candidates <= set(info['inputs']):
            raise ValueError('New documentation sources are not exported yet.')
    return info

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install',action='store_true',help='Install pinned documentation build dependencies using npm ci')
    parser.add_argument('--check',action='store_true',help='Verify the checked-in export without requiring Node.js')
    args = parser.parse_args()
    if not args.check:
        npm = shutil.which('npm.cmd' if os.name=='nt' else 'npm')
        if not npm:
            parser.error('Node.js 22+ and npm are needed to regenerate documentation; reading needs neither.')
        env = {**os.environ,'CYAI_BUILD_PYTHON':sys.executable}
        if args.install:
            subprocess.run([npm,'ci','--prefix',str(ROOT/'documentation')],cwd=ROOT,env=env,check=True)
        subprocess.run([npm,'run','build','--prefix',str(ROOT/'documentation')],cwd=ROOT,env=env,check=True)
    info = verify_export()
    print('CyDoc export verified:', info['version'], '| image | en/fr | local file reader')

if __name__ == '__main__':
    main()
