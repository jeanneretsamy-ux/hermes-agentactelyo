[Setup]
AppName=Actelyo runtime check
AppVersion=1.0
CreateAppDir=no
Uninstallable=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#ifdef Probe64
SetupArchitecture=x64
#endif
OutputDir={#ProbeOutputDir}
OutputBaseFilename=Runtime-Check-{#ProbeArch}
Compression=none

[Code]
#include "runtime-check.iss"

function JsonBool(Value: Boolean): String;
begin
  if Value then Result := 'true' else Result := 'false';
end;

function InitializeSetup: Boolean;
var
  MajorMinor, Build, PreviousMinor: Cardinal;
  BoundaryReady, OlderBuildRejected, OlderMinorRejected, NewerMinorReady: Boolean;
  MissingRejected, ActualReady, Passed: Boolean;
  Proof: String;
begin
  MajorMinor := {#VCRuntimeMajor} * 65536 + {#VCRuntimeMinor};
  Build := {#VCRuntimeBuild} * 65536;
  PreviousMinor := {#VCRuntimeMajor} * 65536 + {#VCRuntimeMinor} - 1;
  BoundaryReady := RuntimeVersionReady(MajorMinor, Build);
  OlderBuildRejected := not RuntimeVersionReady(MajorMinor, Build - 65536);
  OlderMinorRejected := not RuntimeVersionReady(PreviousMinor, $FFFFFFFF);
  NewerMinorReady := RuntimeVersionReady(MajorMinor + 1, 0);
  MissingRejected := not RuntimeDllReady('actelyo-nonexistent-runtime-qualification.dll');
  ActualReady := VCRuntimeReady;
  Passed := BoundaryReady and OlderBuildRejected and OlderMinorRejected and NewerMinorReady and MissingRejected;
  Proof := '{"passed":' + JsonBool(Passed) + ',"runtimeReady":' + JsonBool(ActualReady) +
    ',"boundaryReady":' + JsonBool(BoundaryReady) + ',"olderBuildRejected":' + JsonBool(OlderBuildRejected) +
    ',"olderMinorRejected":' + JsonBool(OlderMinorRejected) + ',"newerMinorReady":' + JsonBool(NewerMinorReady) +
    ',"missingDllRejected":' + JsonBool(MissingRejected) + ',"architecture":"{#ProbeArch}"}';
  if not SaveStringToFile('{#ProbeReceipt}', Proof, False) then RaiseException('Unable to save actual runtime check.');
  { Probe only: no application is installed or uninstalled. }
  Result := False;
end;
