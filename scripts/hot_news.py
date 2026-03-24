#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热插拔新闻控制脚本
=================
功能：实时添加突发新闻，控制智灵显示
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

# 项目路径
PROJECT_ROOT = Path("/home/z/my-project/cyber_director")
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"
TTS_DIR = ASSETS_DIR / "tts"

# 控制文件
SCRIPT_FILE = DATA_DIR / "script.txt"
TICKER_FILE = DATA_DIR / "ticker.txt"
PLAYLIST_FILE = TTS_DIR / "tts_playlist.txt"


def update_script(text: str):
    """更新主字幕"""
    timestamp = datetime.now().strftime("%H:%M")
    content = f"[{timestamp}] {text}"
    SCRIPT_FILE.write_text(content, encoding='utf-8')
    print(f"📝 字幕已更新")


def update_ticker(text: str):
    """更新滚动新闻条"""
    TICKER_FILE.write_text(text, encoding='utf-8')
    print(f"📊 滚动条已更新")


def generate_tts(text: str) -> Path:
    """生成TTS音频"""
    timestamp = int(time.time())
    output_wav = TTS_DIR / f"breaking_{timestamp}.wav"
    output_mp3 = TTS_DIR / f"breaking_{timestamp}.mp3"
    
    # 使用z-ai生成TTS
    cmd = ["z-ai", "tts", "-i", text, "-o", str(output_wav), "-v", "tongtong", "-s", "1.0"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    if result.returncode != 0:
        print(f"❌ TTS生成失败")
        return None
    
    # 转换为MP3
    subprocess.run([
        "ffmpeg", "-y", "-i", str(output_wav),
        "-c:a", "libmp3lame", "-b:a", "128k", str(output_mp3)
    ], capture_output=True, timeout=30)
    
    # 清理WAV
    output_wav.unlink(missing_ok=True)
    
    if output_mp3.exists():
        print(f"✅ TTS已生成: {output_mp3.name}")
        return output_mp3
    
    return None


def add_breaking_news(title: str, content: str, source: str = ""):
    """添加突发新闻（热插拔入口）"""
    print("\n" + "=" * 50)
    print("🚨 突发新闻入队")
    print("=" * 50)
    print(f"📌 标题: {title}")
    print(f"📰 来源: {source}")
    
    # 1. 更新字幕
    full_text = f"【突发】{title}。{content}"
    update_script(full_text[:100])
    
    # 2. 更新滚动条
    update_ticker(f"【突发】{title} | {source}")
    
    # 3. 生成TTS
    tts_text = f"【突发新闻】{title}。{content}"
    audio_path = generate_tts(tts_text)
    
    # 4. 更新播放列表
    if audio_path:
        PLAYLIST_FILE.write_text(f"file '{audio_path}'\n", encoding='utf-8')
        print(f"🎵 播放列表已更新")
    
    print("=" * 50 + "\n")
    
    return {
        "title": title,
        "content": content,
        "audio_path": str(audio_path) if audio_path else None
    }


# 测试
if __name__ == "__main__":
    add_breaking_news(
        title="考研名师张雪峰心脏骤停抢救中",
        content="据多家媒体报道，3月24日中午，知名考研名师张雪峰在苏州被传心脏骤停，正在独墅湖医院ICU抢救。助理表示不清楚此事，合伙人回应暂时无可奉告。",
        source="网络综合"
    )
