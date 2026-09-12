$ErrorActionPreference = "Stop"
$Root = "D:\VamsiCompanion"
Set-Location $Root

$env:UV_CACHE_DIR = "D:\VamsiCompanion\.uv_cache"
$env:UV_PYTHON_INSTALL_DIR = "D:\VamsiCompanion\.uv_python"
$env:HF_HOME = "D:\VamsiCompanion\cache\hf"
$env:TEMP = Join-Path $Root "cache\tmp"
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

if (-not (Test-Path "D:\VamsiCompanion\.venv\Scripts\python.exe")) {
    Write-Host "Creating venv…"
    uv venv "$Root\.venv" --python 3.12
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed" }
}

Write-Host "Installing llama-cpp-python (CPU wheel)…"
uv pip install --python "$Root\.venv\Scripts\python.exe" `
    "https://abetlen.github.io/llama-cpp-python/whl/cpu/v0.3.19/llama_cpp_python-0.3.19-cp312-cp312-win_amd64.whl"

if ($LASTEXITCODE -ne 0) { throw "Model runtime installation failed" }
Write-Host "Installing remaining packages…"
uv pip install --python "$Root\.venv\Scripts\python.exe" -r "$Root\requirements.lock"

if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
$modelDir = "D:\VamsiCompanion\models"
$modelFile = Join-Path $modelDir "qwen2.5-1.5b-instruct-q4_k_m.gguf"
if (-not (Test-Path $modelFile)) {
    Write-Host "Downloading Qwen2.5-1.5B-Instruct Q4_K_M (~1 GB)…"
    New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
    & "$Root\.venv\Scripts\python.exe" "$Root\scripts\download_model.py"
    if ($LASTEXITCODE -ne 0) { throw "Model download failed" }
} else {
    Write-Host "Model already present."
}

Write-Host "Setup complete. Start with scripts\start.ps1"