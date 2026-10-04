param([Parameter(Mandatory=$true)][string]$Compiler, [Parameter(Mandatory=$true)][string]$WorkDir)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($WorkDir)
if (Test-Path -LiteralPath $root) { throw 'Fixture directory already exists' }
New-Item -ItemType Directory -Path $root | Out-Null
$source = Join-Path $root 'source'
$relative = ('deep-sdk-directory-' + ('a' * 65)) + '\' + ('b' * 85) + '\' + ('c' * 100) + '.txt'
$file = Join-Path $source $relative
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($file)) | Out-Null
[IO.File]::WriteAllText($file, 'Actelyo long path exact bytes')
$installed = Join-Path $root 'installed-user-profile-with-long-name'
$iss = Join-Path $root 'fixture.iss'
@"
[Setup]
AppId=ActelyoLongPathVerification
AppName=Actelyo Long Path Verification
AppVersion=1
DefaultDirName=$installed
PrivilegesRequired=lowest
Uninstallable=no
OutputDir=$root
OutputBaseFilename=fixture
[Files]
Source: "$source\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
"@ | Set-Content -LiteralPath $iss -Encoding UTF8
& $Compiler $iss
if ($LASTEXITCODE -ne 0) { throw 'Long path compilation failed' }
$process = Start-Process -FilePath (Join-Path $root 'fixture.exe') -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-') -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Long path installation failed' }
$result = Join-Path $installed $relative
if ($result.Length -le 260 -or [IO.File]::ReadAllText($result) -ne 'Actelyo long path exact bytes') { throw 'Long path installed bytes mismatch' }
Write-Output "Verified compile and install of $($result.Length)-character path"
