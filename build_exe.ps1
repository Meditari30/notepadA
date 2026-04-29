$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$script = Join-Path $here 'diary_gui.py'
if (!(Test-Path $script)) { throw "Missing diary_gui.py in $here" }

# optional icon at .\assets\icon.ico
$icon = Join-Path $here 'assets\icon.ico'
$iconArg = @()
if (Test-Path $icon) {
  $iconArg = @('--icon', $icon)
}

# build (onefile + windowed)
py -m PyInstaller -F -w @iconArg --name '日记本' $script

# copy to Desktop
$desktop = [Environment]::GetFolderPath('Desktop')
$src = Join-Path $here 'dist\日记本.exe'
if (!(Test-Path $src)) { throw "Build output not found: $src" }
Copy-Item $src (Join-Path $desktop '日记本.exe') -Force

Write-Host "OK -> $desktop\日记本.exe"