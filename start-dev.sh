#!/bin/bash
# AI-KTV 本地开发启动脚本
set -e

echo "🎤 AI-KTV 日本語カラオケ動画メーカー"
echo "======================================"
echo ""

# 检查依赖
check_cmd() {
    if ! command -v "$1" &> /dev/null; then
        echo "❌ 未找到 $1，请先安装"
        exit 1
    fi
}

check_cmd node
check_cmd ffmpeg

# 查找 Python 3.11+
PYTHON=""
for py in python3.11 python3.12 python3.13 python3; do
    if command -v "$py" &> /dev/null; then
        ver=$("$py" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$py"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ 需要 Python 3.11+，请安装: brew install python@3.11"
    exit 1
fi

echo "✅ 基础依赖检查通过 (Python: $($PYTHON --version))"
echo ""

# 后端
echo "📦 设置后端环境..."
cd backend

if [ ! -d "venv" ]; then
    $PYTHON -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "🚀 启动后端 (port 8000)..."
python run.py &
BACKEND_PID=$!
cd ..

# 前端
echo "📦 设置前端环境..."
cd frontend

if [ ! -d "node_modules" ]; then
    npm install
fi

echo "🚀 启动前端 (port 5173)..."
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "======================================"
echo "✅ 服务已启动!"
echo "   前端: http://localhost:5173"
echo "   后端: http://localhost:8000"
echo "   API 文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "======================================"

# 等待退出
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
