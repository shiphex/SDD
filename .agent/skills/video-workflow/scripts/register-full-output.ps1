[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('draft', 'audio', 'delivery')][string]$Action,
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')][string]$RunId,
    [string]$CutMap,
    [string]$Audio,
    [string]$Transcript,
    [string]$Alignment,
    [string]$Srt,
    [string]$ScenePlan,
    [string]$Video,
    [string]$QualityReview
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$state = Join-Path $PSScriptRoot 'workflow-state.ps1'
$manifestPath = Join-Path $repoRoot ".local/video/$RunId/workflow.json"
if (-not (Test-Path -LiteralPath $manifestPath)) { throw "Missing workflow state for '$RunId'." }
$script:RunDirAbsolute = [IO.Path]::GetFullPath((Join-Path $repoRoot ".local/video/$RunId"))
$script:RunPrefix = $script:RunDirAbsolute.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar

function Assert-RunFile {
    param([string]$InputPath)
    if (-not $InputPath -or -not (Test-Path -LiteralPath $InputPath -PathType Leaf)) { throw "Missing output: $InputPath" }
    $full = (Resolve-Path -LiteralPath $InputPath).Path
    if (-not $full.StartsWith($script:RunPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Full outputs must stay in the current ignored run directory.'
    }
    return $full
}

function Register-ScenePlan {
    param([string]$PlanPath, [string]$Prefix, [string]$AudioArtifact)
    $scenePath = (Resolve-Path -LiteralPath $PlanPath).Path
    $sceneDir = Split-Path -Parent $scenePath
    $sceneData = Get-Content -Raw -Encoding UTF8 -LiteralPath $scenePath | ConvertFrom-Json
    if (-not $sceneData.scenes -or @($sceneData.scenes).Count -eq 0) { throw 'Scene plan has no scenes.' }
    $images = [System.Collections.Generic.List[string]]::new()
    foreach ($scene in $sceneData.scenes) {
        $image = [string]$scene.image
        if (-not [IO.Path]::IsPathRooted($image)) { $image = Join-Path $sceneDir $image }
        $image = [IO.Path]::GetFullPath($image)
        if (-not $image.StartsWith($script:RunPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Scene images must stay in the current ignored run directory.' }
        if (-not (Test-Path -LiteralPath $image -PathType Leaf)) { throw "Missing scene image: $image" }
        if (-not $images.Contains($image)) { $images.Add($image) }
    }
    $imageIds = @()
    for ($index = 0; $index -lt $images.Count; $index++) {
        $imageId = '{0}-scene-image-{1:D3}' -f $Prefix, ($index + 1)
        & $state -Action register-artifact -RunId $RunId -ArtifactId $imageId -Path $images[$index] | Out-Null
        $imageIds += $imageId
    }
    $planId = "$Prefix-scene-plan"
    $dependencies = @('full-outline', $AudioArtifact) + $imageIds
    & $state -Action register-artifact -RunId $RunId -ArtifactId $planId -Path $PlanPath -DependsOn $dependencies -ConfirmRebuilt | Out-Null
    return $planId
}

function Get-CutMapDependencies {
    param([string]$MapPath)
    $data = Get-Content -Raw -Encoding UTF8 -LiteralPath $MapPath | ConvertFrom-Json
    if ($data.schema_version -and $data.schema_version -notin @(1,2,3)) { throw 'Unknown cut map schema.' }
    if ($data.schema_version -eq 3) {
        if (-not $data.timeline -or -not $data.source_map -or @($data.sources.PSObject.Properties).Count -ne 1) { throw 'Retime map requires timeline and fixed baseline provenance.' }
        & $state -Action assert-retime-approved -RunId $RunId -Path $data.timeline | Out-Null
        $timeline = Get-Content -Raw -Encoding UTF8 -LiteralPath $data.timeline | ConvertFrom-Json
        foreach ($pair in @(@{actual=$data.sources.baseline; expected=$timeline.source}, @{actual=$data.source_map; expected=$timeline.source_map})) {
            $actual = $pair.actual; $expected = $pair.expected
            if (-not $actual -or $actual.artifact_id -ne $expected.artifact_id -or $actual.sha256 -ne $expected.sha256) { throw 'Retime map source differs from approved timeline.' }
            $actualPath = [string]$actual.path
            if (-not [IO.Path]::IsPathRooted($actualPath)) { $actualPath = Join-Path (Split-Path -Parent $MapPath) $actualPath }
            $expectedPath = [string]$expected.path
            if (-not [IO.Path]::IsPathRooted($expectedPath)) { $expectedPath = Join-Path (Split-Path -Parent $data.timeline) $expectedPath }
            if (-not ([IO.Path]::GetFullPath($actualPath)).Equals([IO.Path]::GetFullPath($expectedPath), [StringComparison]::OrdinalIgnoreCase)) { throw 'Retime map source path differs from approved timeline.' }
        }
        return @('full-retime-timeline','full-retime-baseline-audio','full-retime-baseline-map')
    }
    if ($data.schema_version -ne 2) { return @('full-source-wav') }
    if (-not $data.timeline -or -not $data.sources) { throw 'Composite map requires its timeline and sources.' }
    & $state -Action assert-assembly-approved -RunId $RunId -Path $data.timeline | Out-Null
    $timeline = Get-Content -Raw -Encoding UTF8 -LiteralPath $data.timeline | ConvertFrom-Json
    $current = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
    if (@($data.sources.PSObject.Properties).Count -ne @($timeline.sources.PSObject.Properties).Count) { throw 'Composite source set differs from the approved timeline.' }
    $dependencies = @('full-assembly-timeline')
    foreach ($entry in $data.sources.PSObject.Properties) {
        $source = $entry.Value
        $expected = $timeline.sources.PSObject.Properties[$entry.Name]
        $artifact = $current.artifacts.PSObject.Properties[[string]$source.artifact_id]
        if ($null -eq $expected -or $null -eq $artifact -or $artifact.Value.status -ne 'current' -or
            $source.artifact_id -ne $expected.Value.artifact_id -or
            $source.sha256 -ne $artifact.Value.sha256 -or $source.sha256 -ne $expected.Value.sha256) {
            throw 'Composite source hash or registration differs from the approved timeline.'
        }
        $mapSourcePath = [string]$source.path
        if (-not [IO.Path]::IsPathRooted($mapSourcePath)) { $mapSourcePath = Join-Path (Split-Path -Parent $MapPath) $mapSourcePath }
        $registered = [string]$artifact.Value.path
        if (-not [IO.Path]::IsPathRooted($registered)) { $registered = Join-Path $repoRoot $registered }
        if (-not ([IO.Path]::GetFullPath($mapSourcePath)).Equals([IO.Path]::GetFullPath($registered), [StringComparison]::OrdinalIgnoreCase)) { throw 'Composite source path differs from registration.' }
        $dependencies += [string]$source.artifact_id
    }
    return @($dependencies | Select-Object -Unique)
}

& $state -Action reconcile -RunId $RunId | Out-Null
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
if ($Action -eq 'draft') {
    if ($manifest.stage -ne 'full_content_review') { throw 'Draft registration requires full_content_review.' }
    if ($manifest.gates.sample_acceptance.status -ne 'approved' -or $manifest.gates.full_ai_edit_authorization.status -ne 'approved') { throw 'Full draft requires sample acceptance and explicit full AI authorization.' }
    foreach ($path in @($CutMap, $Audio, $Srt, $ScenePlan, $Video)) { Assert-RunFile $path | Out-Null }
    $mapSources = @(Get-CutMapDependencies $CutMap)
    & $state -Action register-artifact -RunId $RunId -ArtifactId full-draft-cut-map -Path $CutMap -DependsOn $mapSources -ConfirmRebuilt | Out-Null
    & $state -Action register-artifact -RunId $RunId -ArtifactId full-draft-audio -Path $Audio -DependsOn (@($mapSources) + @('full-draft-cut-map')) -ConfirmRebuilt | Out-Null
    $captionDependencies = @('full-draft-audio')
    if ($Transcript -or $Alignment) {
        if (-not $Transcript -or -not $Alignment) { throw 'Draft transcript and alignment must be supplied together.' }
        foreach ($path in @($Transcript, $Alignment)) { Assert-RunFile $path | Out-Null }
        & $state -Action register-artifact -RunId $RunId -ArtifactId full-draft-transcript -Path $Transcript -DependsOn full-draft-audio -ConfirmRebuilt | Out-Null
        & $state -Action register-artifact -RunId $RunId -ArtifactId full-draft-alignment -Path $Alignment -DependsOn full-draft-audio,full-draft-transcript -ConfirmRebuilt | Out-Null
        $captionDependencies += @('full-draft-transcript', 'full-draft-alignment')
    }
    & $state -Action register-artifact -RunId $RunId -ArtifactId full-draft-srt -Path $Srt -DependsOn $captionDependencies -ConfirmRebuilt | Out-Null
    $sceneId = Register-ScenePlan -PlanPath $ScenePlan -Prefix full-draft -AudioArtifact full-draft-audio
    & $state -Action register-artifact -RunId $RunId -ArtifactId full-draft-mp4 -Path $Video -DependsOn @('full-outline','full-draft-audio','full-draft-srt',$sceneId) -ConfirmRebuilt | Out-Null
    if ($QualityReview) {
        Assert-RunFile $QualityReview | Out-Null
        & $state -Action register-artifact -RunId $RunId -ArtifactId full-draft-quality-review -Path $QualityReview -DependsOn full-draft-mp4,full-draft-srt,full-draft-audio -ConfirmRebuilt | Out-Null
    }
    Write-Output "Recorded internal draft for '$RunId'. Content and full acceptance are unchanged."
    return
}
if ($manifest.gates.full_content_review.status -ne 'approved') { throw 'Current content review approval is required.' }

if ($Action -eq 'audio') {
    if ($manifest.stage -ne 'full_ai_edit') { throw 'AI audio registration requires full_ai_edit.' }
    if (-not $CutMap -or -not $Audio) { throw '-CutMap and -Audio are required for audio registration.' }
    foreach ($path in @($CutMap, $Audio)) { Assert-RunFile $path | Out-Null }
    $mapSources = @(Get-CutMapDependencies $CutMap)
    & $state -Action register-artifact -RunId $RunId -ArtifactId full-cut-map -Path $CutMap -DependsOn $mapSources -ConfirmRebuilt | Out-Null
    & $state -Action register-artifact -RunId $RunId -ArtifactId full-final-audio -Path $Audio -DependsOn (@($mapSources) + @('source-audio','full-outline','full-cut-map')) -ConfirmRebuilt | Out-Null
    $dependencies = @($manifest.gates.full_content_review.depends_on) + @('full-cut-map', 'full-final-audio') | Select-Object -Unique
    & $state -Action set-gate -RunId $RunId -Gate full_ai_audio_export -Decision approved -DependsOn $dependencies | Out-Null
    & $state -Action set-stage -RunId $RunId -Stage full_final_transcript | Out-Null
    Write-Output "Recorded AI full audio export for '$RunId'. Sample acceptance is unchanged."
    return
}

if ($manifest.stage -notin @('full_final_transcript', 'full_captions', 'full_web_demo', 'full_quality_review')) {
    throw 'Full delivery registration requires the final-transcript stage or later.'
}
if ($manifest.gates.full_ai_audio_export.status -ne 'approved' -and $manifest.gates.shotcut_export.status -ne 'approved') {
    throw 'A current full audio export is required.'
}
foreach ($value in @($Transcript, $Alignment, $Srt, $ScenePlan, $Video, $QualityReview)) {
    if (-not $value) { throw 'Delivery requires -Transcript, -Alignment, -Srt, -ScenePlan, -Video, and -QualityReview.' }
    Assert-RunFile $value | Out-Null
}
& $state -Action register-artifact -RunId $RunId -ArtifactId full-final-transcript -Path $Transcript -DependsOn full-final-audio | Out-Null
& $state -Action register-artifact -RunId $RunId -ArtifactId full-final-alignment -Path $Alignment -DependsOn full-final-audio,full-final-transcript | Out-Null
& $state -Action register-artifact -RunId $RunId -ArtifactId full-srt -Path $Srt -DependsOn full-final-audio,full-final-transcript,full-final-alignment | Out-Null
$sceneId = Register-ScenePlan -PlanPath $ScenePlan -Prefix full -AudioArtifact full-final-audio
& $state -Action register-artifact -RunId $RunId -ArtifactId full-presentation -Path $Video -DependsOn full-outline,full-final-audio,full-srt,full-scene-plan | Out-Null
& $state -Action register-artifact -RunId $RunId -ArtifactId full-quality-review -Path $QualityReview -DependsOn full-presentation,full-srt,full-final-audio | Out-Null
& $state -Action set-stage -RunId $RunId -Stage full_quality_review | Out-Null
Write-Output "Recorded full delivery for '$RunId'. Sample acceptance is unchanged."
