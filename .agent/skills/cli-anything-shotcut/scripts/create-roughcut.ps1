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
$pilotRoot = Join-Path $repoRoot '.local/video/pilot'
$env:UV_CACHE_DIR = Join-Path $pilotRoot 'cache/uv'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $pilotRoot 'env/shotcut-cli'
$toolConfigPath = Join-Path $pilotRoot 'tool-paths.json'
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
