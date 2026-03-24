#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时新闻抓取模块 V2
==================
功能：
- 搜索最新热点新闻
- 获取完整新闻内容（使用web-reader）
- 格式化用于TTS播报
"""

import asyncio
import logging
import json
import re
import subprocess
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsItem:
    """新闻条目"""
    title: str
    content: str
    source: str
    url: str
    category: str
    timestamp: str
    
    def to_tts_text(self, max_length: int = 200) -> str:
        """转换为TTS播报文本"""
        clean_title = self._clean_text(self.title)
        clean_content = self._clean_text(self.content)
        
        # 组合标题和内容
        text = f"{clean_title}。{clean_content}"
        
        # 限制长度
        if len(text) > max_length:
            # 找到最后一个句号
            text = text[:max_length]
            last_period = max(text.rfind('。'), text.rfind('！'), text.rfind('？'), text.rfind('.'))
            if last_period > max_length * 0.5:
                text = text[:last_period + 1]
            else:
                text = text + "。"
        
        return text
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""
        # 移除URL
        text = re.sub(r'https?://\S+', '', text)
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊字符
        text = re.sub(r'[【】\[\]「」『』|│]', '', text)
        # 移除播放列表、订阅等无关内容
        text = re.sub(r'(播放列表|订阅|关注|分享|点赞|评论).*', '', text)
        return text.strip()


class NewsFetcher:
    """新闻抓取器"""
    
    # 新闻分类关键词
    CATEGORIES = {
        "科技": ["AI", "人工智能", "科技", "芯片", "互联网", "数码", "手机", "电脑", "软件", "GPT", "大模型"],
        "财经": ["股市", "经济", "金融", "投资", "股票", "基金", "财经", "银行", "汇率"],
        "国际": ["国际", "美国", "欧洲", "日本", "韩国", "全球", "世界", "联合国"],
        "社会": ["社会", "民生", "教育", "医疗", "交通", "天气", "疫情"],
    }
    
    # 搜索话题
    SEARCH_TOPICS = [
        "今日热点新闻",
        "最新科技新闻",
        "AI人工智能最新消息",
    ]
    
    def __init__(self):
        self.logger = logging.getLogger("NewsFetcher")
        self._cache: List[NewsItem] = []
        self._last_fetch_time: Optional[datetime] = None
    
    def _detect_category(self, title: str, content: str) -> str:
        """检测新闻分类"""
        text = f"{title} {content}".lower()
        for category, keywords in self.CATEGORIES.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    return category
        return "综合"
    
    def _search_web(self, query: str, num: int = 10) -> List[Dict]:
        """搜索网页"""
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
    
    def _read_page(self, url: str) -> Dict:
        """读取网页完整内容"""
        try:
            cmd = [
                "z-ai", "function",
                "-n", "page_reader",
                "-a", json.dumps({"url": url})
            ]
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )
            
            if result.returncode != 0:
                self.logger.error(f"读取页面失败: {result.stderr[:100]}")
                return {}
            
            output = result.stdout
            start_idx = output.find('{')
            if start_idx >= 0:
                # 找到完整的JSON对象
                brace_count = 0
                end_idx = start_idx
                for i, c in enumerate(output[start_idx:], start_idx):
                    if c == '{':
                        brace_count += 1
                    elif c == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break
                
                json_str = output[start_idx:end_idx]
                data = json.loads(json_str)
                
                # 提取内容
                return {
                    "title": data.get("data", {}).get("title", ""),
                    "content": data.get("data", {}).get("html", ""),
                    "text": data.get("data", {}).get("text", ""),
                    "publish_time": data.get("data", {}).get("publishedTime", "")
                }
            return {}
            
        except Exception as e:
            self.logger.error(f"读取页面异常: {e}")
            return {}
    
    def _html_to_text(self, html: str) -> str:
        """HTML转纯文本"""
        if not html:
            return ""
        # 移除script和style
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL|re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL|re.IGNORECASE)
        # 换行
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</p>', '\n', html, flags=re.IGNORECASE)
        # 移除所有标签
        html = re.sub(r'<[^>]+>', '', html)
        # HTML实体
        html = html.replace('&nbsp;', ' ')
        html = html.replace('&amp;', '&')
        html = html.replace('&lt;', '<')
        html = html.replace('&gt;', '>')
        html = html.replace('&quot;', '"')
        # 清理
        html = re.sub(r'\n+', '\n', html)
        html = re.sub(r' +', ' ', html)
        return html.strip()
    
    async def fetch_hot_news(self, max_items: int = 10) -> List[NewsItem]:
        """抓取热点新闻（包含完整内容）"""
        all_results = []
        
        # 搜索新闻
        for topic in self.SEARCH_TOPICS[:2]:
            results = self._search_web(topic, num=5)
            all_results.extend(results)
            await asyncio.sleep(0.3)
        
        # 去重
        seen_urls = set()
        seen_titles = set()
        news_items = []
        
        for item in all_results:
            url = item.get("url", "")
            title = item.get("name", "").strip()
            
            # 过滤
            if not url or url in seen_urls:
                continue
            if not title or title in seen_titles:
                continue
            if len(title) < 10:  # 过滤太短的标题
                continue
            # 过滤视频平台
            if any(x in url for x in ['youtube.com', 'bilibili.com', 'douyin.com']):
                continue
            
            seen_urls.add(url)
            seen_titles.add(title)
            
            # 尝试获取完整内容
            self.logger.info(f"📖 读取: {title[:30]}...")
            page_data = self._read_page(url)
            
            if page_data:
                # 使用完整内容
                content = self._html_to_text(page_data.get("content", ""))
                if not content:
                    content = page_data.get("text", item.get("snippet", ""))
                full_title = page_data.get("title", title)
            else:
                # 使用搜索结果摘要
                content = item.get("snippet", "")
                full_title = title
            
            # 检测分类
            category = self._detect_category(full_title, content)
            
            news = NewsItem(
                title=full_title,
                content=content,
                source=item.get("host_name", ""),
                url=url,
                category=category,
                timestamp=page_data.get("publish_time", "") or item.get("date", "")
            )
            news_items.append(news)
            
            self.logger.info(f"   ✅ [{category}] {full_title[:40]}...")
            
            if len(news_items) >= max_items:
                break
            
            await asyncio.sleep(0.5)  # 避免请求过快
        
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
    
    def format_for_ticker(self, news_items: List[NewsItem], max_items: int = 5) -> str:
        """格式化为滚动条"""
        titles = [item.title[:30] for item in news_items[:max_items]]
        return " | ".join(titles)


# =====================================================
# 测试脚本
# =====================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    async def test():
        print("=" * 60)
        print("📰 实时新闻抓取测试")
        print("=" * 60)
        
        fetcher = NewsFetcher()
        news = await fetcher.fetch_hot_news(3)
        
        print(f"\n获取到 {len(news)} 条新闻:\n")
        
        for i, item in enumerate(news, 1):
            print(f"{i}. [{item.category}] {item.title}")
            print(f"   来源: {item.source}")
            print(f"   内容: {item.content[:100]}...")
            print(f"   TTS文本: {item.to_tts_text(150)}")
            print()
        
        print("=" * 60)
    
    asyncio.run(test())
