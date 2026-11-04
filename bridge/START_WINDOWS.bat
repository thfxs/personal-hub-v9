@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo [Local-only] 默认已改为只允许电脑本机 HTTP，V9 不会通过明文 HTTP 配对。
echo [V9 secure] 请先运行 py -3 tools\setup_secure_bridge.py，再运行 bridge\START_SECURE_WINDOWS.bat
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 bridge\server.py --bind 127.0.0.1
) else (
  python bridge\server.py --bind 127.0.0.1
)
echo.
pause
