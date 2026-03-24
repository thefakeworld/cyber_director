#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI主播台 - 主程序（重构版）
==========================
架构改进：
1. 模块化设计 - 配置、路径、FFmpeg命令独立
2. 启动前验证 - 所有依赖检查通过后才启动
3. 健康监控 - 定期检查推流状态
4. 优雅退出 - 正确处理信号和资源清理
"""

import asyncio
import subprocess
import signal
import sys
import logging
import os
from datetime import datetime
from pathlib import Path
import random
import json

# 导入核心模块
from core.config import Config
from core.paths import PathManager
from core.ffmpeg_cmd import FFmpegBuilder


class AIAnchor:
    """AI主播台核心"""
    
    def __init__(self):
        # 初始化配置
        self.config = Config()
        if not self.config.is_valid():
            print(f"❌ 配置加载失败: {self.config.errors}")
            sys.exit(1)
        
        # 初始化路径
        self.paths = PathManager()
        
        # 设置日志
        self._setup_logging()
        
        # 进程管理（支持多进程）
        # 格式: [(proc, rtmp_url, log_file), ...]
        self.ffmpeg_procs = []  # 改为列表
        self.running = True
        self.start_time = None
        
        # 统计
        self.stats = {
            "restarts": 0,
            "content_updates": 0,
            "uptime_seconds": 0
        }
    
    def _setup_logging(self):
        """配置日志"""
        self.logger = logging.getLogger("AIAnchor")
        self.logger.setLevel(logging.INFO)
        
        # 控制台输出
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter(
            '[%(asctime)s] %(message)s', datefmt='%H:%M:%S'
        ))
        self.logger.addHandler(console)
        
        # 文件输出
        log_file = self.paths.get_log_file()
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s'
        ))
        self.logger.addHandler(file_handler)
    
    def check_environment(self) -> bool:
        """
        启动前环境检查
        返回: 是否全部通过
        """
        self.logger.info("🔍 环境检查...")
        
        errors = []
        
        # 检查路径
        ok, missing = self.paths.check_requirements()
        if not ok:
            errors.extend(missing)
        
        # 检查字体
        has_font, font = self.paths.check_font()
        if not has_font:
            self.logger.warning("⚠️ 未找到中文字体，使用系统默认")
        
        # 检查推流地址
        rtmp_url = self.config.get_rtmp_url()
        if not rtmp_url:
            errors.append("未配置推流地址")
        
        # 检查FFmpeg
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
            if result.returncode != 0:
                errors.append("FFmpeg 无法运行")
        except Exception as e:
            errors.append(f"FFmpeg 检查失败: {e}")
        
        if errors:
            self.logger.error("❌ 环境检查失败:")
            for err in errors:
                self.logger.error(f"   - {err}")
            return False
        
        self.logger.info("✅ 环境检查通过")
        return True
    
    def test_ffmpeg_command(self) -> bool:
        """测试FFmpeg命令是否正确"""
        self.logger.info("🔍 测试FFmpeg命令...")
        
        builder = FFmpegBuilder(
            font_path=self.paths.find_font(),
            bg_video=self.paths.background_video
        )
        builder.set_content_files(self.paths.script_file, self.paths.ticker_file)
        
        success, msg = builder.test_syntax(duration=1)
        if success:
            self.logger.info("✅ FFmpeg命令测试通过")
            return True
        else:
            self.logger.error(f"❌ FFmpeg命令测试失败: {msg[:200]}")
            return False
    
    def test_network(self) -> bool:
        """测试推流连接"""
        self.logger.info("🔍 测试推流连接...")
        
        rtmp_urls = self.config.get_rtmp_urls()
        if not rtmp_urls:
            self.logger.warning("⚠️ 未配置推流地址")
            return True
        
        builder = FFmpegBuilder(font_path=self.paths.find_font())
        
        for url in rtmp_urls:
            display = url.split('?')[0] if '?' in url else url
            success, msg = builder.test_network(url, timeout=10)
            if success:
                self.logger.info(f"✅ {display} 连接成功")
            else:
                self.logger.warning(f"⚠️ {display} 连接失败: {msg}")
        
        return True
    
    def init_content(self):
        """初始化内容文件"""
        self.paths.script_file.write_text("AI主播台 正在直播...", encoding='utf-8')
        self.paths.ticker_file.write_text(
            "欢迎观看AI主播台 | 科技资讯 | AI前沿动态",
            encoding='utf-8'
        )
        self.logger.info("✅ 内容文件初始化完成")
    
    def start_ffmpeg(self) -> bool:
        """启动FFmpeg推流（支持多平台，每个平台独立进程）"""
        rtmp_urls = self.config.get_rtmp_urls()
        
        if not rtmp_urls:
            self.logger.warning("⚠️ 未配置推流地址")
            return False
        
        self.logger.info(f"🎬 启动推流进程 ({len(rtmp_urls)} 个平台)...")
        
        success_count = 0
        self.ffmpeg_procs = []
        
        for i, rtmp_url in enumerate(rtmp_urls):
            # 为每个平台创建独立的builder
            builder = FFmpegBuilder(
                font_path=self.paths.find_font(),
                bg_video=self.paths.background_video
            )
            builder.set_content_files(self.paths.script_file, self.paths.ticker_file)
            builder.set_output(rtmp_urls=[rtmp_url])  # 单个推流地址
            builder.set_video_params(
                bitrate=self.config.get('video', 'bitrate', default='1500k'),
                preset=self.config.get('video', 'preset', default='ultrafast')
            )
            
            cmd = builder.build()
            
            # 创建日志文件（不使用PIPE，避免缓冲区满导致阻塞）
            log_dir = self.paths.logs_dir
            platform_name = self.config.get_platform_names()[i] if i < len(self.config.get_platform_names()) else f"platform_{i}"
            log_file = log_dir / f"ffmpeg_{platform_name.replace(' ', '_')}.log"
            
            try:
                # 打开日志文件
                log_fh = open(log_file, 'w')
                
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=log_fh,
                    stderr=log_fh,
                )
                # 保存进程信息: (proc, rtmp_url, log_file_handle, log_file_path)
                self.ffmpeg_procs.append((proc, rtmp_url, log_fh, log_file))
                
                # 检查是否立即失败
                import time
                time.sleep(0.5)
                
                if proc.poll() is not None:
                    display = rtmp_url.split('?')[0]
                    self.logger.error(f"❌ {display} 启动失败")
                    # 读取日志文件
                    try:
                        log_fh.flush()
                        with open(log_file, 'r') as f:
                            err = f.read()[-500:]
                            self.logger.error(f"   错误: {err}")
                    except:
                        pass
                else:
                    display = rtmp_url.split('?')[0]
                    self.logger.info(f"✅ {display} (PID: {proc.pid})")
                    success_count += 1
                    
            except Exception as e:
                self.logger.error(f"❌ 启动失败: {e}")
        
        return success_count > 0
    
    def stop_ffmpeg(self):
        """停止所有FFmpeg进程"""
        for item in self.ffmpeg_procs:
            if isinstance(item, tuple):
                proc, url, log_fh, log_file = item
            else:
                proc = item
                log_fh = None
            
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except:
                    proc.kill()
            
            # 关闭日志文件
            if log_fh:
                try:
                    log_fh.close()
                except:
                    pass
                    
        self.ffmpeg_procs = []
        self.logger.info("🛑 推流进程已停止")
    
    async def content_updater(self):
        """内容更新协程"""
        news_pool = [
            "AI技术突破：大模型推理速度提升10倍",
            "科技前沿：量子计算进入实用阶段",
            "互联网资讯：元宇宙应用加速落地",
            "行业动态：智能客服覆盖率达95%",
            "创新突破：自动驾驶迈入L4时代",
            "数据安全：隐私计算技术成熟",
            "云计算：成本降低90%不是梦",
            "芯片产业：国产替代加速推进",
            "机器人：人形机器人量产在即",
            "AI医疗：诊断准确率超人类医生",
        ]
        
        interval = self.config.get('content', 'update_interval', default=60)
        
        while self.running:
            try:
                await asyncio.sleep(interval)
                
                # 更新内容
                news = random.sample(news_pool, min(4, len(news_pool)))
                ticker = " | ".join(news)
                self.paths.ticker_file.write_text(ticker, encoding='utf-8')
                
                now = datetime.now().strftime("%H:%M")
                script = f"[{now}] {news[0]}"
                self.paths.script_file.write_text(script, encoding='utf-8')
                
                self.stats["content_updates"] += 1
                self.logger.info(f"📝 内容更新 #{self.stats['content_updates']}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"内容更新出错: {e}")
    
    def _check_connection_alive(self, pid: int) -> bool:
        """检查进程的网络连接是否还活着"""
        try:
            # 使用ss检查TCP连接状态
            result = subprocess.run(
                ['ss', '-tnp'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            for line in result.stdout.split('\n'):
                if f'pid={pid}' in line or f',pid={pid},' in line:
                    # 检查是否是已建立的连接（ESTAB）
                    if 'ESTAB' in line:
                        return True
                    # 如果是CLOSE_WAIT等状态，连接已断开
                    if 'CLOSE' in line or 'TIME_WAIT' in line:
                        return False
            # 如果没有找到连接，说明已经断了
            return False
        except:
            # 如果检查失败，假设连接还在
            return True
    
    async def health_monitor(self):
        """健康监控协程"""
        while self.running:
            try:
                await asyncio.sleep(10)  # 每10秒检查一次
                
                # 更新运行时间
                if self.start_time:
                    self.stats["uptime_seconds"] = (
                        datetime.now() - self.start_time
                    ).total_seconds()
                
                # 检查所有FFmpeg进程
                dead_procs = []
                for item in self.ffmpeg_procs[:]:
                    if isinstance(item, tuple):
                        proc, url, log_fh, log_file = item
                    else:
                        proc = item
                        url = "unknown"
                        log_fh = None
                        log_file = None
                    
                    # 检查进程是否退出
                    if proc.poll() is not None:
                        self.stats["restarts"] += 1
                        retcode = proc.returncode
                        display = url.split('?')[0] if '?' in url else url
                        
                        self.logger.warning(f"⚠️ FFmpeg进程退出 (code={retcode}, PID: {proc.pid}, {display})")
                        
                        # 读取日志文件
                        if log_file and log_file.exists():
                            try:
                                with open(log_file, 'r') as f:
                                    content = f.read()
                                    for line in content.strip().split('\n')[-5:]:
                                        if 'error' in line.lower() or 'Error' in line:
                                            self.logger.error(f"   {line}")
                            except:
                                pass
                        
                        dead_procs.append(item)
                        continue
                    
                    # 检查连接是否还活着
                    if not self._check_connection_alive(proc.pid):
                        display = url.split('?')[0] if '?' in url else url
                        self.logger.warning(f"⚠️ 连接已断开 (PID: {proc.pid}, {display})")
                        
                        # 杀掉进程
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except:
                            proc.kill()
                        
                        if log_fh:
                            try:
                                log_fh.close()
                            except:
                                pass
                        
                        dead_procs.append(item)
                
                # 移除死亡的进程
                for item in dead_procs:
                    if item in self.ffmpeg_procs:
                        self.ffmpeg_procs.remove(item)
                
                # 如果所有进程都挂了，尝试重启
                if not self.ffmpeg_procs:
                    self.stats["restarts"] += 1
                    self.logger.info(f"🔄 重启推流... (#{self.stats['restarts']})")
                    await asyncio.sleep(2)
                    self.start_ffmpeg()
                
                # 保存状态
                self._save_status()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"监控出错: {e}")
    
    def _save_status(self):
        """保存运行状态"""
        status = {
            "status": "running" if self.running else "stopped",
            "platform": self.config.get_platform_name(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime_seconds": self.stats["uptime_seconds"],
            "restarts": self.stats["restarts"],
            "content_updates": self.stats["content_updates"]
        }
        
        with open(self.paths.status_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    
    async def run(self):
        """主运行循环"""
        self.start_time = datetime.now()
        
        # 启动前检查
        if not self.check_environment():
            return False
        
        if not self.test_ffmpeg_command():
            return False
        
        self.test_network()
        
        # 初始化内容
        self.init_content()
        
        # 显示启动信息
        self.logger.info("=" * 50)
        self.logger.info("🎬 AI主播台 启动")
        self.logger.info("=" * 50)
        
        # 显示所有平台
        platforms = self.config.get_platform_names()
        if len(platforms) > 1:
            self.logger.info(f"📺 多平台推流: {', '.join(platforms)}")
        else:
            self.logger.info(f"📺 平台: {platforms[0] if platforms else '未知'}")
        
        self.logger.info(f"📁 背景: {self.paths.background_video if self.paths.background_video.exists() else '纯色背景'}")
        self.logger.info(f"🔤 字体: {self.paths.find_font()}")
        self.logger.info(f"⏱️ 更新间隔: {self.config.get('content', 'update_interval', default=60)}秒")
        
        # 启动FFmpeg
        if not self.start_ffmpeg():
            return False
        
        # 启动协程
        tasks = [
            asyncio.create_task(self.content_updater()),
            asyncio.create_task(self.health_monitor()),
        ]
        
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False
            for task in tasks:
                task.cancel()
            self.stop_ffmpeg()
            self._save_status()
            self.logger.info("👋 AI主播台已关闭")
        
        return True


def main():
    """主入口"""
    print("\n" + "=" * 50)
    print("   🎬 AI主播台 v2.0")
    print("=" * 50 + "\n")
    
    anchor = AIAnchor()
    
    # 信号处理
    def on_signal(signum, frame):
        anchor.running = False
        anchor.logger.info("收到退出信号")
    
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    
    # 运行
    try:
        asyncio.run(anchor.run())
    except KeyboardInterrupt:
        print("\n用户中断")


if __name__ == "__main__":
    main()
