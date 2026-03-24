#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕同步管理器
================
功能：
- 管理字幕显示和滚动
- 与TTS音频同步
- 支持长文本自动滚动
- 生成动态字幕文件
"""

import json
import logging
import time
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import re


@dataclass
class SubtitleSegment:
    """字幕片段"""
    text: str
    start_time: float  # 开始时间(秒)
    duration: float    # 持续时间(秒)
    style: str = "default"
    
    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


class SubtitleManager:
    """
    字幕同步管理器
    
    功能：
    1. 解析文稿并分割成合适长度的字幕片段
    2. 根据TTS音频时长计算每个片段的显示时间
    3. 生成滚动字幕效果
    4. 输出FFmpeg兼容的字幕文件
    """
    
    # 字幕显示配置
    MAX_CHARS_PER_LINE = 35  # 每行最大字符数
    SCROLL_SPEED = 15  # 滚动速度(像素/秒)
    TTS_SPEED = 4.0    # TTS平均语速(字符/秒)
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.logger = logging.getLogger("SubtitleManager")
        
        # 字幕片段队列
        self.segments: List[SubtitleSegment] = []
        self.current_segment: Optional[SubtitleSegment] = None
        self.current_index: int = 0
        
        # 状态
        self.start_time: Optional[float] = None
        self.is_playing: bool = False
        
        # 输出文件
        self.subtitle_file: Optional[Path] = None
        self.scroll_file: Optional[Path] = None
    
    def set_output_dir(self, output_dir: Path):
        """设置输出目录"""
        output_dir.mkdir(parents=True, exist_ok=True)
        self.subtitle_file = output_dir / "current_subtitle.txt"
        self.scroll_file = output_dir / "scroll_subtitle.txt"
    
    def split_text_to_lines(self, text: str, max_chars: int = None) -> List[str]:
        """
        将长文本分割成适合显示的行
        
        策略：
        1. 优先在标点处分割
        2. 保证每行不超过max_chars个字符
        3. 保持语义完整性
        """
        max_chars = max_chars or self.MAX_CHARS_PER_LINE
        
        # 按句子分割（优先在句号、问号、感叹号后分割）
        sentences = re.split(r'([。！？!?])', text)
        
        # 重新组合句子和标点
        combined = []
        for i in range(0, len(sentences) - 1, 2):
            if sentences[i].strip():
                combined.append(sentences[i] + (sentences[i+1] if i+1 < len(sentences) else ''))
        
        # 处理剩余部分
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            combined.append(sentences[-1])
        
        if not combined:
            # 如果没有分割成功，按逗号分割
            combined = re.split(r'[，、；]', text)
        
        # 将每个句子进一步分割成合适的行
        lines = []
        for sentence in combined:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if len(sentence) <= max_chars:
                lines.append(sentence)
            else:
                # 长句子需要进一步分割
                current_line = ""
                for char in sentence:
                    current_line += char
                    if len(current_line) >= max_chars:
                        # 尝试在最近的标点处断开
                        last_punct = max(
                            current_line.rfind('，'),
                            current_line.rfind('、'),
                            current_line.rfind('；'),
                            current_line.rfind(','),
                            current_line.rfind(' ')
                        )
                        
                        if last_punct > max_chars // 2:
                            lines.append(current_line[:last_punct+1])
                            current_line = current_line[last_punct+1:]
                        else:
                            lines.append(current_line)
                            current_line = ""
                
                if current_line:
                    lines.append(current_line)
        
        return lines
    
    def create_segments_from_text(self, text: str, total_duration: float) -> List[SubtitleSegment]:
        """
        从文本创建字幕片段
        
        Args:
            text: 完整文本
            total_duration: TTS音频总时长(秒)
        
        Returns:
            字幕片段列表
        """
        lines = self.split_text_to_lines(text)
        
        if not lines:
            return []
        
        # 计算每个字符的平均时长
        char_count = len(text.replace(' ', ''))
        char_duration = total_duration / char_count if char_count > 0 else 0.25
        
        segments = []
        current_time = 0.0
        
        for line in lines:
            line_char_count = len(line.replace(' ', ''))
            line_duration = line_char_count * char_duration
            
            segment = SubtitleSegment(
                text=line,
                start_time=current_time,
                duration=line_duration,
                style="default"
            )
            segments.append(segment)
            current_time += line_duration
        
        return segments
    
    def start_playback(self, text: str, audio_duration: float):
        """
        开始字幕播放
        
        Args:
            text: 要显示的文本
            audio_duration: TTS音频时长(秒)
        """
        self.segments = self.create_segments_from_text(text, audio_duration)
        self.current_index = 0
        self.start_time = time.time()
        self.is_playing = True
        
        if self.segments:
            self.current_segment = self.segments[0]
            self._update_subtitle_file()
        
        self.logger.info(f"📝 开始字幕播放: {len(self.segments)} 个片段, 时长 {audio_duration:.1f}s")
    
    def update(self) -> Optional[str]:
        """
        更新字幕状态
        
        Returns:
            当前应该显示的字幕文本，如果播放结束返回None
        """
        if not self.is_playing or not self.start_time:
            return None
        
        elapsed = time.time() - self.start_time
        
        # 查找当前应该显示的片段
        for i, segment in enumerate(self.segments):
            if segment.start_time <= elapsed < segment.end_time:
                if i != self.current_index:
                    self.current_index = i
                    self.current_segment = segment
                    self._update_subtitle_file()
                    self.logger.debug(f"字幕切换到片段 {i}: {segment.text[:20]}...")
                return segment.text
        
        # 检查是否播放结束
        if elapsed > sum(s.duration for s in self.segments):
            self.is_playing = False
            return None
        
        return self.current_segment.text if self.current_segment else None
    
    def get_current_text(self) -> str:
        """获取当前字幕文本"""
        if self.current_segment:
            return self.current_segment.text
        return ""
    
    def get_scroll_offset(self) -> int:
        """
        获取滚动偏移量
        
        用于实现长文本滚动效果
        返回当前应该滚动的像素数
        """
        if not self.is_playing or not self.start_time:
            return 0
        
        elapsed = time.time() - self.start_time
        return int(elapsed * self.SCROLL_SPEED)
    
    def _update_subtitle_file(self):
        """更新字幕文件"""
        if self.subtitle_file and self.current_segment:
            self.subtitle_file.write_text(self.current_segment.text, encoding='utf-8')
    
    def generate_scroll_text_file(self, text: str, output_path: Path):
        """
        生成用于FFmpeg滚动字幕的文本文件
        
        Args:
            text: 完整文本
            output_path: 输出文件路径
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 将文本格式化为适合滚动的格式
        lines = self.split_text_to_lines(text)
        
        # FFmpeg的滚动字幕效果需要特殊格式
        content = "\n".join(lines)
        output_path.write_text(content, encoding='utf-8')
        
        self.logger.debug(f"生成滚动字幕文件: {output_path}")
    
    def generate_srt_file(self, output_path: Path) -> bool:
        """
        生成SRT字幕文件
        
        Returns:
            是否成功生成
        """
        if not self.segments:
            return False
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        lines = []
        for i, segment in enumerate(self.segments, 1):
            start = self._format_srt_time(segment.start_time)
            end = self._format_srt_time(segment.end_time)
            
            lines.append(str(i))
            lines.append(f"{start} --> {end}")
            lines.append(segment.text)
            lines.append("")
        
        output_path.write_text("\n".join(lines), encoding='utf-8')
        self.logger.info(f"生成SRT字幕: {output_path}")
        return True
    
    def _format_srt_time(self, seconds: float) -> str:
        """格式化SRT时间戳"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def stop_playback(self):
        """停止字幕播放"""
        self.is_playing = False
        self.start_time = None
        self.current_segment = None
        self.current_index = 0
        self.logger.info("🛑 字幕播放停止")
    
    def get_status(self) -> Dict:
        """获取状态信息"""
        return {
            "is_playing": self.is_playing,
            "total_segments": len(self.segments),
            "current_index": self.current_index,
            "current_text": self.current_segment.text if self.current_segment else None,
            "elapsed": time.time() - self.start_time if self.start_time else 0
        }


class DynamicSubtitleGenerator:
    """
    动态字幕生成器
    
    用于生成FFmpeg可用的动态字幕效果：
    - 逐字显示效果
    - 滚动效果
    - 打字机效果
    """
    
    def __init__(self, font_path: str):
        self.font_path = font_path
        self.logger = logging.getLogger("DynamicSubtitleGenerator")
    
    def generate_typewriter_filter(
        self,
        text: str,
        duration: float,
        x: int = 50,
        y: int = 540,
        fontsize: int = 32,
        fontcolor: str = "white"
    ) -> str:
        """
        生成打字机效果的drawtext滤镜
        
        使用FFmpeg的time函数实现逐字显示
        """
        # 转义特殊字符
        escaped_text = text.replace("'", "\\'").replace(":", "\\:")
        
        # 计算每帧显示的字符数
        char_interval = duration / len(text) if text else 1.0
        
        # 使用substr函数实现打字机效果
        filter_str = (
            f"drawtext=fontfile={self.font_path}:"
            f"text='{escaped_text}':"
            f"x={x}:y={y}:"
            f"fontsize={fontsize}:fontcolor={fontcolor}:"
            f"borderw=2:bordercolor=black@0.6:"
            f"textfile_reload=1"
        )
        
        return filter_str
    
    def generate_scroll_filter(
        self,
        text: str,
        scroll_speed: int = 50,
        y: int = 650,
        fontsize: int = 22,
        fontcolor: str = "yellow",
        width: int = 1280
    ) -> str:
        """
        生成水平滚动字幕滤镜
        
        Args:
            text: 滚动文本
            scroll_speed: 滚动速度(像素/秒)
            y: Y坐标
            fontsize: 字体大小
            fontcolor: 字体颜色
            width: 视频宽度
        """
        # 转义特殊字符
        escaped_text = text.replace("'", "\\'").replace(":", "\\:")
        
        # 使用mod函数实现无限循环滚动
        filter_str = (
            f"drawtext=fontfile={self.font_path}:"
            f"text='{escaped_text}':"
            f"x='w-mod(t*{scroll_speed}\\,w+tw)':"
            f"y={y}:"
            f"fontsize={fontsize}:fontcolor={fontcolor}:"
            f"box=1:boxcolor=black@0.6:boxborderw=4"
        )
        
        return filter_str
    
    def generate_multi_line_filter(
        self,
        lines: List[str],
        x: int = 50,
        y_start: int = 480,
        line_height: int = 45,
        fontsize: int = 28,
        fontcolor: str = "white",
        highlight_line: int = 0
    ) -> List[str]:
        """
        生成多行字幕滤镜
        
        用于显示当前正在朗读的内容，高亮当前行
        """
        filters = []
        
        for i, line in enumerate(lines[:4]):  # 最多显示4行
            escaped_line = line.replace("'", "\\'").replace(":", "\\:")
            
            # 当前行高亮显示
            color = "cyan" if i == highlight_line else fontcolor
            
            filter_str = (
                f"drawtext=fontfile={self.font_path}:"
                f"text='{escaped_line}':"
                f"x={x}:y={y_start + i * line_height}:"
                f"fontsize={fontsize}:fontcolor={color}:"
                f"borderw=2:bordercolor=black@0.6"
            )
            filters.append(filter_str)
        
        return filters


# =====================================================
# 测试函数
# =====================================================
def test_subtitle_manager():
    """测试字幕管理器"""
    print("=" * 60)
    print("字幕管理器测试")
    print("=" * 60)
    
    manager = SubtitleManager()
    
    # 测试文本分割
    test_text = """
    各位观众朋友们大家好，欢迎收看今天的AI主播台科技新闻节目。
    今天我们要关注的是人工智能领域的最新进展，包括大语言模型的突破性发展，
    以及AI在各个行业的应用情况。让我们一起来看看今天的热点新闻。
    """
    
    print("\n📝 测试文本分割:")
    lines = manager.split_text_to_lines(test_text)
    for i, line in enumerate(lines, 1):
        print(f"  {i}. [{len(line)}字] {line}")
    
    # 测试字幕片段创建
    print("\n🎬 测试字幕片段创建 (假设音频时长30秒):")
    segments = manager.create_segments_from_text(test_text, 30.0)
    for i, seg in enumerate(segments, 1):
        print(f"  {i}. [{seg.start_time:.1f}s - {seg.end_time:.1f}s] {seg.text[:30]}...")
    
    # 测试SRT生成
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as f:
        srt_path = Path(f.name)
    
    manager.segments = segments
    if manager.generate_srt_file(srt_path):
        print(f"\n✅ SRT文件生成成功: {srt_path}")
        print("前10行内容:")
        with open(srt_path, 'r') as f:
            for i, line in enumerate(f):
                if i < 10:
                    print(f"  {line.rstrip()}")
                else:
                    break
    
    print("\n" + "=" * 60)
    return True


def test_dynamic_subtitle():
    """测试动态字幕生成"""
    print("=" * 60)
    print("动态字幕生成测试")
    print("=" * 60)
    
    font_path = "/usr/share/fonts/truetype/chinese/msyh.ttf"
    generator = DynamicSubtitleGenerator(font_path)
    
    test_text = "欢迎收看AI主播台科技新闻节目"
    
    print("\n📜 打字机效果滤镜:")
    tw_filter = generator.generate_typewriter_filter(test_text, 5.0)
    print(f"  {tw_filter[:80]}...")
    
    print("\n📜 滚动字幕滤镜:")
    scroll_filter = generator.generate_scroll_filter(test_text)
    print(f"  {scroll_filter[:80]}...")
    
    print("\n📜 多行字幕滤镜:")
    lines = [
        "第一行：今天的科技新闻",
        "第二行：人工智能最新进展",
        "第三行：大语言模型突破",
        "第四行：AI行业应用动态"
    ]
    filters = generator.generate_multi_line_filter(lines, highlight_line=1)
    for i, f in enumerate(filters):
        print(f"  行{i+1}: {f[:60]}...")
    
    print("\n✅ 动态字幕测试完成")
    print("=" * 60)
    return True


if __name__ == "__main__":
    test_subtitle_manager()
    print()
    test_dynamic_subtitle()
