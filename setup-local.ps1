param([string]$PythonPath = "")
$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (!(Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    if ($PythonPath) { & $PythonPath -m venv .venv }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { py -3.12 -m venv .venv }
    else { python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw "Install Python 3.12, then run setup-local.ps1 again." }
}
$projectPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
& $projectPython -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw "Could not initialize pip." }
& $projectPython -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu --timeout 120
if ($LASTEXITCODE -ne 0) { throw "CPU model runtime installation failed." }
& $projectPython -m pip install -r requirements.txt --timeout 120
if ($LASTEXITCODE -ne 0) { throw "Speech package installation failed." }
if (!(Test-Path -LiteralPath "backend\.env")) { Copy-Item -LiteralPath "backend\.env.example" -Destination "backend\.env" }
if (!(Test-Path -LiteralPath "frontend\.env")) { Copy-Item -LiteralPath "frontend\.env.example" -Destination "frontend\.env" }
Set-Location -LiteralPath (Join-Path $projectRoot "backend")
& $projectPython -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
& $projectPython -m app.seed
if ($LASTEXITCODE -ne 0) { throw "Rubric setup failed." }
if (Test-Path -LiteralPath (Join-Path $projectRoot "dataset\contrastive\manifest.json")) {
    & $projectPython -m app.import_dataset
    if ($LASTEXITCODE -ne 0) { throw "Dataset import failed." }
}
Set-Location -LiteralPath (Join-Path $projectRoot "frontend")
npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw "Frontend installation failed." }
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
Set-Location -LiteralPath $projectRoot
& $projectPython scripts\warm_models.py
if ($LASTEXITCODE -ne 0) { throw "Model readiness check failed. Check internet access and retry." }
Write-Output "Setup complete. Run .\start-local.ps1"
