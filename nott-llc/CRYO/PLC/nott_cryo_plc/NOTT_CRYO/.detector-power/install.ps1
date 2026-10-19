$ErrorActionPreference='Stop'
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
foreach($item in $manifest){
    if($item.hash){
        if((Get-FileHash -LiteralPath $item.target -Algorithm SHA256).Hash.ToLower() -ne $item.hash){throw "Changed since inspection: $($item.target)"}
    }elseif(Test-Path -LiteralPath $item.target){throw "New file already exists: $($item.target)"}
}
$backup=Join-Path $PSScriptRoot ('backup-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$index=0
foreach($item in $manifest){
    if(Test-Path -LiteralPath $item.target){Copy-Item -LiteralPath $item.target -Destination (Join-Path $backup ($index.ToString()+'-'+[IO.Path]::GetFileName($item.target)))}
    New-Item -ItemType Directory -Path (Split-Path $item.target) -Force | Out-Null
    Copy-Item -LiteralPath $item.stage -Destination $item.target
    $index++
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Destination (Join-Path $backup 'manifest.json')
Write-Output "Installed $index source files. Backups: $backup. No runtime activation."
