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

function Replace-ExactlyOnce(
    [string]$Text,
    [string]$Before,
    [string]$After,
    [string]$Label
) {
    $first = $Text.IndexOf($Before, [StringComparison]::Ordinal)
    if ($first -lt 0) {
        throw "Patch fragment not found: $Label"
    }
    $second = $Text.IndexOf($Before, $first + $Before.Length, [StringComparison]::Ordinal)
    if ($second -ge 0) {
        throw "Patch fragment is not unique: $Label"
    }
    return $Text.Substring(0, $first) + $After + $Text.Substring($first + $Before.Length)
}

if (-not (Test-Path -LiteralPath $ServicePath -PathType Leaf)) {
    throw "Browser service not found: $ServicePath"
}

$source = [IO.File]::ReadAllText($ServicePath)
$patchedMarker = 'await this.ensureAttachedTab(r.tabId,i)'
$isPatched = $source.Contains($patchedMarker, [StringComparison]::Ordinal)

if ($Mode -eq 'Verify') {
    if (-not $isPatched) {
        throw 'Browser navigation deadline patch is not installed.'
    }

    $required = @(
        'await this.ensureAttachedTab(r.tabId,i)',
        'async ensureAttachedTab(r,n={})',
        'async enableFocusEmulation(r,n={})',
        'timeoutMs:ds(n),preserveDebuggerOnTimeout:!0',
        'async readDocumentState(r,n={})',
        'deadlineMs:o,timeoutMs:n,preserveDebuggerOnTimeout:!0'
    )
    foreach ($fragment in $required) {
        if (-not $source.Contains($fragment, [StringComparison]::Ordinal)) {
            throw "Installed patch is incomplete: $fragment"
        }
    }
    $legacyNavigationVerified = $source.Contains('async function HV(t,e,r={})', [StringComparison]::Ordinal) -and
        $source.Contains('e.cdp.call(r,"Page.navigate",{url:t.url},i)', [StringComparison]::Ordinal)
    $currentNavigationVerified = $source.Contains('async function p7(e,t,r={})', [StringComparison]::Ordinal) -and
        $source.Contains('t.cdp.call(r,"Page.navigate",{url:e.url},i)', [StringComparison]::Ordinal)
    if (-not ($legacyNavigationVerified -or $currentNavigationVerified)) {
        throw 'Installed navigation deadline patch does not match a supported Browser service shape.'
    }

    [pscustomobject]@{
        status = 'verified'
        service_path = $ServicePath
        sha256 = Get-Sha256 $ServicePath
        navigation_deadline_patch = $true
    } | ConvertTo-Json -Depth 3
    exit 0
}

if ($isPatched) {
    & $PSCommandPath -Mode Verify -ServicePath $ServicePath -BackupRoot $BackupRoot
    exit $LASTEXITCODE
}

