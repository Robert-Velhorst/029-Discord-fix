@echo off
cd /d "%~dp0"
python -m discord_fix
if errorlevel 1 pause
