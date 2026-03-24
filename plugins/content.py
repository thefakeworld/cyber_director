#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容生成插件 V3
===============
功能：
- 实时抓取热点新闻
- 与节目文稿系统集成
- 根据时间自动切换主题
- 智能内容生成用于TTS播报
"""

import random
import logging
import asyncio
import json
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.plugin_base import PluginBase, Event, EventType
from core.script_manager import ScriptManager


@dataclass
class NewsItem:
    """新闻条目"""
    title: str
    content: str
    source: str
    url: str
    category: str
    timestamp: str
    
    def to_tts_text(self) -> str:
        """转换为TTS播报文本"""
        clean_content = self._clean_for_tts(self.content)
        return f"{self.title}。{clean_content}"
    
    def _clean_for_tts(self, text: str) -> str:
        """清理文本用于TTS"""
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除CSS样式
        text = re.sub(r'\.[a-z]+\{[^}]*\}', '', text)
        # 移除URL
        text = re.sub(r'https?://\S+', '', text)
        # 移除特殊字符
        text = re.sub(r'[【】\[\]「」『』{}()|\\]', '', text)
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 限制长度
        if len(text) > 150:
            text = text[:150]
            last_period = max(text.rfind('。'), text.rfind('.'))
            if last_period > 50:
                text = text[:last_period + 1]
            else:
                text = text + "。"
        return text.strip()


class NewsFetcher:
    """新闻抓取器"""
    
    CATEGORIES = {
        "科技": ["AI", "人工智能", "科技", "芯片", "互联网", "数码"],
        "财经": ["股市", "经济", "金融", "投资", "股票"],
        "社会": ["社会", "民生", "教育", "医疗"],
        "国际": ["国际", "美国", "欧洲", "全球"],
    }
    
    SEARCH_TOPICS = [
        "今日热点新闻",
        "最新科技新闻",
        "AI人工智能最新动态",
        "财经要闻今日"
    ]
    
    def __init__(self):
        self.logger = logging.getLogger("NewsFetcher")
        self._cache: List[NewsItem] = []
        self._last_fetch_time: Optional[datetime] = None
    
    def _detect_category(self, title: str, snippet: str) -> str:
        text = f"{title} {snippet}".lower()
        for category, keywords in self.CATEGORIES.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    return category
        return "综合"
    
    async def search_news(self, query: str, num: int = 10) -> List[Dict]:
        """搜索新闻"""
        try:
            cmd = [
                "z-ai", "function",
                "-n", "web_search",
                "-a", json.dumps({"query": query, "num": num})
            ]
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                self.logger.error(f"搜索失败: {result.stderr}")
                return []
            
            output = result.stdout
            start_idx = output.find('[')
            end_idx = output.rfind(']') + 1
            if start_idx >= 0 and end_idx > start_idx:
                return json.loads(output[start_idx:end_idx])
            return []
            
        except Exception as e:
            self.logger.error(f"搜索异常: {e}")
            return []
    
    async def fetch_hot_news(self, max_items: int = 10) -> List[NewsItem]:
        """抓取热点新闻"""
        all_results = []
        
        for topic in self.SEARCH_TOPICS[:2]:
            results = await self.search_news(topic, num=5)
            all_results.extend(results)
            await asyncio.sleep(0.3)
        
        seen_titles = set()
        news_items = []
        
        for item in all_results:
            title = item.get("name", "").strip()
            if not title or title in seen_titles:
                continue
            if len(title) < 5:  # 过滤太短的标题
                continue
            
            seen_titles.add(title)
            
            news = NewsItem(
                title=title,
                content=item.get("snippet", ""),
                source=item.get("host_name", ""),
                url=item.get("url", ""),
                category=self._detect_category(title, item.get("snippet", "")),
                timestamp=item.get("date", "")
            )
            news_items.append(news)
            
            if len(news_items) >= max_items:
                break
        
        if news_items:
            self._cache = news_items
            self._last_fetch_time = datetime.now()
        
        self.logger.info(f"📰 获取到 {len(news_items)} 条新闻")
        return news_items
    
    def get_cached_news(self) -> List[NewsItem]:
        return self._cache
    
    def should_refresh(self, max_age_minutes: int = 30) -> bool:
        if not self._last_fetch_time:
            return True
        age = (datetime.now() - self._last_fetch_time).total_seconds() / 60
        return age > max_age_minutes


class ContentPluginV2(PluginBase):
    """内容生成插件 V2 - 实时新闻版"""
    
    name = "content"
    version = "3.0.0"
    description = "内容生成插件 - 实时新闻版"
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # 配置参数
        self.update_interval = self.config.get("update_interval", 60)
        self.ticker_file = Path(self.config.get("ticker_file", "data/ticker.txt"))
        self.script_file = Path(self.config.get("script_file", "data/script.txt"))
        self.scripts_json = Path(self.config.get("scripts_json", "data/scripts.json"))
        self.enable_real_news = self.config.get("enable_real_news", True)
        self.news_refresh_interval = self.config.get("news_refresh_interval", 30)  # 分钟
        
        # 新闻抓取器
        self.news_fetcher: Optional[NewsFetcher] = None
        
        # 文稿管理器
        self.script_manager: Optional[ScriptManager] = None
        
        # 当前新闻列表
        self.current_news: List[NewsItem] = []
        self.current_news_index: int = 0
        
        # 状态
        self._project_root: Optional[Path] = None
        self.update_count = 0
        self.auto_switch_theme = self.config.get("auto_switch_theme", True)
    
    def _resolve_path(self, relative_path: Path) -> Path:
        if relative_path.is_absolute():
            return relative_path
        return self._project_root / relative_path
    
    async def on_event(self, event: Event) -> Optional[Event]:
        """事件处理"""
        if event.type == EventType.ON_START:
            self._project_root = Path(event.data.get("project_root", "."))
            self._init_components()
            # 初始抓取新闻
            if self.enable_real_news:
                await self._refresh_news()
        
        elif event.type == EventType.ON_CONTENT_UPDATE:
            return await self._generate_content()
        
        return None
    
    def _init_components(self):
        """初始化组件"""
        # 初始化内容文件
        ticker_path = self._resolve_path(self.ticker_file)
        script_path = self._resolve_path(self.script_file)
        ticker_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not ticker_path.exists():
            ticker_path.write_text("AI主播台 正在加载最新资讯...", encoding='utf-8')
        
        # 初始化新闻抓取器
        if self.enable_real_news:
            self.news_fetcher = NewsFetcher()
            self.logger.info("✅ 实时新闻抓取器已启用")
        
        # 初始化文稿管理器
        scripts_path = self._resolve_path(self.scripts_json)
        self.script_manager = ScriptManager()
        
        if scripts_path.exists():
            if self.script_manager.load(scripts_path):
                self.logger.info(f"✅ 文稿系统加载成功")
                
                if self.auto_switch_theme:
                    theme = self.script_manager.get_theme_by_time()
                    if theme:
                        self.script_manager.set_theme(theme.id)
                        self.logger.info(f"   当前主题: {theme.name}")
        
        self.logger.info("✅ 内容插件初始化完成")
    
    async def _refresh_news(self):
        """刷新新闻"""
        if not self.news_fetcher:
            return
        
        self.logger.info("📡 正在抓取最新新闻...")
        
        try:
            self.current_news = await self.news_fetcher.fetch_hot_news(10)
            self.current_news_index = 0
            
            if self.current_news:
                self.logger.info(f"✅ 获取 {len(self.current_news)} 条新闻")
        except Exception as e:
            self.logger.error(f"新闻抓取失败: {e}")
    
    async def _generate_content(self) -> Event:
        """生成内容"""
        # 检查是否需要刷新新闻
        if self.enable_real_news and self.news_fetcher:
            if self.news_fetcher.should_refresh(self.news_refresh_interval):
                await self._refresh_news()
        
        # 获取新闻内容
        if self.current_news:
            news = self._get_next_news()
            text = news.to_tts_text()
            category = news.category
            source = news.source
        else:
            # 回退到模拟内容
            text = self._get_fallback_text()
            category = "综合"
            source = "AI主播台"
        
        # 更新滚动条
        ticker_content = self._build_ticker()
        ticker_path = self._resolve_path(self.ticker_file)
        ticker_path.write_text(ticker_content, encoding='utf-8')
        
        # 更新主播台词
        now = datetime.now().strftime("%H:%M")
        script_content = f"[{now}] {text}"
        script_path = self._resolve_path(self.script_file)
        script_path.write_text(script_content, encoding='utf-8')
        
        self.update_count += 1
        self.logger.info(f"📝 内容更新 #{self.update_count} [{category}] {text[:40]}...")
        
        # 获取播报风格
        style = self._get_broadcast_style()
        
        return Event(
            EventType.ON_NEWS_GENERATED,
            {
                "text": text,
                "style": style,
                "ticker": ticker_content,
                "category": category,
                "source": source,
                "theme": self.script_manager.current_theme.name if self.script_manager and self.script_manager.current_theme else "默认"
            },
            source=self.name
        )
    
    def _get_next_news(self) -> NewsItem:
        """获取下一条新闻"""
        if not self.current_news:
            return NewsItem(
                title="AI主播台",
                content="正在为您播报最新资讯",
                source="AI主播台",
                url="",
                category="综合",
                timestamp=""
            )
        
        news = self.current_news[self.current_news_index]
        self.current_news_index = (self.current_news_index + 1) % len(self.current_news)
        return news
    
    def _build_ticker(self) -> str:
        """构建滚动条内容"""
        if self.current_news:
            titles = [n.title for n in self.current_news[:5]]
            return " | ".join(titles)
        return "AI主播台 持续为您播报最新资讯"
    
    def _get_broadcast_style(self) -> str:
        """获取播报风格"""
        if self.script_manager and self.script_manager.current_theme:
            theme_id = self.script_manager.current_theme.id
            style_map = {
                "tech_news": "news",
                "morning_news": "morning",
                "evening_news": "evening",
                "finance_report": "serious",
                "entertainment": "leisure",
                "ai_knowledge": "news"
            }
            return style_map.get(theme_id, "news")
        return "news"
    
    def _get_fallback_text(self) -> str:
        """获取回退文本"""
        texts = [
            "欢迎收看AI主播台，我们正在为您整理最新资讯。",
            "AI主播台持续关注热点动态，精彩内容稍后呈现。",
            "感谢您的关注，更多新闻即将播报。",
        ]
        return random.choice(texts)
    
    def get_ffmpeg_inputs(self) -> List[Dict[str, Any]]:
        return []
    
    def get_ffmpeg_filters(self) -> List[str]:
        return []
    
    def get_current_theme_info(self) -> Dict:
        if not self.script_manager or not self.script_manager.current_theme:
            return {"name": "默认", "style": "news"}
        
        theme = self.script_manager.current_theme
        return {
            "name": theme.name,
            "style": self._get_broadcast_style(),
            "bgm": theme.bgm,
            "description": theme.description
        }
    
    def get_news_stats(self) -> Dict:
        """获取新闻统计"""
        return {
            "total_news": len(self.current_news),
            "current_index": self.current_news_index,
            "update_count": self.update_count,
            "real_news_enabled": self.enable_real_news,
            "last_fetch": self.news_fetcher._last_fetch_time.isoformat() if self.news_fetcher and self.news_fetcher._last_fetch_time else None
        }


# =====================================================
# 测试代码
# =====================================================
if __name__ == "__main__":
    print("=" * 60)
    print("内容插件V3测试 - 实时新闻版")
    print("=" * 60)
    
    config = {
        "update_interval": 60,
        "scripts_json": "data/scripts.json",
        "enable_real_news": True
    }
    
    plugin = ContentPluginV2(config)
    plugin._project_root = Path(__file__).parent.parent
    
    async def test():
        # 初始化
        plugin._init_components()
        
        # 抓取新闻
        print("\n📡 抓取新闻...")
        await plugin._refresh_news()
        
        # 显示新闻
        print(f"\n📰 新闻列表 ({len(plugin.current_news)} 条):")
        for i, news in enumerate(plugin.current_news[:5], 1):
            print(f"  {i}. [{news.category}] {news.title[:40]}...")
            print(f"     来源: {news.source}")
        
        # 生成内容
        print("\n🎤 生成播报内容:")
        event = Event(EventType.ON_CONTENT_UPDATE, {})
        result = await plugin.on_event(event)
        
        if result:
            print(f"  分类: {result.data.get('category', '未知')}")
            print(f"  风格: {result.data.get('style', '未知')}")
            print(f"  文本: {result.data.get('text', '')[:80]}...")
        
        # 统计
        print(f"\n📊 统计:")
        stats = plugin.get_news_stats()
        print(f"  新闻总数: {stats['total_news']}")
        print(f"  更新次数: {stats['update_count']}")
    
    asyncio.run(test())
    print("\n" + "=" * 60)
