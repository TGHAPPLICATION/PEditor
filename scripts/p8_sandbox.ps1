<#
P8 clean-environment check (G8-01, G8-02): build a Windows Sandbox configuration and start it.

Windows Sandbox is a fresh, disposable Windows with no Python and no PEditor. The generated
configuration:
  - disables networking (offline install and core flow, G8-01);
  - maps the folder that holds the installer read-only to C:\P8\installer;
  - maps tests\fixtures\files read-only to C:\P8\fixtures;
  - maps build\p8-sandbox\results read-write to C:\P8\results (save edited PDFs here so they
    can be opened in two PDF readers on the host, G8-02).
Everything inside the sandbox is discarded when it is closed.

Requirements: Windows 11 Pro/Enterprise with the "Windows Sandbox" optional feature enabled
(needs administrator rights once). Follow the P8 acceptance checklist while the sandbox runs.

Usage (from the repo root, normal PowerShell):
  powershell -ExecutionPolicy Bypass -File scripts\p8_sandbox.ps1 -InstallerDir <folder with PEditor-*-setup.exe>

This file is ASCII-only on purpose so Windows PowerShell 5.1 parses it correctly.
#>
param([Parameter(Mandatory = $true)][string]$InstallerDir)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$installer = (Resolve-Path $InstallerDir).Path
if (-not (Get-ChildItem -Path $installer -Filter "PEditor-*-setup.exe" -ErrorAction SilentlyContinue)) {
    throw "No PEditor-*-setup.exe in the installer folder"
}
$fixtures = Join-Path $root "tests\fixtures\files"
$out = Join-Path $root "build\p8-sandbox"
$results = Join-Path $out "results"
New-Item -ItemType Directory -Force -Path $results | Out-Null

function Esc([string]$s) { return [System.Security.SecurityElement]::Escape($s) }

$wsb = @"
<Configuration>
  <Networking>Disable</Networking>
  <vGPU>Disable</vGPU>
  <ClipboardRedirection>Disable</ClipboardRedirection>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>$(Esc $installer)</HostFolder>
      <SandboxFolder>C:\P8\installer</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>$(Esc $fixtures)</HostFolder>
      <SandboxFolder>C:\P8\fixtures</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>$(Esc $results)</HostFolder>
      <SandboxFolder>C:\P8\results</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>explorer.exe C:\P8</Command>
  </LogonCommand>
</Configuration>
"@
$path = Join-Path $out "peditor-p8.wsb"
Set-Content -Path $path -Value $wsb -Encoding UTF8
Write-Host "Sandbox configuration: build\p8-sandbox\peditor-p8.wsb (networking disabled)"
Write-Host "Results folder on the host: build\p8-sandbox\results"
Start-Process -FilePath $path
