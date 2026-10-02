param(
    [Parameter(Mandatory = $true)]
    [string]$Timeline,
    [Parameter(Mandatory = $true)]
    [string]$Audio,
    [Parameter(Mandatory = $true)]
    [string]$Output
)

$ErrorActionPreference = 'Stop'
$skillRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repoRoot = (Resolve-Path (Join-Path $skillRoot '../../..')).Path
$localRoot = Join-Path $repoRoot '.local/video'
$runId = if ($env:VIDEO_RUN_ID) { $env:VIDEO_RUN_ID } else { 'pilot' }
if ($runId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') {
    throw 'VIDEO_RUN_ID must be a short filename-safe run ID.'
}
$runRoot = Join-Path $localRoot $runId
$env:UV_CACHE_DIR = Join-Path $runRoot 'cache/uv'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $runRoot 'env/shotcut-cli'
$toolConfigPath = Join-Path $runRoot 'tool-paths.json'
New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR,$env:UV_PROJECT_ENVIRONMENT | Out-Null

if (Test-Path -LiteralPath $toolConfigPath) {
    $toolConfig = Get-Content -Raw -Encoding UTF8 -LiteralPath $toolConfigPath | ConvertFrom-Json
    if ($toolConfig.shotcutHome -and (Test-Path -LiteralPath $toolConfig.shotcutHome)) {
        $env:PATH = "$($toolConfig.shotcutHome);$env:PATH"
    }
}

& uv run --project $skillRoot --locked --python 3.12 `
    (Join-Path $skillRoot 'scripts/build_roughcut_mlt.py') `
    $Timeline $Audio $Output
exit $LASTEXITCODE
