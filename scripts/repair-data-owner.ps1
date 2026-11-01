param([string]$Path = (Join-Path $PSScriptRoot '..\.data'))
$ErrorActionPreference = 'Stop'
$target = [System.IO.Path]::GetFullPath($Path)
if (-not (Test-Path -LiteralPath $target -PathType Container)) { throw 'Dossier de données introuvable.' }
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $target /setowner $identity /T /C
if ($LASTEXITCODE -ne 0) { throw 'La réparation du propriétaire a échoué.' }
(Get-Acl -LiteralPath $target).Owner
