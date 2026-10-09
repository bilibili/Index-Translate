@echo off
chcp 65001 >nul
title Index-Translate 沉浸式翻译本地代理网桥 (Immersive Translate Proxy)

echo ======================================================================
echo           Index-Translate - 沉浸式翻译本地代理网桥 (Windows)
echo ======================================================================
echo.
echo [1/2] 正在检测 Python 环境...

set PY_CMD=
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set PY_CMD=python
    goto CHECK_SCRIPT
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set PY_CMD=py -3
    goto CHECK_SCRIPT
)

echo.
echo [错误] 未检测到 Python 3 环境！
echo ----------------------------------------------------------------------
echo 请先安装 Python 3：
echo 1. 方式一（推荐）：打开 Windows 微软商店 (Microsoft Store)，搜索 "Python 3.12" 点击获取安装。
echo 2. 方式二：访问官网下载安装包 https://www.python.org/downloads/
echo    ★ 安装时请务必勾选底部 "Add python.exe to PATH"（添加到系统环境变量）！
echo ----------------------------------------------------------------------
echo.
pause
exit /b 1

:CHECK_SCRIPT
echo [成功] 已找到 Python: %PY_CMD%
echo.
echo [2/2] 正在定位代理脚本...

set SCRIPT_PATH=
if exist "%~dp0inference\llm\call_api.py" (
    set "SCRIPT_PATH=%~dp0inference\llm\call_api.py"
) else if exist "%~dp0call_api.py" (
    set "SCRIPT_PATH=%~dp0call_api.py"
) else if exist "%~dp0..\..\inference\llm\call_api.py" (
    set "SCRIPT_PATH=%~dp0..\..\inference\llm\call_api.py"
)

if "%SCRIPT_PATH%"=="" (
    echo.
    echo [错误] 找不到 call_api.py 脚本文件！
    echo 请确保 run_proxy_windows.bat 与 Index-Translate 仓库或 call_api.py 在同一目录中。
    echo.
    pause
    exit /b 1
)

echo [成功] 脚本路径: %SCRIPT_PATH%
echo.
echo ======================================================================
echo 🚀 正在启动本地代理网桥服务...
echo.
echo 📌 沉浸式翻译插件配置参数：
echo   - 自定义接口地址 (API URL) : http://127.0.0.1:8080/v1
echo   - 模型名称 (Model)         : Index-Translate-35B-A3B
echo   - API Key (密钥)           : index (或任意填写)
echo.
echo ⚠️ 避坑提醒：
echo   如果开启了网络代理软件（Clash / v2rayN / Sing-box 等 TUN 模式），
echo   请确保 127.0.0.1 在直连/绕过回环白名单中，以免本地请求被代理劫持报 504 错误。
echo ======================================================================
echo.

%PY_CMD% "%SCRIPT_PATH%" --serve %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo 代理服务异常退出（退出码：%ERRORLEVEL%）。
    pause
)
