; Windows installer source for Inno Setup 6.
; The release workflow compiles this after PyInstaller creates dist/ARISE-I/.

#define AppName "ARISE-I"
#define AppVersion "1.3.0"
#define AppPublisher "Ironlabs"
#define AppURL "https://github.com/arise-om/ARISE-I"
#define AppExeName "ARISE-I.exe"

[Setup]
AppId={{2E6119A1-066E-4E6A-AD55-520EDA2D391B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=release
OutputBaseFilename=ARISE-I-Setup-{#AppVersion}-Windows
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\ARISE-I\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
