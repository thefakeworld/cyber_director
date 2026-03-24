#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容生成插件 V2
===============
功能：
- 与节目文稿系统集成
- 根据时间自动切换主题
- 支持多音色联动
- 智能内容生成
"""

import random
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.plugin_base import PluginBase, Event, EventType
from core.script_manager import ScriptManager


class ContentPluginV2(PluginBase):
    """内容生成插件 V2"""
    
    name = "content"
    version = "2.0.0"
    description = "内容生成插件 - 文稿系统集成版"
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # 配置参数
        self.update_interval = self.config.get("update_interval", 60)
        self.ticker_file = Path(self.config.get("ticker_file", "data/ticker.txt"))
        self.script_file = Path(self.config.get("script_file", "data/script.txt"))
        self.scripts_json = Path(self.config.get("scripts_json", "data/scripts.json"))
        
        # 文稿管理器
        self.script_manager: Optional[ScriptManager] = None
        
        # 状态
        self._project_root: Optional[Path] = None
        self.update_count = 0
        self.auto_switch_theme = self.config.get("auto_switch_theme", True)
    
    def _resolve_path(self, relative_path: Path) -> Path:
        """解析路径"""
        if relative_path.is_absolute():
            return relative_path
        return self._project_root / relative_path
    
    async def on_event(self, event: Event) -> Optional[Event]:
        """事件处理"""
        if event.type == EventType.ON_START:
            self._project_root = Path(event.data.get("project_root", "."))
            self._init_content_files()
            self._init_script_manager()
        
        elif event.type == EventType.ON_CONTENT_UPDATE:
            return await self._generate_content()
        
        return None
    
    def _init_content_files(self):
        """初始化内容文件"""
        ticker_path = self._resolve_path(self.ticker_file)
        script_path = self._resolve_path(self.script_file)
        
        ticker_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not ticker_path.exists():
            ticker_path.write_text("欢迎观看AI主播台 | 内容加载中...", encoding='utf-8')
        
        if not script_path.exists():
            script_path.write_text("AI主播台 正在直播...", encoding='utf-8')
        
        self.logger.info("✅ 内容文件初始化完成")
    
    def _init_script_manager(self):
        """初始化文稿管理器"""
        scripts_path = self._resolve_path(self.scripts_json)
        
        self.script_manager = ScriptManager()
        
        if scripts_path.exists():
            if self.script_manager.load(scripts_path):
                self.logger.info(f"✅ 文稿系统加载成功")
                self.logger.info(f"   主题数: {len(self.script_manager.themes)}")
                self.logger.info(f"   音色数: {len(self.script_manager.voices)}")
                
                # 根据时间选择主题
                if self.auto_switch_theme:
                    theme = self.script_manager.get_theme_by_time()
                    if theme:
                        self.script_manager.set_theme(theme.id)
                        self.logger.info(f"   当前主题: {theme.name} (音色: {theme.voice})")
        else:
            self.logger.warning(f"文稿配置文件不存在: {scripts_path}")
    
    async def _generate_content(self) -> Event:
        """生成内容"""
        if not self.script_manager:
            return self._generate_default_content()
        
        # 检查是否需要切换主题
        if self.auto_switch_theme:
            current_theme = self.script_manager.get_theme_by_time()
            if current_theme and current_theme.id != self.script_manager.current_theme.id if self.script_manager.current_theme else True:
                self.script_manager.set_theme(current_theme.id)
                self.logger.info(f"🔄 自动切换主题: {current_theme.name}")
        
        # 获取下一个文稿
        script_item = self.script_manager.get_next_script()
        
        if script_item:
            text = script_item.text
            voice = self.script_manager.get_current_voice()
        else:
            text = self._generate_default_text()
            voice = "alloy"
        
        # 更新滚动条
        ticker_items = self.script_manager.get_ticker_content(5)
        ticker_content = " | ".join(ticker_items)
        ticker_path = self._resolve_path(self.ticker_file)
        ticker_path.write_text(ticker_content, encoding='utf-8')
        
        # 更新主播台词
        now = datetime.now().strftime("%H:%M")
        script_content = f"[{now}] {text}"
        script_path = self._resolve_path(self.script_file)
        script_path.write_text(script_content, encoding='utf-8')
        
        self.update_count += 1
        self.logger.info(f"📝 内容更新 #{self.update_count}")
        
        # 返回事件，触发TTS
        return Event(
            EventType.ON_NEWS_GENERATED,
            {
                "text": text,
                "voice": voice,
                "ticker": ticker_content,
                "theme": self.script_manager.current_theme.name if self.script_manager.current_theme else "默认"
            },
            source=self.name
        )
    
    def _generate_default_content(self) -> Event:
        """生成默认内容"""
        news_pool = [
            "AI技术突破：大模型推理速度提升10倍",
            "科技前沿：量子计算进入实用阶段",
            "互联网资讯：元宇宙应用加速落地",
        ]
        
        text = random.choice(news_pool)
        voice = "alloy"
        
        ticker_path = self._resolve_path(self.ticker_file)
        ticker_path.write_text(" | ".join(news_pool), encoding='utf-8')
        
        script_path = self._resolve_path(self.script_file)
        now = datetime.now().strftime("%H:%M")
        script_path.write_text(f"[{now}] {text}", encoding='utf-8')
        
        self.update_count += 1
        
        return Event(
            EventType.ON_NEWS_GENERATED,
            {"text": text, "voice": voice},
            source=self.name
        )
    
    def _generate_default_text(self) -> str:
        """生成默认文本"""
        texts = [
            "欢迎收看AI主播台，更多精彩内容即将呈现。",
            "AI主播台持续为您播报最新资讯。",
            "感谢您的关注，精彩内容稍后继续。",
        ]
        return random.choice(texts)
    
    def get_ffmpeg_inputs(self) -> List[Dict[str, Any]]:
        return []
    
    def get_ffmpeg_filters(self) -> List[str]:
        return []
    
    def get_current_theme_info(self) -> Dict:
        """获取当前主题信息"""
        if not self.script_manager or not self.script_manager.current_theme:
            return {"name": "默认", "voice": "alloy"}
        
        theme = self.script_manager.current_theme
        return {
            "name": theme.name,
            "voice": theme.voice,
            "bgm": theme.bgm,
            "description": theme.description
        }


# =====================================================
# 测试代码
# =====================================================
if __name__ == "__main__":
    print("=" * 60)
    print("内容插件V2测试")
    print("=" * 60)
    
    config = {
        "update_interval": 60,
        "scripts_json": "data/scripts.json"
    }
    
    plugin = ContentPluginV2(config)
    plugin._project_root = Path(__file__).parent.parent
    
    # 初始化
    plugin._init_content_files()
    plugin._init_script_manager()
    
    # 显示主题信息
    info = plugin.get_current_theme_info()
    print(f"\n当前主题: {info['name']}")
    print(f"使用音色: {info['voice']}")
    print(f"背景音乐: {info.get('bgm', '无')}")
    
    # 测试生成内容
    import asyncio
    
    async def test():
        event = Event(EventType.ON_CONTENT_UPDATE, {})
        result = await plugin.on_event(event)
        
        if result:
            print(f"\n生成内容:")
            print(f"  主题: {result.data.get('theme', '未知')}")
            print(f"  音色: {result.data.get('voice', '未知')}")
            print(f"  文本: {result.data.get('text', '')[:50]}...")
    
    asyncio.run(test())
    print("\n" + "=" * 60)
