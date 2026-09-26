$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
python -m PyInstaller --noconfirm --clean --onefile --windowed --name DiscordFix --add-data "discord_fix/dashboard.html;discord_fix" launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Write-Output 'Built dist\DiscordFix.exe. This build is unsigned.'
