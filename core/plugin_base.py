#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
插件系统核心
============
提供插件基类和事件驱动机制
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging


class EventType(Enum):
    """事件类型"""
    # 生命周期事件
    ON_START = "on_start"           # 主程序启动
    ON_STOP = "on_stop"             # 主程序停止
    ON_CONFIG_RELOAD = "on_config_reload"  # 配置重载
    
    # 内容事件
    ON_CONTENT_UPDATE = "on_content_update"  # 内容更新
    ON_NEWS_GENERATED = "on_news_generated"  # 新闻生成完成
    
    # TTS事件
    ON_TTS_REQUIRED = "on_tts_required"  # 需要TTS
    ON_TTS_READY = "on_tts_ready"        # TTS文件就绪
    
    # 流事件
    ON_STREAM_START = "on_stream_start"  # 推流开始
    ON_STREAM_ERROR = "on_stream_error"  # 推流错误
    
    # 主题事件
    ON_THEME_CHANGE = "on_theme_change"  # 主题切换


@dataclass
class Event:
    """事件对象"""
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""  # 事件来源插件名


class PluginBase(ABC):
    """
    插件基类
    ========
    所有插件必须继承此类，实现：
    - name: 插件名称
    - version: 版本号
    - on_event(): 事件处理
    """
    
    # 插件元信息
    name: str = "base_plugin"
    version: str = "1.0.0"
    description: str = "基础插件"
    
    # 依赖的其他插件
    dependencies: List[str] = []
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.logger = logging.getLogger(f"Plugin.{self.name}")
        self._event_handlers: Dict[EventType, Callable] = {}
    
    @abstractmethod
    async def on_event(self, event: Event) -> Optional[Event]:
        """
        处理事件
        返回新事件用于链式触发，返回None则不触发新事件
        """
        pass
    
    @abstractmethod
    def get_ffmpeg_inputs(self) -> List[Dict[str, Any]]:
        """
        返回此插件需要的FFmpeg输入源
        格式: [{"type": "file|lavfi", "path": "...", "options": {...}}]
        """
        return []
    
    @abstractmethod
    def get_ffmpeg_filters(self) -> List[str]:
        """
        返回此插件需要的FFmpeg滤镜
        格式: ["filter1=params", "filter2=params"]
        """
        return []
    
    def on_register(self, event_bus: 'EventBus'):
        """插件注册时调用"""
        pass
    
    def on_unregister(self):
        """插件注销时调用"""
        pass
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """订阅事件"""
        self._event_handlers[event_type] = handler
    
    async def emit(self, event: Event) -> Optional[Event]:
        """内部事件处理入口"""
        if not self.enabled:
            return None
        
        # 检查是否有专门的处理函数
        if event.type in self._event_handlers:
            return await self._event_handlers[event.type](event)
        
        # 调用通用处理
        return await self.on_event(event)


