$ErrorActionPreference = 'Stop'
$item = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'repair-manifest.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $item.target -Algorithm SHA256).Hash.ToLower() -ne $item.hash) {
    throw 'HMI configuration changed since inspection; prepare the repair again.'
}
$backup = Join-Path $PSScriptRoot ('before-hmi-repair-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
Copy-Item -LiteralPath $item.target -Destination $backup
Copy-Item -LiteralPath $item.stage -Destination $item.target
if ((Get-FileHash -LiteralPath $item.target).Hash -ne (Get-FileHash -LiteralPath $item.stage).Hash) {
    throw 'Installed file differs from validated repair.'
}
Write-Output "Repaired HMI configuration source. Backup: $backup. No server restart, publishing or PLC access."
