#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI主播台 - 主程序（插件化版本）
==============================
架构：
- 事件驱动的插件系统
- 模块化的功能扩展
- 优雅的功能组合
"""

import asyncio
import subprocess
import signal
import sys
import logging
from datetime import datetime
from pathlib import Path
import json
import time

# 核心模块
from core.config import Config
from core.paths import PathManager
from core.plugin_base import EventBus, EventType, Event
from core.ffmpeg_builder import FFmpegBuilderV2, InputSource, build_from_plugins

# 插件
from plugins.bgm import BGMPlugin
from plugins.tts import TTSPluginV2
from plugins.content import ContentPluginV2


class AIAnchorV2:
    """AI主播台核心（插件化版本）"""
    
    def __init__(self):
        # 初始化配置
        self.config = Config()
        if not self.config.is_valid():
            print(f"❌ 配置加载失败: {self.config.errors}")
            sys.exit(1)
        
        # 初始化路径
        self.paths = PathManager()
        self.project_root = self.paths.project_dir
        
        # 设置日志
        self._setup_logging()
        
        # 事件总线
        self.event_bus = EventBus()
        
        # 插件实例
        self.plugins = {}
        
        # 进程管理
        self.ffmpeg_procs = []
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
    
    def _load_plugins(self):
        """加载插件"""
        plugin_configs = self.config._config.get("plugins", {})
        
        # 内容插件
        if plugin_configs.get("content", {}).get("enabled", True):
            self.plugins["content"] = ContentPluginV2(plugin_configs.get("content", {}))
            self.event_bus.register(self.plugins["content"])
        
        # BGM插件
        if plugin_configs.get("bgm", {}).get("enabled", True):
            self.plugins["bgm"] = BGMPlugin(plugin_configs.get("bgm", {}))
            self.event_bus.register(self.plugins["bgm"])
        
        # TTS插件
        if plugin_configs.get("tts", {}).get("enabled", True):
            self.plugins["tts"] = TTSPluginV2(plugin_configs.get("tts", {}))
            self.event_bus.register(self.plugins["tts"])
        
        self.logger.info(f"✅ 加载了 {len(self.plugins)} 个插件")
    
    async def _init_plugins(self):
        """初始化插件"""
        event = Event(
            EventType.ON_START,
            {"project_root": str(self.project_root)}
        )
        await self.event_bus.emit(event)
    
    def check_environment(self) -> bool:
        """环境检查"""
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
        rtmp_urls = self.config.get_rtmp_urls()
        if not rtmp_urls:
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
    
    def _build_ffmpeg_command(self) -> list:
        """构建FFmpeg命令（集成所有插件）"""
        font_path = self.paths.find_font()
        builder = FFmpegBuilderV2(font_path=font_path)
        
        # 视频输入
        if self.paths.background_video.exists():
            builder.set_bg_video(self.paths.background_video, loop=True)
        else:
            builder.set_color_bg("0x1a1a2e")
        
        # 内容文件
        builder.set_content_files(self.paths.script_file, self.paths.ticker_file)
        
        # BGM音频输入
        if "bgm" in self.plugins:
            bgm_plugin = self.plugins["bgm"]
            bgm_inputs = bgm_plugin.get_ffmpeg_inputs()
            if bgm_inputs:
                for inp in bgm_inputs:
                    source = InputSource(
                        type=inp["type"],
                        path=inp["path"],
                        label=inp.get("label", ""),
                        options=inp.get("options", {})
                    )
                    builder.add_audio_input(source)
                builder.bgm_volume = bgm_plugin.volume
        
        # TTS音频输入
        if "tts" in self.plugins:
            tts_plugin = self.plugins["tts"]
            tts_inputs = tts_plugin.get_ffmpeg_inputs()
            if tts_inputs:
                for inp in tts_inputs:
                    source = InputSource(
                        type=inp["type"],
                        path=inp["path"],
                        label=inp.get("label", ""),
                        options=inp.get("options", {})
                    )
                    builder.add_audio_input(source)
        
        # 视频参数
        video_config = self.config._config.get("video", {})
        builder.set_video_params(
            bitrate=video_config.get("bitrate", "1500k"),
            preset=video_config.get("preset", "ultrafast"),
            width=video_config.get("width", 1280),
            height=video_config.get("height", 720),
            framerate=video_config.get("framerate", 25)
        )
        
        # 推流地址
        builder.set_rtmp_output(self.config.get_rtmp_urls())
        
        return builder.build()
    
    def start_ffmpeg(self) -> bool:
        """启动FFmpeg推流"""
        rtmp_urls = self.config.get_rtmp_urls()
        
        if not rtmp_urls:
            self.logger.warning("⚠️ 未配置推流地址")
            return False
        
        self.logger.info(f"🎬 启动推流进程 ({len(rtmp_urls)} 个平台)...")
        
        success_count = 0
        self.ffmpeg_procs = []
        
        for i, rtmp_url in enumerate(rtmp_urls):
            # 为每个平台构建命令
            font_path = self.paths.find_font()
            builder = FFmpegBuilderV2(font_path=font_path)
            
            # 视频输入
            if self.paths.background_video.exists():
                builder.set_bg_video(self.paths.background_video, loop=True)
            else:
                builder.set_color_bg("0x1a1a2e")
            
            # 内容文件
            builder.set_content_files(self.paths.script_file, self.paths.ticker_file)
            
            # BGM
            if "bgm" in self.plugins:
                bgm_plugin = self.plugins["bgm"]
                bgm_inputs = bgm_plugin.get_ffmpeg_inputs()
                if bgm_inputs:
                    for inp in bgm_inputs:
                        source = InputSource(
                            type=inp["type"],
                            path=inp["path"],
                            label=inp.get("label", ""),
                            options=inp.get("options", {})
                        )
                        builder.add_audio_input(source)
                    builder.bgm_volume = bgm_plugin.volume
            
            # 单平台推流
            builder.set_rtmp_output([rtmp_url])
            
            cmd = builder.build()
            
            # 日志文件
            log_dir = self.paths.logs_dir
            platform_name = self.config.get_platform_names()[i] if i < len(self.config.get_platform_names()) else f"platform_{i}"
            log_file = log_dir / f"ffmpeg_{platform_name.replace(' ', '_')}.log"
            
            try:
                log_fh = open(log_file, 'w')
                
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=log_fh,
                    stderr=log_fh,
                )
                
                self.ffmpeg_procs.append((proc, rtmp_url, log_fh, log_file))
                
                time.sleep(0.5)
                
                if proc.poll() is not None:
                    display = rtmp_url.split('?')[0]
                    self.logger.error(f"❌ {display} 启动失败")
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
            
            if log_fh:
                try:
                    log_fh.close()
                except:
                    pass
                    
        self.ffmpeg_procs = []
        self.logger.info("🛑 推流进程已停止")
    
    async def content_updater(self):
        """内容更新协程"""
        interval = self.config.get('plugins', 'content', 'update_interval', default=60)
        
        while self.running:
            try:
                await asyncio.sleep(interval)
                
                # 触发内容更新事件
                event = Event(EventType.ON_CONTENT_UPDATE, {})
                results = await self.event_bus.emit(event)
                
                self.stats["content_updates"] += 1
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"内容更新出错: {e}")
    
    async def health_monitor(self):
        """健康监控协程"""
        while self.running:
            try:
                await asyncio.sleep(10)
                
                if self.start_time:
                    self.stats["uptime_seconds"] = (
                        datetime.now() - self.start_time
                    ).total_seconds()
                
                # 检查FFmpeg进程
                dead_procs = []
                for item in self.ffmpeg_procs[:]:
                    if isinstance(item, tuple):
                        proc, url, log_fh, log_file = item
                    else:
                        proc = item
                        url = "unknown"
                        log_fh = None
                        log_file = None
                    
                    if proc.poll() is not None:
                        self.stats["restarts"] += 1
                        retcode = proc.returncode
                        display = url.split('?')[0] if '?' in url else url
                        
                        self.logger.warning(f"⚠️ FFmpeg进程退出 (code={retcode}, PID: {proc.pid}, {display})")
                        dead_procs.append(item)
                        
                        if log_file and log_file.exists():
                            try:
                                with open(log_file, 'r') as f:
                                    content = f.read()
                                    for line in content.strip().split('\n')[-5:]:
                                        if 'error' in line.lower() or 'Error' in line:
                                            self.logger.error(f"   {line}")
                            except:
                                pass
                
                for item in dead_procs:
                    if item in self.ffmpeg_procs:
                        self.ffmpeg_procs.remove(item)
                
                if not self.ffmpeg_procs:
                    self.stats["restarts"] += 1
                    self.logger.info(f"🔄 重启推流... (#{self.stats['restarts']})")
                    await asyncio.sleep(2)
                    self.start_ffmpeg()
                
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
            "platforms": self.config.get_platform_names(),
            "plugins": list(self.plugins.keys()),
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
        
        # 环境检查
        if not self.check_environment():
            return False
        
        # 加载插件
        self._load_plugins()
        
        # 初始化插件
        await self._init_plugins()
        
        # 显示启动信息
        self.logger.info("=" * 50)
        self.logger.info("🎬 AI主播台 启动 (插件化版本)")
        self.logger.info("=" * 50)
        
        platforms = self.config.get_platform_names()
        if len(platforms) > 1:
            self.logger.info(f"📺 多平台推流: {', '.join(platforms)}")
        else:
            self.logger.info(f"📺 平台: {platforms[0] if platforms else '未知'}")
        
        self.logger.info(f"🔌 插件: {', '.join(self.plugins.keys())}")
        self.logger.info(f"📁 背景: {self.paths.background_video if self.paths.background_video.exists() else '纯色背景'}")
        
        # BGM状态
        if "bgm" in self.plugins:
            bgm_plugin = self.plugins["bgm"]
            bgm_files = bgm_plugin.discover_files(self.project_root)
            if bgm_files:
                self.logger.info(f"🎵 BGM: {len(bgm_files)} 首音乐")
            else:
                self.logger.warning("🎵 BGM: 未找到音乐文件")
        
        self.logger.info(f"🔤 字体: {self.paths.find_font()}")
        
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
    print("   🎬 AI主播台 v3.0 (插件化)")
    print("=" * 50 + "\n")
    
    anchor = AIAnchorV2()
    
    def on_signal(signum, frame):
        anchor.running = False
        anchor.logger.info("收到退出信号")
    
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    
    try:
        asyncio.run(anchor.run())
    except KeyboardInterrupt:
        print("\n用户中断")


if __name__ == "__main__":
    main()
