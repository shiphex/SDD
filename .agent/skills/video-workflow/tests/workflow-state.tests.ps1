$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$stateScript = Join-Path $PSScriptRoot '../scripts/workflow-state.ps1'
if (-not (Test-Path -LiteralPath $stateScript)) {
    throw "RED: expected workflow state helper at $stateScript"
}

$runId = 'workflow-test-' + [Guid]::NewGuid().ToString('N')
$runDir = Join-Path $repoRoot ".local/video/$runId"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$sourcePath = Join-Path $runDir 'source.txt'
$transcriptPath = Join-Path $runDir 'transcript.txt'
$srtPath = Join-Path $runDir 'captions.srt'
$outlinePath = Join-Path $runDir 'outline.md'
$reviewPath = Join-Path $runDir 'edit-review.md'
$previewPath = Join-Path $runDir 'preview.html'
$finalAudioPath = Join-Path $runDir 'final-audio.wav'
$qualityReviewPath = Join-Path $runDir 'quality-review.md'
$reviewRound2Path = Join-Path $runDir 'review-round-02.md'
[IO.File]::WriteAllText($sourcePath, 'PRIVATE SOURCE SENTINEL')
[IO.File]::WriteAllText($transcriptPath, 'PRIVATE TRANSCRIPT SENTINEL')
[IO.File]::WriteAllText($srtPath, 'caption')
[IO.File]::WriteAllText($outlinePath, '# P01')
[IO.File]::WriteAllText($reviewPath, '# AI review: no open items')
[IO.File]::WriteAllText($previewPath, '<html></html>')
[IO.File]::WriteAllText($finalAudioPath, 'audio')
[IO.File]::WriteAllText($qualityReviewPath, '# Sample quality review')

