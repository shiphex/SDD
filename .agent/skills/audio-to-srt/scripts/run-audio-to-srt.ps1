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
$env:VIDEO_RUN_ID = $runId
$env:UV_CACHE_DIR = Join-Path $runRoot 'cache/uv'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $runRoot 'env/qwen-asr'
$env:HF_HOME = Join-Path $runRoot 'models/huggingface'
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME 'hub'

New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR, $env:UV_PROJECT_ENVIRONMENT, $env:HF_HOME | Out-Null

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& uv run --project $skillRoot --locked --python 3.12 (Join-Path $skillRoot 'scripts/audio_to_srt.py') @cliArgs
$exitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference
exit $exitCode
