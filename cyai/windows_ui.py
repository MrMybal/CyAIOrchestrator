"""User-triggered Windows folder picker; no user text is evaluated as code."""
import base64
import os
import subprocess


def choose_folder():
    if os.name != "nt":
        raise ValueError("Le sélecteur de dossiers nécessite Windows.")
    script = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Choisissez le dossier du projet CyAI'
$dialog.ShowNewFolderButton = $true
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
try {
    if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {
        [Console]::Write([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($dialog.SelectedPath)))
    }
} finally { $dialog.Dispose(); $owner.Dispose() }
'''
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    result = subprocess.run([os.path.join(os.environ["SystemRoot"], "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
        "-NoProfile", "-STA", "-EncodedCommand", encoded], capture_output=True, timeout=600,
        creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError("Le sélecteur Windows n’a pas pu s’ouvrir.")
    return base64.b64decode(result.stdout.strip()).decode("utf-8") if result.stdout.strip() else None


def choose_file():
    if os.name != 'nt':raise ValueError('Sélecteur Windows requis.')
    script = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'Choisir un fichier pour CyAI'
$dialog.Filter = 'Fichiers compatibles|*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.cyannota;*.zip;*.json;*.exe|Tous les fichiers|*.*'
try {
 if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  [Console]::Write([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($dialog.FileName)))
 }
} finally { $dialog.Dispose() }
'''
    encoded=base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    result=subprocess.run([os.path.join(os.environ['SystemRoot'],'System32','WindowsPowerShell','v1.0','powershell.exe'),'-NoProfile','-STA','-EncodedCommand',encoded],capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise ValueError('Impossible d’ouvrir le sélecteur Windows.')
    return base64.b64decode(result.stdout.strip()).decode('utf-8') if result.stdout.strip() else None
