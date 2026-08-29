param(
    [int]$OldCodexPid = 45792,
    [int]$ChatGptPid = 60904,
    [string]$ExpectedCodexPath = 'C:\Users\lzdwy\AppData\Local\OpenAI\Codex\bin\a5c9108151f176e9\codex.exe',
    [string]$ExpectedWorkerPath = 'C:\Users\lzdwy\AppData\Local\OpenAI\Codex\runtimes\cua_node\f24ab376120677c2\bin\node_repl.exe',
    [string]$ServicePath = 'C:\Users\lzdwy\.codex\plugins\cache\openai-bundled\browser\26.820.80927\scripts\browser-service.mjs',
    [string]$ExpectedServiceSha256 = 'a138896fd38968a5d305ee3ccbc724d8867bea525f1f22f824ad4b11d8d8fba5',
    [string]$ReceiptPath = 'D:\AI\AI 媒体爬虫\xiaohongshu-mcp\research\panse_multi_direction\daily_runs\2026-08-28\codex_iab_v3_backend_restart_receipt_20260828.json'
)

$ErrorActionPreference = 'Stop'

function Write-Receipt([hashtable]$Receipt) {
    $directory = Split-Path -Parent $ReceiptPath
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $json = $Receipt | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText($ReceiptPath, $json, [Text.UTF8Encoding]::new($false))
}

$startedAt = Get-Date
$base = @{
    schema_version = 1
    date = '2026-08-28'
    receipt_type = 'codex_iab_v3_backend_restart'
    started_at = $startedAt.ToString('o')
    old_codex_pid = $OldCodexPid
    chatgpt_pid = $ChatGptPid
    expected_service_sha256 = $ExpectedServiceSha256
    platform_navigation_attempted = $false
    platform_or_account_action_performed = $false
}

try {
    $chatgpt = Get-CimInstance Win32_Process -Filter "ProcessId=$ChatGptPid"
    $oldCodex = Get-CimInstance Win32_Process -Filter "ProcessId=$OldCodexPid"
    if (-not $chatgpt -or $chatgpt.Name -ne 'ChatGPT.exe') {
        throw 'Exact ChatGPT supervisor process is not available.'
    }
    if (-not $oldCodex -or $oldCodex.Name -ne 'codex.exe' -or $oldCodex.ExecutablePath -ne $ExpectedCodexPath) {
        throw 'Exact old Codex app-server process does not match the requested target.'
    }
    if ($oldCodex.ParentProcessId -ne $ChatGptPid) {
        throw 'Old Codex app-server is not a direct child of the expected ChatGPT supervisor.'
    }
    $serviceSha = (Get-FileHash -LiteralPath $ServicePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($serviceSha -ne $ExpectedServiceSha256) {
        throw "Installed Browser service hash does not match v3: $serviceSha"
    }

    Stop-Process -Id $OldCodexPid -Force

    $codexDeadline = (Get-Date).AddSeconds(120)
    $newCodex = $null
    do {
        Start-Sleep -Seconds 2
        $newCodex = Get-CimInstance Win32_Process -Filter "Name='codex.exe'" | Where-Object {
            $_.ProcessId -ne $OldCodexPid -and
            $_.ParentProcessId -eq $ChatGptPid -and
            $_.ExecutablePath -eq $ExpectedCodexPath
        } | Sort-Object CreationDate -Descending | Select-Object -First 1
    } while (-not $newCodex -and (Get-Date) -lt $codexDeadline)

    if (-not $newCodex) {
        throw 'ChatGPT supervisor did not recreate the Codex app-server within 120 seconds.'
    }

    $workerDeadline = (Get-Date).AddSeconds(120)
    $workers = @()
    do {
        Start-Sleep -Seconds 2
        $workers = @(Get-CimInstance Win32_Process -Filter "Name='node_repl.exe'" | Where-Object {
            $_.ParentProcessId -eq $newCodex.ProcessId -and $_.ExecutablePath -eq $ExpectedWorkerPath
        })
    } while ($workers.Count -eq 0 -and (Get-Date) -lt $workerDeadline)

    if ($workers.Count -eq 0) {
        throw 'The recreated Codex app-server did not create any Browser control workers within 120 seconds.'
    }

    $workerStarts = foreach ($worker in $workers) {
        $process = Get-Process -Id $worker.ProcessId -ErrorAction SilentlyContinue
        if ($process) { $process.StartTime.ToString('o') }
    }
    Write-Receipt ($base + @{
        status = 'recovered_ready_for_control_probe'
        completed_at = (Get-Date).ToString('o')
        service_sha256 = $serviceSha
        new_codex_pid = $newCodex.ProcessId
        fresh_worker_count = $workers.Count
        earliest_worker_start = ($workerStarts | Sort-Object | Select-Object -First 1)
        latest_worker_start = ($workerStarts | Sort-Object | Select-Object -Last 1)
        next_step = 'Task 01 performs one control-only probe, then one fresh-tab homepage navigation and exact-id URL readback.'
    })
}
catch {
    Write-Receipt ($base + @{
        status = 'blocked_backend_restart'
        completed_at = (Get-Date).ToString('o')
        reason = $_.Exception.Message
        next_step = 'Do not perform Browser or platform actions until the Codex backend transport is restored.'
    })
    exit 1
}
