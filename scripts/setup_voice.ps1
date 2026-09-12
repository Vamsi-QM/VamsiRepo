param(
    [string]$ModelUrl = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    [string]$ModelsDir = "D:\VamsiCompanion\models"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment not found at $Python. Run scripts\setup.ps1 first."
}

$env:UV_CACHE_DIR = Join-Path $Root ".uv_cache"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Root ".uv_python"
$env:TEMP = Join-Path $Root "cache\tmp"
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

Write-Host "Installing Vosk speech-to-text runtime..."
uv pip install --python $Python "vosk==0.3.45"
if ($LASTEXITCODE -ne 0) { throw "Vosk installation failed" }

New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
$zipPath = Join-Path $ModelsDir "vosk-model-small-en-us-0.15.zip"
$modelPath = Join-Path $ModelsDir "vosk-model-small-en-us-0.15"

if (-not (Test-Path -LiteralPath $modelPath)) {
    if (-not (Test-Path -LiteralPath $zipPath)) {
        Write-Host "Downloading Vosk model..."
        $downloadScript = Join-Path $env:TEMP "download_vosk_model.py"
        @"
from pathlib import Path
from urllib.request import urlopen
url = '$ModelUrl'
out = Path(r'$zipPath')
with urlopen(url, timeout=120) as response:
    total = int(response.headers.get('Content-Length') or 0)
    done = 0
    with out.open('wb') as f:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f'{done * 100 // total}%')
"@ | Set-Content -LiteralPath $downloadScript
        & $Python $downloadScript
        if ($LASTEXITCODE -ne 0) { throw "Vosk model download failed" }
    }
    Write-Host "Extracting Vosk model..."
    Expand-Archive -LiteralPath $zipPath -DestinationPath $ModelsDir -Force
}

Write-Host "Voice model ready: $modelPath"
Write-Host "Restart Vamsi Companion, then test Talk on the phone app."
