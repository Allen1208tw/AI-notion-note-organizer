#define MyAppName "AI Notion Note Organizer"
#define MyAppDisplayName "AI Notion 筆記整理器"
#define MyAppExeName "AI_Notion_Note_Organizer.exe"
#define MyAppPublisher "AI Notion Project"
#define MyAppDataDirName "AI Notion Note Organizer"

#ifndef MyAppVersion
  #define MyAppVersion "3.0.0"
#endif

#ifndef SourceDir
  #define SourceDir "..\dist\AI_Notion_Note_Organizer"
#endif

#ifndef OutputDir
  #define OutputDir "..\release"
#endif

[Setup]
AppId={{D86D77E7-E972-49D7-9877-F42136BEB5B8}
AppName={#MyAppDisplayName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppDisplayName}
DisableDirPage=auto
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=AI_Notion_Note_Organizer_Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UsePreviousAppDir=yes
CloseApplications=force
RestartApplications=no
SetupLogging=yes
UninstallDisplayName={#MyAppDisplayName}
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription={#MyAppDisplayName} Setup
VersionInfoCompany={#MyAppPublisher}
VersionInfoProductName={#MyAppDisplayName}
VersionInfoProductVersion={#MyAppVersion}

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "其他工作："; Flags: checkedonce

[InstallDelete]
Type: files; Name: "{app}\{#MyAppExeName}"
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\.env.example"; DestDir: "{localappdata}\{#MyAppDataDirName}"; Flags: onlyifdoesntexist
Source: "..\使用說明.txt"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{localappdata}\{#MyAppDataDirName}"
Name: "{localappdata}\{#MyAppDataDirName}\outputs"

[Icons]
Name: "{autoprograms}\{#MyAppDisplayName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppDisplayName} 使用說明"; Filename: "{app}\使用說明.txt"
Name: "{autodesktop}\{#MyAppDisplayName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "啟動 {#MyAppDisplayName}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Exec(
    ExpandConstant('{cmd}'),
    '/C taskkill /IM "{#MyAppExeName}" /F /T >NUL 2>NUL',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
  Result := True;
end;
