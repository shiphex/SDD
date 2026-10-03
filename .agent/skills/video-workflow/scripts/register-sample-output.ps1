[CmdletBinding()]
param(
    [ValidateSet('sample', 'full')][string]$Scope = 'sample',
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
if ($Scope -eq 'full') {
    $forward = @{} + $PSBoundParameters
    $forward.Remove('Scope')
    & (Join-Path $PSScriptRoot 'register-full-output.ps1') @forward
    return
}
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
        throw 'Sample outputs must stay in the current ignored run directory.'
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
    $dependencies = @('sample-outline', $AudioArtifact) + $imageIds
    & $state -Action register-artifact -RunId $RunId -ArtifactId $planId -Path $PlanPath -DependsOn $dependencies -ConfirmRebuilt | Out-Null
    return $planId
}

& $state -Action reconcile -RunId $RunId | Out-Null
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
if ($Action -eq 'draft') {
    if ($manifest.stage -ne 'sample_content_review') { throw 'Draft registration requires sample_content_review.' }
    foreach ($path in @($CutMap, $Audio, $Srt, $ScenePlan, $Video)) { Assert-RunFile $path | Out-Null }
    $mapSource = if ($manifest.artifacts.PSObject.Properties.Name -contains 'sample-audio') { 'sample-audio' } else { 'source-audio' }
    & $state -Action register-artifact -RunId $RunId -ArtifactId sample-draft-cut-map -Path $CutMap -DependsOn $mapSource | Out-Null
    & $state -Action register-artifact -RunId $RunId -ArtifactId sample-draft-audio -Path $Audio -DependsOn $mapSource,sample-draft-cut-map | Out-Null
    & $state -Action register-artifact -RunId $RunId -ArtifactId sample-draft-srt -Path $Srt -DependsOn sample-draft-audio | Out-Null
    $sceneId = Register-ScenePlan -PlanPath $ScenePlan -Prefix sample-draft -AudioArtifact sample-draft-audio
    & $state -Action register-artifact -RunId $RunId -ArtifactId sample-draft-mp4 -Path $Video -DependsOn @('sample-outline','sample-draft-audio','sample-draft-srt',$sceneId) | Out-Null
    Write-Output "Recorded internal draft for '$RunId'. Content and sample acceptance are unchanged."
    return
}
if ($manifest.gates.content_review.status -ne 'approved') { throw 'Current content review approval is required.' }

if ($Action -eq 'audio') {
    if ($manifest.stage -ne 'sample_ai_edit') { throw 'AI audio registration requires sample_ai_edit.' }
    if (-not $CutMap -or -not $Audio) { throw '-CutMap and -Audio are required for audio registration.' }
    foreach ($path in @($CutMap, $Audio)) { Assert-RunFile $path | Out-Null }
    $mapSource = if ($manifest.artifacts.PSObject.Properties.Name -contains 'sample-audio') { 'sample-audio' } else { 'source-audio' }
    & $state -Action register-artifact -RunId $RunId -ArtifactId sample-cut-map -Path $CutMap -DependsOn $mapSource | Out-Null
    & $state -Action register-artifact -RunId $RunId -ArtifactId sample-final-audio -Path $Audio -DependsOn source-audio,sample-outline,sample-cut-map | Out-Null
    $dependencies = @($manifest.gates.content_review.depends_on) + @('sample-cut-map', 'sample-final-audio') | Select-Object -Unique
    & $state -Action set-gate -RunId $RunId -Gate ai_audio_export -Decision approved -DependsOn $dependencies | Out-Null
    & $state -Action set-stage -RunId $RunId -Stage sample_final_transcript | Out-Null
    Write-Output "Recorded AI sample audio export for '$RunId'. Sample acceptance is unchanged."
    return
}

if ($manifest.stage -notin @('sample_final_transcript', 'sample_captions', 'sample_web_demo', 'sample_quality_review')) {
    throw 'Sample delivery registration requires the final-transcript stage or later.'
}
if ($manifest.gates.ai_audio_export.status -ne 'approved' -and $manifest.gates.shotcut_export.status -ne 'approved') {
    throw 'A current sample audio export is required.'
}
foreach ($value in @($Transcript, $Alignment, $Srt, $ScenePlan, $Video, $QualityReview)) {
    if (-not $value) { throw 'Delivery requires -Transcript, -Alignment, -Srt, -ScenePlan, -Video, and -QualityReview.' }
    Assert-RunFile $value | Out-Null
}
& $state -Action register-artifact -RunId $RunId -ArtifactId sample-final-transcript -Path $Transcript -DependsOn sample-final-audio | Out-Null
& $state -Action register-artifact -RunId $RunId -ArtifactId sample-final-alignment -Path $Alignment -DependsOn sample-final-audio,sample-final-transcript | Out-Null
& $state -Action register-artifact -RunId $RunId -ArtifactId sample-srt -Path $Srt -DependsOn sample-final-audio,sample-final-transcript,sample-final-alignment | Out-Null
$sceneId = Register-ScenePlan -PlanPath $ScenePlan -Prefix sample -AudioArtifact sample-final-audio
& $state -Action register-artifact -RunId $RunId -ArtifactId sample-presentation -Path $Video -DependsOn sample-outline,sample-final-audio,sample-srt,sample-scene-plan | Out-Null
& $state -Action register-artifact -RunId $RunId -ArtifactId sample-quality-review -Path $QualityReview -DependsOn sample-presentation,sample-srt,sample-final-audio | Out-Null
& $state -Action set-stage -RunId $RunId -Stage sample_quality_review | Out-Null
Write-Output "Recorded sample delivery for '$RunId'. Sample acceptance is unchanged."
