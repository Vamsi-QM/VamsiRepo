$ErrorActionPreference = "Stop"
$Root = "D:\VamsiCompanion"
Set-Location $Root
$Venv = Join-Path $Root ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path $Py)) {
    Write-Host "Virtual environment missing. Run scripts\setup.ps1 first."
    exit 1
}

$env:HOST = "0.0.0.0"
$env:PHONE_ACCESS_ENABLED = "1"
$env:HF_HOME = "D:\VamsiCompanion\cache\hf"
$env:UV_CACHE_DIR = "D:\VamsiCompanion\.uv_cache"

Write-Host "Starting Vamsi Companion in phone access mode."
Write-Host "Keep this terminal open. Use the printed phone URL on your Realme while both devices are on the same Wi-Fi."

& $Py -m app.main
