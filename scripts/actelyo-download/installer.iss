#ifndef AppSource
  #error AppSource must point to the verified bundled application
#endif
#ifndef ReleaseDir
  #error ReleaseDir must be supplied
#endif
#ifndef BuildVersion
  #define BuildVersion "2026.10.4"
#endif
#ifndef RepoRoot
  #define RepoRoot "..\.."
#endif
[Setup]
AppId={{4B617AF4-6EA4-4220-849A-8044F224B92C}
AppName=Actelyo Law Harness
AppVersion={#BuildVersion}
AppPublisher=Actelyo
AppPublisherURL=https://actelyo.com
DefaultDirName={localappdata}\Programs\ActelyoLawHarness
DefaultGroupName=Actelyo Law Harness
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#ReleaseDir}
OutputBaseFilename=Actelyo-Law-Harness-Setup-x64
SetupIconFile={#RepoRoot}\apps\desktop\assets\icon.ico
LicenseFile={#RepoRoot}\LICENSE
UninstallDisplayIcon={app}\Actelyo Law Harness.exe
Compression=lzma2/max
SolidCompression=yes
MinVersion=10.0
WizardStyle=modern
CloseApplications=yes
[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci Actelyo Law Harness sur le bureau"
[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Actelyo Law Harness"; Filename: "{app}\Actelyo Law Harness.exe"; IconFilename: "{app}\Actelyo Law Harness.exe"
Name: "{userdesktop}\Actelyo Law Harness"; Filename: "{app}\Actelyo Law Harness.exe"; IconFilename: "{app}\Actelyo Law Harness.exe"; Tasks: desktopicon
