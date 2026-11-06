$ErrorActionPreference = 'Stop'
$temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$fixture = Join-Path $temporaryRoot ('actelyo-qa-evidence-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $fixture 'proof'),(Join-Path $fixture 'icon-proof'),(Join-Path $fixture 'dist') -Force | Out-Null
try {
  [IO.File]::WriteAllText((Join-Path $fixture 'build-manifest.json'), '{}')
  [IO.File]::WriteAllText((Join-Path $fixture 'installer.log'), 'synthetic')
  [IO.File]::WriteAllBytes((Join-Path $fixture 'proof/window.png'), [byte[]]@(1,2,3))
  [IO.File]::WriteAllText((Join-Path $fixture 'icon-proof/report.json'), '{}')
  [IO.File]::WriteAllBytes((Join-Path $fixture 'installer.exe'), (New-Object byte[] 4096))
  [IO.File]::WriteAllBytes((Join-Path $fixture 'dist/installer.part01'), (New-Object byte[] 4096))
  $result = & (Join-Path $PSScriptRoot 'Select-QAEvidence.ps1') -Root $fixture
  if ($result.Files.Count -ne 4 -or $result.TotalBytes -ne 16) { throw 'Evidence selection or byte accounting mismatch' }
  if (@($result.Files | Where-Object { $_ -match '\.(exe|part01)$' }).Count) { throw 'Installer entered QA evidence' }
  $rejected = $false
  try { & (Join-Path $PSScriptRoot 'Select-QAEvidence.ps1') -Root $fixture -MaximumBytes 15 | Out-Null } catch { $rejected = $_.Exception.Message -like 'QA evidence is*' }
  if (!$rejected) { throw 'Oversized evidence was not refused' }
  $empty = & (Join-Path $PSScriptRoot 'Select-QAEvidence.ps1') -Root (Join-Path $fixture 'absent')
  if ($empty.Files.Count -ne 0 -or $empty.TotalBytes -ne 0) { throw 'Missing failure evidence directory must be allowed' }
  Write-Output 'PASS QA evidence: original reports retained, installer excluded, size limit enforced'
} finally {
  $resolved = [IO.Path]::GetFullPath($fixture)
  if (!$resolved.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetFileName($resolved) -notlike 'actelyo-qa-evidence-*') { throw 'Refusing unexpected fixture cleanup path' }
  Remove-Item -LiteralPath $resolved -Recurse -Force
}