$replacements = @(
    @(
        'attach_handler_deadline',
        'this.addTabAttachHandler(async i=>{await this.call(i,"Page.enable"),await this.enableOopifAutoAttach(i)})',
        'this.addTabAttachHandler(async(i,s={})=>{await this.call(i,"Page.enable",void 0,s),await this.enableOopifAutoAttach(i,s)})'
    ),
    @(
        'execute_target_attach_deadline',
        'at(i),await this.ensureAttachedTab(r.tabId),i.prepareDispatch',
        'at(i),await this.ensureAttachedTab(r.tabId,i),i.prepareDispatch'
    ),
    @(
        'oopif_attach_deadline',
        'at(n),await this.ensureAttachedTab(o),!this.oopifAutoAttachTabIds.has(o)',
        'at(n),await this.ensureAttachedTab(o,n),!this.oopifAutoAttachTabIds.has(o)'
    ),
    @(
        'evaluate_deadline_forwarding',
        'let s=await this.call(r,"Runtime.evaluate",i,{telemetryAttrs:o.telemetryAttrs,timeoutMs:o.timeoutMs});',
        'let s=await this.call(r,"Runtime.evaluate",i,{deadlineMs:o.deadlineMs,preserveDebuggerOnTimeout:o.preserveDebuggerOnTimeout,telemetryAttrs:o.telemetryAttrs,timeoutMs:o.timeoutMs});'
    ),
    @(
        'document_state_deadline',
        'async readDocumentState(r){try{let n=await this.evaluateJavascript(r,"({ href: window.location.href, readyState: document.readyState })",{telemetryAttrs:{"browser_use.cdp.eval.kind":"document_state"}}),o=Number(r);return Number.isFinite(o)&&typeof n?.href=="string"&&n.href.length>0&&this.topLevelUrlsByTabId.set(o,n.href),n}catch{return}}',
        'async readDocumentState(r,n={}){try{let o=await this.evaluateJavascript(r,"({ href: window.location.href, readyState: document.readyState })",{deadlineMs:n.deadlineMs,preserveDebuggerOnTimeout:n.preserveDebuggerOnTimeout,telemetryAttrs:{"browser_use.cdp.eval.kind":"document_state"},timeoutMs:n.timeoutMs}),i=Number(r);return Number.isFinite(i)&&typeof o?.href=="string"&&o.href.length>0&&this.topLevelUrlsByTabId.set(i,o.href),o}catch{return}}'
    ),
    @(
        'attach_pipeline_deadline',
        'async runTabAttachHandlers(r){await Promise.allSettled([...this.tabAttachHandlers].map(async n=>n(r)))}async runTabCleanupHandlers(r){await Promise.allSettled([...this.tabCleanupHandlers].map(async n=>n(r)))}deleteFileChoosersForTab(r){for(let[n,o]of this.fileChoosersById)o.tabId===r&&this.fileChoosersById.delete(n)}async ensureAttachedTab(r){this.attachedTabIds.has(r)||(await this.api.attach(r),await this.enableFocusEmulation(r),this.attachedTabIds.add(r),this.emit("tabAttached",r),await this.runTabAttachHandlers(r))}async enableFocusEmulation(r){try{await this.api.executeCdp({target:{tabId:r},method:"Emulation.setFocusEmulationEnabled",commandParams:{enabled:!0}})}catch{}}',
        'async runTabAttachHandlers(r,n={}){await Promise.allSettled([...this.tabAttachHandlers].map(async o=>o(r,n)))}async runTabCleanupHandlers(r){await Promise.allSettled([...this.tabCleanupHandlers].map(async n=>n(r)))}deleteFileChoosersForTab(r){for(let[n,o]of this.fileChoosersById)o.tabId===r&&this.fileChoosersById.delete(n)}async ensureAttachedTab(r,n={}){if(this.attachedTabIds.has(r))return;at(n),await s1(this.api.attach(r),n),at(n),await this.enableFocusEmulation(r,n),at(n),this.attachedTabIds.add(r),this.emit("tabAttached",r),await this.runTabAttachHandlers(r,n),at(n)}async enableFocusEmulation(r,n={}){try{await this.api.executeCdp({target:{tabId:r},method:"Emulation.setFocusEmulationEnabled",commandParams:{enabled:!0},timeoutMs:ds(n),preserveDebuggerOnTimeout:!0})}catch{}}'
    )
)

