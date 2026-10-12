; Inno Setup script for Tender Evaluation (desktop build).
; Don't compile this directly - use `packaging\build.ps1 -Installer`, which builds the bundle at
; ..\..\dist\TenderEval\ first.
;
; Per-user install (no admin rights): the app, its embedded database, downloaded models and the
; OpenVINO compile cache all belong to the installing user (%LOCALAPPDATA%\TenderEval). The only
; machine-level prerequisite is the regular Intel GPU / NPU driver - no oneAPI, OpenVINO, OVMS,
; llama.cpp, Docker, WSL or PostgreSQL install.

#define AppName "Tender Evaluation"
#define AppVersion "0.3.0"
#define AppPublisher "Tender Evaluation"
#define AppExeName "TenderEval.exe"

[Setup]
AppId={{7B2E4C1A-93F0-4D6B-8A55-2C9E0F1D3A47}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\TenderEval
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=TenderEval-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\..\frontend\src\app\favicon.ico
UninstallDisplayIcon={app}\{#AppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; The running app holds its files open; ask it to close before upgrading/uninstalling.
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startup"; Description: "Start {#AppName} when I sign in (runs in the tray)"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "prepareModels"; Description: "Download and prepare the on-device AI models now (~3.5 GB, needs internet)"; GroupDescription: "First-run setup:"

[Files]
Source: "..\..\dist\TenderEval\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Parameters: "--no-browser"; Tasks: startup

[Run]
; Downloads the models and compiles them for this machine's NPU/GPU (cached for later starts).
Filename: "{app}\{#AppExeName}"; Parameters: "setup"; StatusMsg: "Downloading and preparing the AI models (this can take a while)..."; Flags: runhidden waituntilterminated; Tasks: prepareModels
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

; User data (%LOCALAPPDATA%\TenderEval: database, models, settings) is deliberately kept on
; uninstall so a reinstall/upgrade doesn't lose projects or re-download 3.5 GB of models.
