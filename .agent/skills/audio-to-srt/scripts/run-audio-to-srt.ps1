$ErrorActionPreference = 'Stop'
$cliArgs = @($args)
$skillRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repoRoot = (Resolve-Path (Join-Path $skillRoot '../../..')).Path
$localRoot = Join-Path $repoRoot '.local/video'

$pilotRoot = Join-Path $localRoot 'pilot'
$env:UV_CACHE_DIR = Join-Path $pilotRoot 'cache/uv'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $localRoot 'pilot/env/qwen-asr'
$env:HF_HOME = Join-Path $pilotRoot 'models/huggingface'
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME 'hub'

New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR, $env:UV_PROJECT_ENVIRONMENT, $env:HF_HOME | Out-Null

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& uv run --project $skillRoot --locked --python 3.12 (Join-Path $skillRoot 'scripts/audio_to_srt.py') @cliArgs
$exitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference
exit $exitCode