$legacyNavigationBefore = 'var l1=k("navigate_tab_url",async(t,e)=>{if(typeof t.url!="string"||!t.url)throw new Error("navigate_tab_url requires a url");let r=Number(t.tab_id);if(!Number.isInteger(r)||r<=0)throw new Error("navigate_tab_url requires a positive integer tab_id");let n=typeof t.timeout_ms=="number"?t.timeout_ms:1e4,o=await e.cdp.readDocumentState(r),i=Up(o?.href),s=Up(t.url);await e.cdp.call(r,"Page.enable",{});let a=await HV(r,e),l=zV({mainFrameId:a,previousUrl:i,targetUrl:s}),c=new AbortController,p=e.cdp.waitForEvent(r,m=>mr(m)&&(Ao(m)||l(m)),{timeoutMs:n,timeoutMessage:`Timed out waiting for tab ${r} to navigate to ${t.url}.`,signal:c.signal}).then(m=>({event:m}),m=>c.signal.aborted?{event:void 0}:{error:m});try{let m=await e.cdp.call(r,"Page.navigate",{url:t.url});if(m.errorText){let y=YV(t.url)??"this page";throw new Error(`Browser Use cannot open ${y} in tab ${r}. Browser reported: ${JV(m.errorText,t.url,y)}`)}let b=await p;if("error"in b)throw b.error;En(b.event)}finally{c.abort()}return{}});async function HV(t,e){try{return(await e.cdp.call(t,"Page.getFrameTree")).frameTree?.frame?.id}catch{return}}'
$legacyNavigationAfter = 'var l1=k("navigate_tab_url",async(t,e)=>{if(typeof t.url!="string"||!t.url)throw new Error("navigate_tab_url requires a url");let r=Number(t.tab_id);if(!Number.isInteger(r)||r<=0)throw new Error("navigate_tab_url requires a positive integer tab_id");let n=typeof t.timeout_ms=="number"?t.timeout_ms:1e4,o=Date.now()+n,i={deadlineMs:o,timeoutMs:n,preserveDebuggerOnTimeout:!0},s=await e.cdp.readDocumentState(r,i),a=Up(s?.href),l=Up(t.url);await e.cdp.call(r,"Page.enable",{},i);let c=await HV(r,e,i),p=zV({mainFrameId:c,previousUrl:a,targetUrl:l}),m=new AbortController,b=Math.max(1,o-Date.now()),y=e.cdp.waitForEvent(r,w=>mr(w)&&(Ao(w)||p(w)),{timeoutMs:b,timeoutMessage:`Timed out waiting for tab ${r} to navigate to ${t.url}.`,signal:m.signal}).then(w=>({event:w}),w=>m.signal.aborted?{event:void 0}:{error:w});try{let w=await e.cdp.call(r,"Page.navigate",{url:t.url},i);if(w.errorText){let v=YV(t.url)??"this page";throw new Error(`Browser Use cannot open ${v} in tab ${r}. Browser reported: ${JV(w.errorText,t.url,v)}`)}let S=await y;if("error"in S)throw S.error;En(S.event)}finally{m.abort()}return{}});async function HV(t,e,r={}){try{return(await e.cdp.call(t,"Page.getFrameTree",void 0,r)).frameTree?.frame?.id}catch{return}}'
$currentNavigationBefore = 'var yk=D("navigate_tab_url",async(e,t)=>{if(typeof e.url!="string"||!e.url)throw new Error("navigate_tab_url requires a url");let r=Number(e.tab_id);if(!Number.isInteger(r)||r<=0)throw new Error("navigate_tab_url requires a positive integer tab_id");let n=typeof e.timeout_ms=="number"?e.timeout_ms:1e4,o=await t.cdp.readDocumentState(r),i=$p(o?.href),s=$p(e.url);await t.cdp.call(r,"Page.enable",{});let a=await p7(r,t),l=m7({mainFrameId:a,previousUrl:i,targetUrl:s}),c=new AbortController,p=t.cdp.waitForEvent(r,m=>mr(m)&&(Po(m)||l(m)),{timeoutMs:n,timeoutMessage:`Timed out waiting for tab ${r} to navigate to ${e.url}.`,signal:c.signal}).then(m=>({event:m}),m=>c.signal.aborted?{event:void 0}:{error:m});try{let m=await t.cdp.call(r,"Page.navigate",{url:e.url});if(m.errorText){let y=w7(e.url)??"this page";throw new Error(`Browser Use cannot open ${y} in tab ${r}. Browser reported: ${y7(m.errorText,e.url,y)}`)}let g=await p;if("error"in g)throw g.error;An(g.event)}finally{c.abort()}return{}});async function p7(e,t){try{return(await t.cdp.call(e,"Page.getFrameTree")).frameTree?.frame?.id}catch{return}}'
$currentNavigationAfter = 'var yk=D("navigate_tab_url",async(e,t)=>{if(typeof e.url!="string"||!e.url)throw new Error("navigate_tab_url requires a url");let r=Number(e.tab_id);if(!Number.isInteger(r)||r<=0)throw new Error("navigate_tab_url requires a positive integer tab_id");let n=typeof e.timeout_ms=="number"?e.timeout_ms:1e4,o=Date.now()+n,i={deadlineMs:o,timeoutMs:n,preserveDebuggerOnTimeout:!0},s=await t.cdp.readDocumentState(r,i),a=$p(s?.href),l=$p(e.url);await t.cdp.call(r,"Page.enable",{},i);let c=await p7(r,t,i),p=m7({mainFrameId:c,previousUrl:a,targetUrl:l}),m=new AbortController,b=Math.max(1,o-Date.now()),y=t.cdp.waitForEvent(r,w=>mr(w)&&(Po(w)||p(w)),{timeoutMs:b,timeoutMessage:`Timed out waiting for tab ${r} to navigate to ${e.url}.`,signal:m.signal}).then(w=>({event:w}),w=>m.signal.aborted?{event:void 0}:{error:w});try{let w=await t.cdp.call(r,"Page.navigate",{url:e.url},i);if(w.errorText){let v=w7(e.url)??"this page";throw new Error(`Browser Use cannot open ${v} in tab ${r}. Browser reported: ${y7(w.errorText,e.url,v)}`)}let S=await y;if("error"in S)throw S.error;An(S.event)}finally{m.abort()}return{}});async function p7(e,t,r={}){try{return(await t.cdp.call(e,"Page.getFrameTree",void 0,r)).frameTree?.frame?.id}catch{return}}'

