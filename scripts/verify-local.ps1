$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$projectPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$testRoot = Join-Path $projectRoot ("tmp\verification-" + [guid]::NewGuid().ToString("N"))
Set-Location -LiteralPath (Join-Path $projectRoot "backend")
& $projectPython -m pytest -q "--basetemp=$testRoot" --tb=short
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }
Set-Location -LiteralPath (Join-Path $projectRoot "frontend")
npm.cmd test
if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed." }
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw "Production build failed." }
Set-Location -LiteralPath $projectRoot
& $projectPython -m pip check
if ($LASTEXITCODE -ne 0) { throw "Python dependency validation failed." }
Write-Output "All local regression checks passed."
