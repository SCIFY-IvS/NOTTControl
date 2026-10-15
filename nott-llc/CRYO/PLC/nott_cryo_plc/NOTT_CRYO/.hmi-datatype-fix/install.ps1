$ErrorActionPreference = 'Stop'
$stage = [IO.Path]::GetFullPath($PSScriptRoot)
$manifest = Get-Content -LiteralPath (Join-Path $stage 'manifest.json') -Raw | ConvertFrom-Json
$root = [IO.Path]::GetFullPath($manifest.hmiRoot)
if ($root -ne 'C:\Users\u0149673\NOTT\NOTTControl\nott-llc\CRYO\HMI\nott_cryo_hmi\nott_cryo_hmi') { throw 'Unexpected HMI root.' }
foreach ($file in $manifest.files) {
    $source = [IO.Path]::GetFullPath((Join-Path $stage $file.path))
    $target = [IO.Path]::GetFullPath((Join-Path $root $file.path))
    if (-not $source.StartsWith($stage + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or -not $target.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Path outside intended roots.' }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $file.sourceHash -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $file.originalHash) { throw ('File changed since review: ' + $file.path) }
}
foreach ($file in $manifest.files) {
    $target = Join-Path $root $file.path
    $backup = Join-Path (Join-Path $stage 'backup') $file.path
    New-Item -ItemType Directory -Force -Path (Split-Path $backup) | Out-Null
    Copy-Item -LiteralPath $target -Destination $backup
    Copy-Item -LiteralPath (Join-Path $stage $file.path) -Destination $target
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $file.sourceHash) { throw 'Installed hash mismatch.' }
}
Write-Output 'Applied and verified the three HMI datatype edits. Originals backed up; no runtime actions performed.'

