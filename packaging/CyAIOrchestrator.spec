# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_all

root = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(root / 'scripts'))
from package_policy import payload_problem

# The Python SDK is small. Its native CLI is a user-installed optional component.
sdk_data, sdk_binaries, sdk_imports = collect_all('claude_agent_sdk')
data = collect_data_files('cyai') + sdk_data
data = [(source, target) for source, target in data if not payload_problem(target + '/' + Path(source).name)]
binaries = [(source, target) for source, target in sdk_binaries if not payload_problem(target + '/' + Path(source).name)]

a = Analysis([str(root / 'scripts' / 'desktop_entry.py')], pathex=[str(root)],
    binaries=binaries, datas=data, hiddenimports=sdk_imports, hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['torch', 'tensorflow', 'transformers', 'onnxruntime'], noarchive=False, optimize=0)
# Apply the same rule after hooks have contributed additional files.
a.datas = [row for row in a.datas if not payload_problem(row[0])]
a.binaries = [row for row in a.binaries if not payload_problem(row[0])]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CyAIOrchestrator', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=True, console=False,
    disable_windowed_traceback=False, argv_emulation=False, target_arch=None,
    codesign_identity=None, entitlements_file=None, icon=str(root / 'cyai/web/cyai-logo.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[], name='CyAIOrchestrator')
