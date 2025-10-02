@echo off
setlocal ENABLEDELAYEDEXPANSION

REM 一键发布到 GitHub 的批处理脚本
REM 依赖：已安装 Python 与 Git，并在 PATH 中可用；环境变量 GITHUB_TOKEN 已设置。

where python >nul 2>nul
if errorlevel 1 (
  echo [Error] 未检测到 Python，请先安装 Python 并加入 PATH。
  exit /b 1
)

where git >nul 2>nul
if errorlevel 1 (
  echo [Error] 未检测到 Git，请先安装 Git 并加入 PATH。
  exit /b 1
)

if "%GITHUB_TOKEN%"=="" (
  echo [Error] 未检测到環境變量 GITHUB_TOKEN，請先設置你的 GitHub 個人訪問令牌。
  echo  參考: https://github.com/settings/tokens
  exit /b 1
)

REM 透传所有参数给 Python 脚本
python "%~dp0publish_to_github.py" %*
set ERR=%ERRORLEVEL%
if %ERR% NEQ 0 exit /b %ERR%

exit /b 0

