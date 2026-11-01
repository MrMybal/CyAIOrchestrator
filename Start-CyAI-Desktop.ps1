$ErrorActionPreference = 'Stop'
$app = Join-Path $PSScriptRoot 'dist-next\CyAIOrchestrator\CyAIOrchestrator.exe'
if (-not (Test-Path -LiteralPath $app)) { throw "Exécutez Build-Desktop.ps1 pour construire l'application." }
$config = Join-Path $PSScriptRoot 'config.json'
Start-Process -FilePath $app -ArgumentList @('--config', ('"' + $config + '"')) -WorkingDirectory $PSScriptRoot
