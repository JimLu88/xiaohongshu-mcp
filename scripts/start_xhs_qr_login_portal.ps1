[CmdletBinding()]
param(
    [int]$Port = 18765,
    [int]$AccountSlot = 0,
    [string]$PlanDate = "",
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
$entry = Join-Path $PSScriptRoot "xhs_qr_login_portal.py"

if (-not (Test-Path -LiteralPath $entry)) {
    throw "QR login portal entry is missing: $entry"
}

if ($ValidateOnly) {
    Write-Output "xhs_qr_login_portal_launcher=valid"
    exit 0
}

if ($AccountSlot -lt 1 -or $AccountSlot -gt 5) {
    throw "AccountSlot must be an explicit value from 1 to 5."
}

if ($PlanDate -notmatch '^\d{4}-\d{2}-\d{2}$') {
    throw "PlanDate must be explicit in YYYY-MM-DD format."
}

Write-Host "Xiaohongshu dedicated login portal: http://127.0.0.1:$Port/"
Write-Host "Target account slot: $AccountSlot; plan date: $PlanDate"
Write-Host "Use the account-switch button on the page only when you intend to switch."
& python $entry serve --host 127.0.0.1 --port $Port --account-slot $AccountSlot --plan-date $PlanDate
exit $LASTEXITCODE
