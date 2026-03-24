#!/bin/bash
# =====================================================
# AI主播台 - 一键测试脚本
# =====================================================
# 运行所有核心模块测试，快速定位问题

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         🧪 AI主播台 - 系统测试                        ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""

ERRORS=0
WARNINGS=0

# ==================== 环境检查 ====================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📋 环境检查${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Python
echo -n "  Python3: "
if command -v python3 &> /dev/null; then
    VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}✅ $VERSION${NC}"
else
    echo -e "${RED}❌ 未安装${NC}"
    ((ERRORS++))
fi

# FFmpeg
echo -n "  FFmpeg: "
if command -v ffmpeg &> /dev/null; then
    VERSION=$(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f3)
    echo -e "${GREEN}✅ v$VERSION${NC}"
else
    echo -e "${RED}❌ 未安装${NC}"
    ((ERRORS++))
fi

# 字体
echo -n "  中文字体: "
if [ -f "/usr/share/fonts/truetype/chinese/msyh.ttf" ]; then
    echo -e "${GREEN}✅ 微软雅黑${NC}"
elif [ -f "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc" ]; then
    echo -e "${GREEN}✅ 文泉驿${NC}"
else
    echo -e "${YELLOW}⚠️ 未找到中文字体${NC}"
    ((WARNINGS++))
fi

# ==================== 文件检查 ====================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📁 文件检查${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

cd "$PROJECT_DIR"

# 配置文件
echo -n "  config.json: "
if [ -f "config.json" ]; then
    echo -e "${GREEN}✅ 存在${NC}"
else
    echo -e "${RED}❌ 不存在${NC}"
    ((ERRORS++))
fi

# 背景视频
echo -n "  background_loop.mp4: "
if [ -f "assets/background_loop.mp4" ]; then
    SIZE=$(stat -c%s "assets/background_loop.mp4" 2>/dev/null || stat -f%z "assets/background_loop.mp4")
    echo -e "${GREEN}✅ $(($SIZE / 1024))KB${NC}"
else
    echo -e "${YELLOW}⚠️ 不存在（将使用纯色背景）${NC}"
    ((WARNINGS++))
fi

# 目录结构
for dir in data logs output; do
    echo -n "  $dir/: "
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✅ 存在${NC}"
    else
        mkdir -p "$dir"
        echo -e "${GREEN}✅ 已创建${NC}"
    fi
done

# ==================== 模块测试 ====================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔧 模块测试${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 测试配置模块
echo -n "  配置模块 (config.py): "
if python3 core/config.py > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 通过${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
    python3 core/config.py 2>&1 | tail -5
    ((ERRORS++))
fi

# 测试路径模块
echo -n "  路径模块 (paths.py): "
if python3 core/paths.py > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 通过${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
    python3 core/paths.py 2>&1 | tail -5
    ((ERRORS++))
fi

# 测试FFmpeg模块
echo -n "  FFmpeg模块 (ffmpeg_cmd.py): "
if python3 core/ffmpeg_cmd.py > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 通过${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
    python3 core/ffmpeg_cmd.py 2>&1 | tail -5
    ((ERRORS++))
fi

# ==================== 推流测试 ====================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📡 推流测试${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 获取推流地址
RTMP_URL=$(python3 -c "
import json
with open('config.json') as f:
    cfg = json.load(f)
for p in cfg.get('platforms', {}).values():
    if p.get('enabled') and p.get('rtmp_url'):
        print(p['rtmp_url'])
        break
" 2>/dev/null)

if [ -n "$RTMP_URL" ]; then
    DISPLAY_URL=$(echo "$RTMP_URL" | cut -d'?' -f1)
    echo -n "  连接测试 ($DISPLAY_URL): "
    
    # 简单连接测试（3秒超时）
    if timeout 8 ffmpeg -y -f lavfi -i "color=c=black:s=320x240:d=1" \
        -c:v libx264 -preset ultrafast -t 1 \
        -f flv "$RTMP_URL" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 连接成功${NC}"
    else
        echo -e "${YELLOW}⚠️ 连接失败（可能是密钥过期）${NC}"
        ((WARNINGS++))
    fi
else
    echo -e "  ${YELLOW}⚠️ 未配置推流地址${NC}"
    ((WARNINGS++))
fi

# ==================== 生成测试视频 ====================
echo ""
echo -n "  生成测试视频: "
TEST_OUTPUT="output/test_$(date +%s).mp4"
if timeout 10 ffmpeg -y -f lavfi -i "color=c=0x1a1a2e:s=1280x720:d=3" \
    -vf "drawtext=fontfile=/usr/share/fonts/truetype/chinese/msyh.ttf:text='TEST OK':x=(w-tw)/2:y=(h-th)/2:fontsize=48:fontcolor=white" \
    -c:v libx264 -preset ultrafast -t 3 \
    "$TEST_OUTPUT" > /dev/null 2>&1; then
    SIZE=$(stat -c%s "$TEST_OUTPUT" 2>/dev/null || stat -f%z "$TEST_OUTPUT")
    echo -e "${GREEN}✅ ${TEST_OUTPUT} ($(($SIZE / 1024))KB)${NC}"
    rm -f "$TEST_OUTPUT"
else
    echo -e "${RED}❌ 失败${NC}"
    ((ERRORS++))
fi

# ==================== 结果汇总 ====================
echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                 📊 测试结果汇总                       ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo -e "  错误: ${GREEN}0${NC}"
else
    echo -e "  错误: ${RED}$ERRORS${NC}"
fi

if [ $WARNINGS -eq 0 ]; then
    echo -e "  警告: ${GREEN}0${NC}"
else
    echo -e "  警告: ${YELLOW}$WARNINGS${NC}"
fi

echo ""

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ 所有测试通过！可以启动：python3 anchor.py${NC}"
    exit 0
else
    echo -e "${RED}❌ 存在错误，请修复后重试${NC}"
    exit 1
fi
