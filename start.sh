#!/bin/bash
# 医院耗材管理系统 - macOS 启动脚本

cd "$(dirname "$0")"

echo "=========================================="
echo "  医院耗材管理系统"
echo "=========================================="
echo ""

# 检查 Python3
if ! command -v python3 &>/dev/null; then
    echo "[错误] 未找到 python3，请先安装 Python 3.9+"
    echo "  brew install python3"
    echo "  或访问 https://www.python.org/downloads/"
    exit 1
fi

PYTHON=python3

# 安装依赖（仅首次）
if [ ! -f ".deps_installed" ]; then
    echo "[首次运行] 安装依赖..."
    $PYTHON -m pip install -r requirements.txt --quiet
    touch .deps_installed
    echo "依赖安装完成！"
    echo ""
fi

# 启动系统
echo "正在启动系统..."
echo "启动后请在浏览器访问: http://localhost:5000"
echo "按 Ctrl+C 可停止系统"
echo ""

# 尝试自动打开浏览器
if command -v open &>/dev/null; then
    sleep 1 && open http://localhost:5000 &
fi

$PYTHON app.py