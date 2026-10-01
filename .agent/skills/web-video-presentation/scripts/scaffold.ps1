[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Target = 'presentation',
    [string]$Theme = 'midnight-press',
    [string]$AudioPath,
    [string]$TimelinePath
)

$ErrorActionPreference = 'Stop'
$skillRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$targetPath = [System.IO.Path]::GetFullPath($Target)
$themePath = Join-Path $skillRoot "themes/$Theme"

if (-not (Test-Path -LiteralPath (Join-Path $themePath 'tokens.css'))) {
    throw "Theme '$Theme' was not found under the skill's themes directory."
}
if (Test-Path -LiteralPath $targetPath) {
    $existing = Get-ChildItem -Force -LiteralPath $targetPath
    if ($existing.Count -gt 0) {
        throw "Target directory already exists and is not empty: $targetPath"
    }
} else {
    New-Item -ItemType Directory -Force -Path $targetPath | Out-Null
}
if ($AudioPath -and -not $TimelinePath) {
    throw 'When supplying an audio file, also supply a scene timeline JSON file.'
}
if ($TimelinePath -and -not (Test-Path -LiteralPath $TimelinePath -PathType Leaf)) {
    throw "Scene timeline JSON was not found: $TimelinePath"
}
if ($AudioPath -and -not (Test-Path -LiteralPath $AudioPath -PathType Leaf)) {
    throw "Audio file was not found: $AudioPath"
}

Push-Location $targetPath
try {
    npm create vite@latest . -- --template react-ts
    if ($LASTEXITCODE -ne 0) { throw 'Vite scaffold command failed.' }
    npm install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'npm dependency installation failed.' }

    $templateRoot = Join-Path $skillRoot 'templates/audio-sync'
    Copy-Item -LiteralPath (Join-Path $templateRoot 'App.tsx') -Destination 'src/App.tsx' -Force
    Copy-Item -LiteralPath (Join-Path $templateRoot 'index.css') -Destination 'src/index.css' -Force
    Copy-Item -LiteralPath (Join-Path $templateRoot 'audio-sync.css') -Destination 'src/audio-sync.css' -Force
    Copy-Item -LiteralPath (Join-Path $themePath 'tokens.css') -Destination 'src/tokens.css' -Force
    Copy-Item -LiteralPath (Join-Path $templateRoot 'index.html') -Destination 'index.html' -Force
    New-Item -ItemType Directory -Force -Path 'public/audio' | Out-Null

    $timeline = [PSCustomObject]@{ audioSrc = ''; scenes = @() }
    if ($TimelinePath) {
        $timeline = Get-Content -Raw -Encoding UTF8 -LiteralPath $TimelinePath | ConvertFrom-Json
        if (-not ($timeline.PSObject.Properties.Name -contains 'scenes') -or $null -eq $timeline.scenes) {
            throw "Timeline must contain a 'scenes' array: $TimelinePath"
        }
        $previousEnd = -1.0
        foreach ($scene in $timeline.scenes) {
            if ($null -eq $scene.start -or $null -eq $scene.end -or $scene.end -le $scene.start) {
                throw "Each scene must have end > start: $($scene.id)"
            }
            if ($scene.start -lt $previousEnd) {
                throw "Scene time ranges overlap or are out of order: $($scene.id)"
            }
            if (-not $scene.title) { throw "Each scene needs a title: $($scene.id)" }
            $previousEnd = [double]$scene.end
        }
    }

    if (-not ($timeline.PSObject.Properties.Name -contains 'audioSrc')) {
        $timeline | Add-Member -NotePropertyName audioSrc -NotePropertyValue ''
    }

    if ($AudioPath) {
        $audioName = [System.IO.Path]::GetFileName($AudioPath)
        Copy-Item -LiteralPath (Resolve-Path -LiteralPath $AudioPath).Path -Destination (Join-Path 'public/audio' $audioName) -Force
        $timeline.audioSrc = "/audio/$audioName"
    }

    $timeline | ConvertTo-Json -Depth 20 | Set-Content -Encoding utf8 -LiteralPath 'public/timeline.json'
    @'
# Existing-audio presentation

This project follows the supplied scene ranges against the supplied final audio. Scene times are seconds on the final audio playback timeline. If that audio is trimmed or re-recorded, regenerate its SRT and update the scene ranges.

Edit `public/timeline.json`. Each scene has `id`, `start`, `end`, `title`, and optional `body` and `visual` text. Keep ranges ordered and non-overlapping. The browser audio controls support play, pause, and seeking; the active scene follows the audio playhead.

The supplied audio is treated as the source of truth. This project does not synthesize or rewrite narration.
'@ | Set-Content -Encoding utf8 -LiteralPath 'AUDIO-SYNC.md'

    Write-Output "Created existing-audio presentation: $targetPath"
    Write-Output 'Set scene ranges in public/timeline.json, then run npm run dev.'
} finally {
    Pop-Location
}
