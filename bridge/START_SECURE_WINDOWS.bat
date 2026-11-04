@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set "SAFE=%USERPROFILE%\.personal-hub-bridge\security"
if not exist "%SAFE%\server.crt" goto SETUP
if not exist "%SAFE%\server.key" goto SETUP
if not exist "%SAFE%\vault-passphrase.txt" goto SETUP
if not exist ".venv\Scripts\python.exe" goto SETUP
".venv\Scripts\python.exe" bridge\server.py --tls-cert "%SAFE%\server.crt" --tls-key "%SAFE%\server.key" --vault-passphrase-file "%SAFE%\vault-passphrase.txt"
goto END
:SETUP
echo 请先执行: bridge\SETUP_AND_START_WINDOWS.bat
echo 然后运行本脚本
:END
pause
