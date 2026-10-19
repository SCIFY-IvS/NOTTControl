$ErrorActionPreference='Stop'
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
foreach($item in $manifest){
    if((Get-FileHash -LiteralPath $item.target -Algorithm SHA256).Hash.ToLower() -ne $item.hash){throw "Changed since inspection: $($item.target)"}
}
$backup=Join-Path $PSScriptRoot ('backup-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup | Out-Null
$index=0
foreach($item in $manifest){
    Copy-Item -LiteralPath $item.target -Destination (Join-Path $backup ($index.ToString()+'-'+[IO.Path]::GetFileName($item.target)))
    Copy-Item -LiteralPath $item.stage -Destination $item.target
    $index++
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Destination (Join-Path $backup 'manifest.json')
Write-Output "Installed $index HMI source/test files. Backup: $backup. No compilation, publishing, service restart or PLC access."
