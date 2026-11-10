{ Resolve x64 system DLLs for the actual Setup process bitness.
  Inno 7 does not implicitly redirect arbitrary [Code] file operations. }
function RuntimeVersionReady(VersionMS, VersionLS: Cardinal): Boolean;
var RequiredMS: Cardinal;
begin
  RequiredMS := {#VCRuntimeMajor} * 65536 + {#VCRuntimeMinor};
  Result := (VersionMS > RequiredMS) or
    ((VersionMS = RequiredMS) and (VersionLS div 65536 >= {#VCRuntimeBuild}));
end;

function RuntimeDllReady(const Name: String): Boolean;
var
  VersionMS, VersionLS: Cardinal;
  RuntimePath: String;
begin
  RuntimePath := ExpandConstant('{sys}\') + Name;
  #if VER >= EncodeVer(7, 0, 0)
    RuntimePath := ApplyPathRedirRules(True, RuntimePath, tpCurrent);
  #endif
  Result := GetVersionNumbers(RuntimePath, VersionMS, VersionLS);
  if not Result then
  begin
    Log('Required x64 runtime DLL unavailable: ' + RuntimePath);
    Exit;
  end;
  Result := RuntimeVersionReady(VersionMS, VersionLS);
  Log(Format('Required x64 runtime DLL %s: %d.%d.%d.%d', [RuntimePath, VersionMS div 65536, VersionMS mod 65536,
     VersionLS div 65536, VersionLS mod 65536]));
end;

function VCRuntimeReady: Boolean;
begin
  Result := RuntimeDllReady('vcruntime140.dll') and
    RuntimeDllReady('vcruntime140_1.dll') and RuntimeDllReady('msvcp140.dll');
end;
