#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
背景音乐插件 (BGM Plugin)
========================
功能：
- 自动发现BGM文件
- 循环播放
- 音量控制
- 支持多种音频格式
"""

import os
import random
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.plugin_base import PluginBase, Event, EventType


class BGMPlugin(PluginBase):
    """背景音乐插件"""
    
    name = "bgm"
    version = "1.0.0"
    description = "背景音乐播放插件"
    
    # 支持的音频格式
    SUPPORTED_FORMATS = [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"]
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # 配置参数
        self.volume = self.config.get("volume", 0.3)  # 默认音量30%
        self.bgm_dir = Path(self.config.get("dir", "assets/bgm"))
        self.fade_in = self.config.get("fade_in", 2)  # 淡入秒数
        self.fade_out = self.config.get("fade_out", 2)  # 淡出秒数
        self.shuffle = self.config.get("shuffle", True)  # 随机播放
        self.current_track_name = self.config.get("current_track", None)  # 指定当前曲目
        
        # 状态
        self.playlist: List[Path] = []
        self.current_index = 0
        self._initialized = False
    
    def _resolve_bgm_dir(self, project_root: Path) -> Path:
        """解析BGM目录的绝对路径"""
        if self.bgm_dir.is_absolute():
            return self.bgm_dir
        return project_root / self.bgm_dir
    
    def discover_files(self, project_root: Path) -> List[Path]:
        """发现BGM目录下的所有音频文件"""
        bgm_path = self._resolve_bgm_dir(project_root)
        
        if not bgm_path.exists():
            self.logger.warning(f"BGM目录不存在: {bgm_path}")
            return []
        
        files = []
        for ext in self.SUPPORTED_FORMATS:
            files.extend(bgm_path.glob(f"*{ext}"))
            files.extend(bgm_path.glob(f"*{ext.upper()}"))
        
        self.logger.info(f"发现 {len(files)} 个BGM文件")
        return sorted(files)
    
    async def on_event(self, event: Event) -> Optional[Event]:
        """处理事件"""
        if event.type == EventType.ON_START:
            # 启动时发现BGM文件
            project_root = event.data.get("project_root")
            if project_root:
                self.playlist = self.discover_files(Path(project_root))
                
                # 如果指定了当前曲目，优先选择它
                if self.current_track_name and self.playlist:
                    for i, track in enumerate(self.playlist):
                        if track.name == self.current_track_name:
                            self.current_index = i
                            self.logger.info(f"指定BGM: {track.name}")
                            break
                elif self.shuffle and self.playlist:
                    random.shuffle(self.playlist)
                
                self._initialized = True
        
        return None
    
    def get_ffmpeg_inputs(self) -> List[Dict[str, Any]]:
        """
        返回BGM的FFmpeg输入配置
        使用 concat 播放列表实现无缝循环
        """
        if not self.playlist:
            return []
        
        # 选择当前索引的BGM文件
        bgm_file = self.playlist[self.current_index]
        
        self.logger.info(f"使用BGM: {bgm_file.name}")
        
        return [{
            "type": "file",
            "path": str(bgm_file),
            "label": "bgm",
            "options": {
                "stream_loop": -1,  # 无限循环
            }
        }]
    
    def get_ffmpeg_filters(self) -> List[str]:
        """返回BGM的音频滤镜"""
        return []
    
    def get_audio_filter(self) -> str:
        """
        返回音频滤镜字符串
        包括：音量控制、淡入淡出
        """
        filters = []
        
        # 音量控制
        filters.append(f"volume={self.volume}")
        
        # 淡入淡出（可选）
        if self.fade_in > 0:
            filters.append(f"afade=t=in:st=0:d={self.fade_in}")
        
        return ",".join(filters)
    
    def next_track(self) -> Optional[Path]:
        """切换到下一首"""
        if not self.playlist:
            return None
        
        self.current_index = (self.current_index + 1) % len(self.playlist)
        return self.playlist[self.current_index]
    
    def get_current_track(self) -> Optional[Path]:
        """获取当前曲目"""
        if not self.playlist:
            return None
        return self.playlist[self.current_index]


# =====================================================
# 测试代码
# =====================================================
if __name__ == "__main__":
    print("=" * 50)
    print("BGM插件测试")
    print("=" * 50)
    
    config = {
        "volume": 0.3,
        "dir": "assets/bgm"
    }
    
    plugin = BGMPlugin(config)
    plugin.logger.setLevel(logging.INFO)
    
    # 测试发现文件
    project_root = Path(__file__).parent.parent
    files = plugin.discover_files(project_root)
    
    print(f"\nBGM目录: {plugin._resolve_bgm_dir(project_root)}")
    print(f"发现文件: {len(files)}")
    for f in files[:5]:
        print(f"  - {f.name}")
    
    # 测试FFmpeg输入
    inputs = plugin.get_ffmpeg_inputs()
    print(f"\nFFmpeg输入配置:")
    for inp in inputs:
        print(f"  {inp}")
    
    print(f"\n音频滤镜: {plugin.get_audio_filter()}")
    print("=" * 50)
