$ErrorActionPreference = 'Stop'
$cliArgs = @($args)
$skillRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repoRoot = (Resolve-Path (Join-Path $skillRoot '../../..')).Path
$pilotRoot = Join-Path $repoRoot '.local/video/pilot'

$env:UV_CACHE_DIR = Join-Path $pilotRoot 'cache/uv'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $pilotRoot 'env/shotcut-cli'
New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR, $env:UV_PROJECT_ENVIRONMENT | Out-Null

$toolConfigPath = Join-Path $pilotRoot 'tool-paths.json'
if (Test-Path -LiteralPath $toolConfigPath) {
    $toolConfig = Get-Content -Raw -Encoding UTF8 -LiteralPath $toolConfigPath | ConvertFrom-Json
    if ($toolConfig.shotcutHome -and (Test-Path -LiteralPath $toolConfig.shotcutHome)) {
        $env:PATH = "$($toolConfig.shotcutHome);$env:PATH"
    }
}

& uv run --project $skillRoot --locked --python 3.12 cli-anything-shotcut @cliArgs
exit $LASTEXITCODE
