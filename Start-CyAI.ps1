param([int]$Port = 8766)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Test-Path -LiteralPath '.\.venv\Scripts\python.exe') {
    & .\.venv\Scripts\python.exe -m cyai serve --port $Port
} else {
    python -m cyai serve --port $Port
}
