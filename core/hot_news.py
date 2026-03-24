#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热插拔新闻系统
===============
功能：
- 支持随时插入突发新闻
- 不中断直播流
- 智灵主播形象叠加
- TTS与视频同步
"""

import json
import time
import threading
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from queue import Queue, PriorityQueue
import hashlib


@dataclass(order=True)
class NewsItem:
    """新闻条目"""
    priority: int  # 优先级（越小越优先）
    text: str = field(compare=False)
    title: str = field(compare=False, default="")
    source: str = field(compare=False, default="")
    category: str = field(compare=False, default="突发")
    created_at: datetime = field(compare=False, default_factory=datetime.now)
    audio_path: Optional[Path] = field(compare=False, default=None)
    is_breaking: bool = field(compare=False, default=False)
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "text": self.text,
            "source": self.source,
            "category": self.category,
            "priority": self.priority,
            "is_breaking": self.is_breaking,
            "audio_path": str(self.audio_path) if self.audio_path else None,
            "created_at": self.created_at.isoformat()
        }


class HotNewsManager:
    """
    热插拔新闻管理器
    
    特点：
    1. 优先级队列 - 突发新闻优先播放
    2. 热插拔 - 可随时添加新闻，不中断直播
    3. TTS预生成 - 提前生成音频，减少延迟
    """
    
    # 优先级定义
    PRIORITY_BREAKING = 0      # 突发新闻（最高优先）
    PRIORITY_URGENT = 1        # 紧急新闻
    PRIORITY_NORMAL = 5        # 普通新闻
    PRIORITY_SCHEDULED = 10    # 定时新闻
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.logger = logging.getLogger("HotNewsManager")
        
        # 新闻队列（优先级队列）
        self.news_queue: PriorityQueue = PriorityQueue()
        
        # 当前播放状态
        self.current_news: Optional[NewsItem] = None
        self.is_playing: bool = False
        self.play_start_time: Optional[float] = None
        
        # 智灵视频配置
        self.avatar_video: Optional[Path] = None
        self.avatar_enabled: bool = True
        
        # TTS配置
        self.tts_output_dir: Path = Path("assets/tts")
        self.tts_voice: str = "tongtong"
        self.tts_speed: float = 1.0
        
        # 播放列表文件
        self.playlist_file: Optional[Path] = None
        self.state_file: Optional[Path] = None
        
        # 回调函数
        self.on_news_start = None  # 新闻开始播放回调
        self.on_news_end = None    # 新闻结束播放回调
        
        # 线程控制
        self._running: bool = False
        self._worker_thread: Optional[threading.Thread] = None
    
    def set_output_dir(self, output_dir: Path):
        """设置输出目录"""
        self.tts_output_dir = output_dir
        self.tts_output_dir.mkdir(parents=True, exist_ok=True)
        self.playlist_file = output_dir / "tts_playlist.txt"
        self.state_file = output_dir / "news_state.json"
    
    def set_avatar(self, video_path: Path):
        """设置智灵主播视频"""
        if video_path.exists():
            self.avatar_video = video_path
            self.logger.info(f"🎭 智灵主播已设置: {video_path}")
        else:
            self.logger.warning(f"智灵视频不存在: {video_path}")
    
    def add_breaking_news(self, text: str, title: str = "", source: str = "") -> NewsItem:
        """
        添加突发新闻（最高优先级）
        
        立即中断当前播放，优先播报
        """
        news = NewsItem(
            priority=self.PRIORITY_BREAKING,
            text=text,
            title=title or "突发新闻",
            source=source,
            category="突发",
            is_breaking=True
        )
        
        # 预生成TTS
        self._generate_tts(news)
        
        # 加入队列（高优先级）
        self.news_queue.put(news)
        
        self.logger.info(f"🚨 突发新闻入队: {title or text[:30]}...")
        
        # 触发立即播放（如果当前没有播放）
        if not self.is_playing:
            self._trigger_play()
        
        return news
    
    def add_news(self, text: str, title: str = "", source: str = "", 
                 category: str = "综合", priority: int = None) -> NewsItem:
        """添加普通新闻"""
        news = NewsItem(
            priority=priority or self.PRIORITY_NORMAL,
            text=text,
            title=title,
            source=source,
            category=category
        )
        
        # 预生成TTS
        self._generate_tts(news)
        
        self.news_queue.put(news)
        self.logger.info(f"📰 新闻入队 [{category}]: {title or text[:30]}...")
        
        return news
    
    def _generate_tts(self, news: NewsItem) -> bool:
        """生成TTS音频"""
        try:
            timestamp = int(time.time())
            cache_key = hashlib.md5(news.text.encode()).hexdigest()[:8]
            output_file = self.tts_output_dir / f"news_{timestamp}_{cache_key}.mp3"
            
            # 使用CLI生成TTS
            cmd = [
                "z-ai", "tts",
                "-i", news.text,
                "-o", str(output_file).replace('.mp3', '.wav'),
                "-v", self.tts_voice,
                "-s", str(self.tts_speed)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                wav_file = str(output_file).replace('.mp3', '.wav')
                # 转换为mp3
                subprocess.run([
                    "ffmpeg", "-y", "-i", wav_file,
                    "-c:a", "libmp3lame", "-b:a", "128k",
                    str(output_file)
                ], capture_output=True, timeout=30)
                
                # 删除临时wav
                Path(wav_file).unlink(missing_ok=True)
                
                if output_file.exists():
                    news.audio_path = output_file
                    self.logger.info(f"✅ TTS生成: {output_file.name}")
                    return True
            
            self.logger.error(f"TTS生成失败: {result.stderr}")
            return False
            
        except Exception as e:
            self.logger.error(f"TTS生成异常: {e}")
            return False
    
    def get_next_news(self) -> Optional[NewsItem]:
        """获取下一条新闻（按优先级）"""
        try:
            return self.news_queue.get_nowait()
        except:
            return None
    
    def get_playlist(self) -> List[Path]:
        """获取播放列表"""
        playlist = []
        temp_queue = []
        
        # 取出所有新闻
        while not self.news_queue.empty():
            try:
                news = self.news_queue.get_nowait()
                temp_queue.append(news)
                if news.audio_path and news.audio_path.exists():
                    playlist.append(news.audio_path)
            except:
                break
        
        # 放回队列
        for news in temp_queue:
            self.news_queue.put(news)
        
        return playlist
    
    def update_playlist_file(self):
        """更新播放列表文件"""
        if not self.playlist_file:
            return
        
        playlist = self.get_playlist()
        
        with open(self.playlist_file, 'w') as f:
            for audio_path in playlist:
                f.write(f"file '{audio_path}'\n")
        
        self.logger.debug(f"播放列表更新: {len(playlist)} 条")
    
    def get_audio_duration(self, audio_path: Path) -> float:
        """获取音频时长"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-show_entries',
                'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
                str(audio_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
        except:
            return 10.0
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "queue_size": self.news_queue.qsize(),
            "is_playing": self.is_playing,
            "current_news": self.current_news.to_dict() if self.current_news else None,
            "avatar_enabled": self.avatar_enabled,
            "avatar_video": str(self.avatar_video) if self.avatar_video else None
        }
    
    def save_state(self):
        """保存状态"""
        if self.state_file:
            state = {
                "queue_size": self.news_queue.qsize(),
                "updated_at": datetime.now().isoformat()
            }
            self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    
    def clear_queue(self):
        """清空队列"""
        while not self.news_queue.empty():
            try:
                self.news_queue.get_nowait()
            except:
                break
        self.logger.info("新闻队列已清空")
    
    def _trigger_play(self):
        """触发播放（内部方法）"""
        # 这个方法会被外部调用，通知有新新闻需要播放
        pass


