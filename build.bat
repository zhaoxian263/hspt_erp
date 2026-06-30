@echo off
chcp 65001 >nul
title 医院耗材管理系统 - 打包工具

echo ==========================================
echo   医院耗材管理系统 - PyInstaller 打包
echo ==========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

:: 安装依赖
echo [1/3] 安装 Python 依赖...
pip install -r requirements.txt pyinstaller --quiet

:: 打包
echo [2/3] 开始打包（这可能需要几分钟）...
pyinstaller --noconfirm --onedir --name "安居镇中心卫生院护理部耗材管理系统" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "config.py;." ^
    --hidden-import="pandas" ^
    --hidden-import="openpyxl" ^
    app.py

:: 复制必要文件
echo [3/3] 复制配置文件...
copy config.py dist\安居镇中心卫生院护理部耗材管理系统\ >nul 2>&1
if not exist "dist\安居镇中心卫生院护理部耗材管理系统\database" mkdir "dist\安居镇中心卫生院护理部耗材管理系统\database"

echo.
echo ==========================================
echo   打包完成！
echo   输出目录: dist\安居镇中心卫生院护理部耗材管理系统\
echo   运行方式: 双击 dist\安居镇中心卫生院护理部耗材管理系统\安居镇中心卫生院护理部耗材管理系统.exe
echo ==========================================
pause