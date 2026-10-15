$ErrorActionPreference = 'Stop'
$stageRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$manifest = Get-Content -LiteralPath (Join-Path $stageRoot 'install-manifest.json') -Raw | ConvertFrom-Json
$hmiRoot = [IO.Path]::GetFullPath($manifest.hmiRoot)
$expectedRoot = 'C:\Users\u0149673\NOTT\NOTTControl\nott-llc\CRYO\HMI\nott_cryo_hmi\nott_cryo_hmi'
if ($hmiRoot -ne $expectedRoot) { throw 'Unexpected HMI target root.' }
$checked = @()
foreach ($entry in $manifest.files) {
    $source = [IO.Path]::GetFullPath((Join-Path $stageRoot $entry.path))
    $target = [IO.Path]::GetFullPath((Join-Path $hmiRoot $entry.path))
    if (-not $source.StartsWith($stageRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Source escapes staging.' }
    if (-not $target.StartsWith($hmiRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Target escapes HMI root.' }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $entry.sourceHash) { throw ('Staged file changed: ' + $entry.path) }
    if ($entry.originalHash) {
        if (-not (Test-Path -LiteralPath $target) -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $entry.originalHash) { throw ('HMI file changed since review: ' + $entry.path) }
    } elseif (Test-Path -LiteralPath $target) {
        throw ('New HMI file now exists; refusing to overwrite: ' + $entry.path)
    }
    $checked += [pscustomobject]@{entry=$entry;source=$source;target=$target}
}
# Save the existing files before applying this narrowly scoped source update.
foreach ($file in $checked) {
    if ($file.entry.originalHash) {
        $backup = Join-Path (Join-Path $stageRoot 'backup') $file.entry.path
        New-Item -ItemType Directory -Force -Path (Split-Path $backup) | Out-Null
        Copy-Item -LiteralPath $file.target -Destination $backup
    }
}
foreach ($file in $checked) {
    New-Item -ItemType Directory -Force -Path (Split-Path $file.target) | Out-Null
    Copy-Item -LiteralPath $file.source -Destination $file.target
    if ((Get-FileHash -LiteralPath $file.target -Algorithm SHA256).Hash -ne $file.entry.sourceHash) { throw ('Installed hash mismatch: ' + $file.entry.path) }
}
Write-Output ('Installed and verified ' + $checked.Count + ' HMI source files. Original modified files are backed up in staging/backup.')

