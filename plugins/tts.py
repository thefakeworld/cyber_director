#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS语音合成插件 V2
==================
功能：
- 中文TTS支持
- 与节目文稿联动
- 智能缓存
- 队列管理
- 多播报风格（通过语速调节）
"""

import os
import json
import asyncio
import logging
import hashlib
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from collections import deque

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.plugin_base import PluginBase, Event, EventType


@dataclass
class TTSItem:
    """TTS队列项"""
    text: str
    audio_path: Path
    style: str
    speed: float
    created_at: datetime
    status: str = "pending"


class TTSPluginV2(PluginBase):
    """TTS语音合成插件 V2"""
    
    name = "tts"
    version = "2.0.0"
    description = "TTS语音合成插件"
    
    # 可用音色（当前SDK只支持tongtong）
    DEFAULT_VOICE = "tongtong"
    
    # 播报风格配置（通过语速区分）
    BROADCAST_STYLES = {
        "news": {
            "name": "新闻播报",
            "speed": 1.0,
            "description": "标准新闻播报风格"
        },
        "morning": {
            "name": "早间播报",
            "speed": 1.1,
            "description": "轻快活泼风格"
        },
        "evening": {
            "name": "晚间播报",
            "speed": 0.95,
            "description": "稳重舒缓风格"
        },
        "leisure": {
            "name": "休闲播报",
            "speed": 1.05,
            "description": "轻松自然风格"
        },
        "serious": {
            "name": "严肃播报",
            "speed": 0.9,
            "description": "严肃正式风格"
        }
    }
    
    # 主题风格映射
    THEME_STYLE_MAP = {
        "tech_news": "news",
        "morning_news": "morning",
        "evening_news": "evening",
        "finance_report": "serious",
        "entertainment": "leisure",
        "ai_knowledge": "news"
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # 配置参数
        self.output_dir = Path(self.config.get("output_dir", "assets/tts"))
        self.default_style = self.config.get("style", "news")
        self.default_speed = self.config.get("speed", 1.0)
        self.max_queue_size = self.config.get("max_queue_size", 20)
        self.auto_play = self.config.get("auto_play", True)
        self.cache_enabled = self.config.get("cache_enabled", True)
        
        # 状态
        self.queue: deque = deque(maxlen=self.max_queue_size)
        self.current_style = self.default_style
        self._project_root: Optional[Path] = None
        
        # 统计
        self.stats = {
            "generated": 0,
            "cache_hits": 0,
            "errors": 0
        }
    
    def _resolve_output_dir(self, project_root: Path) -> Path:
        """解析输出目录"""
        if self.output_dir.is_absolute():
            return self.output_dir
        return project_root / self.output_dir
    
    def set_style(self, style: str):
        """设置播报风格"""
        if style in self.BROADCAST_STYLES:
            self.current_style = style
            info = self.BROADCAST_STYLES[style]
            self.logger.info(f"🎤 播报风格: {info['name']} (语速: {info['speed']})")
        elif style in self.THEME_STYLE_MAP:
            mapped_style = self.THEME_STYLE_MAP[style]
            self.current_style = mapped_style
            info = self.BROADCAST_STYLES[mapped_style]
            self.logger.info(f"🎤 主题风格映射: {style} -> {info['name']}")
        else:
            self.logger.warning(f"未知风格: {style}, 使用默认风格")
    
    def _get_cache_key(self, text: str, style: str) -> str:
        """生成缓存键"""
        speed = self.BROADCAST_STYLES.get(style, {}).get("speed", 1.0)
        content = f"{text}_{style}_{speed}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _find_cached_file(self, cache_key: str, output_dir: Path) -> Optional[Path]:
        """查找缓存文件"""
        for f in output_dir.glob(f"tts_*_{cache_key}.mp3"):
            return f
        return None
    
    def generate_tts(self, text: str, style: str = None) -> Optional[Path]:
        """
        生成TTS语音
        """
        if not self._project_root:
            self.logger.error("项目根目录未设置")
            return None
        
        style = style or self.current_style
        style_info = self.BROADCAST_STYLES.get(style, self.BROADCAST_STYLES["news"])
        speed = style_info["speed"]
        
        output_path = self._resolve_output_dir(self._project_root)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 检查缓存
        cache_key = self._get_cache_key(text, style)
        if self.cache_enabled:
            cached_file = self._find_cached_file(cache_key, output_path)
            if cached_file and cached_file.exists():
                self.stats["cache_hits"] += 1
                self.logger.debug(f"使用缓存: {cached_file.name}")
                return cached_file
        
        # 生成临时wav文件
        timestamp = int(time.time())
        temp_wav = output_path / f"temp_{timestamp}.wav"
        final_mp3 = output_path / f"tts_{timestamp}_{cache_key}.mp3"
        
        try:
            self.logger.info(f"🎵 生成TTS [{style_info['name']}]: {text[:30]}...")
            
            # 使用CLI调用TTS (生成wav)
            cmd = [
                "z-ai", "tts",
                "-i", text,
                "-o", str(temp_wav),
                "-v", self.DEFAULT_VOICE,
                "-s", str(speed)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                self.logger.error(f"TTS生成失败: {result.stderr}")
                self.stats["errors"] += 1
                return None
            
            # 转换为mp3 (更小的文件)
            if temp_wav.exists():
                ffmpeg_cmd = [
                    "ffmpeg", "-y", "-i", str(temp_wav),
                    "-c:a", "libmp3lame", "-b:a", "128k",
                    str(final_mp3)
                ]
                subprocess.run(ffmpeg_cmd, capture_output=True, timeout=30)
                temp_wav.unlink()  # 删除临时wav
                
                if final_mp3.exists() and final_mp3.stat().st_size > 0:
                    self.stats["generated"] += 1
                    self.logger.info(f"✅ TTS完成: {final_mp3.name}")
                    return final_mp3
            
            self.logger.error("TTS文件生成失败")
            self.stats["errors"] += 1
            return None
            
        except subprocess.TimeoutExpired:
            self.logger.error("TTS生成超时")
            self.stats["errors"] += 1
            return None
        except Exception as e:
            self.logger.error(f"TTS生成异常: {e}")
            self.stats["errors"] += 1
            return None
        finally:
            # 清理临时文件
            if temp_wav.exists():
                temp_wav.unlink()
    
    def add_to_queue(self, text: str, audio_path: Path, style: str = None):
        """添加到播放队列"""
        style_info = self.BROADCAST_STYLES.get(style or self.current_style, {})
        item = TTSItem(
            text=text,
            audio_path=audio_path,
            style=style or self.current_style,
            speed=style_info.get("speed", 1.0),
            created_at=datetime.now(),
            status="ready"
        )
        self.queue.append(item)
        self.logger.debug(f"加入队列: {text[:30]}... (队列: {len(self.queue)})")
    
    def get_playlist_file(self) -> Optional[Path]:
        """生成FFmpeg播放列表"""
        if not self.queue:
            return None
        
        if not self._project_root:
            return None
        
        output_path = self._resolve_output_dir(self._project_root)
        playlist_file = output_path / "tts_playlist.txt"
        
        with open(playlist_file, 'w') as f:
            for item in self.queue:
                if item.audio_path and item.audio_path.exists():
                    f.write(f"file '{item.audio_path}'\n")
        
        return playlist_file
    
    async def on_event(self, event: Event) -> Optional[Event]:
        """事件处理"""
        if event.type == EventType.ON_START:
            self._project_root = Path(event.data.get("project_root", "."))
            output_dir = self._resolve_output_dir(self._project_root)
            output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"✅ TTS插件初始化完成")
            self.logger.info(f"   输出目录: {output_dir}")
            self.logger.info(f"   播报风格: {self.BROADCAST_STYLES[self.current_style]['name']}")
        
        elif event.type == EventType.ON_NEWS_GENERATED:
            # 新闻生成后自动TTS
            news_text = event.data.get("text", "")
            theme_id = event.data.get("theme", "")
            
            # 根据主题选择风格
            if theme_id and theme_id in self.THEME_STYLE_MAP:
                self.set_style(theme_id)
            
            if news_text and self.auto_play:
                audio_path = self.generate_tts(news_text, self.current_style)
                if audio_path:
                    self.add_to_queue(news_text, audio_path, self.current_style)
                    return Event(
                        EventType.ON_TTS_READY,
                        {
                            "text": news_text,
                            "audio_path": str(audio_path),
                            "style": self.current_style
                        },
                        source=self.name
                    )
        
        elif event.type == EventType.ON_TTS_REQUIRED:
            # 外部请求TTS
            text = event.data.get("text", "")
            style = event.data.get("style", self.current_style)
            
            if text:
                audio_path = self.generate_tts(text, style)
                if audio_path:
                    return Event(
                        EventType.ON_TTS_READY,
                        {"text": text, "audio_path": str(audio_path), "style": style},
                        source=self.name
                    )
        
        return None
    
    def get_ffmpeg_inputs(self) -> List[Dict[str, Any]]:
        """返回FFmpeg输入配置"""
        playlist = self.get_playlist_file()
        
        if not playlist or not playlist.exists():
            return []
        
        return [{
            "type": "concat",
            "path": str(playlist),
            "label": "tts",
            "options": {"safe": 0}
        }]
    
    def get_ffmpeg_filters(self) -> List[str]:
        return []
    
    def get_audio_filter(self) -> str:
        return "volume=1.0"
    
    def clear_queue(self):
        """清空队列"""
        self.queue.clear()
        self.logger.info("TTS队列已清空")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        style_info = self.BROADCAST_STYLES.get(self.current_style, {})
        return {
            **self.stats,
            "queue_size": len(self.queue),
            "current_style": self.current_style,
            "style_name": style_info.get("name", "未知")
        }
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """清理旧文件"""
        if not self._project_root:
            return
        
        output_dir = self._resolve_output_dir(self._project_root)
        if not output_dir.exists():
            return
        
        now = time.time()
        count = 0
        
        for f in output_dir.glob("tts_*.mp3"):
            age_hours = (now - f.stat().st_mtime) / 3600
            if age_hours > max_age_hours:
                f.unlink()
                count += 1
        
        if count > 0:
            self.logger.info(f"清理了 {count} 个过期TTS文件")


# =====================================================
# 测试代码
# =====================================================
if __name__ == "__main__":
    print("=" * 60)
    print("TTS插件测试")
    print("=" * 60)
    
    plugin = TTSPluginV2({
        "output_dir": "assets/tts",
        "style": "news"
    })
    plugin._project_root = Path(__file__).parent.parent
    
    print("\n🎤 播报风格:")
    for sid, sinfo in plugin.BROADCAST_STYLES.items():
        print(f"  • {sinfo['name']} ({sid}): 语速 {sinfo['speed']}")
    
    print("\n🎵 测试TTS生成:")
    test_texts = [
        ("news", "各位观众朋友们大家好，欢迎收看今天的AI主播台科技新闻节目。"),
        ("morning", "早上好！新的一天开始了，欢迎收听AI主播台早间新闻。"),
    ]
    
    for style, text in test_texts:
        style_info = plugin.BROADCAST_STYLES[style]
        print(f"\n生成 [{style_info['name']}]: {text[:30]}...")
        result = plugin.generate_tts(text, style)
        if result:
            print(f"  ✅ 成功: {result}")
        else:
            print(f"  ❌ 失败")
    
    print(f"\n📊 统计: {plugin.get_stats()}")
    print("=" * 60)
