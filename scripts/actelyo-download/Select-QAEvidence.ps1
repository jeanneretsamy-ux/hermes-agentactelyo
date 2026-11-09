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
$originalBytes = [long]$total
$logsCompressed = $false
if ($total -gt $MaximumBytes) {
  # Installer file-by-file logs can exceed the artifact budget by themselves.
  # Preserve them losslessly, rather than dropping evidence or raising the gate.
  $logs = @($files | Where-Object { $_.Extension -in '.txt','.log' })
  $logBytes = ($logs | Measure-Object Length -Sum).Sum
  if ($logBytes -ge 64KB) {
    $archivePath = Join-Path ([IO.Path]::GetFullPath($Root)) ('qa-logs-' + [guid]::NewGuid().ToString('N') + '.zip')
    $stream = [IO.File]::Open($archivePath, [IO.FileMode]::CreateNew)
    $zip = [IO.Compression.ZipArchive]::new($stream, [IO.Compression.ZipArchiveMode]::Create)
    try {
      foreach ($log in $logs) {
        $entry = $zip.CreateEntry($log.Name, [IO.Compression.CompressionLevel]::Optimal)
        $source = [IO.File]::OpenRead($log.FullName)
        $destination = $entry.Open()
        try { $source.CopyTo($destination) } finally { $destination.Dispose(); $source.Dispose() }
      }
    } finally { $zip.Dispose(); $stream.Dispose() }
    $files = @($files | Where-Object { $_.Extension -notin '.txt','.log' }) + @(Get-Item -LiteralPath $archivePath)
    $total = ($files | Measure-Object Length -Sum).Sum
    $logsCompressed = $true
  }
}
if ($total -gt $MaximumBytes) {
  throw "QA evidence is $total bytes, above the $MaximumBytes byte limit. Keep installer binaries in the separate verified-installer artifact."
}
[pscustomobject]@{ Files = @($files | ForEach-Object FullName); TotalBytes = [long]$total; OriginalBytes = $originalBytes; LogsCompressed = $logsCompressed }