try {
    & $stateScript -Action initialize -RunId $runId -SourceAudio $sourcePath | Out-Null
    & $stateScript -Action register-artifact -RunId $runId -ArtifactId transcript -Path $transcriptPath -DependsOn source-audio | Out-Null
    & $stateScript -Action register-artifact -RunId $runId -ArtifactId captions -Path $srtPath -DependsOn transcript | Out-Null
    & $stateScript -Action register-artifact -RunId $runId -ArtifactId sample-outline -Path $outlinePath -DependsOn transcript,captions | Out-Null
    & $stateScript -Action register-artifact -RunId $runId -ArtifactId sample-content-review-01 -Path $reviewPath -DependsOn sample-outline,transcript | Out-Null
    & $stateScript -Action register-artifact -RunId $runId -ArtifactId preview -Path $previewPath -DependsOn sample-outline,captions | Out-Null
    & $stateScript -Action register-artifact -RunId $runId -ArtifactId sample-final-audio -Path $finalAudioPath -DependsOn source-audio,sample-outline | Out-Null

    $manifestPath = Join-Path $runDir 'workflow.json'
    $manifest = Get-Content -Raw -Encoding utf8 $manifestPath | ConvertFrom-Json
    if ($manifest.gates.content_review.status -ne 'pending') {
        throw 'A new run must not infer content approval from existing artifacts.'
    }
    & $stateScript -Action set-item -RunId $runId -ItemId I-001 -ItemStatus pending -Decision revise | Out-Null
    & $stateScript -Action set-stage -RunId $runId -Stage sample_content_review | Out-Null
    $blocked = $false
    try {
        & $stateScript -Action set-stage -RunId $runId -Stage sample_shotcut | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'Sample editing must wait for content approval.' }

    $blocked = $false
    try {
        & $stateScript -Action set-gate -RunId $runId -Gate shotcut_export -Decision approved -DependsOn sample-final-audio | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'Shotcut export approval must require an approved content review.' }

    $blocked = $false
    try {
        & $stateScript -Action set-gate -RunId $runId -Gate content_review -Decision approved -DependsOn sample-outline | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'Content gate must block while review items are pending.' }

    & $stateScript -Action set-item -RunId $runId -ItemId I-001 -ItemStatus accepted -Decision retain | Out-Null
    $blocked = $false
    try {
        & $stateScript -Action set-gate -RunId $runId -Gate content_review -Decision approved -DependsOn sample-outline | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'Content review must register both the page outline and its review record.' }

    [IO.File]::WriteAllText($reviewPath, "# AI review`n`n## I-001 | resolved`n`n## I-002 | new`n")
    & $stateScript -Action register-artifact -RunId $runId -ArtifactId sample-content-review-01 -Path $reviewPath -DependsOn sample-outline,transcript | Out-Null
    $blocked = $false
    try {
        & $stateScript -Action set-gate -RunId $runId -Gate content_review -Decision approved -DependsOn sample-outline,sample-content-review-01 | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'Every issue in the latest review record must have a state entry.' }
    & $stateScript -Action set-item -RunId $runId -ItemId I-002 -ItemStatus accepted -Decision accept_no_change | Out-Null
    & $stateScript -Action set-gate -RunId $runId -Gate content_review -Decision approved -DependsOn sample-outline,sample-content-review-01 | Out-Null
    & $stateScript -Action set-stage -RunId $runId -Stage sample_shotcut | Out-Null

    $blocked = $false
    try {
        & $stateScript -Action set-gate -RunId $runId -Gate shotcut_export -Decision approved -DependsOn sample-outline,sample-final-audio | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'Shotcut export approval must name the sample final audio.' }

    $blocked = $false
    try {
        & $stateScript -Action set-stage -RunId $runId -Stage sample_final_transcript | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'Final transcript processing must wait for a Shotcut export approval.' }

    & $stateScript -Action set-gate -RunId $runId -Gate shotcut_export -Decision approved -DependsOn sample-outline,sample-content-review-01,sample-final-audio | Out-Null
    & $stateScript -Action set-stage -RunId $runId -Stage sample_final_transcript | Out-Null
    & $stateScript -Action assert-audio-approved -RunId $runId -InputAudio $finalAudioPath | Out-Null
    & $stateScript -Action register-artifact -RunId $runId -ArtifactId sample-srt -Path $srtPath -DependsOn sample-final-audio,transcript | Out-Null
    & $stateScript -Action register-artifact -RunId $runId -ArtifactId sample-presentation -Path $previewPath -DependsOn sample-outline,sample-srt,sample-final-audio | Out-Null
    & $stateScript -Action register-artifact -RunId $runId -ArtifactId sample-quality-review -Path $qualityReviewPath -DependsOn sample-presentation,sample-srt,sample-final-audio | Out-Null
    & $stateScript -Action set-stage -RunId $runId -Stage sample_quality_review | Out-Null

    $blocked = $false
    try {
        & $stateScript -Action assert-full-approved -RunId $runId | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'Full-audio entrypoint must block before sample acceptance.' }

    $blocked = $false
    try {
        & $stateScript -Action set-gate -RunId $runId -Gate sample_acceptance -Decision approved -DependsOn sample-outline,sample-content-review-01,sample-final-audio,sample-srt,sample-presentation | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'Sample acceptance must include a current quality-review artifact.' }

    & $stateScript -Action set-gate -RunId $runId -Gate sample_acceptance -Decision approved -DependsOn sample-outline,sample-content-review-01,sample-final-audio,sample-srt,sample-presentation,sample-quality-review | Out-Null

    & $stateScript -Action set-stage -RunId $runId -Stage full_outline | Out-Null
    $blocked = $false
    try {
        & $stateScript -Action assert-full-approved -RunId $runId | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'The full-audio entrypoint must require a transcription stage, not only any full_* stage.' }

    & $stateScript -Action set-stage -RunId $runId -Stage full_transcript | Out-Null
    & $stateScript -Action assert-full-approved -RunId $runId | Out-Null
    & $stateScript -Action assert-audio-approved -RunId $runId -InputAudio $sourcePath | Out-Null
    $blocked = $false
    try {
        & $stateScript -Action assert-audio-approved -RunId $runId -InputAudio $finalAudioPath | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'Full transcription must be bound to the registered source audio.' }

    [IO.File]::WriteAllText($reviewRound2Path, "# Content review round 2`n`n## I-001 | resolved`n`n## I-002 | resolved`n")
    & $stateScript -Action register-artifact -RunId $runId -ArtifactId sample-content-review-02 -Path $reviewRound2Path -DependsOn sample-outline,transcript | Out-Null
    $manifest = Get-Content -Raw -Encoding utf8 $manifestPath | ConvertFrom-Json
    if ($manifest.gates.content_review.status -ne 'stale' -or $manifest.gates.shotcut_export.status -ne 'stale' -or $manifest.gates.sample_acceptance.status -ne 'stale') {
        throw 'Registering a new review round must invalidate earlier dependent approvals.'
    }
    $blocked = $false
    try {
        & $stateScript -Action register-artifact -RunId $runId -ArtifactId sample-content-review-01 -Path $reviewPath -DependsOn sample-outline,transcript | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'Registering an older content-review round after a newer one must be rejected.' }
    & $stateScript -Action set-stage -RunId $runId -Stage sample_content_review | Out-Null
    $blocked = $false
    try {
        & $stateScript -Action set-gate -RunId $runId -Gate content_review -Decision approved -DependsOn sample-outline,sample-content-review-01 | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'A content gate must reject an older review round after a newer round is registered.' }
    & $stateScript -Action set-gate -RunId $runId -Gate content_review -Decision approved -DependsOn sample-outline,sample-content-review-02 | Out-Null
    & $stateScript -Action set-stage -RunId $runId -Stage sample_shotcut | Out-Null
    & $stateScript -Action set-gate -RunId $runId -Gate shotcut_export -Decision approved -DependsOn sample-outline,sample-content-review-02,sample-final-audio | Out-Null
    & $stateScript -Action set-stage -RunId $runId -Stage sample_quality_review | Out-Null
    & $stateScript -Action set-gate -RunId $runId -Gate sample_acceptance -Decision approved -DependsOn sample-outline,sample-content-review-02,sample-final-audio,sample-srt,sample-presentation,sample-quality-review | Out-Null
    & $stateScript -Action set-stage -RunId $runId -Stage full_transcript | Out-Null

    # Older manifests did not store scope: an existing sample issue must stay sample.
    $legacyManifest = Get-Content -Raw -Encoding utf8 $manifestPath | ConvertFrom-Json
    $legacyManifest.review_items.'I-001'.PSObject.Properties.Remove('scope')
    [IO.File]::WriteAllText($manifestPath, ($legacyManifest | ConvertTo-Json -Depth 100), [Text.UTF8Encoding]::new($false))
    & $stateScript -Action set-item -RunId $runId -ItemId I-001 -ItemStatus needs_revision -Decision revise | Out-Null
    $manifest = Get-Content -Raw -Encoding utf8 $manifestPath | ConvertFrom-Json
    if ($manifest.gates.content_review.status -ne 'stale' -or $manifest.gates.shotcut_export.status -ne 'stale' -or $manifest.gates.sample_acceptance.status -ne 'stale') {
        throw 'Changing an approved content decision must invalidate audio and sample approvals.'
    }
    $blocked = $false
    try {
        & $stateScript -Action set-stage -RunId $runId -Stage full_shotcut | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'A changed content decision must close the full-recording gate.' }

    & $stateScript -Action set-item -RunId $runId -ItemId I-001 -ItemStatus accepted -Decision retain | Out-Null
    & $stateScript -Action set-stage -RunId $runId -Stage sample_content_review | Out-Null
    & $stateScript -Action set-gate -RunId $runId -Gate content_review -Decision approved -DependsOn sample-outline,sample-content-review-02 | Out-Null
    & $stateScript -Action set-stage -RunId $runId -Stage sample_shotcut | Out-Null
    & $stateScript -Action set-gate -RunId $runId -Gate shotcut_export -Decision approved -DependsOn sample-outline,sample-content-review-02,sample-final-audio | Out-Null
    & $stateScript -Action set-stage -RunId $runId -Stage sample_quality_review | Out-Null
    & $stateScript -Action set-gate -RunId $runId -Gate sample_acceptance -Decision approved -DependsOn sample-outline,sample-content-review-02,sample-final-audio,sample-srt,sample-presentation,sample-quality-review | Out-Null
    & $stateScript -Action set-stage -RunId $runId -Stage full_transcript | Out-Null

    [IO.File]::AppendAllText($finalAudioPath, ' changed')
    & $stateScript -Action reconcile -RunId $runId | Out-Null
    $manifest = Get-Content -Raw -Encoding utf8 $manifestPath | ConvertFrom-Json
    foreach ($artifactId in @('sample-srt', 'sample-presentation', 'sample-quality-review')) {
        if ($manifest.artifacts.$artifactId.status -ne 'stale') {
            throw "Changing final audio must mark downstream '$artifactId' stale."
        }
    }
    if ($manifest.gates.shotcut_export.status -ne 'stale' -or $manifest.gates.sample_acceptance.status -ne 'stale') {
        throw 'Changing final audio must invalidate Shotcut and sample approvals.'
    }
    $blocked = $false
    try {
        & $stateScript -Action assert-full-approved -RunId $runId | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'A changed final audio must block full-recording work.' }

    [IO.File]::AppendAllText($sourcePath, ' changed')
    & $stateScript -Action reconcile -RunId $runId | Out-Null
    $manifest = Get-Content -Raw -Encoding utf8 $manifestPath | ConvertFrom-Json
    foreach ($artifactId in @('sample-final-audio', 'transcript', 'captions', 'sample-outline', 'preview', 'sample-srt', 'sample-presentation', 'sample-quality-review')) {
        if ($manifest.artifacts.$artifactId.status -ne 'stale') {
            throw "Changing source audio must mark downstream '$artifactId' stale."
        }
    }
    if ($manifest.gates.content_review.status -ne 'stale' -or $manifest.gates.shotcut_export.status -ne 'stale' -or $manifest.gates.sample_acceptance.status -ne 'stale') {
        throw 'Input changes must invalidate dependent human approvals.'
    }
    $blocked = $false
    try {
        & $stateScript -Action register-artifact -RunId $runId -ArtifactId transcript -Path $transcriptPath -DependsOn source-audio | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'An unchanged stale artifact must not be silently revived by re-registration.' }
    & $stateScript -Action register-artifact -RunId $runId -ArtifactId transcript -Path $transcriptPath -DependsOn source-audio -ConfirmRebuilt | Out-Null
    $manifest = Get-Content -Raw -Encoding utf8 $manifestPath | ConvertFrom-Json
    if ($manifest.artifacts.transcript.status -ne 'current' -or $manifest.artifacts.captions.status -ne 'stale') {
        throw 'Explicitly revalidated artifacts may become current but must keep descendants stale.'
    }
    $blocked = $false
    try {
        & $stateScript -Action set-stage -RunId $runId -Stage full_shotcut | Out-Null
    } catch { $blocked = $true }
    if (-not $blocked) { throw 'A stale sample approval must block full-recording work.' }
    $serialized = Get-Content -Raw -Encoding utf8 $manifestPath
    if ($serialized.Contains('PRIVATE SOURCE SENTINEL') -or $serialized.Contains('PRIVATE TRANSCRIPT SENTINEL')) {
        throw 'The local state file must not include source media or transcript content.'
    }

    Write-Output 'PASS: workflow state gates, dependency invalidation, and privacy metadata'
} finally {
    $fullRunDir = [IO.Path]::GetFullPath($runDir)
    $allowedRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot '.local/video')) + [IO.Path]::DirectorySeparatorChar
    if (-not $fullRunDir.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove test output outside .local/video: $fullRunDir"
    }
    if (Test-Path -LiteralPath $fullRunDir) {
        Remove-Item -LiteralPath $fullRunDir -Recurse -Force
    }
}
