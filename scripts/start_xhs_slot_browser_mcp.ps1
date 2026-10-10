[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 5)]
    [int]$AccountSlot,
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$policyPath = Join-Path $repoRoot "configs\panse\xhs_browser_profile_slots_v1.json"
$tachikomaRoot = "D:\AI\tachikoma"
$cli = Join-Path $tachikomaRoot ".runtime\playwright-mcp\node_modules\@playwright\mcp\cli.js"
$baseConfig = Join-Path $tachikomaRoot "config\playwright_browser_mcp.json"

if (-not (Test-Path -LiteralPath $policyPath)) {
    throw "Slot browser profile policy is missing: $policyPath"
}
if (-not (Test-Path -LiteralPath $cli)) {
    throw "Playwright MCP runtime is missing: $cli"
}
if (-not (Test-Path -LiteralPath $baseConfig)) {
    throw "Playwright browser base configuration is missing: $baseConfig"
}

$policy = Get-Content -LiteralPath $policyPath -Raw | ConvertFrom-Json
$matches = @($policy.slots | Where-Object { $_.account_slot -eq $AccountSlot })
if ($matches.Count -ne 1) {
    throw "The requested account slot is missing or ambiguous."
}
$slot = $matches[0]
$profileRoot = [System.IO.Path]::GetFullPath([string]$policy.profile_root).TrimEnd('\')
$outputRoot = [System.IO.Path]::GetFullPath([string]$policy.output_root).TrimEnd('\')
$profileDir = [System.IO.Path]::GetFullPath([string]$slot.profile_dir)
$outputDir = [System.IO.Path]::GetFullPath([string]$slot.output_dir)
$comparison = [System.StringComparison]::OrdinalIgnoreCase

if (-not $profileDir.StartsWith($profileRoot + '\', $comparison)) {
    throw "Slot profile path escapes the governed profile root."
}
if (-not $outputDir.StartsWith($outputRoot + '\', $comparison)) {
    throw "Slot output path escapes the governed output root."
}
if ($profileDir -ne (Join-Path $profileRoot "slot-$AccountSlot")) {
    throw "Slot profile path does not match its exact account slot."
}
if ($outputDir -ne (Join-Path $outputRoot "slot-$AccountSlot")) {
    throw "Slot output path does not match its exact account slot."
}

if ($ValidateOnly) {
    [pscustomobject]@{
        valid = $true
        account_slot = $AccountSlot
        mcp_server = [string]$slot.mcp_server
        profile_dir = $profileDir
        output_dir = $outputDir
        browser_started = $false
    } | ConvertTo-Json -Compress
    exit 0
}

New-Item -ItemType Directory -Force -Path $profileDir, $outputDir | Out-Null

# The shared base configuration keeps normal Chrome minimized and off-screen.
# Command-line paths override only the profile and output directories, so each
# slot persists independently without opening the user's everyday Chrome data.
& node.exe $cli --config $baseConfig --user-data-dir $profileDir --output-dir $outputDir
exit $LASTEXITCODE