class EventBus:
    """
    事件总线
    ========
    管理插件注册和事件分发
    """
    
    def __init__(self):
        self.plugins: Dict[str, PluginBase] = {}
        self.logger = logging.getLogger("EventBus")
    
    def register(self, plugin: PluginBase) -> bool:
        """注册插件"""
        if plugin.name in self.plugins:
            self.logger.warning(f"插件 {plugin.name} 已注册，跳过")
            return False
        
        self.plugins[plugin.name] = plugin
        plugin.on_register(self)
        self.logger.info(f"✅ 插件注册: {plugin.name} v{plugin.version}")
        return True
    
    def unregister(self, plugin_name: str) -> bool:
        """注销插件"""
        if plugin_name not in self.plugins:
            return False
        
        plugin = self.plugins.pop(plugin_name)
        plugin.on_unregister()
        self.logger.info(f"🔌 插件注销: {plugin_name}")
        return True
    
    async def emit(self, event: Event) -> List[Event]:
        """
        发布事件到所有插件
        返回所有插件产生的新事件列表
        """
        new_events = []
        
        for name, plugin in self.plugins.items():
            try:
                result = await plugin.emit(event)
                if result:
                    new_events.append(result)
            except Exception as e:
                self.logger.error(f"插件 {name} 处理事件失败: {e}")
        
        return new_events
    
    async def emit_chain(self, event: Event, max_depth: int = 5) -> List[Event]:
        """
        链式发布事件（事件可以触发新事件）
        """
        all_events = [event]
        current_events = [event]
        depth = 0
        
        while current_events and depth < max_depth:
            next_events = []
            for evt in current_events:
                new_events = await self.emit(evt)
                next_events.extend(new_events)
            all_events.extend(next_events)
            current_events = next_events
            depth += 1
        
        return all_events
    
    def get_ffmpeg_inputs(self) -> List[Dict[str, Any]]:
        """收集所有插件的FFmpeg输入"""
        inputs = []
        for plugin in self.plugins.values():
            if plugin.enabled:
                inputs.extend(plugin.get_ffmpeg_inputs())
        return inputs
    
    def get_ffmpeg_filters(self) -> Dict[str, List[str]]:
        """收集所有插件的FFmpeg滤镜，按类型分组"""
        filters = {
            "video": [],
            "audio": []
        }
        for plugin in self.plugins.values():
            if plugin.enabled:
                filters["video"].extend(plugin.get_ffmpeg_filters())
        return filters


class PluginManager:
    """
    插件管理器
    ==========
    负责插件加载、配置、生命周期管理
    """
    
    def __init__(self, config: Dict[str, Any], event_bus: EventBus):
        self.config = config
        self.event_bus = event_bus
        self.logger = logging.getLogger("PluginManager")
    
    def load_plugins(self, plugin_configs: Dict[str, Dict]) -> int:
        """
        根据配置加载插件
        返回成功加载的数量
        """
        # 这里用延迟导入避免循环依赖
        # 实际插件在 plugins/ 目录下
        count = 0
        
        for plugin_name, plugin_config in plugin_configs.items():
            if not plugin_config.get("enabled", True):
                self.logger.info(f"插件 {plugin_name} 已禁用")
                continue
            
            plugin = self._create_plugin(plugin_name, plugin_config)
            if plugin:
                self.event_bus.register(plugin)
                count += 1
        
        return count
    
    def _create_plugin(self, name: str, config: Dict) -> Optional[PluginBase]:
        """创建插件实例"""
        # 插件工厂方法
        try:
            if name == "bgm":
                from plugins.bgm import BGMPlugin
                return BGMPlugin(config)
            elif name == "tts":
                from plugins.tts import TTSPlugin
                return TTSPlugin(config)
            elif name == "content":
                from plugins.content import ContentPlugin
                return ContentPlugin(config)
            else:
                self.logger.warning(f"未知插件: {name}")
                return None
        except ImportError as e:
            self.logger.error(f"加载插件 {name} 失败: {e}")
            return None


# =====================================================
# 测试代码
# =====================================================
if __name__ == "__main__":
    print("=" * 50)
    print("插件系统测试")
    print("=" * 50)
    
    # 创建测试插件
    class TestPlugin(PluginBase):
        name = "test"
        version = "1.0.0"
        description = "测试插件"
        
        async def on_event(self, event: Event):
            print(f"[{self.name}] 收到事件: {event.type.value}")
            return None
        
        def get_ffmpeg_inputs(self):
            return []
        
        def get_ffmpeg_filters(self):
            return []
    
    # 测试事件总线
    bus = EventBus()
    plugin = TestPlugin()
    bus.register(plugin)
    
    # 发送测试事件
    import asyncio
    async def test():
        event = Event(EventType.ON_START, {"test": True})
        await bus.emit(event)
        print("✅ 事件测试通过")
    
    asyncio.run(test())
    print("=" * 50)
