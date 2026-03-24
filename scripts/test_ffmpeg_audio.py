#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFmpeg音频输入测试
检查音频索引是否正确
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ffmpeg_builder import FFmpegBuilderV2, InputSource
from plugins.bgm import BGMPlugin
from plugins.tts import TTSPluginV2


def test_ffmpeg_audio_index():
    """测试FFmpeg音频索引"""
    print("=" * 60)
    print("🔍 FFmpeg音频索引测试")
    print("=" * 60)
    
    font_path = "/usr/share/fonts/truetype/chinese/msyh.ttf"
    project_root = Path(__file__).parent.parent
    
    # 创建builder
    builder = FFmpegBuilderV2(font_path=font_path)
    
    # 设置图片背景
    bg_image = project_root / "assets/bg_frame.png"
    if bg_image.exists():
        builder.set_bg_image(bg_image)
        print(f"✅ 使用图片背景: {bg_image}")
    else:
        builder.set_color_bg("0x1a1a2e")
        print("✅ 使用纯色背景")
    
    # 设置内容文件
    builder.set_content_files(
        project_root / "data/script.txt",
        project_root / "data/ticker.txt"
    )
    
    # 添加BGM输入
    bgm_plugin = BGMPlugin({"dir": "assets/bgm", "volume": 0.3})
    bgm_plugin.playlist = bgm_plugin.discover_files(project_root)
    
    if bgm_plugin.playlist:
        bgm_inputs = bgm_plugin.get_ffmpeg_inputs()
        for inp in bgm_inputs:
            source = InputSource(
                type=inp["type"],
                path=inp["path"],
                label=inp.get("label", ""),
                options=inp.get("options", {})
            )
            builder.add_audio_input(source)
        builder.bgm_volume = bgm_plugin.volume
        print(f"✅ BGM: {len(bgm_plugin.playlist)} 首音乐")
        print(f"   当前: {bgm_plugin.playlist[0].name}")
    else:
        print("❌ 未找到BGM文件")
    
    # 添加TTS输入（模拟）
    tts_dir = project_root / "assets/tts"
    tts_files = list(tts_dir.glob("tts_*.mp3")) if tts_dir.exists() else []
    
    if tts_files:
        # 使用concat播放列表
        playlist_file = tts_dir / "tts_playlist.txt"
        source = InputSource(
            type="concat",
            path=str(playlist_file),
            label="tts",
            options={}
        )
        builder.add_audio_input(source)
        print(f"✅ TTS: {len(tts_files)} 个音频文件")
    else:
        print("⚠️ 未找到TTS文件")
    
    # 设置推流地址来测试输出映射
    builder.set_rtmp_output(["rtmp://test.example.com/live/test"])
    
    # 构建命令
    cmd = builder.build()
    
    print("\n" + "=" * 60)
    print("📝 生成的FFmpeg命令:")
    print("=" * 60)
    
    # 分段显示
    print("\n[输入部分]")
    for i, c in enumerate(cmd):
        if c in ['-i', '-f', '-loop', '-stream_loop']:
            print(f"  {cmd[i]} {cmd[i+1] if i+1 < len(cmd) else ''}")
    
    print("\n[音频滤镜]")
    if '-filter_complex' in cmd:
        idx = cmd.index('-filter_complex')
        print(f"  {cmd[idx+1]}")
    elif '-af' in cmd:
        idx = cmd.index('-af')
        print(f"  {cmd[idx+1]}")
    else:
        print("  ❌ 没有音频滤镜!")
    
    print("\n[输出映射]")
    if '-map' in cmd:
        for i, c in enumerate(cmd):
            if c == '-map':
                print(f"  -map {cmd[i+1]}")
    
    # 分析问题
    print("\n" + "=" * 60)
    print("🔍 问题分析:")
    print("=" * 60)
    
    # 检查输入数量
    input_count = cmd.count('-i')
    print(f"输入总数: {input_count}")
    
    # 检查音频输入数量
    audio_inputs = len(builder.audio_inputs)
    print(f"音频输入: {audio_inputs}")
    
    # 检查滤镜中的索引
    if '-filter_complex' in cmd:
        idx = cmd.index('-filter_complex')
        filter_str = cmd[idx+1]
        
        print(f"\n滤镜字符串: {filter_str}")
        
        # 验证索引是否正确
        # 当使用图片背景时：
        # - 输入0: 图片 (视频)
        # - 输入1: BGM音频
        # - 输入2: TTS音频
        
        if "[1:a]" in filter_str and "[2:a]" in filter_str:
            print("✅ 音频索引正确: [1:a]=BGM, [2:a]=TTS")
        elif "[0:a]" in filter_str:
            print("❌ 发现 [0:a] - 这指向的是图片背景的音频(不存在!)")
        else:
            print("⚠️ 滤镜索引需要验证")
    
    # 检查映射是否正确
    print("\n[映射验证]")
    if '-map' in cmd:
        maps = []
        for i, c in enumerate(cmd):
            if c == '-map':
                maps.append(cmd[i+1])
        
        if '0:v' in maps:
            print("✅ 视频映射正确: 0:v")
        
        if '[aout]' in maps:
            print("✅ 音频混合输出映射: [aout]")
        elif '1:a' in maps and audio_inputs == 1:
            print("✅ 单音频映射正确: 1:a")
        elif '1:a' in maps and audio_inputs > 1:
            print("⚠️ 多音频源但使用了简单映射")
    
    print("\n" + "=" * 60)
    return cmd


def test_ffmpeg_audio_simple():
    """测试简单音频场景（只有BGM）"""
    print("\n" + "=" * 60)
    print("🔍 简单音频测试（只有BGM）")
    print("=" * 60)
    
    font_path = "/usr/share/fonts/truetype/chinese/msyh.ttf"
    project_root = Path(__file__).parent.parent
    
    builder = FFmpegBuilderV2(font_path=font_path)
    builder.set_bg_image(project_root / "assets/bg_frame.png")
    builder.set_content_files(
        project_root / "data/script.txt",
        project_root / "data/ticker.txt"
    )
    
    # 只添加BGM
    bgm_file = project_root / "assets/bgm/ambient_01.mp3"
    if bgm_file.exists():
        source = InputSource(
            type="file",
            path=str(bgm_file),
            label="bgm",
            options={"stream_loop": -1}
        )
        builder.add_audio_input(source)
        builder.bgm_volume = 0.3
    
    # 设置推流地址
    builder.set_rtmp_output(["rtmp://test.example.com/live/test"])
    
    cmd = builder.build()
    
    print("\n生成的命令:")
    print(" ".join(cmd[:20]) + " ...")
    
    # 检查映射
    if '-map' in cmd:
        idx = cmd.index('-map')
        map_args = []
        for i, c in enumerate(cmd):
            if c == '-map':
                map_args.append(cmd[i+1])
        print(f"\n映射参数: {map_args}")
        
        # 检查是否正确
        if '1:a' in map_args:
            print("✅ 正确映射音频输入1")
        else:
            print("❌ 音频映射可能有问题")
    
    # 检查音频滤镜
    if '-af' in cmd:
        idx = cmd.index('-af')
        print(f"音频滤镜: {cmd[idx+1]}")
    
    return cmd


if __name__ == "__main__":
    test_ffmpeg_audio_index()
    test_ffmpeg_audio_simple()
