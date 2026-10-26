; Windows installer source for Inno Setup 6.
; The release workflow compiles this after PyInstaller creates dist/ARISE-I/.

#define AppName "ARISE-I"
; Pass the version on the command line: ISCC /DAppVersion=2.2.0 packaging\ARISE-I.iss
; (the release workflow takes it from the git tag or arise_i/__init__.py).
#ifndef AppVersion
  #error AppVersion is not defined - run ISCC with /DAppVersion=<version>
#endif
#define AppPublisher "Ironlabs"
#define AppURL "https://github.com/arise-om/ARISE-I"
#define AppExeName "ARISE-I.exe"

[Setup]
; Paths below are relative to the repository root.
SourceDir=..
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
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\ARISE-I\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
