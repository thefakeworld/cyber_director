#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cyber Director V2 - 低配服务器生存版
====================================
一个基于 FFmpeg 的虚拟电视台自动化系统

架构特点:
- 管道式异步解耦: Python 只负责内容生产，视频渲染交给 FFmpeg
- drawtext reload=1: 实现零延迟文字热更新
- CPU 友好型: 无 OpenCV 逐帧处理，无内存拷贝

Author: Cyber Director Team
Version: 2.0.0
"""

import asyncio
import subprocess
import os
import signal
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
import random

# ============================================
# 配置区 - 根据你的环境修改
# ============================================

@dataclass
class Config:
    """系统配置"""
    # 推流地址 (支持多推流)
    rtmp_urls: list = None  # 多推流地址列表
    rtmp_url: str = "rtmp://localhost/live/stream"  # 单推流地址(向后兼容)
    
    # 文件路径
    font_path: str = "/usr/share/fonts/truetype/chinese/msyh.ttf"  # 微软雅黑
    font_path_backup: str = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"  # 文泉驿
    bg_video: str = "assets/background_loop.mp4"
    logo_path: str = "assets/logo.png"
    
    # 数据文件
    script_file: str = "data/live_text.txt"
    ticker_file: str = "data/news_ticker.txt"
    audio_file: str = "data/voice.mp3"
    status_file: str = "data/status.json"
    
    # 视频参数
    video_width: int = 1280
    video_height: int = 720
    video_bitrate: str = "1500k"
    preset: str = "ultrafast"  # ultrafast, superfast, veryfast, faster, fast
    
    # 内容更新间隔 (秒)
    content_update_interval: int = 60
    
    # FFmpeg 监控间隔 (秒)
    ffmpeg_monitor_interval: int = 5
    
    # 是否启用音频
    enable_audio: bool = False
    
    # 是否保存本地测试文件
    save_local_test: bool = False
    local_test_output: str = "test_output.mp4"
    
    def __post_init__(self):
        """初始化后处理"""
        if self.rtmp_urls is None:
            self.rtmp_urls = []


class CyberDirector:
    """
    赛博电视台导演 - 核心控制器
    
    负责协调内容生产和视频推流两个子系统
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = self._setup_logger()
        self.ffmpeg_process: Optional[subprocess.Popen] = None
        self.running = True
        self.start_time = datetime.now()
        
        # 获取脚本所在目录作为项目根目录
        self.project_dir = Path(__file__).parent.resolve()
        
        # 确保目录存在
        self._init_directories()
        
        # 将相对路径转换为绝对路径
        self._resolve_paths()
        
        # 初始化内容文件
        self._init_content_files()
        
        # 检查字体
        self.font_path = self._find_font()
    
    def _resolve_paths(self):
        """将相对路径转换为绝对路径"""
        # 背景视频
        if not os.path.isabs(self.config.bg_video):
            self.config.bg_video = str(self.project_dir / self.config.bg_video)
        
        # 字体路径
        if not os.path.isabs(self.config.font_path):
            self.config.font_path = str(self.project_dir / self.config.font_path)
        
        # Logo 路径
        if hasattr(self.config, 'logo_path') and self.config.logo_path:
            if not os.path.isabs(self.config.logo_path):
                self.config.logo_path = str(self.project_dir / self.config.logo_path)
        
        # 数据文件
        if not os.path.isabs(self.config.script_file):
            self.config.script_file = str(self.project_dir / self.config.script_file)
        if not os.path.isabs(self.config.ticker_file):
            self.config.ticker_file = str(self.project_dir / self.config.ticker_file)
        if not os.path.isabs(self.config.status_file):
            self.config.status_file = str(self.project_dir / self.config.status_file)
        if not os.path.isabs(self.config.audio_file):
            self.config.audio_file = str(self.project_dir / self.config.audio_file)
        
    def _setup_logger(self) -> logging.Logger:
        """配置日志系统"""
        logger = logging.getLogger("CyberDirector")
        logger.setLevel(logging.INFO)
        
        # 控制台输出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # 格式化
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 文件输出
        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler(
            f"logs/director_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def _init_directories(self):
        """初始化必要的目录"""
        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        self.logger.info("✅ 目录初始化完成")
    
    def _init_content_files(self):
        """初始化内容文件"""
        # 主播文本
        with open(self.config.script_file, "w", encoding='utf-8') as f:
            f.write("🚀 赛博电视台 正在启动...")
        
        # 底部滚动条
        with open(self.config.ticker_file, "w", encoding='utf-8') as f:
            f.write("欢迎来到赛博电视台 | 系统初始化中... | 即将为您带来精彩内容")
        
        # 状态文件
        status = {
            "status": "starting",
            "start_time": self.start_time.isoformat(),
            "last_update": datetime.now().isoformat(),
            "frame_count": 0,
            "content_updates": 0
        }
        with open(self.config.status_file, "w", encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        
        self.logger.info("✅ 内容文件初始化完成")
    
    def _find_font(self) -> str:
        """查找可用字体"""
        fonts_to_try = [
            self.config.font_path,
            self.config.font_path_backup,
            "/usr/share/fonts/truetype/chinese/SimKai.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
        
        for font in fonts_to_try:
            if os.path.exists(font):
                self.logger.info(f"✅ 使用字体: {font}")
                return font
        
        # 如果找不到中文字体，尝试使用系统默认
        self.logger.warning("⚠️ 未找到中文字体，使用系统默认")
        return "sans"
    
    def _build_filter_complex(self) -> str:
        """
        构建 FFmpeg 滤镜链
        
        滤镜链结构:
        1. 主播文本 (左下角)
        2. 底部滚动条 (跑马灯效果)
        3. 右上角时钟
        4. 台标
        
        注意: FFmpeg 滤镜链转义规则复杂
        冒号 : 需要转义为 \\:
        反斜杠 \\ 需要转义为 \\\\
        """
        # 字体路径转义 - 路径中的冒号需要转义
        def escape_for_filter(text):
            """转义 FFmpeg 滤镜中的特殊字符"""
            return text.replace('\\', '\\\\\\\\').replace(':', '\\:')
        
        font = escape_for_filter(self.font_path)
        script = escape_for_filter(self.config.script_file)
        ticker = escape_for_filter(self.config.ticker_file)
        
        # 构建滤镜 - 使用简单的单引号包裹文本
        filters = []
        
        # 1. 主播文本 - 左下角
        filters.append(
            f"drawtext=fontfile={font}:"
            f"textfile={script}:reload=1:"
            f"x=80:y=h-200:fontsize=36:fontcolor=white:"
            f"borderw=2:bordercolor=black@0.5"
        )
        
        # 2. 滚动条 - 从右向左滚动
        filters.append(
            f"drawtext=fontfile={font}:"
            f"textfile={ticker}:reload=1:"
            f"x='w-mod(t*100\\,w+tw)':y=h-50:fontsize=24:fontcolor=yellow:"
            f"box=1:boxcolor=black@0.7:boxborderw=5"
        )
        
        # 3. 时间显示 - 使用简单格式
        # 在 FFmpeg 中，%{localtime} 会显示完整时间
        filters.append(
            f"drawtext=fontfile={font}:"
            f"text='%{{localtime}}':"
            f"x=w-250:y=30:fontsize=28:fontcolor=white:"
            f"borderw=1:bordercolor=black@0.5"
        )
        
        # 4. 频道名称
        filters.append(
            f"drawtext=fontfile={font}:"
            f"text='CYBER TV':"
            f"x=30:y=30:fontsize=28:fontcolor=cyan:"
            f"borderw=1:bordercolor=black@0.5"
        )
        
        # 5. 底部分隔线
        filters.append(
            f"drawbox=x=0:y=h-70:w=iw:h=2:color=cyan@0.8:t=fill"
        )
        
        # 组合: [0:v] 表示输入视频流
        filter_complex = "[0:v]" + ",".join(filters) + "[outv]"
        
        return filter_complex
    
    def _build_ffmpeg_command(self) -> list:
        """
        构建 FFmpeg 推流命令
        
        支持多推流地址，使用 tee 滤镜实现单编码多输出
        返回完整的命令参数列表
        """
        filter_complex = self._build_filter_complex()
        
        # 收集所有推流地址
        rtmp_targets = []
        if self.config.rtmp_urls:
            rtmp_targets.extend(self.config.rtmp_urls)
        if self.config.rtmp_url and self.config.rtmp_url not in rtmp_targets:
            rtmp_targets.append(self.config.rtmp_url)
        
        cmd = [
            'ffmpeg',
            '-y',  # 覆盖输出文件
            '-re',  # 以实时帧率读取
            '-stream_loop', '-1',  # 无限循环背景视频
            '-i', self.config.bg_video,
        ]
        
        # 音频输入 (如果启用)
        if self.config.enable_audio and os.path.exists(self.config.audio_file):
            cmd.extend([
                '-stream_loop', '-1',
                '-i', self.config.audio_file,
            ])
        
        # 滤镜
        cmd.extend(['-filter_complex', filter_complex])
        
        # 视频映射
        cmd.extend(['-map', '[outv]'])
        
        # 音频映射 (如果有)
        if self.config.enable_audio and os.path.exists(self.config.audio_file):
            cmd.extend(['-map', '1:a'])
        
        # 视频编码参数
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', self.config.preset,
            '-tune', 'zerolatency',  # 低延迟模式
            '-b:v', self.config.video_bitrate,
            '-maxrate', self.config.video_bitrate,
            '-bufsize', '3000k',
            '-pix_fmt', 'yuv420p',
            '-g', '50',  # GOP 大小
            '-keyint_min', '25',
            '-sc_threshold', '0',
        ])
        
        # 音频编码参数 (如果启用)
        if self.config.enable_audio and os.path.exists(self.config.audio_file):
            cmd.extend([
                '-c:a', 'aac',
                '-b:a', '128k',
                '-ar', '44100',
            ])
        
        # 输出格式 - 支持多推流
        if self.config.save_local_test:
            cmd.extend(['-t', '60'])  # 测试模式只录60秒
            cmd.append(self.config.local_test_output)
        elif len(rtmp_targets) == 1:
            # 单推流地址
            cmd.extend([
                '-f', 'flv',
                rtmp_targets[0]
            ])
        elif len(rtmp_targets) > 1:
            # 多推流地址 - 使用 tee 滤镜
            # tee 格式: [f=flv:rtmp_url1]|[f=flv:rtmp_url2]
            tee_parts = [f"[f=flv:{url}]" for url in rtmp_targets]
            tee_url = "|".join(tee_parts)
            cmd.extend([
                '-f', 'tee',
                '-map', '0:v',
                tee_url
            ])
            self.logger.info(f"🎯 多推流模式: {len(rtmp_targets)} 个目标")
        else:
            # 默认推流地址
            cmd.extend([
                '-f', 'flv',
                self.config.rtmp_url
            ])
        
        return cmd
    
    def start_ffmpeg_process(self) -> subprocess.Popen:
        """
        启动 FFmpeg 推流进程
        
        返回 Popen 对象
        """
        cmd = self._build_ffmpeg_command()
        
        self.logger.info("🎬 启动 FFmpeg 推流进程...")
        self.logger.debug(f"命令: {' '.join(cmd)}")
        
        # 启动进程，捕获 stderr 用于调试
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        
        # 更新状态
        self._update_status("running")
        
        return process
    
    def stop_ffmpeg_process(self):
        """安全停止 FFmpeg 进程"""
        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            self.logger.info("🛑 正在停止 FFmpeg 进程...")
            try:
                # 先发送 'q' 命令优雅退出
                self.ffmpeg_process.stdin.write(b'q')
                self.ffmpeg_process.stdin.flush()
                self.ffmpeg_process.wait(timeout=5)
            except:
                # 如果优雅退出失败，强制终止
                self.ffmpeg_process.terminate()
                try:
                    self.ffmpeg_process.wait(timeout=3)
                except:
                    self.ffmpeg_process.kill()
            
            self.logger.info("✅ FFmpeg 进程已停止")
    
    def _update_status(self, status: str, **kwargs):
        """更新状态文件"""
        try:
            current_status = {
                "status": status,
                "start_time": self.start_time.isoformat(),
                "last_update": datetime.now().isoformat(),
                "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
                "config": {
                    "rtmp_url": self.config.rtmp_url,
                    "video_bitrate": self.config.video_bitrate,
                },
                **kwargs
            }
            with open(self.config.status_file, "w", encoding='utf-8') as f:
                json.dump(current_status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"状态更新失败: {e}")

    async def content_producer(self):
        """
        内容生产者协程
        
        负责:
        1. 抓取/生成新闻内容
        2. 调用 LLM 生成播报脚本
        3. 调用 TTS 生成音频 (可选)
        """
        update_count = 0
        
        while self.running:
            try:
                self.logger.info("📡 正在获取新内容...")
                
                # 模拟新闻抓取 (实际项目中可对接 RSS/API)
                news_list = await self._fetch_news()
                
                # 更新滚动条
                ticker_text = " | ".join(news_list)
                with open(self.config.ticker_file, "w", encoding='utf-8') as f:
                    f.write(ticker_text)
                
                # 生成主播脚本 (这里模拟，实际可调用 LLM API)
                script = await self._generate_script(news_list)
                with open(self.config.script_file, "w", encoding='utf-8') as f:
                    f.write(script)
                
                update_count += 1
                self._update_status("running", content_updates=update_count)
                
                self.logger.info(f"✅ 内容已更新 (第 {update_count} 次)")
                self.logger.info(f"   主播: {script[:50]}...")
                self.logger.info(f"   滚动条: {ticker_text[:50]}...")
                
                # 等待下次更新
                await asyncio.sleep(self.config.content_update_interval)
                
            except asyncio.CancelledError:
                self.logger.info("内容生产者收到取消信号")
                break
            except Exception as e:
                self.logger.error(f"内容生产出错: {e}")
                await asyncio.sleep(5)  # 出错后短暂等待重试
    
    async def _fetch_news(self) -> list:
        """
        获取新闻列表
        
        实际项目中可替换为:
        - RSS 订阅抓取
        - 新闻 API 调用
        - 数据库查询
        """
        # 模拟新闻数据
        news_pool = [
            "全球首个AI导演正式上岗，颠覆传统影视制作",
            "低配服务器跑出100帧奇迹，技术突破引关注",
            "赛博搬砖人平均睡眠增加1小时，工作效率翻倍",
            "虚拟主播市场突破百亿，真人主播面临转型",
            "AI生成视频质量超越实拍，影视行业迎来变革",
            "云计算成本降低90%，中小企业数字化转型加速",
            "开源模型性能首超闭源，AI生态格局重塑",
            "元宇宙应用落地加速，虚拟地产交易火爆",
            "智能客服解决率达95%，人工客服将成历史",
            "代码自动生成工具普及，程序员角色重新定义",
        ]
        
        # 随机选择3-5条新闻
        count = random.randint(3, 5)
        return random.sample(news_pool, min(count, len(news_pool)))
    
    async def _generate_script(self, news_list: list) -> str:
        """
        生成主播播报脚本
        
        实际项目中可替换为:
        - 调用 LLM API (如 OpenAI/Claude)
        - 调用本地大模型
        - 使用模板引擎
        """
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        
        # 简单模板生成
        script = f"📅 北京时间 {time_str} | "
        
        if news_list:
            headline = news_list[0]
            script += f"今日头条：{headline}"
            
            if len(news_list) > 1:
                script += f" | 更多新闻请关注底部滚动条"
        else:
            script += "暂无最新消息，请稍候..."
        
        return script
    
    async def ffmpeg_monitor(self):
        """
        FFmpeg 进程监控协程
        
        监控推流进程状态，异常时自动重启
        """
        restart_count = 0
        
        while self.running:
            try:
                if self.ffmpeg_process is None:
                    self.ffmpeg_process = self.start_ffmpeg_process()
                    restart_count += 1
                    self.logger.info(f"✅ FFmpeg 进程已启动 (重启次数: {restart_count})")
                
                elif self.ffmpeg_process.poll() is not None:
                    # 进程意外退出
                    self.logger.warning(f"⚠️ FFmpeg 进程意外退出 (返回码: {self.ffmpeg_process.returncode})")
                    
                    # 读取错误信息
                    stderr = self.ffmpeg_process.stderr
                    if stderr:
                        error_output = stderr.read().decode('utf-8', errors='ignore')
                        if error_output:
                            self.logger.error(f"FFmpeg 错误输出: {error_output[-500:]}")  # 只显示最后500字符
                    
                    # 重启进程
                    self.ffmpeg_process = self.start_ffmpeg_process()
                    restart_count += 1
                    self.logger.info(f"🔄 FFmpeg 进程已重启 (重启次数: {restart_count})")
                
                await asyncio.sleep(self.config.ffmpeg_monitor_interval)
                
            except asyncio.CancelledError:
                self.logger.info("FFmpeg 监控收到取消信号")
                break
            except Exception as e:
                self.logger.error(f"FFmpeg 监控出错: {e}")
                await asyncio.sleep(2)
    
    async def run(self):
        """
        主运行循环
        
        启动所有协程并协调运行
        """
        self.logger.info("=" * 50)
        self.logger.info("🚀 赛博电视台 导演系统 V2 启动")
        self.logger.info("=" * 50)
        
        # 显示推流地址
        rtmp_targets = []
        if self.config.rtmp_urls:
            rtmp_targets.extend(self.config.rtmp_urls)
        if self.config.rtmp_url and self.config.rtmp_url not in rtmp_targets:
            rtmp_targets.append(self.config.rtmp_url)
        
        if len(rtmp_targets) > 1:
            self.logger.info(f"📺 多推流模式: {len(rtmp_targets)} 个目标")
            for i, url in enumerate(rtmp_targets, 1):
                # 隐藏敏感信息
                display_url = url.split('?')[0] if '?' in url else url
                self.logger.info(f"   [{i}] {display_url}...")
        else:
            display_url = self.config.rtmp_url.split('?')[0] if '?' in self.config.rtmp_url else self.config.rtmp_url
            self.logger.info(f"📺 推流地址: {display_url}...")
        
        self.logger.info(f"🎥 背景视频: {self.config.bg_video}")
        self.logger.info(f"🔤 字体文件: {self.font_path}")
        self.logger.info(f"⏱️ 内容更新间隔: {self.config.content_update_interval}秒")
        
        # 设置信号处理
        def signal_handler(signum, frame):
            self.logger.info(f"收到信号 {signum}，准备退出...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # 启动多个协程
            tasks = [
                asyncio.create_task(self.content_producer(), name="content_producer"),
                asyncio.create_task(self.ffmpeg_monitor(), name="ffmpeg_monitor"),
            ]
            
            # 等待所有任务完成
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"主循环异常: {e}")
        finally:
            self.logger.info("🛑 正在关闭系统...")
            self.running = False
            self.stop_ffmpeg_process()
            self._update_status("stopped")
            self.logger.info("👋 导演下班了，再见！")


def main():
    """主入口"""
    # 创建配置
    config = Config()
    
    # 从环境变量覆盖配置
    if os.environ.get("RTMP_URL"):
        config.rtmp_url = os.environ.get("RTMP_URL")
    
    # 解析多推流地址 (JSON 格式)
    if os.environ.get("RTMP_URLS"):
        try:
            import json
            rtmp_urls = json.loads(os.environ.get("RTMP_URLS"))
            if isinstance(rtmp_urls, list):
                config.rtmp_urls = rtmp_urls
                print(f"📋 加载了 {len(rtmp_urls)} 个推流地址")
        except json.JSONDecodeError as e:
            print(f"⚠️ 解析 RTMP_URLS 失败: {e}")
    
    if os.environ.get("VIDEO_BITRATE"):
        config.video_bitrate = os.environ.get("VIDEO_BITRATE")
    
    if os.environ.get("UPDATE_INTERVAL"):
        config.content_update_interval = int(os.environ.get("UPDATE_INTERVAL"))
    
    if os.environ.get("SAVE_TEST"):
        config.save_local_test = True
    
    # 创建导演实例
    director = CyberDirector(config)
    
    # 运行
    try:
        asyncio.run(director.run())
    except KeyboardInterrupt:
        print("\n用户中断")


if __name__ == "__main__":
    main()
