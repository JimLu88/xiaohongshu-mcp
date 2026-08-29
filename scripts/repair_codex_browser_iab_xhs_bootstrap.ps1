param(
    [ValidateSet('Apply', 'Verify')]
    [string]$Mode = 'Apply',
    [string]$ServicePath = '',
    [string]$BackupRoot = 'C:\Users\lzdwy\.codex\browser\patch-backups'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ServicePath)) {
    $browserCache = 'C:\Users\lzdwy\.codex\plugins\cache\openai-bundled\browser'
    $candidates = @(Get-ChildItem -LiteralPath $browserCache -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'scripts\browser-service.mjs') } |
        Sort-Object { [version]$_.Name } -Descending)
    if ($candidates.Count -ne 1) {
        throw "Expected exactly one installed Browser service, found $($candidates.Count). Pass -ServicePath explicitly."
    }
    $ServicePath = Join-Path $candidates[0].FullName 'scripts\browser-service.mjs'
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

if (-not (Test-Path -LiteralPath $ServicePath -PathType Leaf)) {
    throw "Browser service not found: $ServicePath"
}

$source = [IO.File]::ReadAllText($ServicePath)
$legacyMarker = 'setTimeout(()=>window.location.assign(${JSON.stringify(t.url)}),1e3);true'
$currentMarker = 'setTimeout(()=>window.location.assign(${JSON.stringify(e.url)}),1e3);true'

if ($Mode -eq 'Verify') {
    $required = @(
        'setTimeout(()=>window.location.assign(${JSON.stringify(t.url)}),1e3);true',
        'awaitPromise:!1,returnByValue:!0',
        'function OAI_IAB_SAFE_XHS_BOOTSTRAP_URL(t)',
        'e.hostname==="www.xiaohongshu.com"',
        '(e.pathname==="/"||e.pathname==="/explore")&&!e.search&&!e.hash'
    )
    foreach ($fragment in $required) {
        if ($fragment -eq 'setTimeout(()=>window.location.assign(${JSON.stringify(t.url)}),1e3);true') {
            $hasDelayedDispatch = $source.Contains($fragment, [StringComparison]::Ordinal) -or
                $source.Contains('setTimeout(()=>window.location.assign(${JSON.stringify(e.url)}),1e3);true', [StringComparison]::Ordinal)
            if (-not $hasDelayedDispatch) {
                throw "Installed IAB bootstrap patch is incomplete: delayed dispatch"
            }
            continue
        }
        if (-not $source.Contains($fragment, [StringComparison]::Ordinal)) {
            throw "Installed IAB bootstrap patch is incomplete: $fragment"
        }
    }
    $legacyBranchVerified = $source.Contains('e.isIabBackend&&OAI_IAB_SAFE_XHS_BOOTSTRAP_URL(l)){let s=await e.tabs.get(r),a=Up(s?.url);if(a==="about:blank")', [StringComparison]::Ordinal)
    $currentBranchVerified = $source.Contains('t.isIabBackend&&OAI_IAB_SAFE_XHS_BOOTSTRAP_URL(l)){let s=await t.tabs.get(r),a=$p(s?.url);if(a==="about:blank")', [StringComparison]::Ordinal)
    if (-not ($legacyBranchVerified -or $currentBranchVerified)) {
        throw 'Installed IAB bootstrap branch does not match a supported Browser service shape.'
    }
    [pscustomobject]@{
        status = 'verified'
        service_path = $ServicePath
        sha256 = Get-Sha256 $ServicePath
        iab_xhs_nonblocking_bootstrap = $true
        navigation_dispatch_delay_ms = 1000
    } | ConvertTo-Json -Depth 3
    exit 0
}

if ($source.Contains($legacyMarker, [StringComparison]::Ordinal) -or
    $source.Contains($currentMarker, [StringComparison]::Ordinal)) {
    & $PSCommandPath -Mode Verify -ServicePath $ServicePath -BackupRoot $BackupRoot
    exit $LASTEXITCODE
}

