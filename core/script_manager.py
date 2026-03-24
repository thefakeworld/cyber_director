#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节目文稿管理器
==============
功能：
- 加载和管理节目文稿
- 根据时间自动切换主题
- 支持多音色配置
- 提供滚动条内容
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import random


@dataclass
class ScriptItem:
    """文稿项"""
    id: str
    text: str
    duration: int  # 预估时长(秒)


@dataclass
class Theme:
    """主题配置"""
    id: str
    name: str
    description: str
    voice: str
    voice_style: str
    bgm: str
    scripts: List[ScriptItem]


class ScriptManager:
    """节目文稿管理器"""
    
    def __init__(self, script_file: Path = None):
        self.script_file = script_file
        self.logger = logging.getLogger("ScriptManager")
        
        # 数据
        self.themes: Dict[str, Theme] = {}
        self.voices: Dict[str, Dict] = {}
        self.schedule: Dict[str, Dict] = {}
        self.ticker_content: Dict[str, List[str]] = {}
        
        # 当前状态
        self.current_theme: Optional[Theme] = None
        self.current_script_index: int = 0
        
        if script_file:
            self.load(script_file)
    
    def load(self, script_file: Path) -> bool:
        """加载文稿配置文件"""
        if not script_file.exists():
            self.logger.error(f"文稿配置文件不存在: {script_file}")
            return False
        
        try:
            with open(script_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 解析主题
            for theme_id, theme_data in data.get("themes", {}).items():
                scripts = [
                    ScriptItem(
                        id=s["id"],
                        text=s["text"],
                        duration=s.get("duration", 10)
                    )
                    for s in theme_data.get("scripts", [])
                ]
                self.themes[theme_id] = Theme(
                    id=theme_id,
                    name=theme_data["name"],
                    description=theme_data.get("description", ""),
                    voice=theme_data.get("voice", "alloy"),
                    voice_style=theme_data.get("voice_style", ""),
                    bgm=theme_data.get("bgm", ""),
                    scripts=scripts
                )
            
            # 解析音色
            self.voices = data.get("voices", {})
            
            # 解析时间表
            self.schedule = data.get("schedule", {})
            
            # 解析滚动条内容
            self.ticker_content = data.get("ticker_content", {})
            
            self.logger.info(f"✅ 加载了 {len(self.themes)} 个主题, {len(self.voices)} 个音色")
            return True
            
        except Exception as e:
            self.logger.error(f"加载文稿配置失败: {e}")
            return False
    
    def get_theme_by_time(self, time_str: str = None) -> Optional[Theme]:
        """根据时间获取当前主题"""
        if time_str is None:
            time_str = datetime.now().strftime("%H:%M")
        
        # 解析时间
        hour, minute = map(int, time_str.split(":"))
        current_minutes = hour * 60 + minute
        
        # 查找匹配的时间段
        for period, config in self.schedule.items():
            time_range = config.get("time_range", "")
            if not time_range:
                continue
            
            try:
                start_str, end_str = time_range.split("-")
                start_h, start_m = map(int, start_str.split(":"))
                end_h, end_m = map(int, end_str.split(":"))
                
                start_minutes = start_h * 60 + start_m
                end_minutes = end_h * 60 + end_m
                
                # 处理跨午夜情况
                if end_minutes < start_minutes:
                    # 跨午夜 (如 22:00-06:00)
                    if current_minutes >= start_minutes or current_minutes < end_minutes:
                        theme_id = config.get("theme")
                        return self.themes.get(theme_id)
                else:
                    if start_minutes <= current_minutes < end_minutes:
                        theme_id = config.get("theme")
                        return self.themes.get(theme_id)
                        
            except Exception as e:
                self.logger.warning(f"解析时间范围失败: {time_range}, {e}")
        
        # 默认返回第一个主题
        return next(iter(self.themes.values())) if self.themes else None
    
    def set_theme(self, theme_id: str) -> bool:
        """设置当前主题"""
        if theme_id in self.themes:
            self.current_theme = self.themes[theme_id]
            self.current_script_index = 0
            self.logger.info(f"切换主题: {self.current_theme.name}")
            return True
        return False
    
    def get_next_script(self) -> Optional[ScriptItem]:
        """获取下一个文稿"""
        if not self.current_theme:
            return None
        
        scripts = self.current_theme.scripts
        if not scripts:
            return None
        
        script = scripts[self.current_script_index]
        self.current_script_index = (self.current_script_index + 1) % len(scripts)
        return script
    
    def get_current_voice(self) -> str:
        """获取当前主题的音色"""
        if self.current_theme:
            return self.current_theme.voice
        return "alloy"
    
    def get_current_bgm(self) -> str:
        """获取当前主题的BGM"""
        if self.current_theme:
            return self.current_theme.bgm
        return ""
    
    def get_ticker_content(self, count: int = 5) -> List[str]:
        """获取滚动条内容"""
        if not self.current_theme:
            return []
        
        theme_id = self.current_theme.id
        content_pool = self.ticker_content.get(theme_id, [])
        
        if not content_pool:
            # 使用默认内容
            return ["欢迎观看AI主播台", "精彩内容即将呈现"]
        
        return random.sample(content_pool, min(count, len(content_pool)))
    
    def get_all_voices(self) -> Dict[str, Dict]:
        """获取所有音色配置"""
        return self.voices
    
    def get_voice_info(self, voice_id: str) -> Dict:
        """获取音色信息"""
        return self.voices.get(voice_id, {
            "name": voice_id,
            "style": "默认",
            "gender": "未知",
            "suitable": []
        })
    
    def get_all_themes(self) -> List[Dict]:
        """获取所有主题列表"""
        return [
            {
                "id": theme.id,
                "name": theme.name,
                "description": theme.description,
                "voice": theme.voice,
                "voice_style": theme.voice_style,
                "bgm": theme.bgm,
                "script_count": len(theme.scripts)
            }
            for theme in self.themes.values()
        ]
    
    def generate_tts_text(self) -> str:
        """生成用于TTS的完整文稿"""
        script = self.get_next_script()
        if script:
            return script.text
        return ""
    
    def generate_broadcast_intro(self) -> str:
        """生成开场白"""
        if self.current_theme:
            intro_scripts = [s for s in self.current_theme.scripts if s.id == "opening"]
            if intro_scripts:
                return intro_scripts[0].text
        
        now = datetime.now().strftime("%H:%M")
        return f"现在是北京时间{now}，欢迎收看AI主播台。"


# =====================================================
# 测试代码
# =====================================================
if __name__ == "__main__":
    print("=" * 60)
    print("节目文稿管理器测试")
    print("=" * 60)
    
    script_file = Path(__file__).parent.parent / "data" / "scripts.json"
    manager = ScriptManager(script_file)
    
    print(f"\n📋 主题列表 ({len(manager.themes)} 个):")
    for theme in manager.get_all_themes():
        print(f"  • {theme['name']} - {theme['description']}")
        print(f"    音色: {theme['voice']} ({theme['voice_style']})")
        print(f"    文稿: {theme['script_count']} 段")
    
    print(f"\n🎤 音色列表 ({len(manager.voices)} 个):")
    for vid, vinfo in manager.voices.items():
        print(f"  • {vinfo['name']} ({vid}): {vinfo['style']}")
    
    # 测试时间主题
    print(f"\n⏰ 根据时间自动选择主题:")
    now = datetime.now().strftime("%H:%M")
    theme = manager.get_theme_by_time()
    if theme:
        print(f"  当前时间: {now}")
        print(f"  当前主题: {theme.name}")
        print(f"  使用音色: {theme.voice}")
        manager.set_theme(theme.id)
        
        print(f"\n📝 滚动条内容:")
        for item in manager.get_ticker_content(3):
            print(f"  • {item}")
        
        print(f"\n🎙️ TTS文稿示例:")
        for i in range(2):
            text = manager.generate_tts_text()
            print(f"  {i+1}. {text[:50]}...")
    
    print("\n" + "=" * 60)
