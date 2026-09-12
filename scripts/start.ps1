$ErrorActionPreference = "Stop"
$Root = "D:\VamsiCompanion"
Set-Location $Root
$Venv = Join-Path $Root ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path $Py)) {
    Write-Host "Virtual environment missing. Run scripts\setup.ps1 first."
    exit 1
}

$env:HF_HOME = "D:\VamsiCompanion\cache\hf"
$env:UV_CACHE_DIR = "D:\VamsiCompanion\.uv_cache"
if (Test-Path (Join-Path $Root ".env")) {
    Write-Host "Loaded .env configuration."
}

& $Py -m app.main