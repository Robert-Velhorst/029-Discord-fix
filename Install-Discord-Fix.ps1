[CmdletBinding()]
param(
    [string]$InstallDirectory,
    [string]$ShortcutDirectory
)
$ErrorActionPreference = 'Stop'
$sourceExecutable = Join-Path $PSScriptRoot 'DiscordFix.exe'
if (-not (Test-Path -LiteralPath $sourceExecutable)) { throw 'DiscordFix.exe must be next to this installer.' }
if (-not $InstallDirectory) { $InstallDirectory = Join-Path $env:LOCALAPPDATA 'Programs\DiscordFix' }
New-Item -ItemType Directory -Path $installDirectory -Force | Out-Null
$targetExecutable = Join-Path $installDirectory 'DiscordFix.exe'
if (Test-Path -LiteralPath $targetExecutable) {
    Copy-Item -LiteralPath $targetExecutable -Destination (Join-Path $installDirectory ('DiscordFix.previous.' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.exe'))
}
Copy-Item -LiteralPath $sourceExecutable -Destination $targetExecutable -Force
if (-not $ShortcutDirectory) { $ShortcutDirectory = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs' }
New-Item -ItemType Directory -Path $ShortcutDirectory -Force | Out-Null
$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut((Join-Path $shortcutDirectory 'Discord Fix.lnk'))
$shortcut.TargetPath = $targetExecutable
$shortcut.WorkingDirectory = $installDirectory
$shortcut.Description = 'Lokaal Discord-overzicht'
$shortcut.Save()
Write-Output "Discord Fix is installed at $targetExecutable. Start it through the Start menu."
