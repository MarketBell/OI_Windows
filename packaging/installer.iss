; Inno Setup script for OI Pulse Dashboard.
; Build the .exe first (see BUILD.md), then open this file in Inno Setup Compiler and click Build,
; or run:  ISCC.exe packaging\installer.iss   (from the project root).
;
; IMPORTANT: installs per-user into {localappdata} (NOT Program Files) so the app can write its
; own data files (oi_pulse.db, zerodha_credentials.json, license.json) next to the exe without
; admin rights or "read-only folder" errors. This needs no source changes.

#define AppName "OI Pulse Dashboard"
#define AppVersion "1.0.0"
#define AppPublisher "Billionit Wealth"
#define AppExeName "OI Pulse Dashboard.exe"

[Setup]
AppId={{B1A9F0C2-6D3E-4E71-9A2B-OIPULSE00001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://billionitwealth.in
DefaultDirName={localappdata}\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=OI-Pulse-Dashboard-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; SetupIconFile=packaging\app.ico   ; uncomment once an icon is added

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; Copies the whole PyInstaller onedir output.
Source: "..\dist\OI Pulse Dashboard\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
