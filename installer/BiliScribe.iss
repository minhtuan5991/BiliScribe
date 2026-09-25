#define MyAppName "BiliScribe"
#define MyAppVersion "1.2.0"
[Setup]
AppId={{59136726-3F92-476B-9D2B-435184773E58}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=BiliScribe
DefaultDirName={localappdata}\Programs\BiliScribe
DefaultGroupName=BiliScribe
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\release
OutputBaseFilename=BiliScribe-Setup-1.2.0-x64
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\BiliScribe.exe
UninstallDisplayName=BiliScribe
Compression=lzma2/fast
SolidCompression=yes
LZMANumBlockThreads=2
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
InfoBeforeFile=..\docs\INSTALL.txt
[Languages]
Name: "vietnamese"; MessagesFile: "Vietnamese.isl"
[Tasks]
Name: "desktopicon"; Description: "Tạo lối tắt ngoài Desktop"; GroupDescription: "Lối tắt:"
[Files]
Source: "..\dist\BiliScribe-1.2.0\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\BiliScribe"; Filename: "{app}\BiliScribe.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\BiliScribe"; Filename: "{app}\BiliScribe.exe"; WorkingDir: "{app}"; Tasks: desktopicon
[Run]
Filename: "{app}\BiliScribe.exe"; Description: "Mở BiliScribe"; Flags: nowait postinstall skipifsilent
