#!/bin/bash
# =====================================================
# AI主播台 - 启动脚本
# =====================================================
# 使用方法:
#   ./run.sh         # 前台运行
#   ./run.sh bg      # 后台运行
#   ./run.sh stop    # 停止服务
#   ./run.sh test    # 运行测试
#   ./run.sh status  # 查看状态

set -e
cd "$(dirname "$0")"

# ==================== 帮助信息 ====================
show_help() {
    echo ""
    echo "AI主播台 - 使用说明"
    echo ""
    echo "命令:"
    echo "  ./run.sh         前台运行（可看实时日志）"
    echo "  ./run.sh bg      后台运行"
    echo "  ./run.sh stop    停止服务"
    echo "  ./run.sh test    运行测试"
    echo "  ./run.sh status  查看状态"
    echo "  ./run.sh log     查看日志"
    echo ""
}

# ==================== 状态检查 ====================
check_status() {
    echo ""
    echo "📊 AI主播台 状态"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # 进程检查
    if pgrep -f "anchor.py" > /dev/null; then
        PID=$(pgrep -f "anchor.py")
        ETIME=$(ps -p $PID -o etime --no-headers 2>/dev/null | tr -d ' ')
        echo "✅ 运行中 (PID: $PID, 运行时间: $ETIME)"
        
        # FFmpeg进程
        if pgrep ffmpeg > /dev/null; then
            FFMPEG_PID=$(pgrep ffmpeg)
            echo "✅ FFmpeg推流中 (PID: $FFMPEG_PID)"
        fi
        
        # 状态文件
        if [ -f "data/status.json" ]; then
            echo ""
            echo "📈 运行统计:"
            python3 -c "
import json
with open('data/status.json') as f:
    s = json.load(f)
print(f\"   平台: {s.get('platform', 'N/A')}\")
print(f\"   重启次数: {s.get('restarts', 0)}\")
print(f\"   内容更新: {s.get('content_updates', 0)}\")
uptime = s.get('uptime_seconds', 0)
hours = int(uptime // 3600)
mins = int((uptime % 3600) // 60)
print(f\"   运行时长: {hours:02d}:{mins:02d}\")
"
        fi
    else
        echo "❌ 未运行"
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# ==================== 主逻辑 ====================
case "${1:-run}" in
    "help"|"-h"|"--help")
        show_help
        ;;
    
    "test")
        bash scripts/test_all.sh
        ;;
    
    "status")
        check_status
        ;;
    
    "log")
        echo "📜 最新日志 (Ctrl+C 退出):"
        echo ""
        tail -f logs/anchor_*.log 2>/dev/null || echo "日志文件不存在"
        ;;
    
    "stop")
        echo "🛑 停止AI主播台..."
        pkill -f "anchor.py" 2>/dev/null || true
        pkill -f "ffmpeg" 2>/dev/null || true
        sleep 1
        echo "✅ 已停止"
        ;;
    
    "bg"|"daemon")
        echo "🚀 后台启动AI主播台..."
        
        # 先停止旧进程
        pkill -f "anchor.py" 2>/dev/null || true
        pkill -f "ffmpeg" 2>/dev/null || true
        sleep 1
        
        # 启动
        mkdir -p data logs output
        nohup python3 anchor.py > logs/stdout.log 2>&1 &
        echo $! > data/anchor.pid
        
        sleep 2
        
        if pgrep -f "anchor.py" > /dev/null; then
            echo "✅ 启动成功 (PID: $(cat data/anchor.pid))"
            echo "📄 日志: tail -f logs/anchor_*.log"
            check_status
        else
            echo "❌ 启动失败，查看日志:"
            tail -20 logs/anchor_*.log 2>/dev/null
        fi
        ;;
    
    "run"|"start"|"")
        echo "🚀 启动AI主播台（前台模式）..."
        echo "按 Ctrl+C 停止"
        echo ""
        
        # 停止旧进程
        pkill -f "anchor.py" 2>/dev/null || true
        pkill -f "ffmpeg" 2>/dev/null || true
        sleep 1
        
        # 启动
        mkdir -p data logs output
        python3 anchor.py
        ;;
    
    *)
        echo "未知命令: $1"
        show_help
        exit 1
        ;;
esac
