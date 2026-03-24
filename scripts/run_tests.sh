#!/bin/bash
# ============================================================
# AI主播台 - 统一测试入口
# ============================================================
# 用法: ./scripts/run_tests.sh [test_name]
# 示例: 
#   ./scripts/run_tests.sh          # 运行所有测试
#   ./scripts/run_tests.sh audio    # 只运行音频测试
# ============================================================

set -e

# 切换到项目根目录
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试计数
PASSED=0
FAILED=0

# 打印函数
print_header() {
    echo ""
    echo -e "${YELLOW}============================================${NC}"
    echo -e "${YELLOW}$1${NC}"
    echo -e "${YELLOW}============================================${NC}"
}

print_test() {
    echo ""
    echo -e "▶ ${YELLOW}测试: $1${NC}"
}

print_pass() {
    echo -e "  ${GREEN}✅ 通过${NC}"
    ((PASSED++))
}

print_fail() {
    echo -e "  ${RED}❌ 失败: $1${NC}"
    ((FAILED++))
}

# ============================================================
# 测试函数
# ============================================================

test_audio_index() {
    print_test "FFmpeg音频索引"
    
    if python3 scripts/test_ffmpeg_audio.py > /tmp/test_audio.log 2>&1; then
        if grep -q "音频索引正确" /tmp/test_audio.log; then
            print_pass
            return 0
        fi
    fi
    print_fail "查看日志: cat /tmp/test_audio.log"
    return 1
}

test_subtitle_sync() {
    print_test "字幕同步"
    
    if python3 scripts/test_subtitle_sync.py > /tmp/test_subtitle.log 2>&1; then
        if grep -q "总计: 5/5 通过" /tmp/test_subtitle.log; then
            print_pass
            return 0
        fi
    fi
    print_fail "查看日志: cat /tmp/test_subtitle.log"
    return 1
}

test_avatar_overlay() {
    print_test "智灵视频叠加"
    
    # 创建输出目录
    mkdir -p output
    
    # 简化测试 - 只生成3秒
    if timeout 60 ffmpeg -y -nostdin \
        -loop 1 -i assets/bg_frame.png -r 25 \
        -stream_loop -1 -i assets/avatar.mp4 \
        -filter_complex "[1:v]scale=iw*0.3:ih*0.3[av];[0:v][av]overlay=W-w-30:H-h-30,format=yuv420p[vout]" \
        -map "[vout]" -c:v libx264 -preset ultrafast -t 3 \
        output/test_avatar_overlay.mp4 > /tmp/test_avatar.log 2>&1; then
        
        if [ -f output/test_avatar_overlay.mp4 ] && [ -s output/test_avatar_overlay.mp4 ]; then
            SIZE=$(stat -f%z output/test_avatar_overlay.mp4 2>/dev/null || stat -c%s output/test_avatar_overlay.mp4)
            if [ "$SIZE" -gt 10000 ]; then
                print_pass
                return 0
            fi
        fi
    fi
    print_fail "查看日志: cat /tmp/test_avatar.log"
    return 1
}

test_hot_news() {
    print_test "热插拔新闻系统"
    
    if python3 scripts/hot_news.py > /tmp/test_news.log 2>&1; then
        if grep -q "TTS已生成" /tmp/test_news.log; then
            print_pass
            return 0
        fi
    fi
    print_fail "查看日志: cat /tmp/test_news.log"
    return 1
}

test_ffmpeg_command() {
    print_test "FFmpeg命令生成"
    
    # 测试FFmpegBuilderV2生成的命令是否有效
    python3 -c "
import sys
sys.path.insert(0, '.')
from core.ffmpeg_builder import FFmpegBuilderV2
from pathlib import Path

builder = FFmpegBuilderV2('/usr/share/fonts/truetype/chinese/msyh.ttf')
builder.set_bg_image(Path('assets/bg_frame.png'))
builder.set_content_files(Path('data/script.txt'), Path('data/ticker.txt'))
builder.set_rtmp_output(['rtmp://test'])

cmd = builder.build()
print('COMMAND_OK')
" > /tmp/test_cmd.log 2>&1
    
    if grep -q "COMMAND_OK" /tmp/test_cmd.log; then
        print_pass
        return 0
    fi
    print_fail "查看日志: cat /tmp/test_cmd.log"
    return 1
}

test_environment() {
    print_test "环境检查"
    
    ERRORS=0
    
    # 检查FFmpeg
    if ! command -v ffmpeg &> /dev/null; then
        echo "  ❌ FFmpeg未安装"
        ((ERRORS++))
    else
        echo "  ✅ FFmpeg: $(ffmpeg -version 2>&1 | head -1)"
    fi
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        echo "  ❌ Python3未安装"
        ((ERRORS++))
    else
        echo "  ✅ Python: $(python3 --version)"
    fi
    
    # 检查z-ai
    if ! command -v z-ai &> /dev/null; then
        echo "  ⚠️ z-ai CLI未安装"
    else
        echo "  ✅ z-ai CLI已安装"
    fi
    
    # 检查必要文件
    for f in config.json assets/bg_frame.png; do
        if [ -f "$f" ]; then
            echo "  ✅ 文件: $f"
        else
            echo "  ❌ 缺少: $f"
            ((ERRORS++))
        fi
    done
    
    # 检查BGM
    BGM_COUNT=$(ls assets/bgm/*.mp3 2>/dev/null | wc -l)
    if [ "$BGM_COUNT" -gt 0 ]; then
        echo "  ✅ BGM: $BGM_COUNT 首"
    else
        echo "  ⚠️ 无BGM文件"
    fi
    
    # 检查智灵
    if [ -f assets/avatar.mp4 ]; then
        echo "  ✅ 智灵视频: assets/avatar.mp4"
    else
        echo "  ⚠️ 无智灵视频"
    fi
    
    if [ $ERRORS -eq 0 ]; then
        print_pass
        return 0
    else
        print_fail "$ERRORS 个错误"
        return 1
    fi
}

# ============================================================
# 主流程
# ============================================================

print_header "🧪 AI主播台测试套件"

echo "📁 项目目录: $PROJECT_ROOT"
echo "📅 测试时间: $(date '+%Y-%m-%d %H:%M:%S')"

# 根据参数决定运行哪些测试
TEST_NAME="${1:-all}"

case "$TEST_NAME" in
    "all")
        test_environment || true
        test_ffmpeg_command || true
        test_audio_index || true
        test_subtitle_sync || true
        test_avatar_overlay || true
        test_hot_news || true
        ;;
    "env")
        test_environment
        ;;
    "audio")
        test_audio_index
        ;;
    "subtitle")
        test_subtitle_sync
        ;;
    "avatar")
        test_avatar_overlay
        ;;
    "news")
        test_hot_news
        ;;
    "cmd")
        test_ffmpeg_command
        ;;
    *)
        echo "未知测试: $TEST_NAME"
        echo "可用测试: all, env, audio, subtitle, avatar, news, cmd"
        exit 1
        ;;
esac

# 打印结果
print_header "📊 测试结果"
echo -e "  ${GREEN}✅ 通过: $PASSED${NC}"
echo -e "  ${RED}❌ 失败: $FAILED${NC}"

# 返回码
if [ $FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi
