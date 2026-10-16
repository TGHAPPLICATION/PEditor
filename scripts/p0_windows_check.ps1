<#
P0 Windows 11 real-machine check (G0-05).

Runs: environment info -> uv sync -> fetch fonts -> ruff -> pytest -> smoke build
-> (optional) launch the app and ask whether the window appeared.
Writes build\p0-check\summary.md (paste it to Claude or into reports/P0/report.md)
and build\p0-check\log.txt. No computer name, user name or file paths are recorded
in the summary.

Usage (from the repo root, normal PowerShell, not admin):
  powershell -ExecutionPolicy Bypass -File scripts\p0_windows_check.ps1
  powershell -ExecutionPolicy Bypass -File scripts\p0_windows_check.ps1 -SkipLaunch   # CI / no GUI

This file is ASCII-only on purpose so Windows PowerShell 5.1 parses it correctly.
#>
param([switch]$SkipLaunch)

$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$out = Join-Path $root "build\p0-check"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$log = Join-Path $out "log.txt"
Set-Content -Path $log -Value "P0 Windows check $(Get-Date -Format s)" -Encoding UTF8
$rows = @()

function Invoke-Step([string]$name, [string]$cmd) {
    Write-Host "==> $name" -ForegroundColor Cyan
    Add-Content -Path $log -Value "`n==> $name : $cmd" -Encoding UTF8
    $text = & cmd /c "$cmd 2>&1"
    $code = $LASTEXITCODE
    $text | Add-Content -Path $log -Encoding UTF8
    $text | Select-Object -Last 5 | ForEach-Object { Write-Host "    $_" }
    $last = ($text | Where-Object { $_ -match "\S" } | Select-Object -Last 1)
    $script:rows += [pscustomobject]@{ Step = $name; Exit = $code; Last = "$last".Trim() }
    return $text
}

# 1. Environment (no host or user names)
$os = Get-CimInstance Win32_OperatingSystem
$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name.Trim()
$ramGb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$envLine = "$($os.Caption) $($os.Version) (build $($os.BuildNumber)), $($os.OSArchitecture); CPU: $cpu; RAM: $ramGb GB"
Write-Host $envLine
$commit = (& git rev-parse --short HEAD).Trim()
$uvVer = (& uv --version).Trim()

# 2-6. Checks
Invoke-Step "uv sync --locked" "uv sync --locked --all-groups" | Out-Null
Invoke-Step "fetch fonts (SHA-256)" "uv run python scripts/fetch_fonts.py" | Out-Null
Invoke-Step "ruff check" "uv run ruff check ." | Out-Null
Invoke-Step "ruff format --check" "uv run ruff format --check ." | Out-Null
Invoke-Step "pytest" "uv run pytest" | Out-Null
$smoke = Invoke-Step "smoke build" "uv run python packaging/smoke_build.py"
$versions = ($smoke | Where-Object { $_ -like "PEDITOR_SMOKE_OK*" } | Select-Object -First 1)

# 7. Real window (interactive only)
$window = "NOT RUN (-SkipLaunch)"
$windowOk = $true
if (-not $SkipLaunch) {
    Write-Host "==> launching PEditor; close the window after checking it" -ForegroundColor Cyan
    $p = Start-Process -FilePath "uv" -ArgumentList "run", "peditor" -PassThru
    $answer = Read-Host "Did a window titled 'PEditor 0.0.1' appear? (y/n)"
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    $exe = Join-Path $root "build\smoke\dist\peditor\peditor.exe"
    $p2 = Start-Process -FilePath $exe -PassThru
    $answer2 = Read-Host "Did the packaged peditor.exe window appear? (y/n)"
    if (-not $p2.HasExited) { Stop-Process -Id $p2.Id -Force -ErrorAction SilentlyContinue }
    $window = "uv run peditor: $answer; packaged exe: $answer2"
    $windowOk = ($answer -eq "y") -and ($answer2 -eq "y")
}

# Summary
$failed = @($rows | Where-Object { $_.Exit -ne 0 }).Count
$verdict = if ($failed -eq 0 -and $windowOk) { "PASS" } else { "FAIL" }
$md = @()
$md += "## P0 Windows real-machine check (G0-05)"
$md += ""
$md += "- date: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$md += "- commit: $commit"
$md += "- environment: $envLine"
$md += "- uv: $uvVer"
$md += "- versions: $versions"
$md += "- window check: $window"
$md += "- result: **$verdict**"
$md += ""
$md += "| step | exit code | last line |"
$md += "| --- | --- | --- |"
foreach ($r in $rows) { $md += "| $($r.Step) | $($r.Exit) | $($r.Last -replace '\|','/') |" }
$summary = Join-Path $out "summary.md"
$md | Set-Content -Path $summary -Encoding UTF8
Write-Host ""
$md | ForEach-Object { Write-Host $_ }
Write-Host "`nSummary written to build\p0-check\summary.md; full log in build\p0-check\log.txt"
if ($verdict -ne "PASS") { exit 1 }
