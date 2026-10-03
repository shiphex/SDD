$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$state = Join-Path $PSScriptRoot '../scripts/workflow-state.ps1'
$runId = 'reference-test-' + [Guid]::NewGuid().ToString('N')
$runDir = Join-Path $repo ".local/video/$runId"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
function Must-Block([scriptblock]$Call) {
    $blocked = $false
    try { & $Call | Out-Null } catch { $blocked = $true }
    if (-not $blocked) { throw 'Expected reference snapshot operation to be rejected.' }
}
try {
    $source = Join-Path $runDir 'live.md'
    $report = Join-Path $runDir 'report.md'
    [IO.File]::WriteAllText($source, 'Reviewed source content')
    [IO.File]::WriteAllText($report, 'Existing accepted report')
    & $state -Action initialize -RunId $runId -SourceAudio $source | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId project-plan -Path $source | Out-Null
    & $state -Action register-artifact -RunId $runId -ArtifactId report -Path $report -DependsOn project-plan | Out-Null
    $unapproved = Join-Path $runDir 'accepted/unapproved.md'
    Must-Block { & $state -Action snapshot-reference -RunId $runId -ArtifactId project-plan -Path $unapproved }
    if (Test-Path -LiteralPath $unapproved) { throw 'Unapproved source was snapshotted.' }
    & $state -Action set-gate -RunId $runId -Gate reference_review -Decision approved -DependsOn project-plan,report | Out-Null
    $snapshot = Join-Path $runDir 'accepted/source.md'
    & $state -Action snapshot-reference -RunId $runId -ArtifactId project-plan -Path $snapshot | Out-Null
    $m = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($m.artifacts.'project-plan'.sha256 -ne (Get-FileHash -LiteralPath $source).Hash.ToLowerInvariant()) { throw 'Snapshot changed source hash.' }
    if ($m.artifacts.'project-plan'.snapshot_of -ne ".local/video/$runId/live.md") { throw 'Snapshot origin missing.' }
    if ($m.artifacts.report.status -ne 'current' -or $m.gates.reference_review.status -ne 'approved') { throw 'Immutable reference move invalidated accepted outputs.' }
    Must-Block { & $state -Action snapshot-reference -RunId $runId -ArtifactId project-plan -Path $snapshot }
    Must-Block { & $state -Action snapshot-reference -RunId $runId -ArtifactId source-audio -Path (Join-Path $runDir 'media.md') }
    $outside = Join-Path (Split-Path -Parent $runDir) "$runId-outside.md"
    Must-Block { & $state -Action snapshot-reference -RunId $runId -ArtifactId project-plan -Path $outside }
    if (Test-Path -LiteralPath $outside) { throw 'Snapshot escaped current run.' }
    [IO.File]::WriteAllText($source, 'New source facts')
    & $state -Action reconcile -RunId $runId | Out-Null
    $m = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($m.gates.reference_review.status -ne 'approved') { throw 'Live document maintenance changed archived acceptance.' }
    & $state -Action register-artifact -RunId $runId -ArtifactId project-plan -Path $source | Out-Null
    $m = Get-Content -Raw -Encoding UTF8 (Join-Path $runDir 'workflow.json') | ConvertFrom-Json
    if ($m.artifacts.report.status -ne 'stale' -or $m.gates.reference_review.status -ne 'stale') { throw 'New source registration did not invalidate outputs.' }
    [IO.File]::WriteAllText($source, 'Unregistered edit')
    $changed = Join-Path $runDir 'accepted/changed.md'
    Must-Block { & $state -Action snapshot-reference -RunId $runId -ArtifactId project-plan -Path $changed }
    if (Test-Path -LiteralPath $changed) { throw 'Changed or unaccepted source was snapshotted.' }
    Write-Output 'PASS: reviewed reference snapshot, unchanged acceptance, bounded path, input hash and source invalidation.'
} finally {
    $resolved = [IO.Path]::GetFullPath($runDir)
    $videoRoot = [IO.Path]::GetFullPath((Join-Path $repo '.local/video')).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($videoRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe fixture cleanup path.' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
