@echo off
chcp 65001 >nul
title 医院耗材管理系统

echo ==========================================
echo   医院耗材管理系统
echo ==========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 安装依赖（仅首次）
if not exist ".deps_installed" (
    echo [首次运行] 安装依赖...
    pip install -r requirements.txt --quiet
    echo. > .deps_installed
    echo 依赖安装完成！
    echo.
)

:: 启动系统
echo 正在启动系统...
echo 启动后请在浏览器访问: http://localhost:5000
echo 按 Ctrl+C 可停止系统
echo.
start http://localhost:5000
python app.py