# =====================================================
# 智灵视频叠加滤镜生成器
# =====================================================
class AvatarOverlayBuilder:
    """
    智灵视频叠加构建器
    
    功能：
    1. 在背景上叠加智灵视频
    2. 支持位置调整
    3. 支持循环播放
    4. 静音处理
    """
    
    # 默认位置（右下角）
    POSITION_RIGHT_BOTTOM = "main_w-overlay_w-50:main_h-overlay_h-50"
    POSITION_RIGHT_TOP = "main_w-overlay_w-50:50"
    POSITION_LEFT_BOTTOM = "50:main_h-overlay_h-50"
    POSITION_LEFT_TOP = "50:50"
    POSITION_CENTER = "(main_w-overlay_w)/2:(main_h-overlay_h)/2"
    
    def __init__(self, avatar_video: Path):
        self.avatar_video = avatar_video
        self.position = self.POSITION_RIGHT_BOTTOM
        self.scale: Optional[str] = None  # 缩放比例，如 "0.5" 或 "320:480"
        self.enabled: bool = True
        self.alpha: float = 1.0  # 透明度 0-1
    
    def set_position(self, position: str):
        """设置位置"""
        self.position = position
        return self
    
    def set_scale(self, scale: str):
        """
        设置缩放
        
        scale: "0.5" 表示50%，或 "320:480" 表示指定宽高
        """
        self.scale = scale
        return self
    
    def set_alpha(self, alpha: float):
        """设置透明度"""
        self.alpha = max(0.0, min(1.0, alpha))
        return self
    
    def build_filter(self) -> str:
        """
        构建FFmpeg overlay滤镜
        
        返回完整的filter_complex字符串
        """
        if not self.enabled or not self.avatar_video.exists():
            return ""
        
        filters = []
        
        # 1. 循环智灵视频
        filters.append(
            f"movie={self.avatar_video},loop=0:-1:0,setpts=PTS-STARTPTS[avatar]"
        )
        
        # 2. 缩放（如果需要）
        if self.scale:
            if ':' in self.scale:
                # 指定宽高
                filters.append(
                    f"[avatar]scale={self.scale}[avatar_scaled]"
                )
            else:
                # 按比例
                filters.append(
                    f"[avatar]scale=iw*{self.scale}:ih*{self.scale}[avatar_scaled]"
                )
            avatar_source = "[avatar_scaled]"
        else:
            avatar_source = "[avatar]"
        
        # 3. 透明度处理
        if self.alpha < 1.0:
            filters.append(
                f"{avatar_source}format=rgba,colorchannelmixer=aa={self.alpha}[avatar_final]"
            )
            avatar_source = "[avatar_final]"
        
        # 4. 叠加到主视频
        filters.append(
            f"[base]{avatar_source}overlay={self.position}[out]"
        )
        
        return ";".join(filters)
    
    def build_input_args(self) -> List[str]:
        """构建输入参数"""
        return []


# =====================================================
# 测试代码
# =====================================================
if __name__ == "__main__":
    print("=" * 60)
    print("热插拔新闻系统测试")
    print("=" * 60)
    
    manager = HotNewsManager()
    manager.set_output_dir(Path("/home/z/my-project/cyber_director/assets/tts"))
    
    # 测试添加突发新闻
    print("\n🚨 测试突发新闻:")
    news = manager.add_breaking_news(
        text="【突发】张雪峰心脏骤停抢救中，多方消息待官方确认",
        title="张雪峰突发心脏骤停",
        source="网络综合"
    )
    print(f"  优先级: {news.priority}")
    print(f"  音频: {news.audio_path}")
    
    # 测试状态
    print("\n📊 状态:")
    status = manager.get_status()
    for k, v in status.items():
        print(f"  {k}: {v}")
    
    print("\n" + "=" * 60)
