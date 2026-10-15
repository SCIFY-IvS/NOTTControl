$ErrorActionPreference = 'Stop'
$root = 'C:\Users\u0149673\NOTT\NOTTControl\nott-llc\CRYO\HMI\nott_cryo_hmi\nott_cryo_hmi'
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
foreach ($item in $manifest) {
    $target = Join-Path $root $item.file
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLower() -ne $item.hash) {
        throw "File changed since inspection: $target"
    }
}
$backup = Join-Path $PSScriptRoot ('backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
foreach ($item in $manifest) {
    $target = Join-Path $root $item.file
    $saved = Join-Path $backup $item.file
    New-Item -ItemType Directory -Path (Split-Path $saved) -Force | Out-Null
    Copy-Item -LiteralPath $target -Destination $saved
    Copy-Item -LiteralPath (Join-Path (Join-Path $PSScriptRoot 'files') $item.file) -Destination $target
}
Write-Output "Updated $($manifest.Count) HMI files. Backups: $backup"
