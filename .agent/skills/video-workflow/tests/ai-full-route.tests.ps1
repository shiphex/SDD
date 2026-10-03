$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$state = Join-Path $PSScriptRoot '../scripts/workflow-state.ps1'
$register = Join-Path $PSScriptRoot '../scripts/register-sample-output.ps1'
$media = Join-Path $PSScriptRoot '../scripts/media_tools.py'
$runId = 'ai-full-test-' + [Guid]::NewGuid().ToString('N')
$runDir = Join-Path $repoRoot ".local/video/$runId"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
function File([string]$Name, [string]$Text) {
    $path = Join-Path $runDir $Name
    [IO.File]::WriteAllText($path, $Text)
    return $path
}
function Must-Block([scriptblock]$Call, [string]$Reason) {
    $blocked = $false
    try { & $Call | Out-Null } catch { $blocked = $true }
    if (-not $blocked) { throw $Reason }
}
try {
    $source = File 'source.wav' 'source'
    $fixture = File 'fixture.py' "import sys,wave; w=wave.open(sys.argv[1],'wb'); w.setparams((1,2,16000,0,'NONE','')); w.writeframes(bytes(181*16000*2)); w.close()"
    & python $fixture $source
    if ($LASTEXITCODE -ne 0) { throw 'WAV fixture failed.' }
    $outline = File 'outline.md' '# P01'
    $review = File 'review.md' '# Review'
    $brief = File 'brief.md' '# Explicit AI full editing authorization'
    $sample = File 'sample.wav' 'sample'
    $map = File 'map.json' '{}'
    $srt = File 'draft.srt' 'caption'
    $video = File 'draft.mp4' 'video'
    $quality = File 'quality.md' 'automatic checks only'
    $image = File 'P01.png' 'image'
    $scenes = File 'scenes.json' '{"scenes":[{"start":0,"end":1,"image":"P01.png"}]}'
    & $state -Action initialize -RunId $runId -SourceAudio $source | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId run-brief -Path $brief | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-outline -Path $outline -DependsOn source-audio | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-content-review-01 -Path $review -DependsOn sample-outline | Out-Null
    & $state -Action set-stage -RunId $runId -Stage sample_content_review | Out-Null
    & $state -Action set-gate -RunId $runId -Gate content_review -Decision approved -DependsOn sample-outline,sample-content-review-01 | Out-Null
    & $state -Action set-stage -RunId $runId -Stage sample_ai_edit | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-cut-map -Path $map -DependsOn source-audio | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-final-audio -Path $sample -DependsOn sample-cut-map | Out-Null
    & $state -Action set-gate -RunId $runId -Gate ai_audio_export -Decision approved -DependsOn sample-outline,sample-content-review-01,sample-cut-map,sample-final-audio | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-srt -Path $srt -DependsOn sample-final-audio | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-presentation -Path $video -DependsOn sample-srt | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId sample-quality-review -Path $quality -DependsOn sample-presentation | Out-Null
    Must-Block { & $state -Action set-gate -RunId $runId -Gate full_ai_edit_authorization -Decision approved -DependsOn source-audio,run-brief } 'Full AI authorization must require accepted sample.'
    & $state -Action set-stage -RunId $runId -Stage sample_quality_review | Out-Null
    & $state -Action set-gate -RunId $runId -Gate sample_acceptance -Decision approved -DependsOn sample-outline,sample-content-review-01,sample-cut-map,sample-final-audio,sample-srt,sample-presentation,sample-quality-review | Out-Null
    & $state -Action set-stage -RunId $runId -Stage full_content_review | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId full-source-wav -Path $source -DependsOn source-audio | Out-Null
    Must-Block { & $state -Action assert-full-edit-approved -RunId $runId -InputAudio $source } 'Full editing must require explicit full authorization.'
    & $state -Action set-gate -RunId $runId -Gate full_ai_edit_authorization -Decision approved -DependsOn source-audio,run-brief | Out-Null
    & $state -Action assert-full-edit-approved -RunId $runId -InputAudio $source | Out-Null
    $pickup = File 'pickup.wav' 'pickup'
    $pickupAuthorization = File 'pickup-authorization.md' 'explicit pickup editing authorization'
    & $state -Action register-artifact -RunId $runId -ArtifactId full-pickup-source-audio -Path $pickup | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId full-pickup-wav -Path $pickup -DependsOn full-pickup-source-audio | Out-Null
    Must-Block { & $state -Action assert-audio-approved -RunId $runId -InputAudio $pickup } 'Pickup transcription requires its explicit authorization artifact.'
    & $state -Action register-artifact -RunId $runId -ArtifactId full-pickup-authorization -Path $pickupAuthorization -DependsOn full-pickup-source-audio | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId full-pickup-wav -Path $pickup -DependsOn full-pickup-source-audio,full-pickup-authorization | Out-Null
    & $state -Action assert-audio-approved -RunId $runId -InputAudio $pickup | Out-Null
    [IO.File]::AppendAllText($pickup, ' changed')
    Must-Block { & $state -Action assert-audio-approved -RunId $runId -InputAudio $pickup } 'Pickup source hash changes must invalidate authorization.'
    $edits = File 'edits.json' '{"cuts":[{"start":0,"end":1,"reason":"pause"}]}'
    $builtAudio = Join-Path $runDir 'built.wav'
    $builtMap = Join-Path $runDir 'built-map.json'
    & python $media build-audio --scope full --run-id $runId --source $source --edits $edits --audio $builtAudio --map $builtMap
    if ($LASTEXITCODE -ne 0) { throw 'Authorized full CLI edit must succeed.' }
    $actualMap = Get-Content -Raw -Encoding UTF8 $builtMap | ConvertFrom-Json
    if ($actualMap.output_duration -ne 180 -or $actualMap.kept[0].source_start -ne 1) { throw 'Full CLI must preserve source-time mapping.' }
    $other = File 'other.wav' 'source'
    Must-Block { & $state -Action assert-full-edit-approved -RunId $runId -InputAudio $other } 'An unregistered source path must be rejected.'
    & $state -Action set-item -RunId $runId -ItemId I-101 -ItemStatus pending -Decision retain | Out-Null
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($manifest.gates.sample_acceptance.status -ne 'approved') { throw 'A full-only issue must preserve accepted sample.' }
    & $state -Action set-item -RunId $runId -ItemId I-101 -ItemStatus resolved -Decision retain | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId full-outline -Path $outline -DependsOn source-audio | Out-Null
    $draft = File 'full-draft.wav' 'edited source'
    $fullSrt = File 'full-draft.srt' 'full caption'
    $fullVideo = File 'full-draft.mp4' 'full video'
    & $register -Scope full -Action draft -RunId $runId -CutMap $map -Audio $draft -Srt $fullSrt -ScenePlan $scenes -Video $fullVideo | Out-Null
    & $state -Action assert-audio-approved -RunId $runId -InputAudio $draft | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId full-preview-baseline-cut-map -Path $builtMap -DependsOn full-source-wav | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId full-preview-baseline-audio -Path $builtAudio -DependsOn full-preview-baseline-cut-map | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId full-pickup-authorization -Path $pickupAuthorization -DependsOn full-pickup-source-audio -ConfirmRebuilt | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId full-pickup-wav -Path $pickup -DependsOn full-pickup-source-audio,full-pickup-authorization -ConfirmRebuilt | Out-Null
    $sources = @{
        baseline = @{ artifact_id='full-preview-baseline-audio'; path=$builtAudio; sha256=(Get-FileHash -LiteralPath $builtAudio -Algorithm SHA256).Hash.ToLowerInvariant(); duration=180 }
        pickup = @{ artifact_id='full-pickup-wav'; path=$pickup; sha256=(Get-FileHash -LiteralPath $pickup -Algorithm SHA256).Hash.ToLowerInvariant(); duration=1 }
    }
    $timeline = File 'assembly.json' (ConvertTo-Json @{sources=$sources; segments=@(@{source_id='baseline';start=0;end=1})} -Depth 8)
    & $state -Action register-artifact -RunId $runId -ArtifactId full-assembly-timeline -Path $timeline -DependsOn full-preview-baseline-audio,full-pickup-wav | Out-Null
    & $state -Action assert-assembly-approved -RunId $runId -Path $timeline | Out-Null
    $compositeMap = File 'composite-map.json' (ConvertTo-Json @{schema_version=2; timeline=$timeline; sources=$sources} -Depth 8)
    [IO.File]::AppendAllText($draft, ' rebuilt composite')
    & $register -Scope full -Action draft -RunId $runId -CutMap $compositeMap -Audio $draft -Srt $fullSrt -ScenePlan $scenes -Video $fullVideo | Out-Null
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    foreach ($id in @('full-preview-baseline-audio','full-pickup-wav','full-assembly-timeline')) {
        if ($id -notin $manifest.artifacts.'full-draft-cut-map'.depends_on) { throw "Composite map must retain dependency $id" }
    }
    $sources.pickup.sha256 = '0' * 64
    $badComposite = File 'bad-composite.json' (ConvertTo-Json @{schema_version=2; timeline=$timeline; sources=$sources} -Depth 8)
    Must-Block { & $register -Scope full -Action draft -RunId $runId -CutMap $badComposite -Audio $draft -Srt $fullSrt -ScenePlan $scenes -Video $fullVideo } 'Composite registration must reject a changed source hash.'
    $unknownMap = File 'unknown-map.json' '{"schema_version":99}'
    Must-Block { & $register -Scope full -Action draft -RunId $runId -CutMap $unknownMap -Audio $draft -Srt $fullSrt -ScenePlan $scenes -Video $fullVideo } 'Unknown map schemas must not silently discard source dependencies.'
    & $state -Action register-artifact -RunId $runId -ArtifactId full-retime-baseline-map -Path $compositeMap -DependsOn full-assembly-timeline,full-preview-baseline-audio,full-pickup-wav | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId full-retime-baseline-audio -Path $draft -DependsOn full-retime-baseline-map | Out-Null
    $retimeSource = @{artifact_id='full-retime-baseline-audio';path=$draft;sha256=(Get-FileHash -LiteralPath $draft -Algorithm SHA256).Hash.ToLowerInvariant()}
    $retimeBaseMap = @{artifact_id='full-retime-baseline-map';path=$compositeMap;sha256=(Get-FileHash -LiteralPath $compositeMap -Algorithm SHA256).Hash.ToLowerInvariant()}
    $retimeData = @{source=$retimeSource;source_map=$retimeBaseMap;segments=@(@{start=0;end=1;kind='speech';tempo=1.25})}
    $retimeTimeline = File 'retime.json' (ConvertTo-Json $retimeData -Depth 8)
    Must-Block { & $state -Action assert-retime-approved -RunId $runId -Path $retimeTimeline } 'Retime must require registered timeline.'
    & $state -Action register-artifact -RunId $runId -ArtifactId full-retime-timeline -Path $retimeTimeline -DependsOn full-retime-baseline-audio,full-retime-baseline-map | Out-Null
    & $state -Action assert-retime-approved -RunId $runId -Path $retimeTimeline | Out-Null
    $retimeSource.sha256='0'*64
    [IO.File]::WriteAllText($retimeTimeline,(ConvertTo-Json $retimeData -Depth 8))
    & $state -Action register-artifact -RunId $runId -ArtifactId full-retime-timeline -Path $retimeTimeline -DependsOn full-retime-baseline-audio,full-retime-baseline-map | Out-Null
    Must-Block { & $state -Action assert-retime-approved -RunId $runId -Path $retimeTimeline } 'Retime source hash must match registration.'
    $retimeSource.sha256=(Get-FileHash -LiteralPath $draft -Algorithm SHA256).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText($retimeTimeline,(ConvertTo-Json $retimeData -Depth 8))
    & $state -Action register-artifact -RunId $runId -ArtifactId full-retime-timeline -Path $retimeTimeline -DependsOn full-retime-baseline-audio,full-retime-baseline-map | Out-Null
    $retimeMap = File 'retime-map.json' (ConvertTo-Json @{schema_version=3;timeline=$retimeTimeline;sources=@{baseline=$retimeSource};source_map=$retimeBaseMap} -Depth 8)
    $retimed = File 'retimed.wav' 'retimed audio'
    & $register -Scope full -Action draft -RunId $runId -CutMap $retimeMap -Audio $retimed -Srt $fullSrt -ScenePlan $scenes -Video $fullVideo | Out-Null
    [IO.File]::AppendAllText($retimeTimeline,' ')
    & $state -Action reconcile -RunId $runId | Out-Null
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($manifest.artifacts.'full-draft-mp4'.status -ne 'stale') { throw 'Retime timeline change must invalidate downstream video.' }
    if ($manifest.gates.sample_acceptance.status -ne 'approved') { throw 'Speech retiming must preserve original sample acceptance.' }
    [IO.File]::AppendAllText($pickup, ' changed again')
    & $state -Action reconcile -RunId $runId | Out-Null
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($manifest.artifacts.'full-draft-audio'.status -ne 'stale' -or $manifest.artifacts.'full-draft-srt'.status -ne 'stale' -or $manifest.artifacts.'full-draft-mp4'.status -ne 'stale') { throw 'Pickup change must invalidate assembled audio, captions and video.' }
    if ($manifest.gates.sample_acceptance.status -ne 'approved') { throw 'Pickup changes must preserve the accepted sample.' }
    [IO.File]::AppendAllText($draft, ' rebuilt legacy')
    & $register -Scope full -Action draft -RunId $runId -CutMap $map -Audio $draft -Srt $fullSrt -ScenePlan $scenes -Video $fullVideo | Out-Null
    Must-Block { & $state -Action assert-audio-approved -RunId $runId -InputAudio $other } 'Draft transcription must match the registered draft.'
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($manifest.gates.full_content_review.status -ne 'pending') { throw 'Draft must not approve full content.' }
    if ($manifest.gates.full_ai_audio_export.status -ne 'pending') { throw 'Draft must not approve final audio.' }
    [IO.File]::AppendAllText($draft, ' changed')
    & $state -Action reconcile -RunId $runId | Out-Null
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($manifest.artifacts.'full-draft-srt'.status -ne 'stale' -or $manifest.artifacts.'full-draft-mp4'.status -ne 'stale') { throw 'Draft audio changes must invalidate SRT and video.' }
    [IO.File]::AppendAllText($fullSrt, ' rebuilt')
    [IO.File]::AppendAllText($fullVideo, ' rebuilt')
    & $register -Scope full -Action draft -RunId $runId -CutMap $map -Audio $draft -Srt $fullSrt -ScenePlan $scenes -Video $fullVideo | Out-Null
    [IO.File]::AppendAllText($image, ' changed')
    & $state -Action reconcile -RunId $runId | Out-Null
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($manifest.artifacts.'full-draft-mp4'.status -ne 'stale') { throw 'Image changes must invalidate video.' }
    if ($manifest.artifacts.'full-draft-audio'.status -ne 'current') { throw 'Image changes must leave audio current.' }
    & $state -Action register-artifact -RunId $runId -ArtifactId full-content-review-01 -Path $review -DependsOn full-outline | Out-Null
    & $state -Action set-gate -RunId $runId -Gate full_content_review -Decision approved -DependsOn full-outline,full-content-review-01 | Out-Null
    & $state -Action set-stage -RunId $runId -Stage full_ai_edit | Out-Null
    & $register -Scope full -Action audio -RunId $runId -CutMap $map -Audio $draft | Out-Null
    & $state -Action assert-audio-approved -RunId $runId -InputAudio $draft | Out-Null
    $review2 = File 'review2.md' '# Full review round 2'
    & $state -Action register-artifact -RunId $runId -ArtifactId full-content-review-02 -Path $review2 -DependsOn full-outline | Out-Null
    & $state -Action set-stage -RunId $runId -Stage full_content_review | Out-Null
    & $state -Action set-gate -RunId $runId -Gate full_content_review -Decision approved -DependsOn full-outline,full-content-review-02 | Out-Null
    $manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($manifest.gates.full_ai_audio_export.status -ne 'stale') { throw 'New full review must invalidate earlier AI export.' }
    Must-Block { & $state -Action set-stage -RunId $runId -Stage full_final_transcript } 'An export from an earlier review must not authorize final transcription.'
    [IO.File]::AppendAllText($source, ' changed')
    Must-Block { & $state -Action assert-full-edit-approved -RunId $runId -InputAudio $source } 'Changed source must invalidate full authorization.'
    Write-Output 'PASS: full authorization, draft, final AI audio, path/hash and invalidation checks'
} finally {
    $absolute = [IO.Path]::GetFullPath($runDir)
    $allowed = [IO.Path]::GetFullPath((Join-Path $repoRoot '.local/video')) + [IO.Path]::DirectorySeparatorChar
    if (-not $absolute.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe test cleanup path.' }
    if (Test-Path -LiteralPath $absolute) { Remove-Item -LiteralPath $absolute -Recurse -Force }
}
