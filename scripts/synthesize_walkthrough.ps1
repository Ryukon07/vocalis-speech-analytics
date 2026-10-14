param([Parameter(Mandatory=$true)][string]$WorkDirectory)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$narrator = New-Object System.Speech.Synthesis.SpeechSynthesizer
$narrator.Rate = -1
$segments = Get-Content -LiteralPath (Join-Path $WorkDirectory "narration.json") -Raw | ConvertFrom-Json
try {
    for ($i=0; $i -lt $segments.Count; $i++) {
        $target = Join-Path $WorkDirectory ("narration-" + ($i+1) + ".wav")
        $narrator.SetOutputToWaveFile($target)
        $narrator.Speak([string]$segments[$i])
    }
} finally { $narrator.Dispose() }
