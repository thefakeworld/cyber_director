#!/bin/bash
# =====================================================
# 赛博电视台 - 停止脚本
# =====================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${YELLOW}🛑 正在停止赛博电视台...${NC}"

# 停止 Python 主进程
if pgrep -f "cyber_director_v2.py" > /dev/null; then
    echo "停止 Python 进程..."
    pkill -TERM -f "cyber_director_v2.py"
    sleep 2
    
    # 如果还在运行，强制终止
    if pgrep -f "cyber_director_v2.py" > /dev/null; then
        echo -e "${YELLOW}强制终止 Python 进程...${NC}"
        pkill -KILL -f "cyber_director_v2.py"
    fi
    echo -e "${GREEN}✓${NC} Python 进程已停止"
else
    echo -e "${YELLOW}⚠${NC} 未找到运行中的 Python 进程"
fi

# 停止 FFmpeg 进程
if pgrep -f "ffmpeg.*background_loop" > /dev/null; then
    echo "停止 FFmpeg 进程..."
    pkill -INT -f "ffmpeg.*background_loop"
    sleep 2
    
    if pgrep -f "ffmpeg.*background_loop" > /dev/null; then
        pkill -KILL -f "ffmpeg.*background_loop"
    fi
    echo -e "${GREEN}✓${NC} FFmpeg 进程已停止"
fi

# 清理 PID 文件
if [ -f "data/director.pid" ]; then
    rm -f data/director.pid
fi

echo -e "${GREEN}👋 赛博电视台已完全停止${NC}"
