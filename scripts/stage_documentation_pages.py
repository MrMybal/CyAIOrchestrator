"""Stage the generated showcase and complete CyDoc reader for GitHub Pages."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
from build_documentation import ROOT, verify_export

READER_FILES = {'Documentation.html','DocAI.md','DocData/data.js','DocData/viewer.js','DocData/cyai-host.js','DocData/viewer.css','DocData/media-image.js','DocData/manifest.json','DocData/CyDoc-LICENSE.txt','DocData/CyAI-LICENSE.txt'}
OWNER = '.cyai-pages.json'


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def listed_files(directory):
    entries = list(directory.rglob('*'))
    if any(p.is_symlink() or not (p.is_file() or p.is_dir()) for p in entries):
        raise ValueError('Unsupported entry in generated Pages directory.')
    return {p.relative_to(directory).as_posix() for p in entries if p.is_file()}


def verified_files(directory, metadata, kind):
    try:
        info = json.loads((directory/metadata).read_text('utf-8'))
        files = info['files']
        if info['kind'] != kind or not isinstance(files, dict) or not files:
            raise ValueError('Invalid generated artifact manifest.')
        if listed_files(directory) != set(files) | {metadata}:
            raise ValueError('Unexpected files in generated artifact; preserving the directory.')
        for name, expected in files.items():
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name or not (directory/name).resolve().is_relative_to(directory.resolve()):
                raise ValueError('Generated resource escapes its artifact.')
            if digest(directory/name) != expected:
                raise ValueError('Modified generated resource; preserving '+name)
        return set(files)
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid generated artifact manifest.') from error


def stage_pages(root=ROOT, output=None):
    root = Path(root).resolve()
    source = root/'Documentation'
    info = verify_export(root)
    reader_names = set(info['outputs'])
    if not READER_FILES <= reader_names:
        raise ValueError('The complete CyDoc reader is required for Pages.')
    showcase = root/'dist/website'
    output_path = Path(output or root/'dist-docs-pages')
    if output_path.is_symlink():
        raise ValueError('The Pages directory cannot be a symbolic link.')
    target = output_path.resolve()
    allowed = target == root/'dist-docs-pages' or any(target != base and target.is_relative_to(base) for base in [root/'dist',root/'test-results'])
    if not allowed or target.is_relative_to(showcase) or showcase.is_relative_to(target):
        raise ValueError('Pages output must be a separate generated directory inside the repository.')

    def check_target():
        if not target.exists():
            return
        if not target.is_dir():
            raise ValueError('Pages output must be a generated directory.')
        if (target/OWNER).exists():
            verified_files(target, OWNER, 'cyai-pages')
            return
        # Recognize the former reader-only stage once, with exact current bytes.
        legacy = reader_names | {'index.html','DocData/pages-entry.js','.nojekyll'}
        if listed_files(target) != legacy:
            raise ValueError('Unexpected files in the Pages stage; refusing to remove or publish them.')
        for name in legacy:
            expected = b'' if name == '.nojekyll' else ((source/name).read_bytes() if name in reader_names else (root/'.CyDocBuild/host'/Path(name).name).read_bytes())
            if (target/name).read_bytes() != expected:
                raise ValueError('Modified legacy Pages stage; preserving '+name)

    check_target()
    node = shutil.which('node')
    if not node:
        raise ValueError('Node.js 22 or later is required to build the showcase.')
    subprocess.run([node, str(root/'website/build.mjs')], cwd=root, check=True, capture_output=True, text=True)
    showcase_names = verified_files(showcase, '.cyai-showcase.json', 'cyai-showcase')
    # Retain both historical reader URLs and the showcase's portable manual copy.
    for name in reader_names | {'DocData/build-info.json'}:
        if (showcase/'manual'/name).read_bytes() != (source/name).read_bytes():
            raise ValueError('The showcase contains a different manual: '+name)
    copies = {name: showcase/name for name in showcase_names}
    if set(copies) & reader_names:
        raise ValueError('Showcase and legacy reader resources overlap.')
    copies.update({name: source/name for name in reader_names})
    copies['DocData/pages-entry.js'] = root/'.CyDocBuild/host/pages-entry.js'
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.cyai-pages-', dir=target.parent))
    try:
        for name, file in sorted(copies.items()):
            if file.is_symlink() or not file.resolve().is_relative_to(root):
                raise ValueError('A publication resource escapes the project.')
            destination = temporary/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, destination)
        (temporary/'.nojekyll').write_text('', encoding='utf-8')
        hashes = {name: digest(temporary/name) for name in sorted(listed_files(temporary))}
        (temporary/OWNER).write_text(json.dumps({'kind':'cyai-pages','files':hashes}, indent=2)+'\n', encoding='utf-8')
        verified_files(temporary, OWNER, 'cyai-pages')
        check_target()
        if target.exists():
            # The resolved, repository-contained owned artifact was checked above.
            shutil.rmtree(target)
        temporary.rename(target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='Generated directory inside the repository (default: dist-docs-pages)')
    args = parser.parse_args()
    target = stage_pages(output=args.output)
    print('Showcase and complete CyDoc reader staged for Pages:',target)

if __name__ == '__main__':
    main()
