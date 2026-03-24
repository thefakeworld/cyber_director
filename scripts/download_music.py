#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
背景音乐下载脚本
================
从免费音乐网站下载无版权音乐

使用方法:
1. 手动访问以下网站下载音乐:
   - https://pixabay.com/music (免费无版权)
   - https://www.chosic.com/free-music/all (免费无版权)
   - https://mixkit.co/free-stock-music (免费无版权)
   - https://freetouse.com/music (免费无版权)

2. 将下载的mp3文件放入 assets/bgm/ 目录

热门背景音乐风格推荐:
- Lofi Hip Hop (学习/工作背景)
- Ambient/Chillout (放松/冥想)
- Electronic/Synth (科技感)
- Acoustic/Folk (温馨氛围)
- Piano/Classical (优雅氛围)
"""

import os
import subprocess
from pathlib import Path
import random

# BGM输出目录
BGM_DIR = Path(__file__).parent.parent / "assets" / "bgm"

# 音乐风格配置
MUSIC_STYLES = [
    {
        "name": "lofi_chill",
        "description": "Lo-fi Hip Hop风格 - 适合学习工作",
        "freqs": [220, 277, 330, 440],  # A3, C#4, E4, A4
        "volume": 0.08,
        "lowpass": 2000,
        "highpass": 100,
        "reverb": True
    },
    {
        "name": "ambient_dream",
        "description": "氛围梦幻 - 适合冥想放松",
        "freqs": [261.63, 329.63, 392, 523.25],  # C4, E4, G4, C5
        "volume": 0.06,
        "lowpass": 1200,
        "highpass": 80,
        "reverb": True
    },
    {
        "name": "electronic_pulse",
        "description": "电子脉冲 - 适合科技主题",
        "freqs": [130.81, 164.81, 196, 261.63],  # C3, E3, G3, C4
        "volume": 0.07,
        "lowpass": 3000,
        "highpass": 150,
        "reverb": False
    },
    {
        "name": "piano_ambient",
        "description": "钢琴氛围 - 优雅风格",
        "freqs": [293.66, 349.23, 440, 523.25],  # D4, F4, A4, C5
        "volume": 0.05,
        "lowpass": 1500,
        "highpass": 60,
        "reverb": True
    },
    {
        "name": "deep_bass",
        "description": "深沉低音 - 适合严肃主题",
        "freqs": [65.41, 82.41, 98, 130.81],  # C2, E2, G2, C3
        "volume": 0.1,
        "lowpass": 800,
        "highpass": 40,
        "reverb": True
    },
    {
        "name": "bright_upbeat",
        "description": "明亮欢快 - 积极氛围",
        "freqs": [329.63, 392, 493.88, 659.25],  # E4, G4, B4, E5
        "volume": 0.07,
        "lowpass": 4000,
        "highpass": 200,
        "reverb": False
    },
    {
        "name": "nature_ambient",
        "description": "自然氛围 - 白噪声混合",
        "freqs": None,
        "use_noise": True,
        "volume": 0.03,
        "lowpass": 1500,
        "highpass": 200,
        "reverb": False
    },
    {
        "name": "synthwave",
        "description": "合成器波浪 - 复古未来",
        "freqs": [110, 146.83, 174.61, 220],  # A2, D3, F3, A3
        "volume": 0.08,
        "lowpass": 2500,
        "highpass": 100,
        "reverb": True
    }
]


def generate_music(style: dict, duration: int = 120, output_path: Path = None) -> Path:
    """生成指定风格的背景音乐"""
    name = style["name"]
    output_path = output_path or BGM_DIR / f"{name}.mp3"

    print(f"🎵 生成: {style['description']}")

    # 构建FFmpeg命令
    cmd = ["ffmpeg", "-y"]

    if style.get("use_noise"):
        # 白噪声风格
        cmd.extend([
            "-f", "lavfi",
            "-i", f"anoisesrc=d={duration}:c=pink:r=44100"
        ])
    else:
        # 多频率正弦波混合
        inputs = []
        for i, freq in enumerate(style["freqs"]):
            cmd.extend([
                "-f", "lavfi",
                "-i", f"sine=frequency={freq}:duration={duration}"
            ])
            inputs.append(f"[{i}:a]")

        # 构建滤镜
        filter_parts = []
        amix_input = "".join(inputs)
        filter_parts.append(f"{amix_input}amix=inputs={len(style['freqs'])}:duration=longest")

    # 添加音量和滤波
    filters = [f"volume={style['volume']}"]

    if style.get("lowpass"):
        filters.append(f"lowpass=f={style['lowpass']}")
    if style.get("highpass"):
        filters.append(f"highpass=f={style['highpass']}")

    if style.get("use_noise"):
        filter_str = ",".join(filters)
        cmd.extend(["-af", filter_str])
    else:
        filter_parts.append(",".join(filters))
        filter_str = ";".join(filter_parts)
        cmd.extend(["-filter_complex", filter_str])

    # 输出设置
    cmd.extend([
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        str(output_path)
    ])

    # 执行
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0:
        size = output_path.stat().st_size / 1024
        print(f"   ✅ 完成: {output_path.name} ({size:.0f}KB)")
        return output_path
    else:
        print(f"   ❌ 失败: {result.stderr.decode()[:100]}")
        return None


def generate_all_styles(duration: int = 120):
    """生成所有风格的音乐"""
    BGM_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("🎵 生成背景音乐库")
    print("=" * 50)
    print(f"输出目录: {BGM_DIR}")
    print(f"每首时长: {duration}秒")
    print()

    success = 0
    for style in MUSIC_STYLES:
        result = generate_music(style, duration)
        if result:
            success += 1
        print()

    print("=" * 50)
    print(f"✅ 完成: {success}/{len(MUSIC_STYLES)} 首音乐")
    print("=" * 50)


def download_from_urls(url_list: list):
    """
    从URL列表下载音乐
    需要安装 yt-dlp: pip install yt-dlp
    """
    print("📥 从网络下载音乐...")
    print("提示: 需要先安装 yt-dlp")
    print()

    try:
        import yt_dlp
    except ImportError:
        print("❌ 未安装 yt-dlp")
        print("安装命令: pip install yt-dlp")
        return

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(BGM_DIR / '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for url in url_list:
            try:
                print(f"下载: {url}")
                ydl.download([url])
                print("  ✅ 完成")
            except Exception as e:
                print(f"  ❌ 失败: {e}")


# =====================================================
# 推荐的免费音乐URL（YouTube无版权音乐频道）
# =====================================================
FREE_MUSIC_URLS = [
    # YouTube Audio Library - No Copyright Music
    # 需要手动访问下载或使用yt-dlp
]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "generate":
            duration = int(sys.argv[2]) if len(sys.argv) > 2 else 120
            generate_all_styles(duration)
        elif sys.argv[1] == "info":
            print("推荐免费音乐网站:")
            for url, desc in [
                ("https://pixabay.com/music", "Pixabay免费音乐"),
                ("https://mixkit.co/free-stock-music", "Mixkit免费音效"),
                ("https://freetouse.com/music", "FreeToUse音乐"),
                ("https://www.chosic.com/free-music/all", "Chosic免费音乐"),
                ("https://www.bensound.com/royalty-free-music", "Bensound版权音乐"),
            ]:
                print(f"  - {desc}: {url}")
    else:
        generate_all_styles(120)
