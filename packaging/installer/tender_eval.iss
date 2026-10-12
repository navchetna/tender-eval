; Inno Setup script for Tender Evaluation (desktop build).
; Don't compile this directly - use `packaging\build.ps1 -Installer`, which builds the bundle at
; ..\..\dist\TenderEval\ first.
;
; Per-user install (no admin rights): the app, its embedded database, downloaded models and the
; OpenVINO compile cache all belong to the installing user (%LOCALAPPDATA%\TenderEval). The only
; machine-level prerequisite is the regular Intel GPU / NPU driver - no oneAPI, OpenVINO, OVMS,
; llama.cpp, Docker, WSL or PostgreSQL install.
;
; The wizard asks for the settings (admin account, optional Claude, optional Google) and writes
; them into %LOCALAPPDATA%\TenderEval\config.env, created from desktop\config.env.example. On an
; upgrade/reinstall an existing config.env is kept as-is and those pages are skipped.

#define AppName "Tender Evaluation"
#define AppVersion "0.3.1"
#define AppPublisher "Tender Evaluation"
#define AppExeName "TenderEval.exe"
#define ConfigDir "{localappdata}\TenderEval"

[Setup]
AppId={{7B2E4C1A-93F0-4D6B-8A55-2C9E0F1D3A47}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\TenderEval
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
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
; Settings file, only on a fresh install; filled in from the wizard pages by WriteSettings.
Source: "..\..\desktop\config.env.example"; DestDir: "{#ConfigDir}"; DestName: "config.env"; Flags: onlyifdoesntexist uninsneveruninstall; Check: ConfigMissing; AfterInstall: WriteSettings

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{#AppName} settings"; Filename: "{sys}\notepad.exe"; Parameters: """{#ConfigDir}\config.env"""; Comment: "Edit settings, then restart {#AppName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Parameters: "--no-browser"; Tasks: startup

[Run]
; Downloads the models and compiles them for this machine's NPU/GPU (cached for later starts).
Filename: "{app}\{#AppExeName}"; Parameters: "setup"; StatusMsg: "Downloading and preparing the AI models (this can take a while)..."; Flags: runhidden waituntilterminated; Tasks: prepareModels
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
Filename: "{sys}\notepad.exe"; Parameters: """{#ConfigDir}\config.env"""; Description: "Review all settings (config.env)"; Flags: nowait postinstall skipifsilent unchecked

; User data (%LOCALAPPDATA%\TenderEval: database, models, settings) is deliberately kept on
; uninstall so a reinstall/upgrade doesn't lose projects or re-download 3.5 GB of models.

[Code]
var
  AdminPage, ClaudePage, GooglePage: TInputQueryWizardPage;
  ConfigExists: Boolean;

function ConfigPath: String;
begin
  Result := ExpandConstant('{#ConfigDir}\config.env');
end;

procedure InitializeWizard;
begin
  ConfigExists := FileExists(ConfigPath);

  AdminPage := CreateInputQueryPage(wpSelectTasks,
    'Admin account', 'Who signs in to Tender Evaluation first?',
    'You will sign in to the app with this email and password. Both can be changed later in the ' +
    'settings file (Start menu > Tender Evaluation settings).');
  AdminPage.Add('Admin email:', False);
  AdminPage.Add('Admin password (at least 8 characters):', True);
  AdminPage.Values[0] := 'admin@example.com';

  ClaudePage := CreateInputQueryPage(AdminPage.ID,
    'Claude (optional)', 'Use Claude for the compliance matrix, scoring and comparison?',
    'Leave both fields empty to use the on-device model instead - you can switch any time on the ' +
    'Operations page. For an Anthropic API key (sk-ant-...), leave the endpoint empty. For Claude ' +
    'on Azure AI Foundry, enter the Foundry key and https://<resource>.openai.azure.com/anthropic');
  ClaudePage.Add('API key:', True);
  ClaudePage.Add('Endpoint (Azure AI Foundry only):', False);

  GooglePage := CreateInputQueryPage(ClaudePage.ID,
    'Gmail and Google Drive (optional)', 'Needed to upload or ingest tender and bid PDFs.',
    'Use a Google Cloud OAuth client of type "Desktop app" with the Gmail API and Google Drive ' +
    'API enabled. After installing, click "Connect Google" on the app''s Projects page once. ' +
    'Leave empty to set up later.');
  GooglePage.Add('OAuth client ID:', False);
  GooglePage.Add('OAuth client secret:', True);
  GooglePage.Add('Reviewer email for notifications (optional):', False);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  // Upgrade/reinstall: keep the existing settings untouched.
  Result := ConfigExists and
    ((PageID = AdminPage.ID) or (PageID = ClaudePage.ID) or (PageID = GooglePage.ID));
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  // Silent installs never show the page; they keep the example's defaults (see SetValue).
  if (CurPageID = AdminPage.ID) and not WizardSilent and
     ((Pos('@', AdminPage.Values[0]) = 0) or (Length(AdminPage.Values[1]) < 8)) then
  begin
    MsgBox('Enter an admin email and a password of at least 8 characters.', mbError, MB_OK);
    Result := False;
  end;
end;

function ConfigMissing: Boolean;
begin
  Result := not ConfigExists;
end;

procedure SetValue(var Lines: TArrayOfString; const Key, Value: String);
var
  I: Integer;
begin
  // Empty = keep the example's default (also what a /SILENT install, which skips the pages, gets).
  if Value = '' then
    Exit;
  for I := 0 to GetArrayLength(Lines) - 1 do
    if Pos(Key + '=', Lines[I]) = 1 then
    begin
      Lines[I] := Key + '=' + Value;
      Exit;
    end;
end;

procedure WriteSettings;
var
  Lines: TArrayOfString;
begin
  if not LoadStringsFromFile(ConfigPath, Lines) then
    Exit;
  SetValue(Lines, 'ADMIN_EMAIL', Trim(AdminPage.Values[0]));
  SetValue(Lines, 'ADMIN_PASSWORD', AdminPage.Values[1]);
  SetValue(Lines, 'ANTHROPIC_API_KEY', Trim(ClaudePage.Values[0]));
  SetValue(Lines, 'ANTHROPIC_BASE_URL', Trim(ClaudePage.Values[1]));
  SetValue(Lines, 'GMAIL_CLIENT_ID', Trim(GooglePage.Values[0]));
  SetValue(Lines, 'GMAIL_CLIENT_SECRET', Trim(GooglePage.Values[1]));
  SetValue(Lines, 'REVIEWER_EMAIL', Trim(GooglePage.Values[2]));
  SaveStringsToUTF8File(ConfigPath, Lines, False);
end;
