#ifndef AppSource
  #error AppSource must point to the verified bundled application
#endif
#ifndef ReleaseDir
  #error ReleaseDir must be supplied
#endif
#ifndef BuildVersion
  #define BuildVersion "2026.11.3"
#endif
#ifndef VCRedistSource
  #error VCRedistSource must point to the hash- and publisher-verified x64 Microsoft runtime
#endif
#ifndef VCRedistSHA256
  #error VCRedistSHA256 must match the pinned runtime manifest
#endif
#ifndef VCRuntimeMajor
  #error VCRuntimeMajor must be supplied from the runtime manifest
#endif
#ifndef VCRuntimeMinor
  #error VCRuntimeMinor must be supplied from the runtime manifest
#endif
#ifndef VCRuntimeBuild
  #error VCRuntimeBuild must be supplied from the runtime manifest
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
SetupIconFile=..\..\apps\desktop\assets\icon.ico
LicenseFile=..\..\LICENSE
UninstallDisplayIcon={app}\Actelyo Law Harness.exe
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci Actelyo Law Harness sur le bureau"
[Files]
Source: "{#VCRedistSource}"; DestDir: "{tmp}"; DestName: "vc_redist.x64.exe"; Flags: dontcopy
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Actelyo Law Harness"; Filename: "{app}\Actelyo Law Harness.exe"; IconFilename: "{app}\Actelyo Law Harness.exe"
Name: "{userdesktop}\Actelyo Law Harness"; Filename: "{app}\Actelyo Law Harness.exe"; IconFilename: "{app}\Actelyo Law Harness.exe"; Tasks: desktopicon

[Code]
function RuntimeDllReady(const Name: String): Boolean;
var
  VersionMS, VersionLS, RequiredMS: Cardinal;
begin
  Result := False;
  if not GetVersionNumbers(ExpandConstant('{sys}\') + Name, VersionMS, VersionLS) then
    Exit;
  RequiredMS := {#VCRuntimeMajor} * 65536 + {#VCRuntimeMinor};
  Result := (VersionMS > RequiredMS) or
    ((VersionMS = RequiredMS) and (VersionLS div 65536 >= {#VCRuntimeBuild}));
end;

function VCRuntimeReady: Boolean;
begin
  Result := RuntimeDllReady('vcruntime140.dll') and
    RuntimeDllReady('vcruntime140_1.dll') and RuntimeDllReady('msvcp140.dll');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  RuntimePath: String;
  ExitCode: Integer;
begin
  Result := '';
  if VCRuntimeReady then
  begin
    Log('Verified x64 Microsoft Visual C++ runtime already present.');
    Exit;
  end;
  Log('Installing missing x64 Microsoft Visual C++ runtime before Actelyo.');
  ExtractTemporaryFile('vc_redist.x64.exe');
  RuntimePath := ExpandConstant('{tmp}\vc_redist.x64.exe');
  if CompareText(GetSHA256OfFile(RuntimePath), '{#VCRedistSHA256}') <> 0 then
  begin
    Result := 'Le prerequis Microsoft est endommage. Installation Actelyo interrompue.';
    Exit;
  end;
  { Only Microsoft's prerequisite elevates. The Actelyo installation stays per-user. }
  if not ShellExec('runas', RuntimePath, '/install /passive /norestart', '',
    SW_SHOWNORMAL, ewWaitUntilTerminated, ExitCode) then
  begin
    Result := 'Le prerequis Microsoft Visual C++ doit etre autorise dans Windows : ' + SysErrorMessage(ExitCode);
    Exit;
  end;
  if ExitCode = 3010 then
  begin
    NeedsRestart := True;
    Result := 'Redemarrez Windows, puis relancez cet installateur Actelyo.';
    Exit;
  end;
  if (ExitCode <> 0) and (ExitCode <> 1638) then
  begin
    Result := 'Echec du prerequis Microsoft Visual C++ (code ' + IntToStr(ExitCode) + ').';
    Exit;
  end;
  if not VCRuntimeReady then
    Result := 'Le runtime Microsoft requis reste indisponible. Installation Actelyo interrompue.'
  else
    Log('Verified x64 Microsoft Visual C++ runtime after prerequisite installation.');
end;
