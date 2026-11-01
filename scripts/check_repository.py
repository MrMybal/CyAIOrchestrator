"""Check the exact Git candidate set and all local refs before a publication."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

from package_policy import payload_problem

GITLEAKS_VERSION = '8.30.1'


def git(root, *arguments):
    return subprocess.run(['git', '-c', 'safe.directory=' + root.as_posix(), *arguments],
                          cwd=root, capture_output=True, check=True).stdout


def candidate_files(root):
    return sorted(set(name.decode('utf-8') for name in
        git(root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').split(b'\0') if name))


def bootstrap_gitleaks(destination):
    system = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'darwin'}.get(platform.system())
    architecture = 'arm64' if platform.machine().lower() in {'arm64', 'aarch64'} else 'x64'
    if system is None: raise ValueError('Plateforme Gitleaks non prise en charge.')
    name = f'gitleaks_{GITLEAKS_VERSION}_{system}_{architecture}' + ('.zip' if system == 'windows' else '.tar.gz')
    base = f'https://github.com/gitleaks/gitleaks/releases/download/v{GITLEAKS_VERSION}/'
    with urllib.request.urlopen(base + 'gitleaks_' + GITLEAKS_VERSION + '_checksums.txt', timeout=45) as response:
        lines = response.read().decode().splitlines()
    expected = next(line.split()[0] for line in lines if line.split()[-1] == name)
    with urllib.request.urlopen(base + name, timeout=90) as response: data = response.read()
    if hashlib.sha256(data).hexdigest() != expected: raise ValueError('Empreinte Gitleaks invalide.')
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / name
    archive.write_bytes(data)
    filename = 'gitleaks.exe' if system == 'windows' else 'gitleaks'
    if system == 'windows':
        with zipfile.ZipFile(archive) as package: binary = package.read(filename)
    else:
        with tarfile.open(archive) as package:
            member = next(m for m in package.getmembers() if m.name == filename)
            with package.extractfile(member) as stream: binary = stream.read()
    target = destination / filename
    target.write_bytes(binary)
    if system != 'windows': target.chmod(0o755)
    return target


def scan(executable, root, target, report, history=False):
    command = [str(executable), 'git' if history else 'dir', str(target), '--config', str(root / '.gitleaks.toml'),
               '--redact=100', '--no-banner', '--no-color', '--max-archive-depth=3', '--report-format=json', '--report-path=' + str(report)]
    if history: command += ['--log-opts=--all --full-history']
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    report.with_suffix('.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    findings = json.loads(report.read_text(encoding='utf-8')) if report.is_file() else []
    if result.returncode not in (0, 1) or result.returncode and not findings:
        raise ValueError('Le scan Gitleaks a échoué ; consultez le rapport local masqué.')
    return len(findings)


def inspect_candidates(root, names):
    problems = []
    for name in names:
        file = root / name
        if not file.is_file(): continue
        problem = payload_problem(name)
        # Distribution build scripts belong to source; build outputs do not.
        if problem: problems.append((name, problem))
        if name.split('/')[0] in {'releases', 'dist', 'dist-next', 'build', 'build-next', 'build-release'}:
            problems.append((name, 'Sortie de compilation à exclure de Git'))
        if file.stat().st_size >= 50 * 1024 * 1024:
            problems.append((name, 'Fichier de 50 Mio ou plus dans les sources'))
        if file.is_symlink(): problems.append((name, 'Lien symbolique à examiner avant publication'))
    tracked_ignored = git(root, 'ls-files', '--cached', '--ignored', '--exclude-standard', '-z')
    for name in tracked_ignored.split(b'\0'):
        if name: problems.append((name.decode('utf-8'), 'Fichier local exclu mais déjà suivi par Git'))
    return problems


def run(root, reports, executable, history=True):
    reports.mkdir(parents=True, exist_ok=True)
    names = candidate_files(root)
    problems = inspect_candidates(root, names)
    result = {'files': len(names), 'bytes': sum((root/n).stat().st_size for n in names if (root/n).is_file()),
              'problems': problems, 'source_findings': None, 'history_commits': 0, 'history_findings': None}
    if problems:
        (reports / 'summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        raise ValueError('Fichiers à corriger dans la sélection Git ; consultez le rapport local.')
    with tempfile.TemporaryDirectory(prefix='cyai-source-scan-') as temporary:
        stage = Path(temporary)
        for name in names:
            source = root / name
            if source.is_file():
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        result['source_findings'] = scan(executable, root, stage, reports / 'sources.json')
    count = int(git(root, 'rev-list', '--all', '--count').decode().strip() or 0)
    result['history_commits'] = count
    if history and count: result['history_findings'] = scan(executable, root, root, reports / 'history.json', history=True)
    (reports / 'summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    if result['source_findings'] or result['history_findings']:
        raise ValueError('Alertes Gitleaks à examiner dans le rapport local masqué.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--reports-dir', type=Path)
    parser.add_argument('--gitleaks', type=Path)
    parser.add_argument('--download-gitleaks', action='store_true')
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    reports = (arguments.reports_dir or root / 'test-results' / 'repository-check').resolve()
    executable = arguments.gitleaks or shutil.which('gitleaks')
    if arguments.download_gitleaks: executable = bootstrap_gitleaks(reports / 'tools')
    if not executable: parser.error('Installez Gitleaks ou utilisez --download-gitleaks.')
    try:
        result = run(root, reports, Path(executable).resolve())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print('Contrôle terminé :', result['files'], 'fichiers ;', result['history_commits'], 'commits disponibles.')
    return 0


if __name__ == '__main__': sys.exit(main())
