"""Stage the existing CyDoc export for GitHub Pages, without application runtime data."""
import argparse
from pathlib import Path
import shutil
from build_documentation import ROOT, verify_export

READER_FILES = {'index.html','data.js','cyai-reader.js','viewer.css','media-image.js','manifest.json','CyDoc-LICENSE.txt','CyAI-LICENSE.txt'}

def stage_pages(root=ROOT, output=None):
    root = Path(root).resolve()
    source = root/'cyai/help'
    info = verify_export(root)
    names = set(info['outputs'])
    if not READER_FILES <= names:
        raise ValueError('The complete CyDoc reader is required for Pages.')
    output_path = Path(output or root/'dist-docs-pages')
    if output_path.is_symlink():
        raise ValueError('The Pages directory cannot be a symbolic link.')
    target = output_path.resolve()
    if not target.is_relative_to(root) or target == root or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError('Pages output must be a separate generated directory inside the repository.')
    if target.exists():
        existing = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
        if existing - names - {'.nojekyll'} or any(p.is_symlink() for p in target.rglob('*')):
            raise ValueError('Unexpected files in the Pages stage; refusing to remove or publish them.')
        # The resolved, repository-contained generated directory has been checked above.
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for name in sorted(names):
        file = source/name
        if file.is_symlink() or not file.resolve().is_relative_to(source.resolve()):
            raise ValueError('A documentation asset escapes the export.')
        destination = target/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(file,destination)
    (target/'.nojekyll').write_text('',encoding='utf-8')
    actual = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
    if actual != names | {'.nojekyll'}:
        raise ValueError('The Pages stage differs from the generated CyDoc export.')
    return target

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='Generated directory inside the repository (default: dist-docs-pages)')
    args = parser.parse_args()
    target = stage_pages(output=args.output)
    print('Complete CyDoc reader staged for Pages:',target)

if __name__ == '__main__':
    main()
