#!/bin/bash
# =====================================================
# AI主播台 - 启动脚本 (插件化版本)
# =====================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/data/anchor.pid"
LOG_FILE="$SCRIPT_DIR/logs/anchor.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

show_banner() {
    echo ""
    echo "═════════════════════════════════════════════════════════"
    echo "           🎬 AI主播台 v3.0 (插件化)"
    echo "═════════════════════════════════════════════════════════"
}

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️ 服务已在运行 (PID: $PID)${NC}"
            return 1
        fi
        rm -f "$PID_FILE"
    fi
    
    echo -e "${GREEN}🚀 启动AI主播台...${NC}"
    
    # 确保目录存在
    mkdir -p "$SCRIPT_DIR/data"
    mkdir -p "$SCRIPT_DIR/logs"
    mkdir -p "$SCRIPT_DIR/assets/bgm"
    mkdir -p "$SCRIPT_DIR/assets/tts"
    
    # 检查BGM文件
    BGM_COUNT=$(ls -1 "$SCRIPT_DIR/assets/bgm/"*.mp3 2>/dev/null | wc -l)
    if [ "$BGM_COUNT" -eq 0 ]; then
        echo -e "${YELLOW}⚠️ 未找到BGM文件，正在生成默认音乐...${NC}"
        ffmpeg -y -f lavfi -i "sine=frequency=220:duration=60" \
               -f lavfi -i "sine=frequency=330:duration=60" \
               -filter_complex "[0:a][1:a]amix=inputs=2:duration=longest,volume=0.1,lowpass=f=800" \
               -c:a libmp3lame -b:a 128k "$SCRIPT_DIR/assets/bgm/default.mp3" > /dev/null 2>&1
        echo -e "${GREEN}✅ 已生成默认BGM${NC}"
    fi
    
    # 启动主程序（使用新版本）
    nohup python3 "$SCRIPT_DIR/anchor_v2.py" > "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    
    echo -e "${CYAN}⏳ 等待启动...${NC}"
    sleep 3
    
    # 检查进程
    if ps -p $PID > /dev/null 2>&1; then
        echo ""
        status
    else
        echo -e "${RED}❌ 启动失败，请检查日志:${NC}"
        echo "   tail -20 $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${YELLOW}⚠️ 服务未运行${NC}"
        return 0
    fi
    
    PID=$(cat "$PID_FILE")
    echo -e "${YELLOW}🛑 停止服务 (PID: $PID)...${NC}"
    
    # 停止主进程
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID 2>/dev/null
        sleep 2
        if ps -p $PID > /dev/null 2>&1; then
            kill -9 $PID 2>/dev/null
        fi
    fi
    
    # 停止所有FFmpeg进程
    pkill -f "ffmpeg.*anchor" 2>/dev/null
    
    rm -f "$PID_FILE"
    echo -e "${GREEN}✅ 服务已停止${NC}"
}

status() {
    show_banner
    
    # 检查主进程
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${GREEN}✅ 运行中 (PID: $PID)${NC}"
        else
            echo -e "${RED}❌ 已停止（进程不存在）${NC}"
            rm -f "$PID_FILE"
        fi
    else
        echo -e "${RED}❌ 未运行${NC}"
    fi
    
    # 检查FFmpeg进程
    FFMPEG_PIDS=$(pgrep -f "ffmpeg.*anchor" 2>/dev/null)
    if [ -n "$FFMPEG_PIDS" ]; then
        COUNT=$(echo "$FFMPEG_PIDS" | wc -l)
        echo -e "${GREEN}✅ FFmpeg 推流中 ($COUNT 个平台)${NC}"
        for FID in $FFMPEG_PIDS; do
            echo "   PID: $FID "
        done
    fi
    
    # 读取配置显示推流目标
    echo ""
    echo "📡 推流目标:"
    if command -v jq &> /dev/null; then
        jq -r '.platforms | to_entries[] | select(.value.enabled == true) | "   • \(.value.name): \(.value.rtmp_url | split("?")[0])"' "$SCRIPT_DIR/config.json" 2>/dev/null
    else
        grep -o '"rtmp_url": "[^"]*"' "$SCRIPT_DIR/config.json" | head -2 | while read line; do
            URL=$(echo "$line" | cut -d'"' -f4 | cut -d'?' -f1)
            echo "   • $URL"
        done
    fi
    
    # 显示插件状态
    echo ""
    echo "🔌 插件状态:"
    if command -v jq &> /dev/null; then
        jq -r '.plugins | to_entries[] | "   • \(.key): \(if .value.enabled then "✅ 启用" else "❌ 禁用" end)"' "$SCRIPT_DIR/config.json" 2>/dev/null
    else
        echo "   • content: ✅"
        echo "   • bgm: ✅"
        echo "   • tts: ✅"
    fi
    
    # BGM文件
    BGM_COUNT=$(ls -1 "$SCRIPT_DIR/assets/bgm/"*.mp3 2>/dev/null | wc -l)
    echo ""
    echo "🎵 BGM文件: $BGM_COUNT 首"
    
    # 直播间链接
    echo ""
    echo "📺 斗鱼: https://www.douyu.com/12898962"
    echo "📺 YouTube: https://youtube.com"
    
    echo "═════════════════════════════════════════════════════════"
}

log() {
    echo -e "${CYAN}📋 最近日志:${NC}"
    echo "───────────────────────────────────────────────────────"
    tail -30 "$LOG_FILE" 2>/dev/null || echo "日志文件不存在"
    echo "───────────────────────────────────────────────────────"
    echo "完整日志: $LOG_FILE"
}

test_plugins() {
    echo -e "${CYAN}🧪 测试插件模块...${NC}"
    echo ""
    
    echo "测试内容插件..."
    python3 -c "from plugins.content import ContentPlugin; print('✅ 内容插件正常')" 2>&1
    
    echo "测试BGM插件..."
    python3 -c "from plugins.bgm import BGMPlugin; print('✅ BGM插件正常')" 2>&1
    
    echo "测试TTS插件..."
    python3 -c "from plugins.tts import TTSPlugin; print('✅ TTS插件正常')" 2>&1
    
    echo ""
    echo -e "${GREEN}插件测试完成${NC}"
}

# 主入口
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2
        start
        ;;
    status)
        status
        ;;
    log)
        log
        ;;
    test)
        test_plugins
        ;;
    *)
        show_banner
        echo "用法: $0 {start|stop|restart|status|log|test}"
        echo ""
        echo "  start   - 启动服务"
        echo "  stop    - 停止服务"
        echo "  restart - 重启服务"
        echo "  status  - 查看状态"
        echo "  log     - 查看日志"
        echo "  test    - 测试插件"
        echo ""
        ;;
esac
