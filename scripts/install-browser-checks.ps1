$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $projectRoot "model-artifacts\playwright"
$env:PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT = "120000"
Set-Location -LiteralPath (Join-Path $projectRoot "frontend")
npx.cmd playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "Chromium download failed. Check the connection and retry." }
Write-Output "Isolated browser checks are ready. Run npm run test:e2e with the local website running."
