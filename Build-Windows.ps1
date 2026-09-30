$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
python -m PyInstaller --noconfirm --clean --onefile --windowed --name DiscordFix --add-data "discord_fix/dashboard.html;discord_fix" launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
python -m PyInstaller --noconfirm --clean --onefile --console --name DiscordFixPairing native_host_launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Pairing helper build failed' }
Write-Output 'Built dist\DiscordFix.exe and dist\DiscordFixPairing.exe. These builds are unsigned; browser pairing is not registered automatically.'
