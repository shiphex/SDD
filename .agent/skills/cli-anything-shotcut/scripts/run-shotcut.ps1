$ErrorActionPreference = 'Stop'
$cliArgs = @($args)
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
New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR, $env:UV_PROJECT_ENVIRONMENT | Out-Null

$toolConfigPath = Join-Path $runRoot 'tool-paths.json'
if (Test-Path -LiteralPath $toolConfigPath) {
    $toolConfig = Get-Content -Raw -Encoding UTF8 -LiteralPath $toolConfigPath | ConvertFrom-Json
    if ($toolConfig.shotcutHome -and (Test-Path -LiteralPath $toolConfig.shotcutHome)) {
        $env:PATH = "$($toolConfig.shotcutHome);$env:PATH"
    }
}

& uv run --project $skillRoot --locked --python 3.12 cli-anything-shotcut @cliArgs
exit $LASTEXITCODE
