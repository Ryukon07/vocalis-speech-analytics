$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$demoRoot = Join-Path $projectRoot "tmp\public-demo"
foreach ($service in @("tunnel","proxy","backend")) {
  $pidFile = Join-Path $demoRoot ($service + ".pid")
  if (!(Test-Path -LiteralPath $pidFile)) { continue }
  $demoProcessId = [int](Get-Content -LiteralPath $pidFile)
  $process = Get-CimInstance Win32_Process -Filter "ProcessId=$demoProcessId" -ErrorAction SilentlyContinue
  if (!$process) { continue }
  $expected = switch ($service) {
    "tunnel" { $process.ExecutablePath -eq (Join-Path $projectRoot "tools-local\cloudflared.exe") }
    "proxy" { $process.CommandLine.Contains((Join-Path $projectRoot "scripts\serve-public-demo.mjs")) }
    "backend" { $process.ExecutablePath -eq (Join-Path $projectRoot ".venv\Scripts\python.exe") -and $process.CommandLine -like "*uvicorn public_demo_api:app*" }
  }
  if (!$expected) { throw "Saved demo process ID belongs to another program; refusing to stop it." }
  Stop-Process -Id $demoProcessId
  Write-Output ($service + " stopped.")
}
