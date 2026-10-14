$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$logRoot = Join-Path $projectRoot "tmp\local-server"
foreach ($service in @("backend","frontend")) {
    $pidFile = Join-Path $logRoot ($service + ".pid")
    if (!(Test-Path -LiteralPath $pidFile)) { continue }
    $serviceProcessId = [int](Get-Content -LiteralPath $pidFile)
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$serviceProcessId" -ErrorAction SilentlyContinue
    if (!$process) { continue }
    $expected = if ($service -eq "backend") { $process.ExecutablePath -eq (Join-Path $projectRoot ".venv\Scripts\python.exe") -and $process.CommandLine -like "*uvicorn app.main:app*" }
        else { $process.CommandLine.Contains((Join-Path $projectRoot "scripts\serve-frontend.mjs")) }
    if (!$expected) { throw "Saved process ID now belongs to another program. Refusing to stop it." }
    Stop-Process -Id $serviceProcessId
    Write-Output ($service + " stopped.")
}
