[CmdletBinding()]
param(
    [string]$Root = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'CyAI\Models'),
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$models = @('qwen3.5:4b', 'qwen3.5:9b', 'qwen2.5-coder:7b', 'qwen3.5:27b')
$appDir = Join-Path $Root 'Ollama\app'
$modelDir = Join-Path $Root 'Ollama\models'
$installer = Join-Path $Root 'Ollama\installers\OllamaSetup.exe'
$exe = Join-Path $appDir 'ollama.exe'
$settings = @{
    OLLAMA_MODELS = $modelDir
    OLLAMA_HOST = '127.0.0.1:11434'
    OLLAMA_CONTEXT_LENGTH = '4096'
    OLLAMA_NUM_PARALLEL = '1'
    OLLAMA_MAX_LOADED_MODELS = '1'
    OLLAMA_KEEP_ALIVE = '30s'
    OLLAMA_FLASH_ATTENTION = '1'
    OLLAMA_KV_CACHE_TYPE = 'q8_0'
}
if ($ValidateOnly) {
    Write-Output "Application: $appDir"
    Write-Output "Models: $modelDir"
    Write-Output "Downloads: $($models -join ', ')"
    Write-Output 'Validation only: no installation, downloads or configuration changes.'
    exit 0
}

# Run under the Windows account that uses CyAI, in a normal PowerShell terminal.
if ($ExecutionContext.SessionState.LanguageMode -ne 'FullLanguage') {
    throw 'Lancez ce script dans PowerShell sous votre compte Windows (mode FullLanguage requis).'
}
$drive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($Root).TrimEnd('\').TrimEnd(':'))
if ($drive.Free -lt 40GB) { throw 'Il faut au moins 40 Go libres pour cette installation.' }
foreach ($dir in @($appDir, $modelDir, (Split-Path $installer))) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

if (-not (Test-Path -LiteralPath $exe)) {
    Write-Host 'Telechargement de l installateur officiel Ollama...'
    & curl.exe --location --fail --retry 3 --output $installer 'https://ollama.com/download/OllamaSetup.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Telechargement de Ollama impossible.' }
    $signature = Get-AuthenticodeSignature -LiteralPath $installer
    if ($signature.Status -ne 'Valid') { throw 'Signature de l installateur non valide.' }
}

# Keep existing model files intact; the new store is separate from other GGUF files.
$sessionId = (Get-Process -Id $PID).SessionId
Get-Process -Name 'ollama app', 'ollama' -ErrorAction SilentlyContinue |
    Where-Object { $_.SessionId -eq $sessionId } | Stop-Process
Start-Sleep -Seconds 2
foreach ($name in $settings.Keys) {
    [Environment]::SetEnvironmentVariable($name, $settings[$name], 'User')
    Set-Item -Path "Env:$name" -Value $settings[$name]
}
if (-not (Test-Path -LiteralPath $exe)) {
    $setup = Start-Process -FilePath $installer -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', ('/DIR="' + $appDir + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($setup.ExitCode -notin @(0, 3010)) { throw "Installation echouee: $($setup.ExitCode)" }
}
if (-not (Test-Path -LiteralPath $exe)) { throw "Executable introuvable: $exe" }

# Restart any process launched by the installer with the explicit settings above.
Get-Process -Name 'ollama app', 'ollama' -ErrorAction SilentlyContinue |
    Where-Object { $_.SessionId -eq $sessionId } | Stop-Process
Start-Sleep -Seconds 2
$gui = Join-Path $appDir 'ollama app.exe'
if (Test-Path -LiteralPath $gui) {
    Start-Process -FilePath $gui -WindowStyle Hidden
} else {
    Start-Process -FilePath $exe -ArgumentList 'serve' -WindowStyle Hidden
}
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
        $ready = $true
        break
    } catch { Start-Sleep -Seconds 1 }
}
if (-not $ready) { throw 'Ollama ne repond pas sur le port 11434.' }
foreach ($model in $models) {
    Write-Host "Telechargement: $model"
    & $exe pull $model
    if ($LASTEXITCODE -ne 0) { throw "Echec du telechargement: $model. Relancez le script pour reprendre." }
}
$catalog = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags'
foreach ($model in $models) {
    if ($model -notin $catalog.models.name) { throw "Modele absent: $model" }
}
if (-not (Test-Path -LiteralPath (Join-Path $modelDir 'manifests'))) {
    throw 'Le catalogue ne se trouve pas dans le dossier demande.'
}
$body = @{model=$models[0]; messages=@(@{role='user'; content='Reponds simplement Bonjour.'}); stream=$false; think=$false; keep_alive=0; options=@{num_ctx=4096; num_predict=32}} | ConvertTo-Json -Depth 5
$reply = Invoke-RestMethod 'http://127.0.0.1:11434/api/chat' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 180
if (-not $reply.message.content) { throw 'Le test de generation ne renvoie aucun texte.' }
Write-Host "Test reel: $($reply.message.content)"

# Patch only this connector after successful downloads and inference.
# Close CyAI before running: a running instance can otherwise overwrite config.json.
$configPath = Join-Path $PSScriptRoot '..\config.json'
if (Test-Path -LiteralPath $configPath) {
    $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Copy-Item -LiteralPath $configPath -Destination ($configPath + '.before-ollama-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bak')
    if (-not $config.connectors) { $config | Add-Member -NotePropertyName connectors -NotePropertyValue ([pscustomobject]@{}) -Force }
    $config.connectors | Add-Member -NotePropertyName ollama -NotePropertyValue ([pscustomobject]@{enabled=$true; base_url='http://127.0.0.1:11434'; model=$models[0]}) -Force
    $config | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $configPath -Encoding UTF8
}
& $exe list
Write-Host 'Installation et test termines. Relancez CyAI. Modele par defaut: qwen3.5:4b.'
Write-Host 'Avec Unreal: privilegiez le 4b. Le 27b est reserve aux sessions avec assez de VRAM libre.'
