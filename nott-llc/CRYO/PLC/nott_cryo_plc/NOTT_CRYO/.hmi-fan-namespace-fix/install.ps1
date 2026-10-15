$ErrorActionPreference = 'Stop'
$stageRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$manifest = Get-Content -LiteralPath (Join-Path $stageRoot 'manifest.json') -Raw | ConvertFrom-Json
$hmiRoot = [IO.Path]::GetFullPath($manifest.hmiRoot)
if ($hmiRoot -ne 'C:\Users\u0149673\NOTT\NOTTControl\nott-llc\CRYO\HMI\nott_cryo_hmi\nott_cryo_hmi') { throw 'Unexpected HMI root.' }
foreach ($entry in $manifest.files) {
    $source = [IO.Path]::GetFullPath((Join-Path $stageRoot $entry.path))
    $target = [IO.Path]::GetFullPath((Join-Path $hmiRoot $entry.path))
    if (-not $source.StartsWith($stageRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or -not $target.StartsWith($hmiRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Path outside intended roots.' }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $entry.sourceHash) { throw 'Staged source changed.' }
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $entry.originalHash) { throw ('HMI file changed: '+$entry.path) }
}
foreach ($entry in $manifest.files) {
    $source = Join-Path $stageRoot $entry.path
    $target = Join-Path $hmiRoot $entry.path
    $backup = Join-Path (Join-Path $stageRoot 'backup') $entry.path
    New-Item -ItemType Directory -Force -Path (Split-Path $backup) | Out-Null
    Copy-Item -LiteralPath $target -Destination $backup
    Copy-Item -LiteralPath $source -Destination $target
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $entry.sourceHash) { throw 'Installed hash mismatch.' }
}
Write-Output 'Namespace correction installed and verified. Existing files backed up. No server or PLC action performed.'

