$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$state = Join-Path $PSScriptRoot '../scripts/workflow-state.ps1'
$runId = 'ai-sample-test-' + [Guid]::NewGuid().ToString('N')
$runDir = Join-Path $repoRoot ".local/video/$runId"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$source = Join-Path $runDir 'source.wav'
$outline = Join-Path $runDir 'outline.md'
$review = Join-Path $runDir 'review.md'
$audio = Join-Path $runDir 'final.wav'
$cutMap = Join-Path $runDir 'cuts.json'
$srt = Join-Path $runDir 'final.srt'
$presentation = Join-Path $runDir 'sample.mp4'
$quality = Join-Path $runDir 'quality.md'
[IO.File]::WriteAllText($source, 'source')
[IO.File]::WriteAllText($outline, '# P01')
[IO.File]::WriteAllText($review, '# Review')
[IO.File]::WriteAllText($audio, 'edited sample')
[IO.File]::WriteAllText($cutMap, '{}')
[IO.File]::WriteAllText($srt, 'caption')
[IO.File]::WriteAllText($presentation, 'video')
[IO.File]::WriteAllText($quality, 'review')
try {
    & $state -Action initialize -RunId $runId -SourceAudio $source | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-outline -Path $outline -DependsOn source-audio | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-content-review-01 -Path $review -DependsOn sample-outline | Out-Null
    & $state -Action set-stage -RunId $runId -Stage sample_content_review | Out-Null
    & $state -Action set-gate -RunId $runId -Gate content_review -Decision approved -DependsOn sample-outline,sample-content-review-01 | Out-Null
    & $state -Action set-stage -RunId $runId -Stage sample_ai_edit | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-cut-map -Path $cutMap -DependsOn source-audio | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-final-audio -Path $audio -DependsOn source-audio,sample-outline,sample-cut-map | Out-Null
    $blocked = $false
    try { & $state -Action set-gate -RunId $runId -Gate ai_audio_export -Decision approved -DependsOn sample-final-audio | Out-Null } catch { $blocked = $true }
    if (-not $blocked) { throw 'AI export must include current content review and cut map.' }
    & $state -Action set-gate -RunId $runId -Gate ai_audio_export -Decision approved -DependsOn sample-outline,sample-content-review-01,sample-cut-map,sample-final-audio | Out-Null
    & $state -Action set-stage -RunId $runId -Stage sample_final_transcript | Out-Null
    & $state -Action assert-audio-approved -RunId $runId -InputAudio $audio | Out-Null
    $blocked = $false
    try { & $state -Action assert-full-approved -RunId $runId | Out-Null } catch { $blocked = $true }
    if (-not $blocked) { throw 'AI sample export must not open full-recording work.' }
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-srt -Path $srt -DependsOn sample-final-audio | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-presentation -Path $presentation -DependsOn sample-outline,sample-srt,sample-final-audio | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-quality-review -Path $quality -DependsOn sample-presentation,sample-srt,sample-final-audio | Out-Null
    & $state -Action set-stage -RunId $runId -Stage sample_quality_review | Out-Null
    & $state -Action set-gate -RunId $runId -Gate sample_acceptance -Decision approved -DependsOn sample-outline,sample-content-review-01,sample-cut-map,sample-final-audio,sample-srt,sample-presentation,sample-quality-review | Out-Null
    & $state -Action set-stage -RunId $runId -Stage full_transcript | Out-Null
    & $state -Action assert-full-approved -RunId $runId | Out-Null
    [IO.File]::AppendAllText($audio, ' changed')
    & $state -Action reconcile -RunId $runId | Out-Null
    $manifest = Get-Content -Raw -Encoding utf8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($manifest.gates.ai_audio_export.status -ne 'stale') { throw 'Changing AI audio must invalidate AI export record.' }
    if ($manifest.gates.sample_acceptance.status -ne 'stale') { throw 'Changing AI audio must invalidate sample acceptance.' }
    Write-Output 'PASS: authorized AI sample route and full-recording block'
} finally {
    $absolute = [IO.Path]::GetFullPath($runDir)
    $allowed = [IO.Path]::GetFullPath((Join-Path $repoRoot '.local/video')) + [IO.Path]::DirectorySeparatorChar
    if (-not $absolute.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe test cleanup path.' }
    if (Test-Path -LiteralPath $absolute) { Remove-Item -LiteralPath $absolute -Recurse -Force }
}
