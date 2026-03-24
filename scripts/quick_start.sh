#!/bin/bash
# ============================================================
# AI主播台 - 快速启动脚本
# ============================================================
# 用法: ./scripts/quick_start.sh
# 功能: 清理旧进程 -> 检查环境 -> 启动直播
# ============================================================

set -e

# 切换到项目根目录
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}   🎬 AI主播台 - 快速启动${NC}"
echo -e "${CYAN}================================================${NC}"
echo ""
echo "📁 项目目录: $PROJECT_ROOT"

# ============================================================
# Step 1: 清理旧进程
# ============================================================
echo ""
echo -e "${YELLOW}Step 1: 清理旧进程...${NC}"

# 检查并清理anchor进程
if pgrep -f "anchor_v2.py" > /dev/null; then
    echo "  发现残留anchor进程，正在清理..."
    pkill -9 -f "anchor_v2.py"
    sleep 1
fi

# 检查并清理ffmpeg进程
if pgrep -f "ffmpeg.*rtmp" > /dev/null; then
    echo "  发现残留ffmpeg进程，正在清理..."
    pkill -9 -f "ffmpeg.*rtmp"
    sleep 1
fi

echo -e "  ${GREEN}✅ 进程清理完成${NC}"

# ============================================================
# Step 2: 检查环境
# ============================================================
echo ""
echo -e "${YELLOW}Step 2: 检查环境...${NC}"

ERRORS=0

# 检查FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo -e "  ${RED}❌ FFmpeg未安装${NC}"
    ((ERRORS++))
else
    echo "  ✅ FFmpeg已安装"
fi

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "  ${RED}❌ Python3未安装${NC}"
    ((ERRORS++))
else
    echo "  ✅ Python3已安装"
fi

# 检查配置文件
if [ ! -f config.json ]; then
    echo -e "  ${RED}❌ 配置文件不存在${NC}"
    ((ERRORS++))
else
    echo "  ✅ 配置文件存在"
fi

# 检查背景图片
if [ ! -f assets/bg_frame.png ]; then
    echo -e "  ${RED}❌ 背景图片不存在${NC}"
    ((ERRORS++))
else
    echo "  ✅ 背景图片存在"
fi

# 检查字体
FONT_PATH="/usr/share/fonts/truetype/chinese/msyh.ttf"
if [ ! -f "$FONT_PATH" ]; then
    echo "  ⚠️ 中文字体不存在，使用系统默认"
else
    echo "  ✅ 中文字体存在"
fi

# 检查BGM
BGM_COUNT=$(ls assets/bgm/*.mp3 2>/dev/null | wc -l || echo 0)
if [ "$BGM_COUNT" -gt 0 ]; then
    echo "  ✅ BGM: $BGM_COUNT 首"
else
    echo "  ⚠️ 无BGM文件"
fi

# 检查推流地址
if grep -q "rtmp://" config.json; then
    echo "  ✅ 推流地址已配置"
else
    echo -e "  ${RED}❌ 未配置推流地址${NC}"
    ((ERRORS++))
fi

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ 环境检查失败，请修复后重试${NC}"
    exit 1
fi

echo -e "  ${GREEN}✅ 环境检查通过${NC}"

# ============================================================
# Step 3: 创建必要目录
# ============================================================
echo ""
echo -e "${YELLOW}Step 3: 准备目录...${NC}"

mkdir -p logs
mkdir -p output
mkdir -p assets/tts

echo -e "  ${GREEN}✅ 目录准备完成${NC}"

# ============================================================
# Step 4: 启动直播
# ============================================================
echo ""
echo -e "${YELLOW}Step 4: 启动直播...${NC}"

# 后台启动
nohup python3 anchor_v2.py > logs/console.log 2>&1 &
ANCHOR_PID=$!

echo "  进程PID: $ANCHOR_PID"
sleep 5

# 验证启动
if pgrep -f "anchor_v2.py" > /dev/null; then
    echo -e "  ${GREEN}✅ 主程序启动成功${NC}"
    
    # 等待FFmpeg启动
    sleep 3
    
    # 检查FFmpeg
    FFMPEG_COUNT=$(pgrep -c -f "ffmpeg.*rtmp" || echo 0)
    if [ "$FFMPEG_COUNT" -gt 0 ]; then
        echo -e "  ${GREEN}✅ FFmpeg推流已启动 ($FFMPEG_COUNT 个进程)${NC}"
    else
        echo -e "  ${RED}⚠️ FFmpeg未启动，请检查日志${NC}"
    fi
else
    echo -e "  ${RED}❌ 主程序启动失败${NC}"
    echo ""
    echo "查看日志: tail -50 logs/console.log"
    exit 1
fi

# ============================================================
# Step 5: 显示状态
# ============================================================
echo ""
echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}   📺 直播状态${NC}"
echo -e "${CYAN}================================================${NC}"
echo ""
echo "  斗鱼直播: https://www.douyu.com/12898962"
echo "  查看日志: tail -f logs/console.log"
echo "  停止直播: pkill -f anchor_v2.py"
echo ""
echo -e "${GREEN}✅ AI主播台已启动！${NC}"
echo ""
