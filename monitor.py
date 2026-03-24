#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛博电视台 - 性能监控脚本
=========================
实时监控 FFmpeg 推流进程和系统资源

功能:
- CPU/内存实时监控
- FFmpeg 进程状态
- 推流健康检查
- 日志文件监控
"""

import os
import sys
import json
import time
import signal
import subprocess
from datetime import datetime
from pathlib import Path

# 颜色定义
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def clear_screen():
    """清屏"""
    os.system('clear' if os.name == 'posix' else 'cls')

def get_system_stats():
    """获取系统资源统计"""
    try:
        # CPU 使用率
        with open('/proc/stat', 'r') as f:
            line = f.readline()
            values = [int(x) for x in line.split()[1:8]]
            idle = values[3]
            total = sum(values)
        
        # 等待 1 秒后再次读取
        time.sleep(0.1)
        
        with open('/proc/stat', 'r') as f:
            line = f.readline()
            values2 = [int(x) for x in line.split()[1:8]]
            idle2 = values2[3]
            total2 = sum(values2)
        
        cpu_usage = 100 * (1 - (idle2 - idle) / (total2 - total))
        
        # 内存使用
        with open('/proc/meminfo', 'r') as f:
            mem_total = int(f.readline().split()[1])
            mem_free = int(f.readline().split()[1])
            f.readline()  # MemAvailable
            mem_buffers = int(f.readline().split()[1])
            mem_cached = int(f.readline().split()[1])
        
        mem_used = mem_total - mem_free - mem_buffers - mem_cached
        mem_percent = 100 * mem_used / mem_total
        
        return {
            'cpu_percent': cpu_usage,
            'mem_total_mb': mem_total // 1024,
            'mem_used_mb': mem_used // 1024,
            'mem_percent': mem_percent
        }
    except Exception as e:
        return {'error': str(e)}

def get_ffmpeg_stats():
    """获取 FFmpeg 进程信息"""
    try:
        # 查找 ffmpeg 进程
        result = subprocess.run(
            ['pgrep', '-a', 'ffmpeg'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return {'running': False, 'message': 'FFmpeg 进程未运行'}
        
        pids = result.stdout.strip().split('\n')
        processes = []
        
        for line in pids:
            if not line:
                continue
            parts = line.split(' ', 1)
            pid = parts[0]
            cmd = parts[1] if len(parts) > 1 else ''
            
            # 获取进程 CPU 和内存
            try:
                stat_result = subprocess.run(
                    ['ps', '-p', pid, '-o', '%cpu,%mem,etime,vsz,rss', '--no-headers'],
                    capture_output=True,
                    text=True
                )
                if stat_result.returncode == 0:
                    stats = stat_result.stdout.strip().split()
                    processes.append({
                        'pid': pid,
                        'cpu': float(stats[0]),
                        'mem': float(stats[1]),
                        'etime': stats[2],
                        'vsz_kb': int(stats[3]),
                        'rss_kb': int(stats[4]),
                        'cmd': cmd[:60] + '...' if len(cmd) > 60 else cmd
                    })
            except:
                pass
        
        return {
            'running': True,
            'count': len(processes),
            'processes': processes
        }
    except Exception as e:
        return {'running': False, 'error': str(e)}

def get_director_status():
    """获取导演系统状态"""
    status_file = Path('data/status.json')
    if status_file.exists():
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'status': 'unknown'}

def get_network_stats():
    """获取网络统计"""
    try:
        result = subprocess.run(
            ['ss', '-tunp', 'state', 'established'],
            capture_output=True,
            text=True
        )
        
        lines = result.stdout.strip().split('\n')
        connections = []
        
        for line in lines[1:]:  # 跳过标题行
            parts = line.split()
            if len(parts) >= 6:
                connections.append({
                    'proto': parts[0],
                    'local': parts[4],
                    'remote': parts[5] if len(parts) > 5 else 'N/A'
                })
        
        return {'connections': len(connections), 'list': connections[:5]}
    except:
        return {'connections': 0}

def get_disk_usage():
    """获取磁盘使用情况"""
    try:
        result = subprocess.run(
            ['df', '-h', '/'],
            capture_output=True,
            text=True
        )
        lines = result.stdout.strip().split('\n')
        if len(lines) >= 2:
            parts = lines[1].split()
            return {
                'total': parts[1],
                'used': parts[2],
                'avail': parts[3],
                'percent': parts[4]
            }
    except:
        pass
    return {}

def format_bar(percent, width=20):
    """生成进度条"""
    filled = int(width * percent / 100)
    empty = width - filled
    
    if percent < 50:
        color = Colors.GREEN
    elif percent < 80:
        color = Colors.YELLOW
    else:
        color = Colors.RED
    
    bar = '█' * filled + '░' * empty
    return f"{color}{bar}{Colors.RESET}"

def draw_dashboard():
    """绘制监控仪表盘"""
    clear_screen()
    
    # 标题
    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("╔" + "═" * 58 + "╗")
    print("║" + "📺 赛博电视台 - 性能监控中心".center(50) + "║")
    print("║" + f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(50) + "║")
    print("╚" + "═" * 58 + "╝")
    print(f"{Colors.RESET}")
    
    # 系统资源
    print(f"\n{Colors.BOLD}🖥️  系统资源{Colors.RESET}")
    print("─" * 50)
    
    sys_stats = get_system_stats()
    if 'error' not in sys_stats:
        cpu = sys_stats['cpu_percent']
        mem = sys_stats['mem_percent']
        
        print(f"  CPU 使用率: {format_bar(cpu)} {cpu:.1f}%")
        print(f"  内存使用:   {format_bar(mem)} {mem:.1f}% ({sys_stats['mem_used_mb']}/{sys_stats['mem_total_mb']} MB)")
    else:
        print(f"  {Colors.RED}获取系统信息失败: {sys_stats['error']}{Colors.RESET}")
    
    # 磁盘
    disk = get_disk_usage()
    if disk:
        disk_percent = int(disk['percent'].replace('%', ''))
        print(f"  磁盘使用:   {format_bar(disk_percent)} {disk['percent']} ({disk['used']}/{disk['total']})")
    
    # FFmpeg 进程
    print(f"\n{Colors.BOLD}🎬 FFmpeg 进程状态{Colors.RESET}")
    print("─" * 50)
    
    ffmpeg_stats = get_ffmpeg_stats()
    if ffmpeg_stats['running']:
        print(f"  状态: {Colors.GREEN}● 运行中{Colors.RESET} ({ffmpeg_stats['count']} 个进程)")
        
        for proc in ffmpeg_stats.get('processes', []):
            print(f"\n  {Colors.YELLOW}PID: {proc['pid']}{Colors.RESET}")
            print(f"  ├─ CPU: {proc['cpu']:.1f}% | 内存: {proc['mem']:.1f}%")
            print(f"  ├─ 运行时间: {proc['etime']}")
            print(f"  ├─ 内存占用: {proc['rss_kb'] // 1024} MB")
            print(f"  └─ 命令: {proc['cmd']}")
    else:
        msg = ffmpeg_stats.get('message', '未知状态')
        print(f"  状态: {Colors.RED}○ {msg}{Colors.RESET}")
    
    # 导演系统状态
    print(f"\n{Colors.BOLD}🎭 导演系统状态{Colors.RESET}")
    print("─" * 50)
    
    director_status = get_director_status()
    status = director_status.get('status', 'unknown')
    
    status_colors = {
        'running': Colors.GREEN,
        'starting': Colors.YELLOW,
        'stopped': Colors.RED,
        'unknown': Colors.MAGENTA
    }
    status_color = status_colors.get(status, Colors.WHITE)
    
    print(f"  状态: {status_color}{status}{Colors.RESET}")
    
    if 'last_update' in director_status:
        print(f"  最后更新: {director_status['last_update']}")
    if 'content_updates' in director_status:
        print(f"  内容更新次数: {director_status['content_updates']}")
    if 'uptime_seconds' in director_status:
        uptime = int(director_status['uptime_seconds'])
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)
        print(f"  运行时长: {hours:02d}:{minutes:02d}:{seconds:02d}")
    if 'config' in director_status:
        print(f"  推流地址: {director_status['config'].get('rtmp_url', 'N/A')}")
    
    # 网络连接
    print(f"\n{Colors.BOLD}🌐 网络连接{Colors.RESET}")
    print("─" * 50)
    
    net_stats = get_network_stats()
    print(f"  活跃连接: {net_stats['connections']}")
    for conn in net_stats.get('list', [])[:3]:
        print(f"  ├─ {conn['proto']}: {conn['local']} → {conn['remote']}")
    
    # 底部操作提示
    print(f"\n{Colors.BOLD}{'─' * 50}{Colors.RESET}")
    print(f"  {Colors.CYAN}[R]{Colors.RESET} 刷新  {Colors.CYAN}[Q]{Colors.RESET} 退出")
    print(f"  {Colors.CYAN}[L]{Colors.RESET} 查看日志  {Colors.CYAN}[K]{Colors.RESET} 终止 FFmpeg")

def watch_logs(lines=20):
    """查看最近的日志"""
    clear_screen()
    print(f"{Colors.BOLD}📜 最近 {lines} 条日志{Colors.RESET}")
    print("═" * 60)
    
    log_files = list(Path('logs').glob('*.log')) if Path('logs').exists() else []
    
    if not log_files:
        print("没有找到日志文件")
        return
    
    # 使用最新的日志文件
    latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
    
    try:
        result = subprocess.run(
            ['tail', '-n', str(lines), str(latest_log)],
            capture_output=True,
            text=True
        )
        print(result.stdout)
    except Exception as e:
        print(f"读取日志失败: {e}")
    
    print(f"\n{Colors.CYAN}按任意键返回...{Colors.RESET}")
    input()

def kill_ffmpeg():
    """终止 FFmpeg 进程"""
    try:
        result = subprocess.run(['pkill', '-INT', 'ffmpeg'], capture_output=True)
        if result.returncode == 0:
            print(f"{Colors.GREEN}✅ 已发送终止信号给 FFmpeg{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}⚠️ 没有找到 FFmpeg 进程{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}❌ 终止失败: {e}{Colors.RESET}")
    
    time.sleep(1)

def main():
    """主函数"""
    import tty
    import termios
    import select
    
    running = True
    
    def getch():
        """非阻塞获取单个字符"""
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None
    
    # 设置非阻塞输入
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        
        while running:
            draw_dashboard()
            
            # 等待用户输入或超时
            start_time = time.time()
            while time.time() - start_time < 2:  # 2秒刷新间隔
                char = getch()
                if char:
                    char = char.lower()
                    if char == 'q':
                        running = False
                        break
                    elif char == 'r':
                        break  # 立即刷新
                    elif char == 'l':
                        watch_logs()
                        break
                    elif char == 'k':
                        kill_ffmpeg()
                        break
                time.sleep(0.1)
    
    finally:
        # 恢复终端设置
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    clear_screen()
    print(f"{Colors.GREEN}👋 监控结束，再见！{Colors.RESET}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}用户中断{Colors.RESET}")
