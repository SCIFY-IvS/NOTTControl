# Creates a Desktop shortcut with the NOTT icon for NOTTControl.
param(
    [string]$Destination = (Join-Path $env:USERPROFILE "Desktop\NOTTControl.lnk")
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$IconPath = Join-Path $RepoRoot "nottcontrol\windows\NOTT.ico"
$Pythonw = $null

$candidates = @(
    (Join-Path $RepoRoot ".venv\Scripts\pythonw.exe"),
    (Join-Path $RepoRoot "venv\Scripts\pythonw.exe")
)

foreach ($candidate in $candidates) {
    if (Test-Path $candidate) {
        $Pythonw = $candidate
        break
    }
}

if (-not $Pythonw) {
    $pythonwCmd = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($pythonwCmd) {
        $Pythonw = $pythonwCmd.Source
    }
}

if (-not $Pythonw) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $Pythonw = $pythonCmd.Source
    }
}

if (-not $Pythonw) {
    throw "Python was not found. Install Python 3 or activate the project virtual environment."
}

if (-not (Test-Path $IconPath)) {
    throw "Missing icon file: $IconPath. Run nottcontrol/windows/build_assets.py first."
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($Destination)
$shortcut.TargetPath = $Pythonw
$shortcut.Arguments = "-m nottcontrol.main"
$shortcut.WorkingDirectory = $RepoRoot
$shortcut.WindowStyle = 1
$shortcut.Description = "NOTT instrument control"
$shortcut.IconLocation = "$IconPath,0"
$shortcut.Save()

Write-Host "Created shortcut: $Destination"
