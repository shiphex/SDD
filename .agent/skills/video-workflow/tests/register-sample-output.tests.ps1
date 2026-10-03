$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$state = Join-Path $PSScriptRoot '../scripts/workflow-state.ps1'
$register = Join-Path $PSScriptRoot '../scripts/register-sample-output.ps1'
$runId = 'sample-register-test-' + [Guid]::NewGuid().ToString('N')
$runDir = Join-Path $repoRoot ".local/video/$runId"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
foreach ($name in @('source.wav','outline.md','review.md','cuts.json','draft.wav','draft.srt','draft.mp4','final.wav','transcript.md','alignment.json','final.srt','scene.png','sample.mp4','quality.md')) {
    [IO.File]::WriteAllText((Join-Path $runDir $name), $name)
}
[IO.File]::WriteAllText((Join-Path $runDir 'scenes.json'), '{"scenes":[{"start":0,"end":1,"image":"scene.png"}]}')
try {
    & $state -Action initialize -RunId $runId -SourceAudio (Join-Path $runDir 'source.wav') | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-outline -Path (Join-Path $runDir 'outline.md') -DependsOn source-audio | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-content-review-01 -Path (Join-Path $runDir 'review.md') -DependsOn sample-outline | Out-Null
    & $state -Action set-stage -RunId $runId -Stage sample_content_review | Out-Null
    & $register -Action draft -RunId $runId -CutMap (Join-Path $runDir 'cuts.json') -Audio (Join-Path $runDir 'draft.wav') -Srt (Join-Path $runDir 'draft.srt') -ScenePlan (Join-Path $runDir 'scenes.json') -Video (Join-Path $runDir 'draft.mp4') | Out-Null
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($manifest.gates.content_review.status -ne 'pending') { throw 'Draft must not approve content.' }
    if ($manifest.artifacts.'sample-draft-mp4'.status -ne 'current') { throw 'Draft MP4 not recorded.' }
    & $state -Action set-gate -RunId $runId -Gate content_review -Decision approved -DependsOn sample-outline,sample-content-review-01 | Out-Null
    & $state -Action set-stage -RunId $runId -Stage sample_ai_edit | Out-Null
    & $register -Action audio -RunId $runId -CutMap (Join-Path $runDir 'cuts.json') -Audio (Join-Path $runDir 'final.wav') | Out-Null
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($manifest.gates.ai_audio_export.status -ne 'approved') { throw 'AI export not recorded.' }
    if ($manifest.gates.sample_acceptance.status -ne 'pending') { throw 'Sample acceptance must stay pending.' }
    if ($manifest.stage -ne 'sample_final_transcript') { throw 'Stage must move to final transcription.' }
    & $register -Action delivery -RunId $runId -Transcript (Join-Path $runDir 'transcript.md') -Alignment (Join-Path $runDir 'alignment.json') -Srt (Join-Path $runDir 'final.srt') -ScenePlan (Join-Path $runDir 'scenes.json') -Video (Join-Path $runDir 'sample.mp4') -QualityReview (Join-Path $runDir 'quality.md') | Out-Null
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($manifest.gates.sample_acceptance.status -ne 'pending') { throw 'Delivery must not approve sample acceptance.' }
    if ($manifest.stage -ne 'sample_quality_review') { throw 'Delivery must move to quality review.' }
    if ('sample-scene-plan' -notin @($manifest.artifacts.'sample-presentation'.depends_on)) { throw 'Scene plan dependency missing.' }
    $blocked = $false
    try { & $state -Action assert-full-approved -RunId $runId | Out-Null } catch { $blocked = $true }
    if (-not $blocked) { throw 'Full recording must remain blocked.' }
    [IO.File]::AppendAllText((Join-Path $runDir 'scene.png'), 'changed')
    & $state -Action reconcile -RunId $runId | Out-Null
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($manifest.artifacts.'sample-presentation'.status -ne 'stale') { throw 'Scene change must stale video.' }
    if ($manifest.artifacts.'sample-draft-mp4'.status -ne 'stale') { throw 'Scene change must stale draft video.' }
    Write-Output 'PASS: sample output registration and gate isolation'
} finally {
    $absolute = [IO.Path]::GetFullPath($runDir)
    $allowed = [IO.Path]::GetFullPath((Join-Path $repoRoot '.local/video')) + [IO.Path]::DirectorySeparatorChar
    if (-not $absolute.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe test cleanup path.' }
    if (Test-Path -LiteralPath $absolute) { Remove-Item -LiteralPath $absolute -Recurse -Force }
}
