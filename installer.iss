; Inno Setup 6 Script for Desktop Utility Suite
; Generates a professional Windows installer executable (.exe)

#define MyAppName "Desktop Utility Suite"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Desktop Utility Suite Team"
#define MyAppURL "https://github.com/ashugit1234622/wallpaper-selector"
#define MyAppExeName "DesktopUtilitySuite.exe"

[Setup]
AppId={{9F83D1B4-61B2-4C7D-8912-3D8B08FA36A1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\Desktop Utility Suite
DisableProgramGroupPage=yes
LicenseFile=LICENSE
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist_installer
OutputBaseFilename=Desktop-Utility-Suite-v2.0.0-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "autostart"; Description: "Automatically start Desktop Utility Suite on Windows login"; GroupDescription: "Startup Options:"; Flags: unchecked

[Files]
Source: "dist\DesktopUtilitySuite\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\icon.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\icon.png"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon.ico"
Name: "{autoprograms}\{#MyAppName}\Download Folder Organizer"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--organizer"; IconFilename: "{app}\assets\icon.ico"
Name: "{autoprograms}\{#MyAppName}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DesktopUtilitySuite"; ValueData: """{app}\{#MyAppExeName}"" --on-login"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
