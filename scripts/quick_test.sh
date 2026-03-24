#!/bin/bash
# =====================================================
# AI主播台 - 快速测试脚本
# =====================================================

cd "$(dirname "$0")/.."

echo ""
echo "🧪 AI主播台 - 快速测试"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ERRORS=0

# 1. 环境检查
echo ""
echo "📋 环境检查:"

echo -n "  Python3: "
python3 --version 2>&1 | head -1 && echo "    ✅" || { echo "    ❌"; ((ERRORS++)); }

echo -n "  FFmpeg: "
ffmpeg -version 2>&1 | head -1 | cut -d' ' -f3 && echo "    ✅" || { echo "    ❌"; ((ERRORS++)); }

echo -n "  字体: "
[ -f "/usr/share/fonts/truetype/chinese/msyh.ttf" ] && echo "微软雅黑 ✅" || \
[ -f "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc" ] && echo "文泉驿 ✅" || \
echo "默认字体 ⚠️"

# 2. 文件检查
echo ""
echo "📁 文件检查:"

echo -n "  config.json: "
[ -f "config.json" ] && echo "✅" || { echo "❌"; ((ERRORS++)); }

echo -n "  background.mp4: "
[ -f "assets/background_loop.mp4" ] && echo "✅" || echo "⚠️ (将用纯色)"

echo -n "  目录结构: "
mkdir -p data logs output && echo "✅"

# 3. 模块测试
echo ""
echo "🔧 模块测试:"

echo -n "  config.py: "
timeout 5 python3 -c "from core.config import Config; c=Config(); print('✅' if c.is_valid() else '❌')" 2>/dev/null || { echo "❌"; ((ERRORS++)); }

echo -n "  paths.py: "
timeout 5 python3 -c "from core.paths import PathManager; p=PathManager(); print('✅')" 2>/dev/null || { echo "❌"; ((ERRORS++)); }

echo -n "  ffmpeg_cmd.py: "
timeout 10 python3 -c "
from core.paths import PathManager
from core.ffmpeg_cmd import FFmpegBuilder
pm = PathManager()
b = FFmpegBuilder(pm.find_font(), pm.background_video)
ok, msg = b.test_syntax(1)
print('✅' if ok else '❌')
" 2>/dev/null || { echo "❌"; ((ERRORS++)); }

# 4. 生成测试视频
echo ""
echo "🎬 视频生成测试:"

echo -n "  测试视频: "
TEST_FILE="output/test_quick.mp4"
timeout 15 ffmpeg -y -f lavfi -i "color=c=0x1a1a2e:s=640x360:d=2" \
    -vf "drawtext=fontfile=/usr/share/fonts/truetype/chinese/msyh.ttf:text='OK':x=10:y=10:fontsize=24:fontcolor=white" \
    -c:v libx264 -preset ultrafast -t 2 "$TEST_FILE" > /dev/null 2>&1 && \
echo "✅ ($(($(stat -c%s "$TEST_FILE" 2>/dev/null || echo 0) / 1024))KB)" || { echo "❌"; ((ERRORS++)); }
rm -f "$TEST_FILE"

# 结果
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $ERRORS -eq 0 ]; then
    echo "✅ 测试通过！"
    echo ""
    echo "启动命令:"
    echo "  python3 anchor.py      # 前台运行"
    echo "  bash run.sh bg         # 后台运行"
else
    echo "❌ 发现 $ERRORS 个错误"
fi

echo ""
