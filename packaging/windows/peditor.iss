; PEditor Windows installer (Inno Setup 6; ADR-0025). Built by packaging/build_release.py:
;   ISCC.exe /DAppVersion=<ver> /DSourceDir=<dist\PEditor> /DOutputDir=<build\release> peditor.iss
; Per-user install (no admin rights). Uninstall removes the program files only; the user's
; recovery drafts and the temp-file registry under %LOCALAPPDATA%\PEditor are left in place and
; are documented in docs/release/install.md (draft cleanup).
; Unsigned test build: not an official deployment (spec P8).
; Explorer integration (ADR-0031): per-user (HKCU) right-click verb and an "Open with" entry
; for .pdf; the default PDF app is NOT changed. All keys are removed on uninstall.
; This file is UTF-8 (Inno Setup 6.3+ reads UTF-8 without BOM; CI pins 6.7.1). Only the menu
; label below is non-ASCII.

#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef SourceDir
  #error SourceDir is required
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

[Setup]
AppId={{6F1D2A4C-8B3E-4F5A-9C7D-2E1B0A9F8C34}
AppName=PEditor
AppVersion={#AppVersion}
AppPublisher=PEditor project (AGPL-3.0)
DefaultDirName={localappdata}\Programs\PEditor
DefaultGroupName=PEditor
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=PEditor-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
LicenseFile={#SourceDir}\LICENSE
UninstallDisplayName=PEditor {#AppVersion}
WizardStyle=modern
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PEditor"; Filename: "{app}\PEditor.exe"
Name: "{autodesktop}\PEditor"; Filename: "{app}\PEditor.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
Filename: "{app}\PEditor.exe"; Description: "{cm:LaunchProgram,PEditor}"; Flags: nowait postinstall skipifsilent

[Registry]
; Right-click verb on .pdf (Windows 10 menu; Windows 11 under "Show more options")
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PEditor"; ValueType: string; ValueName: ""; ValueData: "用 PEditor 開啟"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PEditor"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\PEditor.exe"",0"
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PEditor\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PEditor.exe"" ""%1"""
; "Open with" list (Windows 11 top-level menu); does not become the default app
Root: HKCU; Subkey: "Software\Classes\PEditor.pdf"; ValueType: string; ValueName: ""; ValueData: "PDF (PEditor)"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\PEditor.pdf\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\PEditor.exe"",0"
Root: HKCU; Subkey: "Software\Classes\PEditor.pdf\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PEditor.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "PEditor.pdf"; ValueData: ""; Flags: uninsdeletevalue
