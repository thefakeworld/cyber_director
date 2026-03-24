#!/bin/bash
# =====================================================
# AI主播台 - 停止脚本
# =====================================================

set -e
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "=========================================="
echo "🛑 AI主播台 - 停止服务"
echo "=========================================="
echo ""

# 1. 停止主程序
echo "🔍 查找anchor_v2进程..."
if pgrep -f "anchor_v2.py" > /dev/null 2>&1; then
    PIDS=$(pgrep -f "anchor_v2.py")
    echo "找到进程: $PIDS"
    
    echo "正在停止..."
    pkill -TERM -f "anchor_v2.py" 2>/dev/null || true
    sleep 2
    
    # 检查是否成功停止
    if pgrep -f "anchor_v2.py" > /dev/null 2>&1; then
        echo "⚠️ 进程未响应，强制终止..."
        pkill -9 -f "anchor_v2.py" 2>/dev/null || true
        sleep 1
    fi
    
    echo "✅ anchor_v2 已停止"
else
    echo "⚠️ 未找到anchor_v2进程"
fi

# 2. 停止FFmpeg进程
echo ""
echo "🔍 查找FFmpeg推流进程..."
if pgrep -f "ffmpeg.*rtmp" > /dev/null 2>&1; then
    echo "正在停止FFmpeg进程..."
    pkill -TERM -f "ffmpeg.*rtmp" 2>/dev/null || true
    sleep 2
    
    if pgrep -f "ffmpeg.*rtmp" > /dev/null 2>&1; then
        pkill -9 -f "ffmpeg.*rtmp" 2>/dev/null || true
    fi
    
    echo "✅ FFmpeg进程已停止"
else
    echo "⚠️ 未找到FFmpeg推流进程"
fi

# 3. 清理PID文件
echo ""
echo "🧹 清理临时文件..."
if [ -f "data/anchor.pid" ]; then
    rm -f data/anchor.pid
    echo "✅ PID文件已清理"
fi

echo ""
echo "=========================================="
echo "✅ 服务已完全停止"
echo "=========================================="
