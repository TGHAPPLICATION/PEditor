; LUMICAT Windows installer (Inno Setup 6; ADR-0025). Built by packaging/build_release.py:
;   ISCC.exe /DAppVersion=<ver> /DSourceDir=<dist\LUMICAT> /DOutputDir=<build\release> lumicat.iss
; Per-user install (no admin rights). Uninstall removes the program files only; the user's
; recovery drafts and the temp-file registry under %LOCALAPPDATA%\LUMICAT are left in place and
; are documented in docs/release/install.md (draft cleanup).
; Unsigned test build: not an official deployment (spec P8).
; Explorer integration (ADR-0031): per-user (HKCU) right-click verb and an "Open with" entry
; for .pdf; the default PDF app is NOT changed. All keys are removed on uninstall.
; This file is ASCII-only. Chinese UI strings are built in [Code] from Unicode code points
; (#$XXXX), so they do not depend on how the script file is decoded (ADR-0031 section 5).

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
; New AppId for the LUMICAT name (ADR-0034); PEditor test installs are uninstalled separately
AppId={{C1D285B1-CE4F-4431-A669-F12FEB8E0D91}
AppName=LUMICAT
AppVersion={#AppVersion}
AppPublisher=LUMICAT project (AGPL-3.0)
DefaultDirName={localappdata}\Programs\LUMICAT
DefaultGroupName=LUMICAT
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=LUMICAT-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
LicenseFile={#SourceDir}\LICENSE
UninstallDisplayName=LUMICAT {#AppVersion}
WizardStyle=modern
; Relative to this script (packaging\windows)
SetupIconFile=..\icons\lumicat.ico
UninstallDisplayIcon={app}\LUMICAT.exe
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\LUMICAT"; Filename: "{app}\LUMICAT.exe"
Name: "{autodesktop}\LUMICAT"; Filename: "{app}\LUMICAT.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
Filename: "{app}\LUMICAT.exe"; Description: "{cm:LaunchProgram,LUMICAT}"; Flags: nowait postinstall skipifsilent
; Optional, unchecked: open Windows "Default apps" for LUMICAT so the user picks it for .pdf
; (Windows does not let installers set the default themselves; ADR-0031 section 6)
Filename: "ms-settings:defaultapps?registeredAppUser=LUMICAT"; Description: "{code:DefaultAppCaption}"; Flags: shellexec nowait postinstall skipifsilent unchecked

[Registry]
; Right-click verb on .pdf (Windows 10 menu; Windows 11 under "Show more options")
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\LUMICAT"; ValueType: string; ValueName: ""; ValueData: "{code:OpenVerbCaption}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\LUMICAT"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\LUMICAT.exe"",0"
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\LUMICAT\command"; ValueType: string; ValueName: ""; ValueData: """{app}\LUMICAT.exe"" ""%1"""
; "Open with" list (Windows 11 top-level menu); does not become the default app
Root: HKCU; Subkey: "Software\Classes\LUMICAT.pdf"; ValueType: string; ValueName: ""; ValueData: "PDF (LUMICAT)"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\LUMICAT.pdf\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\LUMICAT.exe"",0"
Root: HKCU; Subkey: "Software\Classes\LUMICAT.pdf\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\LUMICAT.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "LUMICAT.pdf"; ValueData: ""; Flags: uninsdeletevalue
; Registered application (lets Windows "Default apps" list LUMICAT for .pdf)
Root: HKCU; Subkey: "Software\LUMICAT"; Flags: uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\LUMICAT\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "LUMICAT"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\LUMICAT\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Offline PDF text editor"
Root: HKCU; Subkey: "Software\LUMICAT\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "LUMICAT.pdf"
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "LUMICAT"; ValueData: "Software\LUMICAT\Capabilities"; Flags: uninsdeletevalue

[LangOptions]
; The English wizard font may lack CJK glyphs on some systems; this one has them (ADR-0031 section 5)
DialogFontName=Microsoft JhengHei UI

[Code]
function DefaultAppCaption(Param: String): String;
begin
  // Caption of the optional last-page checkbox
  Result := #$8A2D + #$5B9A + ' LUMICAT ' + #$70BA + ' PDF ' + #$9810 + #$8A2D + #$7A0B + #$5F0F + #$FF08 + #$958B + #$555F + ' Windows ' + #$8A2D + #$5B9A + #$FF09;
end;

function OpenVerbCaption(Param: String): String;
begin
  // Right-click menu label for .pdf
  Result := #$7528 + ' LUMICAT ' + #$958B + #$555F;
end;
