$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$demoRoot = Join-Path $projectRoot "tmp\public-demo"
$projectPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath (Join-Path $demoRoot "seed-manifest.json"))) { throw "Run prepare_public_demo.py from backend first." }
if (!(Test-Path -LiteralPath (Join-Path $demoRoot "dist\index.html"))) { throw "Build the public frontend first." }
$env:PYTHONPATH = (Join-Path $projectRoot "backend") + ";" + (Join-Path $projectRoot "scripts")
$backend = Start-Process -FilePath $projectPython -ArgumentList "-X","faulthandler","-m","uvicorn","public_demo_api:app","--host","127.0.0.1","--port","8001" -WorkingDirectory (Join-Path $projectRoot "backend") -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $demoRoot "backend.log") -RedirectStandardError (Join-Path $demoRoot "backend-errors.log")
$backend.Id | Set-Content -LiteralPath (Join-Path $demoRoot "backend.pid")
$nodePath = (Get-Command node.exe).Source
$proxyScript = Join-Path $projectRoot "scripts\serve-public-demo.mjs"
$proxy = Start-Process -FilePath $nodePath -ArgumentList ('"' + $proxyScript + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $demoRoot "proxy.log") -RedirectStandardError (Join-Path $demoRoot "proxy-errors.log")
$proxy.Id | Set-Content -LiteralPath (Join-Path $demoRoot "proxy.pid")
for ($i=0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:5174/api/v1/health -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep -Milliseconds 500 } }
$tunnelBinary = Join-Path $projectRoot "tools-local\cloudflared.exe"
$tunnel = Start-Process -FilePath $tunnelBinary -ArgumentList "tunnel","--url","http://127.0.0.1:5174","--protocol","http2","--no-autoupdate" -WorkingDirectory $demoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $demoRoot "tunnel.log") -RedirectStandardError (Join-Path $demoRoot "tunnel-errors.log")
$tunnel.Id | Set-Content -LiteralPath (Join-Path $demoRoot "tunnel.pid")
Write-Output "Isolated backend, proxy and temporary HTTPS tunnel started. URL appears in tmp/public-demo/tunnel-errors.log."
