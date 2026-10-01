param(
    [string]$InputAudio,
    [ValidateRange(30, 180)]
    [int]$SampleSeconds = 180,
    [switch]$SkipTranscription
)

$ErrorActionPreference = 'Stop'
$skillRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repoRoot = (Resolve-Path (Join-Path $skillRoot '../../..')).Path
$pilotRoot = Join-Path $repoRoot '.local/video/pilot'
$localRoot = Join-Path $repoRoot '.local/video'
$env:UV_CACHE_DIR = Join-Path $pilotRoot 'cache/uv'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $pilotRoot 'env/qwen-asr'
New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR | Out-Null
if (-not $InputAudio) {
    $toolConfigPath = Join-Path $pilotRoot 'tool-paths.json'
    if (Test-Path -LiteralPath $toolConfigPath) {
        $toolConfig = Get-Content -Raw -Encoding UTF8 -LiteralPath $toolConfigPath | ConvertFrom-Json
        $InputAudio = $toolConfig.sourceAudio
    }
    if (-not $InputAudio) {
        throw 'Pass -InputAudio or set sourceAudio in the ignored .local/video/pilot/tool-paths.json.'
    }
}
$InputAudio = (Resolve-Path -LiteralPath $InputAudio).Path

New-Item -ItemType Directory -Force -Path $pilotRoot | Out-Null
$sampleAudio = Join-Path $pilotRoot 'source-first-3m.wav'
$sourceSrt = Join-Path $pilotRoot 'source.srt'
$alignmentJson = Join-Path $pilotRoot 'source.alignment.json'
$timelineFile = Join-Path $pilotRoot 'roughcut.v2'
$reviewFile = Join-Path $pilotRoot 'edit-review.md'
$mltFile = Join-Path $pilotRoot 'roughcut-candidate.mlt'
$autoEditor = Join-Path $pilotRoot 'tools/auto-editor-31.6.0-windows-x86_64.exe'

if (Test-Path -LiteralPath $mltFile) {
    throw 'A rough-cut project already exists. Review it first; start a separate pilot before replacing its source or timeline.'
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw 'ffmpeg is required and was not found on PATH.'
}
if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    throw 'ffprobe is required and was not found on PATH.'
}
if (-not (Test-Path -LiteralPath $autoEditor)) {
    throw "Auto-Editor executable is missing: $autoEditor"
}

# The original recording is only read. This creates a mono 16 kHz PCM sample.
& ffmpeg -hide_banner -loglevel error -y -i $InputAudio -t $SampleSeconds -map 0:a:0 -vn -ac 1 -ar 16000 -c:a pcm_s16le $sampleAudio
if ($LASTEXITCODE -ne 0) { throw 'ffmpeg could not prepare the sample audio.' }

$durationText = & ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $sampleAudio
if ($LASTEXITCODE -ne 0) { throw 'ffprobe could not read the sample duration.' }
$duration = [double]::Parse($durationText, [Globalization.CultureInfo]::InvariantCulture)

& $autoEditor $sampleAudio --margin 0.2s --export v2 -o $timelineFile
if ($LASTEXITCODE -ne 0) { throw 'Auto-Editor did not produce the rough-cut timeline.' }

& uv run --project $skillRoot --locked --python 3.12 (Join-Path $skillRoot 'scripts/build_edit_review.py') $timelineFile $duration $reviewFile
if ($LASTEXITCODE -ne 0) { throw 'The edit review list could not be generated.' }

$shotcutBuilder = Join-Path $repoRoot '.agent/skills/cli-anything-shotcut/scripts/create-roughcut.ps1'
& $shotcutBuilder -Timeline $timelineFile -Audio $sampleAudio -Output $mltFile
if ($LASTEXITCODE -ne 0) { throw 'The Shotcut MLT rough-cut project could not be generated.' }

if (-not $SkipTranscription) {
    $runner = Join-Path $skillRoot 'scripts/run-audio-to-srt.ps1'
    & $runner $sampleAudio --language Chinese --output $sourceSrt --json-output $alignmentJson
    if ($LASTEXITCODE -ne 0) { throw 'Qwen transcription did not complete.' }

    & uv run --project $skillRoot --locked --python 3.12 `
        (Join-Path $skillRoot 'scripts/build_edit_review.py') `
        $timelineFile $duration $reviewFile --alignment $alignmentJson
    if ($LASTEXITCODE -ne 0) { throw 'Transcript review candidates could not be added.' }
}

Write-Output "Sample audio: $sampleAudio"
Write-Output "Original-time transcript: $sourceSrt"
Write-Output "Silence timeline: $timelineFile"
Write-Output "Shotcut rough-cut project: $mltFile"
Write-Output "Review list: $reviewFile"
Write-Output 'Open the rough cut in Shotcut, listen and approve changes before exporting final audio.'
