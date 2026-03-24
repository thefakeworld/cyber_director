#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕同步和TTS音频测试
====================
测试功能：
1. 字幕分割和滚动效果
2. TTS音频生成
3. 音频时长获取
4. FFmpeg命令生成（包含字幕和音频）
"""

import sys
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.subtitle_manager import SubtitleManager, DynamicSubtitleGenerator
from core.ffmpeg_builder import FFmpegBuilderV2, InputSource


def test_subtitle_split():
    """测试字幕分割功能"""
    print("\n" + "=" * 60)
    print("📝 测试1: 字幕分割功能")
    print("=" * 60)
    
    manager = SubtitleManager()
    
    test_cases = [
        # 短文本
        ("欢迎收看AI主播台科技新闻节目。", "短文本(1行)"),
        # 中等长度
        ("各位观众朋友们大家好，欢迎收看今天的AI主播台科技新闻节目。今天我们要关注的是人工智能领域的最新进展。", "中等文本(2-3行)"),
        # 长文本
        ("""各位观众朋友们大家好，欢迎收看今天的AI主播台科技新闻节目。
今天我们要关注的是人工智能领域的最新进展，包括大语言模型的突破性发展，以及AI在各个行业的应用情况。
首先来看第一条新闻，OpenAI发布了最新的GPT-5模型，在多项基准测试中取得了优异成绩。
第二，国内科技巨头纷纷布局AI赛道，百度、阿里、腾讯相继推出自己的大语言模型产品。
第三，AI在教育领域的应用日益广泛，智能辅导系统正在改变传统教育模式。""", "长文本(多行)"),
    ]
    
    all_passed = True
    
    for text, name in test_cases:
        lines = manager.split_text_to_lines(text)
        print(f"\n[{name}] 原文 {len(text)} 字符 -> {len(lines)} 行:")
        
        for i, line in enumerate(lines, 1):
            status = "✅" if len(line) <= manager.MAX_CHARS_PER_LINE else "❌"
            print(f"  {status} 行{i}: [{len(line)}字] {line}")
            if len(line) > manager.MAX_CHARS_PER_LINE:
                all_passed = False
    
    print(f"\n{'✅ 字幕分割测试通过' if all_passed else '❌ 字幕分割测试失败'}")
    return all_passed


def test_subtitle_segments():
    """测试字幕片段创建"""
    print("\n" + "=" * 60)
    print("📝 测试2: 字幕片段创建（时间同步）")
    print("=" * 60)
    
    manager = SubtitleManager()
    
    text = "各位观众朋友们大家好，欢迎收看今天的AI主播台科技新闻节目。今天我们要关注的是人工智能领域的最新进展。"
    duration = 10.0  # 假设音频时长10秒
    
    segments = manager.create_segments_from_text(text, duration)
    
    print(f"\n原文: {text}")
    print(f"音频时长: {duration}秒")
    print(f"片段数: {len(segments)}")
    print("\n时间轴:")
    
    all_passed = True
    total_duration = 0
    
    for i, seg in enumerate(segments, 1):
        print(f"  [{seg.start_time:5.2f}s - {seg.end_time:5.2f}s] {seg.text}")
        total_duration += seg.duration
        
        # 检查时间连续性
        if i > 1 and abs(seg.start_time - segments[i-2].end_time) > 0.01:
            print(f"    ⚠️ 时间不连续!")
            all_passed = False
    
    # 检查总时长
    if abs(total_duration - duration) > 0.5:
        print(f"\n⚠️ 总时长不匹配: {total_duration:.2f}s vs {duration:.2f}s")
        all_passed = False
    
    print(f"\n{'✅ 字幕片段测试通过' if all_passed else '❌ 字幕片段测试失败'}")
    return all_passed


def test_ffmpeg_subtitle_filter():
    """测试FFmpeg字幕滤镜生成"""
    print("\n" + "=" * 60)
    print("📝 测试3: FFmpeg字幕滤镜生成")
    print("=" * 60)
    
    font_path = "/usr/share/fonts/truetype/chinese/msyh.ttf"
    builder = FFmpegBuilderV2(font_path=font_path)
    
    # 测试多行字幕
    lines = [
        "欢迎收看AI主播台科技新闻节目",
        "今天关注人工智能领域最新进展",
        "OpenAI发布GPT-5模型",
        "国内科技巨头布局AI赛道"
    ]
    
    builder.set_subtitle_config(lines, current_index=0)
    
    # 设置其他必要参数
    builder.set_color_bg("0x1a1a2e")
    builder.set_content_files(
        Path("/tmp/test_script.txt"),
        Path("/tmp/test_ticker.txt")
    )
    
    # 创建测试文件
    Path("/tmp/test_script.txt").write_text("测试字幕", encoding='utf-8')
    Path("/tmp/test_ticker.txt").write_text("测试滚动条", encoding='utf-8')
    
    # 构建滤镜
    vf = builder._build_video_filters()
    
    print(f"\n生成的滤镜链 ({len(vf)} 字符):")
    # 打印每个滤镜
    for i, f in enumerate(vf.split(','), 1):
        print(f"  {i}. {f[:80]}{'...' if len(f) > 80 else ''}")
    
    # 检查是否包含多行字幕
    has_multiple_lines = vf.count('drawtext') >= 4
    has_highlight = 'cyan' in vf
    
    print(f"\n检查结果:")
    print(f"  {'✅' if has_multiple_lines else '❌'} 包含多行字幕")
    print(f"  {'✅' if has_highlight else '❌'} 包含高亮效果")
    
    all_passed = has_multiple_lines and has_highlight
    print(f"\n{'✅ FFmpeg字幕滤镜测试通过' if all_passed else '❌ FFmpeg字幕滤镜测试失败'}")
    return all_passed


def test_tts_integration():
    """测试TTS集成"""
    print("\n" + "=" * 60)
    print("📝 测试4: TTS音频生成")
    print("=" * 60)
    
    try:
        from plugins.tts import TTSPluginV2
    except ImportError:
        print("❌ 无法导入TTS插件")
        return False
    
    plugin = TTSPluginV2({"output_dir": "/tmp/tts_test"})
    plugin._project_root = Path("/tmp")
    
    test_text = "欢迎收看AI主播台，这是一段测试文本。"
    
    print(f"\n生成TTS: {test_text}")
    print("请稍候...")
    
    audio_path = plugin.generate_tts(test_text, "news")
    
    if audio_path and audio_path.exists():
        file_size = audio_path.stat().st_size
        print(f"✅ TTS生成成功: {audio_path}")
        print(f"   文件大小: {file_size} 字节")
        
        # 获取音频时长
        duration = get_audio_duration(audio_path)
        print(f"   音频时长: {duration:.2f} 秒")
        
        return True
    else:
        print("❌ TTS生成失败")
        return False


def get_audio_duration(audio_path: Path) -> float:
    """获取音频文件时长"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries',
            'format=duration', '-of',
            'default=noprint_wrappers=1:nokey=1',
            str(audio_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except:
        return 0.0


def test_full_pipeline():
    """测试完整流程"""
    print("\n" + "=" * 60)
    print("📝 测试5: 完整流程（字幕+TTS+FFmpeg）")
    print("=" * 60)
    
    # 1. 创建字幕管理器
    manager = SubtitleManager()
    
    # 2. 测试文本
    text = "欢迎收看AI主播台科技新闻节目，今天我们关注人工智能领域最新动态。"
    
    # 3. 分割字幕
    lines = manager.split_text_to_lines(text)
    print(f"\n字幕分割: {len(lines)} 行")
    for i, line in enumerate(lines):
        print(f"  {i+1}. {line}")
    
    # 4. 创建字幕片段（假设8秒音频）
    segments = manager.create_segments_from_text(text, 8.0)
    print(f"\n字幕片段: {len(segments)} 个")
    
    # 5. 生成FFmpeg命令
    font_path = "/usr/share/fonts/truetype/chinese/msyh.ttf"
    builder = FFmpegBuilderV2(font_path=font_path)
    builder.set_subtitle_config(lines, current_index=0)
    builder.set_color_bg("0x1a1a2e")
    builder.set_content_files(
        Path("/tmp/test_script.txt"),
        Path("/tmp/test_ticker.txt")
    )
    
    # 模拟BGM输入
    builder.bgm_volume = 0.3
    
    # 构建命令
    cmd = builder.build()
    
    print(f"\nFFmpeg命令: {' '.join(cmd[:15])} ...")
    print(f"命令总长度: {len(cmd)} 参数")
    
    # 检查命令有效性
    valid = len(cmd) > 10 and 'ffmpeg' in cmd[0]
    
    print(f"\n{'✅ 完整流程测试通过' if valid else '❌ 完整流程测试失败'}")
    return valid


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🧪 AI主播台 - 字幕同步和TTS音频测试")
    print("=" * 60)
    
    tests = [
        ("字幕分割", test_subtitle_split),
        ("字幕片段", test_subtitle_segments),
        ("FFmpeg滤镜", test_ffmpeg_subtitle_filter),
        ("TTS集成", test_tts_integration),
        ("完整流程", test_full_pipeline),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ 测试 {name} 出错: {e}")
            results.append((name, False))
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, p in results:
        status = "✅ 通过" if p else "❌ 失败"
        print(f"  {status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
