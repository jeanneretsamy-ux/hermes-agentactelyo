param(
    [Parameter(Mandatory=$true)][string]$Destination,
    [string]$ManifestPath=(Join-Path $PSScriptRoot 'vc-runtime.json')
)
$ErrorActionPreference='Stop'
$spec=Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if($spec.sha256 -notmatch '^[0-9a-f]{64}$' -or $spec.publisher -ne 'Microsoft Corporation' -or $spec.url -notlike 'https://download.visualstudio.microsoft.com/*'){throw 'Invalid Visual C++ runtime manifest'}
$parent=Split-Path -Parent ([IO.Path]::GetFullPath($Destination))
New-Item -ItemType Directory -Path $parent -Force | Out-Null
if(!(Test-Path -LiteralPath $Destination)){
    [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri $spec.url -OutFile $Destination
}
if((Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $spec.sha256){throw 'Visual C++ runtime checksum mismatch; refusing to execute or package this file'}
$signature=Get-AuthenticodeSignature -LiteralPath $Destination
if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(^|,\s*)O=Microsoft Corporation(,|$)'){throw 'Visual C++ runtime Authenticode publisher verification failed'}
$version=[version]$spec.version
if((Get-Item -LiteralPath $Destination).VersionInfo.FileVersion -ne $spec.version){throw 'Visual C++ runtime file version differs from manifest'}
[pscustomobject]@{path=[IO.Path]::GetFullPath($Destination);sha256=$spec.sha256;version=$spec.version;major=$version.Major;minor=$version.Minor;build=$version.Build;signatureStatus=[string]$signature.Status}
