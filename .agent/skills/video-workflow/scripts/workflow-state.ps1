[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('initialize', 'register-artifact', 'snapshot-reference', 'set-stage', 'set-item', 'set-gate', 'reconcile', 'status', 'assert-full-approved', 'assert-audio-approved', 'assert-full-edit-approved', 'assert-assembly-approved', 'assert-retime-approved')]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')]
    [string]$RunId,

    [string]$SourceAudio,
    [string]$ArtifactId,
    [string]$Path,
    [string]$InputAudio,
    [string[]]$DependsOn = @(),
    [switch]$ConfirmRebuilt,
    [ValidateSet('sample_prepare', 'sample_outline', 'sample_content_review', 'sample_shotcut', 'sample_ai_edit', 'sample_final_transcript', 'sample_captions', 'sample_web_demo', 'sample_quality_review', 'full_transcript', 'full_outline', 'full_content_review', 'full_shotcut', 'full_ai_edit', 'full_final_transcript', 'full_captions', 'full_web_demo', 'full_quality_review', 'complete')]
    [string]$Stage,
    [string]$ItemId,
    [ValidateSet('sample', 'full')]
    [string]$ReviewScope,
    [ValidateSet('pending', 'needs_revision', 'accepted', 'resolved')]
    [string]$ItemStatus,
    [string]$Decision,
    [string]$Gate
)

$ErrorActionPreference = 'Stop'
$script:RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path.TrimEnd([IO.Path]::DirectorySeparatorChar)
$script:VideoRoot = Join-Path $script:RepoRoot '.local/video'
$script:RunDir = Join-Path $script:VideoRoot $RunId
$script:ManifestPath = Join-Path $script:RunDir 'workflow.json'

function Set-ObjectProperty {
    param([object]$Object, [string]$Name, [object]$Value)
    $property = $Object.PSObject.Properties[$Name]
    if ($null -ne $property) {
        $property.Value = $Value
    } else {
        $Object | Add-Member -MemberType NoteProperty -Name $Name -Value $Value
    }
}

