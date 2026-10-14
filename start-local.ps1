$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$projectPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $projectPython)) { throw "Run setup-local.ps1 first." }
if (!(Test-Path -LiteralPath (Join-Path $projectRoot "frontend\dist\index.html"))) { throw "Build the frontend with setup-local.ps1 first." }
$logRoot = Join-Path $projectRoot "tmp\local-server"
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
try {
    $health = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 2
    if ($health.version -ne "3.1.3") { throw "Port 8000 is used by a different server or an older Vocalis version. Stop that server before starting Vocalis." }
} catch {
    if ($_.Exception.Message -like "*different server*") { throw }
    $backendProcess = Start-Process -FilePath $projectPython -ArgumentList "-X","faulthandler","-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory (Join-Path $projectRoot "backend") -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot "backend.log") -RedirectStandardError (Join-Path $logRoot "backend-errors.log")
    $backendProcess.Id | Set-Content -LiteralPath (Join-Path $logRoot "backend.pid")
}
try { Invoke-WebRequest "http://127.0.0.1:5173" -TimeoutSec 2 | Out-Null }
catch {
    $nodePath = (Get-Command node.exe).Source
    $serveScript = Join-Path $projectRoot "scripts\serve-frontend.mjs"
    $frontendProcess = Start-Process -FilePath $nodePath -ArgumentList ('"' + $serveScript + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot "frontend.log") -RedirectStandardError (Join-Path $logRoot "frontend-errors.log")
    $frontendProcess.Id | Set-Content -LiteralPath (Join-Path $logRoot "frontend.pid")
}
$ready = $false
for ($i=0; $i -lt 30; $i++) {
    try { $health = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 2; $ready = $true; break } catch { Start-Sleep -Milliseconds 500 }
}
if (!$ready) { throw "Backend did not start. See tmp\local-server\backend-errors.log" }
Write-Output "Vocalis is running at http://127.0.0.1:5173"
Write-Output $health.message
