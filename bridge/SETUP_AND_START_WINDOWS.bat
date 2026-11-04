@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if errorlevel 1 (echo 未发现 Python 3 启动器 py，不能完成自动配置。& pause & exit /b 1)
  py -3 -m venv .venv
  if errorlevel 1 (echo 创建独立 Python 环境失败。& pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install -r bridge\requirements-security.txt
if errorlevel 1 (echo 电脑加密依赖安装失败；检查网络并重试。& pause & exit /b 1)
".venv\Scripts\python.exe" tools\setup_secure_bridge.py
if errorlevel 1 (echo 安全证书或密码初始化失败；未启动服务。& pause & exit /b 1)
call bridge\START_SECURE_WINDOWS.bat
