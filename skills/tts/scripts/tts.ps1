param(
    [Parameter(Mandatory=$true)][string]$OutFile,
    [Parameter(Mandatory=$true)][string]$Text,
    [ValidateSet('pavel','irina')][string]$Voice = 'pavel',
    [int]$Rate = 3,
    [ValidateSet('ogg','wav')][string]$Format = 'ogg'
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

if ($Rate -lt -10 -or $Rate -gt 10) {
    throw 'Rate must be between -10 and 10 for System.Speech'
}

$text = $Text.Trim()
if (-not $text) {
    throw 'Text is empty'
}

$dir = Split-Path -Parent $OutFile
if ($dir) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

$ffmpeg = 'ffmpeg'
$ffmpegCmd = Get-Command $ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpegCmd) {
    throw 'ffmpeg not found in PATH'
}

$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voiceMap = @{
        pavel = '*Pavel*'
        irina = '*Irina*'
    }

    $pattern = $voiceMap[$Voice]
    $selected = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -like $pattern } | Select-Object -First 1
    if (-not $selected) {
        throw "Requested voice not found: $Voice"
    }

    $s.SelectVoice($selected.VoiceInfo.Name)
    $s.Rate = $Rate

    if ($Format -eq 'wav') {
        $target = [System.IO.Path]::ChangeExtension($OutFile, '.wav')
        $s.SetOutputToWaveFile($target)
        $s.Speak($text)
        Write-Output $target
    }
    else {
        $tempBase = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), [System.Guid]::NewGuid().ToString())
        $tempWav = "$tempBase.wav"
        $target = [System.IO.Path]::ChangeExtension($OutFile, '.ogg')
        try {
            $s.SetOutputToWaveFile($tempWav)
            $s.Speak($text)
            & $ffmpeg -y -i $tempWav -c:a libopus -b:a 48k -ar 48000 -ac 1 $target | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "ffmpeg failed with exit code $LASTEXITCODE"
            }
            Write-Output $target
        }
        finally {
            if (Test-Path $tempWav) {
                Remove-Item $tempWav -Force -ErrorAction SilentlyContinue
            }
        }
    }

    Write-Output $selected.VoiceInfo.Name
    Write-Output ("voice=" + $Voice)
    Write-Output ("rate=" + $Rate)
    Write-Output ("format=" + $Format)
}
finally {
    $s.Dispose()
}