$legacyBefore = 's=await e.cdp.readDocumentState(r,i),a=Up(s?.href),l=Up(t.url);if(e.isIabBackend&&a==="about:blank"&&OAI_IAB_SAFE_XHS_BOOTSTRAP_URL(l)){await e.cdp.call(r,"Runtime.evaluate",{expression:`setTimeout(()=>window.location.assign(${JSON.stringify(t.url)}),0);true`,awaitPromise:!1,returnByValue:!0},i);return{}}await e.cdp.call(r,"Page.enable",{},i);let c=await HV(r,e,i)'
$legacyAfter = 'l=Up(t.url);if(e.isIabBackend&&OAI_IAB_SAFE_XHS_BOOTSTRAP_URL(l)){let s=await e.tabs.get(r),a=Up(s?.url);if(a==="about:blank"){await e.cdp.call(r,"Runtime.evaluate",{expression:`setTimeout(()=>window.location.assign(${JSON.stringify(t.url)}),1e3);true`,awaitPromise:!1,returnByValue:!0},i);return{}}}let s=await e.cdp.readDocumentState(r,i),a=Up(s?.href);await e.cdp.call(r,"Page.enable",{},i);let c=await HV(r,e,i)'
$originalBefore = 's=await e.cdp.readDocumentState(r,i),a=Up(s?.href),l=Up(t.url);await e.cdp.call(r,"Page.enable",{},i);let c=await HV(r,e,i)'
$originalAfter = 'l=Up(t.url);if(e.isIabBackend&&OAI_IAB_SAFE_XHS_BOOTSTRAP_URL(l)){let s=await e.tabs.get(r),a=Up(s?.url);if(a==="about:blank"){await e.cdp.call(r,"Runtime.evaluate",{expression:`setTimeout(()=>window.location.assign(${JSON.stringify(t.url)}),1e3);true`,awaitPromise:!1,returnByValue:!0},i);return{}}}let s=await e.cdp.readDocumentState(r,i),a=Up(s?.href);await e.cdp.call(r,"Page.enable",{},i);let c=await HV(r,e,i)'
$currentBefore = 's=await t.cdp.readDocumentState(r,i),a=$p(s?.href),l=$p(e.url);await t.cdp.call(r,"Page.enable",{},i);let c=await p7(r,t,i)'
$currentAfter = 'l=$p(e.url);if(t.isIabBackend&&OAI_IAB_SAFE_XHS_BOOTSTRAP_URL(l)){let s=await t.tabs.get(r),a=$p(s?.url);if(a==="about:blank"){await t.cdp.call(r,"Runtime.evaluate",{expression:`setTimeout(()=>window.location.assign(${JSON.stringify(e.url)}),1e3);true`,awaitPromise:!1,returnByValue:!0},i);return{}}}let s=await t.cdp.readDocumentState(r,i),a=$p(s?.href);await t.cdp.call(r,"Page.enable",{},i);let c=await p7(r,t,i)'
$v2Before = 'l=Up(t.url);if(e.isIabBackend&&OAI_IAB_SAFE_XHS_BOOTSTRAP_URL(l)){let s=await e.tabs.get(r),a=Up(s?.url);if(a==="about:blank"){await e.cdp.call(r,"Runtime.evaluate",{expression:`setTimeout(()=>window.location.assign(${JSON.stringify(t.url)}),0);true`,awaitPromise:!1,returnByValue:!0},i);return{}}}let s=await e.cdp.readDocumentState(r,i),a=Up(s?.href);await e.cdp.call(r,"Page.enable",{},i);let c=await HV(r,e,i)'
$v2After = $legacyAfter
$functionBefore = 'async function HV(t,e,r={}){'
$functionAfter = 'function OAI_IAB_SAFE_XHS_BOOTSTRAP_URL(t){try{let e=new URL(t);return e.protocol==="https:"&&e.hostname==="www.xiaohongshu.com"&&(e.pathname==="/"||e.pathname==="/explore")&&!e.search&&!e.hash}catch{return!1}}async function HV(t,e,r={}){'
$currentFunctionBefore = 'async function p7(e,t,r={}){'
$currentFunctionAfter = 'function OAI_IAB_SAFE_XHS_BOOTSTRAP_URL(t){try{let e=new URL(t);return e.protocol==="https:"&&e.hostname==="www.xiaohongshu.com"&&(e.pathname==="/"||e.pathname==="/explore")&&!e.search&&!e.hash}catch{return!1}}async function p7(e,t,r={}){'

