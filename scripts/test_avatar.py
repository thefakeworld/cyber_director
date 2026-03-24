#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智灵视频叠加测试
测试智灵主播叠加到背景上
"""

import subprocess
import time
from pathlib import Path

def test_avatar_overlay():
    """测试智灵视频叠加"""
    project_root = Path(__file__).parent.parent
    font_path = "/usr/share/fonts/truetype/chinese/msyh.ttf"
    
    # 输入文件
    bg_image = project_root / "assets/bg_frame.png"
    avatar_video = project_root / "assets/avatar.mp4"
    bgm_file = project_root / "assets/bgm/calm_01.mp3"
    tts_file = project_root / "assets/tts/breaking_news_001.mp3"
    ticker_file = project_root / "data/ticker.txt"
    script_file = project_root / "data/script.txt"
    
    output_file = project_root / "output/avatar_test.mp4"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 检查文件存在
    if not bg_image.exists():
        print(f"❌ 背景图片不存在: {bg_image}")
        return False
    if not avatar_video.exists():
        print(f"❌ 智灵视频不存在: {avatar_video}")
        return False
    if not bgm_file.exists():
        print(f"❌ BGM不存在: {bgm_file}")
        return False
    
    # 构建FFmpeg命令
    # 智灵叠加：scale=0.3 (30%大小)，位置右下角
    cmd = [
        'ffmpeg', '-y',
        # 输入0: 背景图片
        '-loop', '1',
        '-i', str(bg_image),
        '-r', '25',
        
        # 输入1: 智灵视频（循环）
        '-stream_loop', '-1',
        '-i', str(avatar_video),
        
        # 输入2: BGM（循环）
        '-stream_loop', '-1',
        '-i', str(bgm_file),
        
        # 输入3: TTS音频
        '-i', str(tts_file),
        
        # Filter Complex
        '-filter_complex',
        f"""
        [1:v]scale=iw*0.35:ih*0.35,format=rgba[avatar];
        [0:v][avatar]overlay=W-w-30:H-h-30[base];
        [base]
        drawtext=fontfile={font_path}:textfile={script_file}:reload=1:x=50:y=H-180:fontsize=32:fontcolor=white:borderw=2:bordercolor=black@0.6,
        drawtext=fontfile={font_path}:textfile={ticker_file}:reload=1:x='W-mod(t*80\\,W+tw)':y=H-50:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.6:boxborderw=4,
        drawtext=fontfile={font_path}:text='AI ANCHOR':x=30:y=30:fontsize=24:fontcolor=cyan:borderw=1:bordercolor=black@0.5,
        drawtext=fontfile={font_path}:text='%{{localtime}}':x=W-220:y=30:fontsize=22:fontcolor=white:borderw=1:bordercolor=black@0.5[vout];
        [2:a]volume=0.3[bgm];
        [3:a]volume=1.0[tts];
        [bgm][tts]amix=inputs=2:duration=longest[aout]
        """,
        
        # 映射
        '-map', '[vout]',
        '-map', '[aout]',
        
        # 视频编码
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-tune', 'zerolatency',
        '-b:v', '1500k',
        '-pix_fmt', 'yuv420p',
        
        # 音频编码
        '-c:a', 'aac',
        '-b:a', '128k',
        
        # 输出时长
        '-t', '30',  # 输出30秒
        
        str(output_file)
    ]
    
    print("=" * 60)
    print("🎭 智灵视频叠加测试")
    print("=" * 60)
    print(f"背景: {bg_image}")
    print(f"智灵: {avatar_video}")
    print(f"BGM: {bgm_file.name}")
    print(f"TTS: {tts_file.name if tts_file.exists() else '无'}")
    print(f"输出: {output_file}")
    print()
    
    print("⏳ 正在生成测试视频 (30秒)...")
    start_time = time.time()
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    
    if result.returncode != 0:
        print(f"❌ 生成失败")
        print(f"错误: {result.stderr[-2000:]}")
        return False
    
    elapsed = time.time() - start_time
    
    if output_file.exists() and output_file.stat().st_size > 0:
        size_mb = output_file.stat().st_size / 1024 / 1024
        print(f"✅ 生成成功!")
        print(f"   文件大小: {size_mb:.2f} MB")
        print(f"   耗时: {elapsed:.1f} 秒")
        print(f"   位置: {output_file}")
        return True
    else:
        print("❌ 输出文件为空")
        return False


def test_avatar_live():
    """测试智灵直播推流（短时间）"""
    project_root = Path(__file__).parent.parent
    font_path = "/usr/share/fonts/truetype/chinese/msyh.ttf"
    
    bg_image = project_root / "assets/bg_frame.png"
    avatar_video = project_root / "assets/avatar.mp4"
    bgm_file = project_root / "assets/bgm/calm_01.mp3"
    ticker_file = project_root / "data/ticker.txt"
    script_file = project_root / "data/script.txt"
    
    # 使用测试推流地址
    rtmp_url = "rtmp://test.example.com/live/test"
    
    cmd = [
        'ffmpeg', '-y', '-re',
        '-loop', '1', '-i', str(bg_image), '-r', '25',
        '-stream_loop', '-1', '-i', str(avatar_video),
        '-stream_loop', '-1', '-i', str(bgm_file),
        
        '-filter_complex',
        f"""
        [1:v]scale=iw*0.35:ih*0.35,format=rgba[avatar];
        [0:v][avatar]overlay=W-w-30:H-h-30[vout];
        [2:a]volume=0.3[aout]
        """,
        
        '-map', '[vout]',
        '-map', '[aout]',
        
        '-c:v', 'libx264', '-preset', 'ultrafast',
        '-c:a', 'aac', '-b:a', '128k',
        '-t', '5',  # 只推5秒
        '-f', 'flv', rtmp_url
    ]
    
    print("\n测试直播命令:")
    print(" ".join(cmd[:15]) + " ...")
    
    return cmd


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("智灵视频叠加测试套件")
    print("=" * 60)
    
    # 测试1: 生成本地测试视频
    success = test_avatar_overlay()
    
    if success:
        print("\n✅ 智灵视频叠加功能正常!")
        print("   可以集成到直播系统中")
    else:
        print("\n❌ 智灵视频叠加测试失败")
        print("   请检查FFmpeg滤镜配置")
