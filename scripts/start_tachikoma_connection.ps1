param(
    [switch]$EnableProductionRead,
    [ValidateRange(1, 65535)]
    [int]$Port = 18060
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$executable = Join-Path $projectRoot "bin\xiaohongshu-mcp-tachikoma.exe"
$logRoot = Join-Path $projectRoot "logs"
$stdoutLog = Join-Path $logRoot "tachikoma-connection.out.log"
$stderrLog = Join-Path $logRoot "tachikoma-connection.err.log"

Set-Location -LiteralPath $projectRoot
$null = New-Item -ItemType Directory -Path (Split-Path -Parent $executable) -Force
$null = New-Item -ItemType Directory -Path $logRoot -Force

$goPath = (Get-Command go.exe -ErrorAction SilentlyContinue).Source
if (-not $goPath) {
    $goPath = Get-ChildItem -LiteralPath (Join-Path $projectRoot ".toolchains") -Recurse -Filter "go.exe" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $goPath) {
    throw "Go toolchain is required. Install Go or place a local toolchain under .toolchains."
}

& $goPath build -trimpath -o $executable .
if ($LASTEXITCODE -ne 0) {
    throw "Failed to build the Tachikoma connection executable."
}

$env:XHS_MCP_PORT = [string]$Port
$env:XHS_MCP_PRODUCTION_READ_ENABLED = if ($EnableProductionRead) { "true" } else { "false" }
$env:XHS_MCP_PRODUCTION_EXECUTION_ENABLED = "false"

$ErrorActionPreference = "Continue"
& $executable -headless=true 1>> $stdoutLog 2>> $stderrLog
exit $LASTEXITCODE
