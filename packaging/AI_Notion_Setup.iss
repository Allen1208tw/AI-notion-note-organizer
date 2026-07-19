#ifndef MyAppVersion
  #define MyAppVersion "3.0.0"
#endif

#ifndef SourceDir
  #define SourceDir "..\dist\AI_Notion_Note_Organizer"
#endif

#ifndef OutputDir
  #define OutputDir "..\release"
#endif

#define MyAppName "AI Notion 筆記整理器"
#define MyAppExeName "AI_Notion_Note_Organizer.exe"
#define MyAppPublisher "AI Notion Project"

[Setup]
AppId={{D86D77E7-E972-49D7-9877-F42136BEB5B8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\AI Notion Note Organizer
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=AI_Notion_Note_Organizer_Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=yes
SetupLogging=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription={#MyAppName} 安裝程式
VersionInfoCompany={#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "其他工作："; Flags: checkedonce

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\.env.example"; DestDir: "{localappdata}\AI Notion Note Organizer"; Flags: onlyifdoesntexist

[Dirs]
Name: "{localappdata}\AI Notion Note Organizer"
Name: "{localappdata}\AI Notion Note Organizer\outputs"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "啟動 {#MyAppName}"; Flags: nowait postinstall skipifsilent
