#!/bin/bash
# =====================================================
# AI主播台 - 统一测试脚本
# =====================================================
# 运行所有测试用例，输出测试报告

set -e
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "=========================================="
echo "🧪 AI主播台 - 测试套件"
echo "=========================================="
echo ""
echo "📁 项目目录: $PROJECT_ROOT"
echo ""

# 测试计数
PASSED=0
FAILED=0
TOTAL=0

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试函数
run_test() {
    local name=$1
    local cmd=$2
    local timeout=${3:-60}
    
    TOTAL=$((TOTAL + 1))
    echo ""
    echo "▶ 测试 $TOTAL: $name"
    echo "  命令: $cmd"
    
    # 运行测试
    if timeout $timeout bash -c "$cmd" > /tmp/test_output.txt 2>&1; then
        echo -e "  ${GREEN}✅ 通过${NC}"
        PASSED=$((PASSED + 1))
    else
        echo -e "  ${RED}❌ 失败${NC}"
        FAILED=$((FAILED + 1))
        # 显示错误信息
        echo "  错误输出:"
        head -10 /tmp/test_output.txt | sed 's/^/    /'
    fi
}

# 1. 环境检查测试
echo "========== 环境测试 =========="

run_test "Python环境" "python3 --version"

run_test "FFmpeg安装" "ffmpeg -version"

run_test "FFprobe安装" "ffprobe -version"

# 2. 核心模块测试
echo ""
echo "========== 模块测试 =========="

run_test "路径模块" "python3 core/paths.py" 30

run_test "配置模块" "python3 -c 'from core.config import Config; c = Config(); print(\"配置加载:\", c.is_valid())'" 30

run_test "InputManager模块" "python3 core/input_manager.py" 30

run_test "FFmpeg构建器模块" "python3 core/ffmpeg_builder.py" 30

# 3. 功能测试
echo ""
echo "========== 功能测试 =========="

run_test "音频索引测试" "python3 scripts/test_ffmpeg_audio.py" 60

run_test "字幕同步测试" "python3 scripts/test_subtitle_sync.py" 60

# 4. 视频生成测试（生成测试文件）
echo ""
echo "========== 视频测试 =========="

run_test "视频生成测试" "ffmpeg -y -f lavfi -i 'color=c=0x1a1a2e:s=320x240:d=1' -c:v libx264 -preset ultrafast -t 1 output/test_video.mp4" 30

# 5. 字体测试
echo ""
echo "========== 字体测试 =========="

run_test "中文字体渲染" "ffmpeg -y -f lavfi -i 'color=c=0x1a1a2e:s=320x240:d=1' -vf \"drawtext=fontfile=/usr/share/fonts/truetype/chinese/msyh.ttf:text='测试':x=10:y=10:fontsize=20:fontcolor=white\" -c:v libx264 -preset ultrafast -t 1 output/test_font.mp4" 30 || \
run_test "Noto字体渲染" "ffmpeg -y -f lavfi -i 'color=c=0x1a1a2e:s=320x240:d=1' -vf \"drawtext=fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc:text='测试':x=10:y=10:fontsize=20:fontcolor=white\" -c:v libx264 -preset ultrafast -t 1 output/test_font.mp4" 30

# 6. 热插拔新闻测试
echo ""
echo "========== 热插拔测试 =========="

run_test "热插拔新闻模块" "python3 scripts/hot_news.py" 30

# 测试结果
echo ""
echo "=========================================="
echo "📊 测试结果"
echo "=========================================="
echo ""
echo -e "  总计: $TOTAL"
echo -e "  ${GREEN}通过: $PASSED${NC}"
echo -e "  ${RED}失败: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ 所有测试通过!${NC}"
    exit 0
else
    echo -e "${RED}❌ 有 $FAILED 个测试失败${NC}"
    exit 1
fi