if ($source.Contains($legacyNavigationBefore, [StringComparison]::Ordinal)) {
    $replacements += ,@('navigation_total_deadline_legacy', $legacyNavigationBefore, $legacyNavigationAfter)
}
elseif ($source.Contains($currentNavigationBefore, [StringComparison]::Ordinal)) {
    $replacements += ,@('navigation_total_deadline_current', $currentNavigationBefore, $currentNavigationAfter)
}
else {
    throw 'Supported original navigation handler was not found.'
}

$patched = $source
foreach ($replacement in $replacements) {
    $patched = Replace-ExactlyOnce -Text $patched -Before $replacement[1] -After $replacement[2] -Label $replacement[0]
}

if ($patched -eq $source) {
    throw 'Patch unexpectedly produced no change.'
}

$sourceSha = Get-Sha256 $ServicePath
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
$browserVersion = Split-Path -Leaf (Split-Path -Parent (Split-Path -Parent $ServicePath))
$backupPath = Join-Path $BackupRoot "browser-service.$browserVersion.$sourceSha.mjs"
if (-not (Test-Path -LiteralPath $backupPath)) {
    Copy-Item -LiteralPath $ServicePath -Destination $backupPath
}
if ((Get-Sha256 $backupPath) -ne $sourceSha) {
    throw "Backup verification failed: $backupPath"
}

$utf8NoBom = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText($ServicePath, $patched, $utf8NoBom)

try {
    & $PSCommandPath -Mode Verify -ServicePath $ServicePath -BackupRoot $BackupRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Post-write verification exited with $LASTEXITCODE"
    }
}
catch {
    Copy-Item -LiteralPath $backupPath -Destination $ServicePath -Force
    throw "Patch verification failed and the original service was restored. $($_.Exception.Message)"
}

[pscustomobject]@{
    status = 'applied'
    service_path = $ServicePath
    original_sha256 = $sourceSha
    patched_sha256 = Get-Sha256 $ServicePath
    backup_path = $backupPath
} | ConvertTo-Json -Depth 3
