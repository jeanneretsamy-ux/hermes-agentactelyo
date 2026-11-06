[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Root,
  [long]$MaximumBytes = 64MB
)
$ErrorActionPreference = 'Stop'
$files = @()
if (Test-Path -LiteralPath $Root -PathType Container) {
  $files += @(Get-ChildItem -LiteralPath $Root -File | Where-Object { $_.Extension -in '.txt','.log','.json' })
  foreach ($name in @('proof','icon-proof')) {
    $directory = Join-Path $Root $name
    if (Test-Path -LiteralPath $directory -PathType Container) {
      $files += @(Get-ChildItem -LiteralPath $directory -File | Where-Object { $_.Extension -in '.png','.json' })
    }
  }
}
$files = @($files | Sort-Object FullName -Unique)
$total = ($files | Measure-Object Length -Sum).Sum
if ($null -eq $total) { $total = 0 }
if ($total -gt $MaximumBytes) {
  throw "QA evidence is $total bytes, above the $MaximumBytes byte limit. Keep installer binaries in the separate verified-installer artifact."
}
[pscustomobject]@{ Files = @($files | ForEach-Object FullName); TotalBytes = [long]$total }
