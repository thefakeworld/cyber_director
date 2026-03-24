#!/bin/bash
# =====================================================
# AI主播台 - 突发新闻快速插入脚本
# =====================================================
# 用法: ./breaking_news.sh "新闻标题" ["新闻内容"]
# 示例: ./breaking_news.sh "突发：某重大事件发生" "详细内容..."

set -e
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# 检查参数
if [ -z "$1" ]; then
    echo "用法: $0 '新闻标题' ['新闻内容']"
    echo ""
    echo "示例:"
    echo "  $0 '突发：重大新闻事件'"
    echo "  $0 '热点事件' '详细内容描述...'"
    echo ""
    echo "功能说明:"
    echo "  - 将突发新闻插入到播报队列"
    echo "  - 自动生成TTS音频"
    echo "  - 触发直播间字幕更新"
    exit 1
fi

TITLE="$1"
CONTENT="${2:-详情请关注官方消息}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "=========================================="
echo "📰 突发新闻插入"
echo "=========================================="
echo ""
echo "时间: $TIMESTAMP"
echo "标题: $TITLE"
echo "内容: $CONTENT"
echo ""

# Python脚本处理
python3 << EOF
import sys
sys.path.insert(0, '$PROJECT_ROOT')

from pathlib import Path
from datetime import datetime

# 写入突发新闻播报稿
breaking_file = Path('$PROJECT_ROOT/data/breaking_broadcast.txt')
ticker_file = Path('$PROJECT_ROOT/data/ticker.txt')

# 突发新闻播报内容
broadcast_content = f"""【突发新闻】{datetime.now().strftime('%H:%M')}
{ '$TITLE' }
{ '$CONTENT' }
"""

# 更新播报稿
breaking_file.write_text(broadcast_content, encoding='utf-8')
print(f"✅ 播报稿已更新: {breaking_file}")

# 更新滚动条
ticker_content = f"【突发】{ '$TITLE' } - { '$CONTENT' }"
ticker_file.write_text(ticker_content, encoding='utf-8')
print(f"✅ 滚动条已更新: {ticker_file}")

# 触发TTS生成
try:
    from core.paths import PathManager
    from plugins.tts import TTSPluginV2
    
    paths = PathManager()
    tts_config = {
        'voice': 'zh-CN-XiaoxiaoNeural',
        'style': 'urgent',  # 紧急播报风格
        'output_dir': str(paths.assets_dir / 'tts')
    }
    
    tts = TTSPluginV2(tts_config)
    tts.on_start({'project_root': '$PROJECT_ROOT'})
    
    # 生成TTS音频
    audio_path = tts.generate_tts(
        text=f"突发新闻。{ '$TITLE' }。{ '$CONTENT' }",
        style='urgent'
    )
    
    if audio_path:
        print(f"✅ TTS音频已生成: {audio_path}")
        
        # 添加到播放队列
        tts.add_to_queue(
            text=f"突发新闻。{ '$TITLE' }。{ '$CONTENT' }",
            audio_path=audio_path,
            style='urgent'
        )
        print(f"✅ 已添加到TTS播放队列")
    else:
        print("⚠️ TTS生成失败，请手动检查")
        
except ImportError as e:
    print(f"⚠️ TTS模块导入失败: {e}")
    print("  请手动生成TTS音频")
except Exception as e:
    print(f"⚠️ TTS处理出错: {e}")

print()
print("==========================================")
print("📰 突发新闻插入完成")
print("==========================================")
EOF

echo ""
echo "提示:"
echo "  - 播报稿文件: data/breaking_broadcast.txt"
echo "  - 滚动条文件: data/ticker.txt"
echo "  - 如需立即生效，可能需要重启anchor_v2服务"
