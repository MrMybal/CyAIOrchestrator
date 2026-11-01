$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e '.[claude]'
Write-Host 'Installation terminée. Lancez : .\.venv\Scripts\python.exe -m cyai'
