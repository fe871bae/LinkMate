@echo off
rem Double-click on Windows to set up and start LinkMate.
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 start_linkmate.py %*
    goto end
)

python --version >nul 2>nul
if %errorlevel%==0 (
    python start_linkmate.py %*
    goto end
)

echo Python is not installed.
echo Get it from https://www.python.org/downloads/ and tick "Add python.exe to PATH" in the installer.
pause

:end
