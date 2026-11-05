<#
P7 Windows real-machine check: offline open/edit/save and outbound monitoring
(G7-01, G7-02, G7-03).

Before running: disconnect the network (unplug the cable / turn off Wi-Fi or airplane mode)
for G7-01. The script records how many network adapters are up; it still runs if some are up
(G7-02 then also shows that nothing tried to connect while the network was available).

Runs scripts\p7_flow.py (open, analyse, render, plan, preview, apply, undo, redo, save T01;
open and render the malicious samples S02-S06) and, while it runs, polls every 100 ms the
TCP connections, TCP listeners and UDP endpoints of the machine; at the end it keeps those
owned by the flow process or any of its child processes (uv, Python, PDF worker; the process
tree is refreshed about once a second). Polling can miss a connection attempt shorter than
the polling interval; the automated tests (audit hook, Job Object) cover that gap.

Writes build\p7-check\summary.md (paste it to Claude or into reports/P7/report.md) and
build\p7-check\log.txt. No computer name, user name or file paths are recorded.

Usage (from the repo root, normal PowerShell, not admin):
  powershell -ExecutionPolicy Bypass -File scripts\p7_offline_check.ps1

This file is ASCII-only on purpose so Windows PowerShell 5.1 parses it correctly.
#>

param([int]$Rounds = 10)

$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$out = Join-Path $root "build\p7-check"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$log = Join-Path $out "log.txt"
Set-Content -Path $log -Value "P7 Windows check $(Get-Date -Format s)" -Encoding UTF8

function Get-Tree([int]$rootPid) {
    $all = Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name
    $tree = @{}
    $tree[$rootPid] = $true
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($p in $all) {
            if ($tree.ContainsKey([int]$p.ParentProcessId) -and -not $tree.ContainsKey([int]$p.ProcessId)) {
                $tree[[int]$p.ProcessId] = $true
                $changed = $true
            }
        }
    }
    return $tree
}

# 1. Network state (adapter count only)
$up = @(Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Up" }).Count
$windows = (Get-CimInstance Win32_OperatingSystem).Caption + " " + (Get-CimInstance Win32_OperatingSystem).Version
Write-Host "Network adapters up: $up"

# 2. Run the flow and monitor sockets
$flowOut = Join-Path $out "flow"
if (Test-Path $flowOut) { Remove-Item -Recurse -Force $flowOut }
$stdout = Join-Path $out "flow-stdout.txt"
$stderr = Join-Path $out "flow-stderr.txt"
$proc = Start-Process -FilePath "uv" -ArgumentList @("run", "python", "-P", "scripts\p7_flow.py", "`"$flowOut`"", "$Rounds") `
    -NoNewWindow -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$null = $proc.Handle  # keep the handle so ExitCode is available after exit
$startedAt = Get-Date
$rows = New-Object System.Collections.ArrayList
$pids = @{}
$maxPids = 0
$polls = 0
$lastTree = [datetime]::MinValue
while (-not $proc.HasExited) {
    if (((Get-Date) - $lastTree).TotalMilliseconds -ge 1000) {
        $tree = Get-Tree $proc.Id
        foreach ($k in $tree.Keys) { $pids[$k] = $true }
        if ($tree.Count -gt $maxPids) { $maxPids = $tree.Count }
        $lastTree = Get-Date
    }
    foreach ($c in @(Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
        [void]$rows.Add(@([int]$c.OwningProcess, "TCP $($c.LocalAddress):$($c.LocalPort) -> $($c.RemoteAddress):$($c.RemotePort) $($c.State)"))
    }
    foreach ($u in @(Get-NetUDPEndpoint -ErrorAction SilentlyContinue)) {
        [void]$rows.Add(@([int]$u.OwningProcess, "UDP $($u.LocalAddress):$($u.LocalPort)"))
    }
    $polls += 1
    Start-Sleep -Milliseconds 100
}
$seen = @{}
foreach ($r in $rows) { if ($pids.ContainsKey($r[0])) { $seen[$r[1]] = $true } }
$proc.WaitForExit()
$elapsed = ((Get-Date) - $startedAt).TotalSeconds
$flowExit = $proc.ExitCode
$flowLast = (Get-Content $stdout -ErrorAction SilentlyContinue | Select-Object -Last 1)
Get-Content $stdout, $stderr -ErrorAction SilentlyContinue | Add-Content -Path $log -Encoding UTF8
$flowJson = Join-Path $flowOut "flow.json"
$flow = if (Test-Path $flowJson) { Get-Content $flowJson -Raw -Encoding UTF8 } else { "(missing)" }

# 3. Summary
$sockets = @($seen.Keys | Sort-Object)
$commit = (& git rev-parse --short HEAD).Trim()
$lines = @(
    "# P7 Windows real-machine check",
    "",
    "- Date: $(Get-Date -Format s)",
    "- Commit: $commit",
    "- OS: $windows",
    "- Network adapters up during the run: $up (0 = offline, G7-01)",
    "- Flow exit code: $flowExit; last line: $flowLast",
    "- Flow rounds: $Rounds; duration: $([math]::Round($elapsed, 1)) s; socket polls: $polls (average interval $([math]::Round($elapsed / [math]::Max($polls, 1), 2)) s); max processes in tree: $maxPids",
    "- Sockets seen (any address, including loopback and listeners): $($sockets.Count)"
)
foreach ($s in $sockets) { $lines += "  - $s" }
$lines += @("", "## flow.json", "", '```json', $flow.Trim(), '```')
$summary = Join-Path $out "summary.md"
Set-Content -Path $summary -Value $lines -Encoding UTF8
$lines | ForEach-Object { Write-Host $_ }
Write-Host ""
Write-Host "Summary written to build\p7-check\summary.md"
if ($flowExit -ne 0 -or $sockets.Count -gt 0) { exit 1 } else { exit 0 }
