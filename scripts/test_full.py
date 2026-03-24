#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整测试脚本
============
测试：
1. 新闻抓取
2. TTS生成
3. FFmpeg背景图片
"""

import asyncio
import sys
import logging
import subprocess
import json
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict

# 设置路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ==================== 新闻抓取模块 ====================

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
        clean_title = self._clean_text(self.title)
        clean_content = self._clean_text(self.content)
        text = f"{clean_title}。{clean_content}"
        if len(text) > max_length:
            text = text[:max_length]
            last_period = max(text.rfind('。'), text.rfind('.'))
            if last_period > max_length * 0.5:
                text = text[:last_period + 1]
            else:
                text = text + "。"
        return text
    
    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除CSS样式
        text = re.sub(r'\.[a-z]+\{[^}]*\}', '', text)
        # 移除URL
        text = re.sub(r'https?://\S+', '', text)
        # 移除特殊字符
        text = re.sub(r'[{}()\[\]|\\]', '', text)
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


def search_news(query: str, num: int = 10) -> List[Dict]:
    """搜索新闻"""
    try:
        cmd = [
            "z-ai", "function",
            "-n", "web_search",
            "-a", json.dumps({"query": query, "num": num})
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"  搜索失败: {result.stderr[:100]}")
            return []
        
        output = result.stdout
        start_idx = output.find('[')
        end_idx = output.rfind(']') + 1
        if start_idx >= 0 and end_idx > start_idx:
            return json.loads(output[start_idx:end_idx])
        return []
    except Exception as e:
        print(f"  搜索异常: {e}")
        return []


def read_page_content(url: str) -> Dict:
    """读取网页内容"""
    try:
        cmd = [
            "z-ai", "function",
            "-n", "page_reader",
            "-a", json.dumps({"url": url})
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            return {}
        
        output = result.stdout
        start_idx = output.find('{')
        if start_idx >= 0:
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
            
            data = json.loads(output[start_idx:end_idx])
            return {
                "title": data.get("data", {}).get("title", ""),
                "content": data.get("data", {}).get("html", ""),
                "text": data.get("data", {}).get("text", ""),
            }
        return {}
    except Exception as e:
        print(f"  读取页面异常: {e}")
        return {}


def detect_category(title: str, content: str) -> str:
    """检测新闻分类"""
    categories = {
        "科技": ["AI", "人工智能", "科技", "芯片", "互联网", "数码"],
        "财经": ["股市", "经济", "金融", "投资", "股票"],
        "国际": ["国际", "美国", "欧洲", "全球"],
    }
    text = f"{title} {content}".lower()
    for cat, keywords in categories.items():
        for kw in keywords:
            if kw.lower() in text:
                return cat
    return "综合"


def fetch_hot_news(max_items: int = 5) -> List[NewsItem]:
    """抓取热点新闻"""
    print("\n📡 正在抓取新闻...")
    
    topics = ["今日热点新闻", "最新科技新闻"]
    all_results = []
    
    for topic in topics:
        results = search_news(topic, num=5)
        all_results.extend(results)
    
    seen_urls = set()
    news_items = []
    
    for item in all_results:
        url = item.get("url", "")
        title = item.get("name", "").strip()
        
        if not url or url in seen_urls or len(title) < 10:
            continue
        if any(x in url for x in ['youtube.com', 'bilibili.com']):
            continue
        
        seen_urls.add(url)
        
        # 读取完整内容
        print(f"  📖 读取: {title[:40]}...")
        page = read_page_content(url)
        
        if page:
            content = page.get("text", "") or page.get("content", "")
            title = page.get("title") or title
        else:
            content = item.get("snippet", "")
        
        # 清理内容
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r'\s+', ' ', content)
        
        news = NewsItem(
            title=title,
            content=content[:500],
            source=item.get("host_name", ""),
            url=url,
            category=detect_category(title, content),
            timestamp=item.get("date", "")
        )
        news_items.append(news)
        
        print(f"     ✅ [{news.category}] {title[:35]}...")
        
        if len(news_items) >= max_items:
            break
    
    return news_items


# ==================== TTS模块 ====================

def generate_tts(text: str, output_path: str, style: str = "news") -> bool:
    """生成TTS音频"""
    speeds = {
        "news": 1.0,
        "morning": 1.1,
        "evening": 0.95,
    }
    speed = speeds.get(style, 1.0)
    
    try:
        cmd = [
            "z-ai", "tts",
            "-i", text,
            "-o", output_path,
            "-v", "tongtong",
            "-s", str(speed)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        return result.returncode == 0 and Path(output_path).exists()
    except Exception as e:
        print(f"  TTS异常: {e}")
        return False


# ==================== 主测试 ====================

def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("🧪 AI主播台 完整测试")
    print("=" * 60)
    
    # 1. 测试新闻抓取
    print("\n" + "-" * 40)
    print("📰 测试1: 新闻抓取")
    print("-" * 40)
    
    news_items = fetch_hot_news(3)
    
    if not news_items:
        print("❌ 未获取到新闻")
    else:
        print(f"\n✅ 获取到 {len(news_items)} 条新闻")
    
    # 2. 测试TTS
    print("\n" + "-" * 40)
    print("🎵 测试2: TTS生成")
    print("-" * 40)
    
    audio_files = []
    
    if news_items:
        for i, news in enumerate(news_items[:2], 1):
            tts_text = news.to_tts_text(150)
            output = f"/home/z/my-project/cyber_director/assets/tts/test_{i}.mp3"
            
            print(f"\n  生成 {i}: {news.title[:30]}...")
            print(f"  TTS: {tts_text[:60]}...")
            
            if generate_tts(tts_text, output):
                size = Path(output).stat().st_size / 1024
                print(f"  ✅ 成功: {Path(output).name} ({size:.1f} KB)")
                audio_files.append(output)
            else:
                print(f"  ❌ 失败")
    
    # 3. 测试背景图片
    print("\n" + "-" * 40)
    print("🖼️ 测试3: 背景图片")
    print("-" * 40)
    
    bg_image = Path("/home/z/my-project/cyber_director/assets/bg_frame.png")
    
    if bg_image.exists():
        size = bg_image.stat().st_size / 1024
        print(f"✅ 背景图片存在: {bg_image}")
        print(f"   大小: {size:.1f} KB")
    else:
        print(f"❌ 背景图片不存在")
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    print(f"  新闻数量: {len(news_items)}")
    print(f"  TTS音频: {len(audio_files)}")
    print(f"  背景图片: {'✅' if bg_image.exists() else '❌'}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
