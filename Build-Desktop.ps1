$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.desktop-venv\Scripts\python.exe')) {
    python -m venv .desktop-venv
    if ($LASTEXITCODE -ne 0) { throw 'Création du venv impossible.' }
}
& .\.desktop-venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Mise à jour de pip impossible.' }
& .\.desktop-venv\Scripts\python.exe -m pip install -e '.[desktop,claude]' 'pyinstaller==6.22.3'
if ($LASTEXITCODE -ne 0) { throw 'Installation des dépendances impossible.' }
& .\.desktop-venv\Scripts\python.exe scripts/build_documentation.py --install
if ($LASTEXITCODE -ne 0) { throw 'Documentation generation failed.' }
& .\.desktop-venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath dist-next --workpath build-next packaging/CyAIOrchestrator.spec
if ($LASTEXITCODE -ne 0) { throw "Construction de l'application impossible." }
$shortcutPath = Join-Path $PSScriptRoot 'CyAI Orchestrator.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $PSScriptRoot 'dist-next\CyAIOrchestrator\CyAIOrchestrator.exe'
$shortcut.Arguments = '--config "' + (Join-Path $PSScriptRoot 'config.json') + '"'
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description = 'CyAI Orchestrator - application de bureau'
$shortcut.IconLocation = Join-Path $PSScriptRoot 'cyai\web\cyai-logo.ico'
$shortcut.Save()
Write-Host 'Application créée : dist-next\CyAIOrchestrator\CyAIOrchestrator.exe'