$replacements = @()
if ($source.Contains($v2Before, [StringComparison]::Ordinal)) {
    $replacements += ,@('navigation dispatch delay v2 to v3', $v2Before, $v2After)
}
elseif ($source.Contains($legacyBefore, [StringComparison]::Ordinal)) {
    $replacements += ,@('navigation branch v1 to v2', $legacyBefore, $legacyAfter)
}
elseif ($source.Contains($originalBefore, [StringComparison]::Ordinal)) {
    $replacements += ,@('navigation branch original to v2', $originalBefore, $originalAfter)
}
elseif ($source.Contains($currentBefore, [StringComparison]::Ordinal)) {
    $replacements += ,@('navigation branch current to v3', $currentBefore, $currentAfter)
}
else {
    throw 'Neither the original nor v1 navigation branch was found.'
}
if (-not $source.Contains('function OAI_IAB_SAFE_XHS_BOOTSTRAP_URL(t)', [StringComparison]::Ordinal)) {
    if ($source.Contains($functionBefore, [StringComparison]::Ordinal)) {
        $replacements += ,@('URL allowlist helper legacy', $functionBefore, $functionAfter)
    }
    elseif ($source.Contains($currentFunctionBefore, [StringComparison]::Ordinal)) {
        $replacements += ,@('URL allowlist helper current', $currentFunctionBefore, $currentFunctionAfter)
    }
    else {
        throw 'Supported URL allowlist insertion point was not found.'
    }
}

foreach ($replacement in $replacements) {
    $first = $source.IndexOf($replacement[1], [StringComparison]::Ordinal)
    if ($first -lt 0) {
        throw "Patch fragment not found: $($replacement[0])"
    }
    $second = $source.IndexOf($replacement[1], $first + $replacement[1].Length, [StringComparison]::Ordinal)
    if ($second -ge 0) {
        throw "Patch fragment is not unique: $($replacement[0])"
    }
    $source = $source.Substring(0, $first) + $replacement[2] + $source.Substring($first + $replacement[1].Length)
}

$currentSha = Get-Sha256 $ServicePath
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
$browserVersion = Split-Path -Leaf (Split-Path -Parent (Split-Path -Parent $ServicePath))
$backupPath = Join-Path $BackupRoot "browser-service.$browserVersion.$currentSha.mjs"
if (-not (Test-Path -LiteralPath $backupPath)) {
    Copy-Item -LiteralPath $ServicePath -Destination $backupPath
}
if ((Get-Sha256 $backupPath) -ne $currentSha) {
    throw "Backup verification failed: $backupPath"
}

$utf8NoBom = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText($ServicePath, $source, $utf8NoBom)

try {
    & $PSCommandPath -Mode Verify -ServicePath $ServicePath -BackupRoot $BackupRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Post-write verification exited with $LASTEXITCODE"
    }
}
catch {
    Copy-Item -LiteralPath $backupPath -Destination $ServicePath -Force
    throw "IAB bootstrap patch verification failed and the previous service was restored. $($_.Exception.Message)"
}

[pscustomobject]@{
    status = 'applied'
    service_path = $ServicePath
    previous_sha256 = $currentSha
    patched_sha256 = Get-Sha256 $ServicePath
    backup_path = $backupPath
    navigation_dispatch_delay_ms = 1000
} | ConvertTo-Json -Depth 3