function Get-ObjectProperty {
    param([object]$Object, [string]$Name)
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Get-RepoDisplayPath {
    param([string]$AbsolutePath)
    $prefix = $script:RepoRoot + [IO.Path]::DirectorySeparatorChar
    if ($AbsolutePath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        return $AbsolutePath.Substring($prefix.Length).Replace('\', '/')
    }
    return $AbsolutePath
}

function Resolve-InputFile {
    param([string]$InputPath)
    if (-not $InputPath) { throw 'A file path is required.' }
    $resolved = Resolve-Path -LiteralPath $InputPath -ErrorAction Stop
    if (Test-Path -LiteralPath $resolved.Path -PathType Container) {
        throw "Expected a file, got a directory: $InputPath"
    }
    return $resolved.Path
}

function Get-FileHashHex {
    param([string]$FilePath)
    $stream = [IO.File]::OpenRead($FilePath)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
        $stream.Dispose()
    }
}

function Save-Manifest {
    param([object]$Manifest)
    $Manifest.updated_at = [DateTime]::UtcNow.ToString('o')
    $json = ConvertTo-Json -InputObject $Manifest -Depth 30
    $tempPath = Join-Path $script:RunDir ('workflow.' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllText($tempPath, $json + "`n", (New-Object System.Text.UTF8Encoding($false)))
        Move-Item -LiteralPath $tempPath -Destination $script:ManifestPath -Force
    } finally {
        if (Test-Path -LiteralPath $tempPath) {
            Remove-Item -LiteralPath $tempPath -Force
        }
    }
}

function Read-Manifest {
    if (-not (Test-Path -LiteralPath $script:ManifestPath -PathType Leaf)) {
        throw "Workflow state does not exist: $script:ManifestPath"
    }
    $manifest = Get-Content -Raw -Encoding utf8 -LiteralPath $script:ManifestPath | ConvertFrom-Json
    if (-not (Get-ObjectProperty $manifest.gates 'ai_audio_export')) {
        Set-ObjectProperty $manifest.gates 'ai_audio_export' ([pscustomobject]@{ status = 'pending'; depends_on = @(); input_hashes = [pscustomobject]@{} })
    }
    foreach ($id in @('full_ai_edit_authorization', 'full_ai_audio_export')) {
        if (-not (Get-ObjectProperty $manifest.gates $id)) {
            Set-ObjectProperty $manifest.gates $id ([pscustomobject]@{ status = 'pending'; depends_on = @(); input_hashes = [pscustomobject]@{} })
        }
    }
    return $manifest
}

function Get-AbsoluteArtifactPath {
    param([string]$StoredPath)
    if ([IO.Path]::IsPathRooted($StoredPath)) { return $StoredPath }
    return Join-Path $script:RepoRoot ($StoredPath.Replace('/', [IO.Path]::DirectorySeparatorChar))
}

function Get-Artifact {
    param([object]$Manifest, [string]$Id)
    return Get-ObjectProperty $Manifest.artifacts $Id
}

function Assert-Dependencies {
    param([object]$Manifest, [string[]]$Ids)
    foreach ($id in $Ids) {
        if (-not (Get-Artifact $Manifest $id)) {
            throw "Unknown dependency '$id'. Register it before referencing it."
        }
    }
}

function Invalidate-Dependents {
    param([object]$Manifest, [string[]]$ChangedIds)
    $invalidated = @{}
    foreach ($id in $ChangedIds) { $invalidated[$id] = $true }

    $progress = $true
    while ($progress) {
        $progress = $false
        foreach ($property in $Manifest.artifacts.PSObject.Properties) {
            $artifact = $property.Value
            if ($artifact.status -eq 'stale') { $invalidated[$property.Name] = $true; continue }
            foreach ($dependency in @($artifact.depends_on)) {
                if ($invalidated.ContainsKey([string]$dependency)) {
                    $artifact.status = 'stale'
                    $invalidated[$property.Name] = $true
                    $progress = $true
                    break
                }
            }
        }
    }

    foreach ($property in $Manifest.gates.PSObject.Properties) {
        $gate = $property.Value
        if ($gate.status -ne 'approved') { continue }
        $dependsOnChange = $false
        foreach ($dependency in @($gate.depends_on)) {
            $artifact = Get-Artifact $Manifest ([string]$dependency)
            if ($invalidated.ContainsKey([string]$dependency) -or $null -eq $artifact -or $artifact.status -ne 'current') {
                $dependsOnChange = $true
                break
            }
            $storedHash = Get-ObjectProperty $gate.input_hashes ([string]$dependency)
            if ($storedHash -ne $artifact.sha256) {
                $dependsOnChange = $true
                break
            }
        }
        if ($dependsOnChange) { $gate.status = 'stale' }
    }
}

function Reconcile-Manifest {
    param([object]$Manifest)
    $changedIds = [Collections.Generic.List[string]]::new()
    foreach ($property in $Manifest.artifacts.PSObject.Properties) {
        $artifact = $property.Value
        $absolutePath = Get-AbsoluteArtifactPath ([string]$artifact.path)
        if (-not (Test-Path -LiteralPath $absolutePath -PathType Leaf)) {
            if ($artifact.status -ne 'missing') { $changedIds.Add($property.Name) }
            $artifact.status = 'missing'
            continue
        }

        $currentHash = Get-FileHashHex $absolutePath
        if ($artifact.sha256 -ne $currentHash -or $artifact.status -eq 'missing') {
            $artifact.sha256 = $currentHash
            $artifact.status = 'current'
            $artifact.last_seen_at = [DateTime]::UtcNow.ToString('o')
            $changedIds.Add($property.Name)
        }
    }
    Invalidate-Dependents $Manifest $changedIds.ToArray()
}

function Assert-GateDependenciesCurrent {
    param([object]$Manifest, [string[]]$Ids)
    if ($Ids.Count -eq 0) { throw 'A gate approval must name the artifacts it reviewed.' }
    Assert-Dependencies $Manifest $Ids
    foreach ($id in $Ids) {
        $artifact = Get-Artifact $Manifest $id
        if ($artifact.status -ne 'current') {
            throw "Cannot approve a gate while dependency '$id' is $($artifact.status)."
        }
    }
}

function Assert-RequiredArtifactIds {
    param([string[]]$ActualIds, [string[]]$RequiredIds, [string]$GateName)
    foreach ($requiredId in $RequiredIds) {
        if ($requiredId -notin $ActualIds) {
            throw "The '$GateName' gate must include current artifact '$requiredId'."
        }
    }
}

function Assert-ReviewIssueIdsRegistered {
    param([object]$Manifest, [string[]]$ReviewArtifactIds, [string]$GateName)
    $gateState = Get-ObjectProperty $Manifest.gates $GateName
    $reviewArtifactId = [string](Get-ObjectProperty $gateState 'latest_review_artifact_id')
    if (-not $reviewArtifactId -or $reviewArtifactId -notin $ReviewArtifactIds) {
        throw "The '$GateName' gate must include its latest review record '$reviewArtifactId'."
    }
    foreach ($candidateId in $ReviewArtifactIds) {
        if ($candidateId -match '^(sample|full)-content-review-' -and $candidateId -ne $reviewArtifactId) {
            throw "The '$GateName' gate may reference only the latest review record '$reviewArtifactId', not '$candidateId'."
        }
    }
    $reviewArtifact = Get-Artifact $Manifest $reviewArtifactId
    if ($null -eq $reviewArtifact -or $reviewArtifact.status -ne 'current') {
        throw "The latest review record '$reviewArtifactId' is missing or stale."
    }
    $reviewPath = Get-AbsoluteArtifactPath ([string]$reviewArtifact.path)
    $reviewText = [IO.File]::ReadAllText($reviewPath, [Text.Encoding]::UTF8)
    $issueIds = [regex]::Matches($reviewText, '(?m)^##\s+(I-\d{3,})\b')
    foreach ($match in $issueIds) {
        $issueId = $match.Groups[1].Value
        if ($null -eq (Get-ObjectProperty $Manifest.review_items $issueId)) {
            throw "The latest review record contains unregistered issue '$issueId'. Record its human status before approval."
        }
    }
}

function Sync-LatestReviewArtifactId {
    param([object]$Manifest, [ValidateSet('sample', 'full')][string]$ReviewScope)
    $gateName = if ($ReviewScope -eq 'sample') { 'content_review' } else { 'full_content_review' }
    $prefix = if ($ReviewScope -eq 'sample') { 'sample-content-review-' } else { 'full-content-review-' }
    $latestId = $null
    $latestRound = -1
    foreach ($property in $Manifest.artifacts.PSObject.Properties) {
        if ($property.Name -match ('^' + [regex]::Escape($prefix) + '(0[1-9]|[1-9]\d+)$')) {
            $round = [int]$Matches[1]
            if ($round -gt $latestRound) {
                $latestRound = $round
                $latestId = $property.Name
            }
        }
    }
    $gateState = Get-ObjectProperty $Manifest.gates $gateName
    if ($null -eq $gateState) {
        $gateState = [pscustomobject]@{ status = 'pending'; depends_on = @(); input_hashes = [pscustomobject]@{}; latest_review_artifact_id = $null }
        Set-ObjectProperty $Manifest.gates $gateName $gateState
    }
    if ($latestId) { Set-ObjectProperty $gateState 'latest_review_artifact_id' $latestId }
    return [pscustomobject]@{ id = $latestId; round = $latestRound; gate = $gateName }
}

function Assert-AudioMatchesArtifact {
    param([object]$Manifest, [string]$InputAudioPath, [string]$ArtifactId)
    $artifact = Get-Artifact $Manifest $ArtifactId
    if ($null -eq $artifact -or $artifact.status -ne 'current') {
        throw "The required audio artifact '$ArtifactId' is missing or stale."
    }
    $absoluteInputPath = Resolve-InputFile $InputAudioPath
    $expectedPath = [IO.Path]::GetFullPath((Get-AbsoluteArtifactPath ([string]$artifact.path)))
    $actualPath = [IO.Path]::GetFullPath($absoluteInputPath)
    if (-not $actualPath.Equals($expectedPath, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Input audio does not match the registered '$ArtifactId' path."
    }
    if ((Get-FileHashHex $actualPath) -ne $artifact.sha256) {
        throw "Input audio does not match the registered '$ArtifactId' hash."
    }
}

function Test-SampleExportApproved {
    param([object]$Manifest)
    return ($Manifest.gates.shotcut_export.status -eq 'approved' -or
            (Get-ObjectProperty $Manifest.gates 'ai_audio_export').status -eq 'approved')
}

function Test-FullExportApproved {
    param([object]$Manifest)
    foreach ($id in @('shotcut_export', 'full_ai_audio_export')) {
        $export = Get-ObjectProperty $Manifest.gates $id
        if ($export.status -ne 'approved' -or 'full-final-audio' -notin @($export.depends_on)) { continue }
        $matches = $true
        foreach ($dependency in @($Manifest.gates.full_content_review.depends_on) + @('full-final-audio')) {
            $artifact = Get-Artifact $Manifest $dependency
            if ($null -eq $artifact -or $artifact.status -ne 'current' -or
                $dependency -notin @($export.depends_on) -or
                (Get-ObjectProperty $export.input_hashes $dependency) -ne $artifact.sha256) { $matches = $false; break }
        }
        if ($matches) { return $true }
    }
    return $false
}

function Assert-FullAIApproved {
    param([object]$Manifest)
    if ($Manifest.gates.sample_acceptance.status -ne 'approved' -or
        $Manifest.gates.full_ai_edit_authorization.status -ne 'approved') {
        throw 'Full AI editing requires current sample acceptance and explicit full AI authorization.'
    }
}

function Assert-ApprovedAudioInput {
    param([object]$Manifest, [string]$InputAudioPath)
    if (-not $InputAudioPath) { throw '-InputAudio is required for audio approval checks.' }
    switch ([string]$Manifest.stage) {
        'sample_final_transcript' {
            if ($Manifest.gates.content_review.status -ne 'approved' -or -not (Test-SampleExportApproved $Manifest)) {
                throw 'Sample final-audio transcription requires current content_review and a sample audio export approval.'
            }
            Assert-AudioMatchesArtifact $Manifest $InputAudioPath 'sample-final-audio'
            return
        }
        'full_transcript' {
            if ($Manifest.gates.sample_acceptance.status -ne 'approved') {
                throw 'Full recording work requires a current sample_acceptance approval.'
            }
            $decoded = Get-Artifact $Manifest 'full-source-wav'
            if ($decoded -and ([IO.Path]::GetFullPath((Resolve-InputFile $InputAudioPath))).Equals([IO.Path]::GetFullPath((Get-AbsoluteArtifactPath $decoded.path)), [StringComparison]::OrdinalIgnoreCase)) {
                if ('source-audio' -notin @($decoded.depends_on)) { throw 'Decoded full source must depend on source-audio.' }
                Assert-AudioMatchesArtifact $Manifest $InputAudioPath 'full-source-wav'
            } else {
                Assert-AudioMatchesArtifact $Manifest $InputAudioPath 'source-audio'
            }
            return
        }
        'full_content_review' {
            Assert-FullAIApproved $Manifest
            $pickup = Get-Artifact $Manifest 'full-pickup-wav'
            if ($pickup -and ([IO.Path]::GetFullPath((Resolve-InputFile $InputAudioPath))).Equals([IO.Path]::GetFullPath((Get-AbsoluteArtifactPath $pickup.path)), [StringComparison]::OrdinalIgnoreCase)) {
                Assert-PickupApproved $Manifest $InputAudioPath
                return
            }
            Assert-AudioMatchesArtifact $Manifest $InputAudioPath 'full-draft-audio'
            return
        }
        'full_final_transcript' {
            if ($Manifest.gates.sample_acceptance.status -ne 'approved' -or $Manifest.gates.full_content_review.status -ne 'approved' -or -not (Test-FullExportApproved $Manifest)) {
                throw 'Full final-audio transcription requires current sample, content, and audio export approvals.'
            }
            Assert-AudioMatchesArtifact $Manifest $InputAudioPath 'full-final-audio'
            return
        }
        default {
            throw "Long audio is not allowed at workflow stage '$($Manifest.stage)'. Use sample_final_transcript, full_transcript, or full_final_transcript with the registered audio artifact."
        }
    }
}

function Assert-PickupApproved {
    param([object]$Manifest, [string]$InputPath)
    Assert-FullAIApproved $Manifest
    if ($Manifest.stage -notin @('full_content_review', 'full_ai_edit')) { throw 'Pickup editing requires a full editing stage.' }
    $wav = Get-Artifact $Manifest 'full-pickup-wav'
    $authorization = Get-Artifact $Manifest 'full-pickup-authorization'
    if ($null -eq $authorization -or $authorization.status -ne 'current' -or
        'full-pickup-source-audio' -notin @($authorization.depends_on) -or
        'full-pickup-source-audio' -notin @($wav.depends_on) -or
        'full-pickup-authorization' -notin @($wav.depends_on)) {
        throw 'Pickup requires current source and explicit pickup authorization dependencies.'
    }
    foreach ($id in @('full-pickup-source-audio', 'full-pickup-authorization')) {
        $artifact = Get-Artifact $Manifest $id
        Assert-AudioMatchesArtifact $Manifest (Get-AbsoluteArtifactPath $artifact.path) $id
    }
    Assert-AudioMatchesArtifact $Manifest $InputPath 'full-pickup-wav'
}

function Invoke-WorkflowAction {
    switch ($Action) {
        'initialize' {
            if (-not $SourceAudio) { throw '-SourceAudio is required for initialize.' }
            if (Test-Path -LiteralPath $script:ManifestPath) {
                throw "Workflow state already exists; use status or reconcile instead of reinitializing: $script:ManifestPath"
            }
            New-Item -ItemType Directory -Force -Path $script:RunDir | Out-Null
            $sourcePath = Resolve-InputFile $SourceAudio
            $sourceAudioArtifact = [pscustomobject]@{
                path = Get-RepoDisplayPath $sourcePath
                sha256 = Get-FileHashHex $sourcePath
                status = 'current'
                depends_on = @()
                last_seen_at = [DateTime]::UtcNow.ToString('o')
            }
            $manifest = [pscustomobject]@{
                schema_version = 1
                run_id = $RunId
                stage = 'sample_prepare'
                created_at = [DateTime]::UtcNow.ToString('o')
                updated_at = [DateTime]::UtcNow.ToString('o')
                artifacts = [pscustomobject]@{ 'source-audio' = $sourceAudioArtifact }
                review_items = [pscustomobject]@{}
                gates = [pscustomobject]@{
                    content_review = [pscustomobject]@{ status = 'pending'; depends_on = @(); input_hashes = [pscustomobject]@{}; latest_review_artifact_id = $null }
                    shotcut_export = [pscustomobject]@{ status = 'pending'; depends_on = @(); input_hashes = [pscustomobject]@{} }
                    ai_audio_export = [pscustomobject]@{ status = 'pending'; depends_on = @(); input_hashes = [pscustomobject]@{} }
                    sample_acceptance = [pscustomobject]@{ status = 'pending'; depends_on = @(); input_hashes = [pscustomobject]@{} }
                    full_content_review = [pscustomobject]@{ status = 'pending'; depends_on = @(); input_hashes = [pscustomobject]@{}; latest_review_artifact_id = $null }
                }
            }
            Save-Manifest $manifest
            Write-Output "Initialized workflow state for '$RunId'."
            return
        }

        'snapshot-reference' {
            if (-not $ArtifactId -or -not $Path) { throw '-ArtifactId and -Path are required.' }
            if ($ArtifactId -notmatch '^(project-plan|content-source-[A-Za-z0-9._-]+)$') {
                throw 'Only declared content reference documents may be snapshotted; media and approval records are excluded.'
            }
            $manifest = Read-Manifest
            $artifact = Get-Artifact $manifest $ArtifactId
            if (-not $artifact -or $artifact.status -ne 'current') { throw 'Reference must be current before snapshotting.' }
            $source = Get-AbsoluteArtifactPath $artifact.path
            if ([IO.Path]::GetExtension($source) -notin @('.md', '.txt')) { throw 'Reference must be a text document.' }
            if ((Get-FileHashHex $source) -ne $artifact.sha256) { throw 'Reference hash changed; register and review the new source first.' }
            $reviewed = $false
            foreach ($gateProperty in $manifest.gates.PSObject.Properties) {
                $gate = $gateProperty.Value
                if ($gate.status -eq 'approved' -and $ArtifactId -in @($gate.depends_on) -and
                    (Get-ObjectProperty $gate.input_hashes $ArtifactId) -eq $artifact.sha256) { $reviewed = $true }
            }
            if (-not $reviewed) { throw 'Reference has no current approval to preserve.' }
            $target = if ([IO.Path]::IsPathRooted($Path)) { [IO.Path]::GetFullPath($Path) } else { [IO.Path]::GetFullPath((Join-Path $script:RepoRoot $Path)) }
            $runPrefix = [IO.Path]::GetFullPath($script:RunDir).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
            if (-not $target.StartsWith($runPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Reference snapshot must stay in the current ignored run directory.' }
            if ((Test-Path -LiteralPath $target) -or [IO.Path]::GetExtension($target) -notin @('.md', '.txt')) { throw 'Use a new text snapshot path.' }
            $parent = Split-Path -Parent $target
            $ancestor = $parent
            while ($ancestor -and $ancestor.StartsWith($script:RepoRoot, [StringComparison]::OrdinalIgnoreCase)) {
                if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Snapshot path must not pass through a link or junction.' }
                $ancestor = Split-Path -Parent $ancestor
            }
            [IO.Directory]::CreateDirectory($parent) | Out-Null
            [IO.File]::Copy($source, $target, $false)
            if ((Get-FileHashHex $target) -ne $artifact.sha256 -or (Get-FileHashHex $source) -ne $artifact.sha256) {
                Remove-Item -LiteralPath $target -Force
                throw 'Reference changed while creating snapshot.'
            }
            $origin = Get-ObjectProperty $artifact 'snapshot_of'
            if (-not $origin) { $origin = $artifact.path }
            Set-ObjectProperty $artifact 'snapshot_of' $origin
            Set-ObjectProperty $artifact 'snapshot_at' ([DateTime]::UtcNow.ToString('o'))
            $artifact.path = Get-RepoDisplayPath $target
            # Approval hashes and dependent bytes refer to the identical reviewed document.
            Save-Manifest $manifest
            Write-Output "Preserved reviewed reference '$ArtifactId' as a fixed snapshot."
            return
        }

        'register-artifact' {
            if (-not $ArtifactId -or -not $Path) { throw '-ArtifactId and -Path are required for register-artifact.' }
            $manifest = Read-Manifest
            Reconcile-Manifest $manifest
            Assert-Dependencies $manifest $DependsOn
            foreach ($dependencyId in $DependsOn) {
                $dependencyArtifact = Get-Artifact $manifest $dependencyId
                if ($dependencyArtifact.status -ne 'current') {
                    throw "Cannot register '$ArtifactId' while dependency '$dependencyId' is $($dependencyArtifact.status). Rebuild its stale inputs first."
                }
            }
            $absolutePath = Resolve-InputFile $Path
            $hash = Get-FileHashHex $absolutePath
            $previous = Get-Artifact $manifest $ArtifactId
            $changed = ($null -eq $previous) -or ($previous.sha256 -ne $hash) -or ($previous.path -ne (Get-RepoDisplayPath $absolutePath)) -or ((@($previous.depends_on) -join '|') -ne (@($DependsOn) -join '|'))
            $sameContent = $previous -and $previous.sha256 -eq $hash
            if ($ArtifactId -match '^(sample|full)-content-review-' -and $ArtifactId -notmatch '^(sample|full)-content-review-(0[1-9]|[1-9]\d+)$') {
                throw "Review artifact IDs must include a numeric round, for example 'sample-content-review-01': $ArtifactId"
            }
            $revalidatedStale = $previous -and $previous.status -eq 'stale' -and $sameContent -and $ConfirmRebuilt
            $isReviewArtifact = $ArtifactId -match '^(sample|full)-content-review-(0[1-9]|[1-9]\d+)$'
            if ($isReviewArtifact) {
                $reviewScope = if ($Matches[1] -eq 'sample') { 'sample' } else { 'full' }
                $reviewRound = [int]$Matches[2]
                $latestReview = Sync-LatestReviewArtifactId $manifest $reviewScope
                if ($latestReview.round -gt $reviewRound) {
                    throw "Cannot register older review round '$ArtifactId'; latest is '$($latestReview.id)'."
                }
            }
            if ($previous -and $previous.status -eq 'stale' -and $sameContent -and -not $ConfirmRebuilt) {
                throw "Artifact '$ArtifactId' is stale and its bytes are unchanged. Rebuild it or explicitly revalidate it, then register with -ConfirmRebuilt."
            }
            $artifact = [pscustomobject]@{
                path = Get-RepoDisplayPath $absolutePath
                sha256 = $hash
                status = 'current'
                depends_on = @($DependsOn)
                last_seen_at = [DateTime]::UtcNow.ToString('o')
            }
            Set-ObjectProperty $manifest.artifacts $ArtifactId $artifact
            if ($isReviewArtifact) {
                $latestReview = Sync-LatestReviewArtifactId $manifest $reviewScope
                Set-ObjectProperty (Get-ObjectProperty $manifest.gates $latestReview.gate) 'latest_review_artifact_id' $ArtifactId
            }
            if ($changed -or $revalidatedStale) {
                Invalidate-Dependents $manifest @($ArtifactId)
                if ($ArtifactId -match '^sample-content-review') {
                    foreach ($gateId in @('content_review', 'full_content_review', 'shotcut_export', 'ai_audio_export', 'sample_acceptance')) {
                        $gateState = Get-ObjectProperty $manifest.gates $gateId
                        if ($gateState -and $gateState.status -eq 'approved') { $gateState.status = 'stale' }
                    }
                } elseif ($ArtifactId -match '^full-content-review') {
                    foreach ($gateId in @('full_content_review', 'shotcut_export', 'full_ai_audio_export')) {
                        $gateState = Get-ObjectProperty $manifest.gates $gateId
                        if ($gateState -and $gateState.status -eq 'approved') { $gateState.status = 'stale' }
                    }
                }
            }
            Save-Manifest $manifest
            Write-Output "Registered artifact '$ArtifactId'."
            return
        }

        'set-stage' {
            if (-not $Stage) { throw '-Stage is required for set-stage.' }
            $manifest = Read-Manifest
            Reconcile-Manifest $manifest
            if ($Stage -match '^full_' -or $Stage -eq 'complete') {
                if ($manifest.gates.sample_acceptance.status -ne 'approved') {
                    throw 'Full-recording stages require a current sample_acceptance approval.'
                }
            }
            if ($Stage -match '^sample_(shotcut|ai_edit|final_transcript|captions|web_demo|quality_review)$' -and $manifest.gates.content_review.status -ne 'approved') {
                throw 'Sample audio editing requires an approved, current content_review gate.'
            }
            if ($Stage -match '^sample_(final_transcript|captions|web_demo|quality_review)$' -and -not (Test-SampleExportApproved $manifest)) {
                throw 'This stage requires an approved sample audio export.'
            }
            if ($Stage -match '^sample_(final_transcript|captions|web_demo|quality_review)$' -and $manifest.gates.content_review.status -ne 'approved') {
                throw 'This stage requires a current content_review approval.'
            }
            if ($Stage -in @('full_shotcut', 'full_ai_edit') -and $manifest.gates.full_content_review.status -ne 'approved') {
                throw 'Full audio editing requires an approved, current full_content_review gate.'
            }
            if ($Stage -eq 'full_ai_edit') { Assert-FullAIApproved $manifest }
            if ($Stage -match '^full_(final_transcript|captions|web_demo|quality_review)$' -and -not (Test-FullExportApproved $manifest)) {
                throw 'This stage requires an approved full audio export.'
            }
            if ($Stage -match '^full_(final_transcript|captions|web_demo|quality_review)$' -and $manifest.gates.full_content_review.status -ne 'approved') {
                throw 'This stage requires a current full_content_review approval.'
            }
            $manifest.stage = $Stage
            Save-Manifest $manifest
            Write-Output "Workflow stage is now '$Stage'."
            return
        }

        'set-item' {
            if (-not $ItemId -or -not $ItemStatus -or -not $Decision) { throw '-ItemId, -ItemStatus, and -Decision are required for set-item.' }
            if ($Decision -notin @('retain', 'revise', 'cut', 'rewrite', 'pickup', 'accept_no_change')) {
                throw "Unsupported content decision: $Decision"
            }
            $manifest = Read-Manifest
            $previous = Get-ObjectProperty $manifest.review_items $ItemId
            $scope = if ($ReviewScope) { $ReviewScope } elseif ($previous) { if (Get-ObjectProperty $previous 'scope') { $previous.scope } else { 'sample' } } elseif ($manifest.stage -match '^full_') { 'full' } else { 'sample' }
            $changed = ($null -eq $previous) -or ($previous.status -ne $ItemStatus) -or ($previous.decision -ne $Decision) -or ((Get-ObjectProperty $previous 'scope') -ne $scope)
            $reviewItem = [pscustomobject]@{
                scope = $scope
                status = $ItemStatus
                decision = $Decision
                updated_at = [DateTime]::UtcNow.ToString('o')
            }
            Set-ObjectProperty $manifest.review_items $ItemId $reviewItem
            if ($changed) {
                $invalidGates = if ($scope -eq 'full') { @('full_content_review', 'shotcut_export', 'full_ai_audio_export') } else { @('content_review', 'full_content_review', 'shotcut_export', 'ai_audio_export', 'sample_acceptance', 'full_ai_audio_export') }
                foreach ($gateId in $invalidGates) {
                    $gateState = Get-ObjectProperty $manifest.gates $gateId
                    if ($gateState -and $gateState.status -eq 'approved') { $gateState.status = 'stale' }
                }
            }
            Save-Manifest $manifest
            Write-Output "Recorded review decision for '$ItemId'."
            return
        }

        'set-gate' {
            if (-not $Gate -or -not $Decision) { throw '-Gate and -Decision are required for set-gate.' }
            if ($Decision -notin @('approved', 'rejected', 'pending')) { throw "Unsupported gate decision: $Decision" }
            $manifest = Read-Manifest
            Reconcile-Manifest $manifest
            if (-not (Get-ObjectProperty $manifest.gates $Gate)) {
                Set-ObjectProperty $manifest.gates $Gate ([pscustomobject]@{ status = 'pending'; depends_on = @(); input_hashes = [pscustomobject]@{} })
            }
            if ($Decision -eq 'approved') {
                Assert-GateDependenciesCurrent $manifest $DependsOn
                if ($Gate -eq 'full_ai_edit_authorization') {
                    if ($manifest.gates.sample_acceptance.status -ne 'approved') { throw 'Full AI authorization requires current sample acceptance.' }
                    Assert-RequiredArtifactIds $DependsOn @('source-audio', 'run-brief') 'full_ai_edit_authorization'
                }
                if ($Gate -eq 'full_ai_audio_export') {
                    Assert-FullAIApproved $manifest
                    if ($manifest.stage -ne 'full_ai_edit' -or $manifest.gates.full_content_review.status -ne 'approved') { throw 'Full AI final audio requires full_ai_edit and approved full content.' }
                    Assert-RequiredArtifactIds $DependsOn @($manifest.gates.full_content_review.depends_on) 'full_ai_audio_export'
                    Assert-RequiredArtifactIds $DependsOn @('full-cut-map', 'full-final-audio') 'full_ai_audio_export'
                }
                if ($Gate -eq 'content_review' -or $Gate -eq 'full_content_review') {
                    $expectedStage = if ($Gate -eq 'content_review') { 'sample_content_review' } else { 'full_content_review' }
                    if ($manifest.stage -ne $expectedStage) {
                        throw "The '$Gate' gate can only be approved while the workflow stage is '$expectedStage'."
                    }
                    $hasOutline = @($DependsOn | Where-Object { $_ -match 'outline' }).Count -gt 0
                    $hasReviewRecord = @($DependsOn | Where-Object { $_ -match 'content-review' }).Count -gt 0
                    if (-not $hasOutline -or -not $hasReviewRecord) {
                        throw 'Content review approval must depend on both the current outline and its review record.'
                    }
                    Assert-ReviewIssueIdsRegistered $manifest $DependsOn $Gate
                    foreach ($itemProperty in $manifest.review_items.PSObject.Properties) {
                        $itemScope = Get-ObjectProperty $itemProperty.Value 'scope'
                        if (-not $itemScope) { $itemScope = 'sample' }
                        $gateScope = if ($Gate -eq 'content_review') { 'sample' } else { 'full' }
                        if ($itemScope -ne $gateScope) { continue }
                        if ($itemProperty.Value.status -notin @('accepted', 'resolved')) {
                            throw "Content review has an unresolved item: $($itemProperty.Name) ($($itemProperty.Value.status))."
                        }
                    }
                }
                if ($Gate -eq 'shotcut_export') {
                    if ($manifest.stage -eq 'sample_shotcut') {
                        if ($manifest.gates.content_review.status -ne 'approved') {
                            throw 'Sample Shotcut export approval requires an approved content_review gate.'
                        }
                        Assert-RequiredArtifactIds $DependsOn @($manifest.gates.content_review.depends_on) 'shotcut_export'
                        Assert-RequiredArtifactIds $DependsOn @('sample-final-audio') 'shotcut_export'
                    } elseif ($manifest.stage -eq 'full_shotcut') {
                        if ($manifest.gates.full_content_review.status -ne 'approved') {
                            throw 'Full Shotcut export approval requires an approved full_content_review gate.'
                        }
                        Assert-RequiredArtifactIds $DependsOn @($manifest.gates.full_content_review.depends_on) 'shotcut_export'
                        Assert-RequiredArtifactIds $DependsOn @('full-final-audio') 'shotcut_export'
                    } else {
                        throw 'Shotcut export approval is only valid during sample_shotcut or full_shotcut.'
                    }
                }
                if ($Gate -eq 'ai_audio_export') {
                    if ($manifest.stage -ne 'sample_ai_edit') {
                        throw 'AI sample audio export is only valid during sample_ai_edit.'
                    }
                    if ($manifest.gates.content_review.status -ne 'approved') {
                        throw 'AI sample audio export requires an approved content_review gate.'
                    }
                    Assert-RequiredArtifactIds $DependsOn @($manifest.gates.content_review.depends_on) 'ai_audio_export'
                    Assert-RequiredArtifactIds $DependsOn @('sample-cut-map', 'sample-final-audio') 'ai_audio_export'
                }
                if ($Gate -eq 'sample_acceptance' -and $manifest.gates.content_review.status -ne 'approved') {
                    throw 'Sample acceptance requires an approved content_review gate.'
                }
                if ($Gate -eq 'sample_acceptance' -and -not (Test-SampleExportApproved $manifest)) {
                    throw 'Sample acceptance requires an approved sample audio export gate.'
                }
                if ($Gate -eq 'sample_acceptance') {
                    if ($manifest.stage -ne 'sample_quality_review') {
                        throw 'Sample acceptance can only be recorded after sample_quality_review.'
                    }
                    Assert-RequiredArtifactIds $DependsOn @(
                        'sample-outline',
                        'sample-final-audio',
                        'sample-srt',
                        'sample-presentation',
                        'sample-quality-review'
                    ) 'sample_acceptance'
                    Assert-RequiredArtifactIds $DependsOn @($manifest.gates.content_review.depends_on) 'sample_acceptance'
                    $exportGate = if ($manifest.gates.ai_audio_export.status -eq 'approved') { $manifest.gates.ai_audio_export } else { $manifest.gates.shotcut_export }
                    Assert-RequiredArtifactIds $DependsOn @($exportGate.depends_on) 'sample_acceptance'
                    if ('sample-final-audio' -notin @($exportGate.depends_on)) {
                        throw 'The current sample export approval must reference sample-final-audio.'
                    }
                    if ($exportGate.input_hashes.'sample-final-audio' -ne (Get-Artifact $manifest 'sample-final-audio').sha256) {
                        throw 'The sample export approval is stale for the current sample-final-audio.'
                    }
                }
            }
            $hashes = [pscustomobject]@{}
            foreach ($id in @($DependsOn)) {
                $artifact = Get-Artifact $manifest $id
                if ($null -ne $artifact) { Set-ObjectProperty $hashes ([string]$id) $artifact.sha256 }
            }
            $latestReviewArtifactId = Get-ObjectProperty (Get-ObjectProperty $manifest.gates $Gate) 'latest_review_artifact_id'
            Set-ObjectProperty $manifest.gates $Gate ([pscustomobject]@{
                status = $Decision
                depends_on = @($DependsOn)
                input_hashes = $hashes
                latest_review_artifact_id = $latestReviewArtifactId
                updated_at = [DateTime]::UtcNow.ToString('o')
            })
            if ($Decision -ne 'approved' -and $Gate -eq 'content_review') {
                foreach ($gateId in @('shotcut_export', 'ai_audio_export', 'sample_acceptance')) {
                    $gateState = Get-ObjectProperty $manifest.gates $gateId
                    if ($gateState -and $gateState.status -eq 'approved') { $gateState.status = 'stale' }
                }
            } elseif ($Decision -ne 'approved' -and $Gate -eq 'full_content_review') {
                $shotcutGate = Get-ObjectProperty $manifest.gates 'shotcut_export'
                if ($shotcutGate -and $shotcutGate.status -eq 'approved') { $shotcutGate.status = 'stale' }
                if ($manifest.gates.full_ai_audio_export.status -eq 'approved') { $manifest.gates.full_ai_audio_export.status = 'stale' }
            }
            Save-Manifest $manifest
            Write-Output "Recorded gate '$Gate' as '$Decision'."
            return
        }

        'reconcile' {
            $manifest = Read-Manifest
            Reconcile-Manifest $manifest
            Save-Manifest $manifest
            Write-Output "Reconciled artifact state for '$RunId'."
            return
        }

        'status' {
            $manifest = Read-Manifest
            Reconcile-Manifest $manifest
            Save-Manifest $manifest
            $artifactLines = foreach ($property in $manifest.artifacts.PSObject.Properties) {
                "  $($property.Name): $($property.Value.status)"
            }
            $gateLines = foreach ($property in $manifest.gates.PSObject.Properties) {
                "  $($property.Name): $($property.Value.status)"
            }
            Write-Output "Run: $RunId`nStage: $($manifest.stage)`nGates:`n$($gateLines -join "`n")`nArtifacts:`n$($artifactLines -join "`n")"
            return
        }

        'assert-full-approved' {
            $manifest = Read-Manifest
            Reconcile-Manifest $manifest
            Save-Manifest $manifest
            if ($manifest.gates.sample_acceptance.status -ne 'approved') {
                throw 'Full recording work requires a current sample_acceptance approval.'
            }
            if ($manifest.stage -notin @('full_transcript', 'full_final_transcript')) {
                throw 'Set full_transcript or full_final_transcript before processing long audio.'
            }
            Write-Output "Full recording is approved at stage '$($manifest.stage)'."
            return
        }

        'assert-full-edit-approved' {
            $manifest = Read-Manifest
            Reconcile-Manifest $manifest
            Assert-FullAIApproved $manifest
            if ($manifest.stage -notin @('full_content_review', 'full_ai_edit')) { throw 'Full AI cutting requires full_content_review or full_ai_edit.' }
            $decoded = Get-Artifact $manifest 'full-source-wav'
            if ($null -eq $decoded -or 'source-audio' -notin @($decoded.depends_on)) { throw 'Full source WAV must depend on source-audio.' }
            Assert-AudioMatchesArtifact $manifest $InputAudio 'full-source-wav'
            Save-Manifest $manifest
            Write-Output 'Full AI editing is authorized for the registered source WAV.'
            return
        }
        'assert-assembly-approved' {
            $manifest = Read-Manifest
            Reconcile-Manifest $manifest
            Assert-FullAIApproved $manifest
            if ($manifest.stage -notin @('full_content_review', 'full_ai_edit')) { throw 'Assembly requires a full editing stage.' }
            Assert-AudioMatchesArtifact $manifest $Path 'full-assembly-timeline'
            $timelineArtifact = Get-Artifact $manifest 'full-assembly-timeline'
            $timeline = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path | ConvertFrom-Json
            if (-not $timeline.sources -or -not $timeline.segments) { throw 'Assembly requires sources and segments.' }
            foreach ($entry in $timeline.sources.PSObject.Properties) {
                $source = $entry.Value
                $id = [string]$source.artifact_id
                if ($id -notin @('full-preview-baseline-audio', 'full-pickup-wav') -or $id -notin @($timelineArtifact.depends_on)) { throw 'Unapproved assembly source or missing timeline dependency.' }
                $inputPath = [string]$source.path
                if (-not [IO.Path]::IsPathRooted($inputPath)) { $inputPath = Join-Path (Split-Path -Parent $Path) $inputPath }
                Assert-AudioMatchesArtifact $manifest $inputPath $id
                $artifact = Get-Artifact $manifest $id
                if ($artifact.sha256 -ne $source.sha256) { throw 'Timeline source hash differs from registration.' }
                if ($id -eq 'full-pickup-wav') {
                    Assert-PickupApproved $manifest $inputPath
                } else {
                    if ('full-preview-baseline-cut-map' -notin @($artifact.depends_on)) { throw 'Baseline must retain its original cut map.' }
                    $baselineMap = Get-Artifact $manifest 'full-preview-baseline-cut-map'
                    if ($null -eq $baselineMap -or 'full-source-wav' -notin @($baselineMap.depends_on)) { throw 'Baseline map must depend on the original source WAV.' }
                    Assert-AudioMatchesArtifact $manifest (Get-AbsoluteArtifactPath $baselineMap.path) 'full-preview-baseline-cut-map'
                }
            }
            Save-Manifest $manifest
            Write-Output 'Assembly timeline and all registered inputs are approved for editing.'
            return
        }
        'assert-retime-approved' {
            $manifest = Read-Manifest
            Reconcile-Manifest $manifest
            Assert-FullAIApproved $manifest
            if ($manifest.stage -notin @('full_content_review', 'full_ai_edit')) { throw 'Retime requires a full editing stage.' }
            Assert-AudioMatchesArtifact $manifest $Path 'full-retime-timeline'
            $timeline = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path | ConvertFrom-Json
            $timelineArtifact = Get-Artifact $manifest 'full-retime-timeline'
            foreach ($key in @('source','source_map')) {
                $expectedId = if ($key -eq 'source') { 'full-retime-baseline-audio' } else { 'full-retime-baseline-map' }
                $entry = $timeline.$key
                if (-not $entry -or $entry.artifact_id -ne $expectedId -or $expectedId -notin @($timelineArtifact.depends_on)) { throw 'Unapproved retime input or missing dependency.' }
                $inputPath = [string]$entry.path
                if (-not [IO.Path]::IsPathRooted($inputPath)) { $inputPath = Join-Path (Split-Path -Parent $Path) $inputPath }
                Assert-AudioMatchesArtifact $manifest $inputPath $expectedId
                if ((Get-Artifact $manifest $expectedId).sha256 -ne $entry.sha256) { throw 'Retime input hash differs from registration.' }
            }
            $baseline = Get-Artifact $manifest 'full-retime-baseline-audio'
            if ('full-retime-baseline-map' -notin @($baseline.depends_on)) { throw 'Retime baseline must retain its source map.' }
            $baselineMap = Get-Artifact $manifest 'full-retime-baseline-map'
            Assert-RequiredArtifactIds $baselineMap.depends_on @('full-assembly-timeline','full-preview-baseline-audio','full-pickup-wav') 'retime baseline provenance'
            $assemblyArtifact = Get-Artifact $manifest 'full-assembly-timeline'
            & $PSCommandPath -Action assert-assembly-approved -RunId $RunId -Path (Get-AbsoluteArtifactPath $assemblyArtifact.path) | Out-Null
            Save-Manifest $manifest
            Write-Output 'Retime timeline and fixed baseline inputs are approved for editing.'
            return
        }
        'assert-audio-approved' {
            $manifest = Read-Manifest
            Reconcile-Manifest $manifest
            Assert-ApprovedAudioInput $manifest $InputAudio
            Save-Manifest $manifest
            Write-Output "Audio input is approved at stage '$($manifest.stage)' and matches its registered artifact."
            return
        }
    }
}

try {
    if ($RunId -in @('.', '..')) { throw 'RunId cannot be a relative path component.' }
    Invoke-WorkflowAction
} catch {
    Write-Error $_
    throw
}
