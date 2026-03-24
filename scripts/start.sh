#!/bin/bash
# =====================================================
# AI主播台 - 标准启动脚本
# =====================================================
# 功能：
# - 确保在正确目录运行
# - 清理残留进程
# - 环境检查
# - 启动服务
# - 验证启动结果

set -e  # 遇错即停

# 确保在正确目录
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "=========================================="
echo "🎬 AI主播台 - 启动脚本"
echo "=========================================="
echo ""
echo "📁 项目目录: $PROJECT_ROOT"

# 1. 清理旧进程
echo ""
echo "🔍 检查残留进程..."

# 检查anchor_v2进程
if pgrep -f "anchor_v2.py" > /dev/null 2>&1; then
    echo "⚠️ 发现残留的anchor_v2进程，正在终止..."
    pkill -f "anchor_v2.py" 2>/dev/null || true
    sleep 2
    # 强制终止
    if pgrep -f "anchor_v2.py" > /dev/null 2>&1; then
        pkill -9 -f "anchor_v2.py" 2>/dev/null || true
        sleep 1
    fi
fi

# 检查FFmpeg推流进程
if pgrep -f "ffmpeg.*rtmp" > /dev/null 2>&1; then
    echo "⚠️ 发现残留的FFmpeg推流进程，正在终止..."
    pkill -f "ffmpeg.*rtmp" 2>/dev/null || true
    sleep 1
fi

# 清理PID文件
if [ -f "data/anchor.pid" ]; then
    rm -f data/anchor.pid
fi

echo "✅ 进程检查完成"

# 2. 环境检查
echo ""
echo "🔍 环境检查..."

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi
echo "✅ Python3: $(python3 --version)"

# 检查FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg 未安装"
    exit 1
fi
FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1)
echo "✅ FFmpeg: $FFMPEG_VERSION"

# 检查配置文件
if [ ! -f "config.json" ]; then
    echo "❌ 配置文件不存在: config.json"
    exit 1
fi
echo "✅ 配置文件: config.json"

# 检查必要资源
if [ ! -f "assets/bg_frame.png" ]; then
    echo "⚠️ 背景图片不存在（将使用纯色背景）"
else
    echo "✅ 背景图片: assets/bg_frame.png"
fi

# 检查字体
if [ -f "/usr/share/fonts/truetype/chinese/msyh.ttf" ]; then
    echo "✅ 字体: 微软雅黑"
elif [ -f "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc" ]; then
    echo "✅ 字体: NotoSansCJK"
else
    echo "⚠️ 中文字体未找到，使用系统默认"
fi

# 3. 确保必要目录存在
mkdir -p logs data output assets/tts assets/bgm

# 4. 启动服务
echo ""
echo "🚀 启动服务..."

# 创建日志目录
LOG_FILE="logs/console_$(date +%Y%m%d_%H%M%S).log"

# 使用nohup后台运行
nohup python3 anchor_v2.py > "$LOG_FILE" 2>&1 &
PID=$!

echo "📝 PID: $PID"
echo "📝 日志: $LOG_FILE"

# 等待启动
sleep 3

# 5. 验证启动
if kill -0 $PID 2>/dev/null; then
    echo ""
    echo "=========================================="
    echo "✅ 启动成功!"
    echo "=========================================="
    echo ""
    echo "📺 斗鱼直播: https://www.douyu.com/12898962"
    echo ""
    echo "常用命令:"
    echo "  查看日志: tail -f $LOG_FILE"
    echo "  停止服务: pkill -f 'anchor_v2.py'"
    echo "  查看状态: cat data/status.json"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "❌ 启动失败"
    echo "=========================================="
    echo ""
    echo "查看日志获取详细信息:"
    echo "  tail -50 $LOG_FILE"
    exit 1
fi
