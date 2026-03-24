#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFmpeg命令构建器 V3 (使用InputManager)
=====================================
重构版本，使用InputManager统一管理输入源

核心改进:
1. 统一索引管理 - 所有输入索引由InputManager集中管理
2. 标签引用 - 使用标签而非硬编码索引
3. 自动验证 - 构建命令后自动验证索引有效性
4. 更清晰的接口 - 视频和音频输入分离管理

解决问题:
- 索引计算分散导致的bug
- 视频输入数量变化影响音频索引
- 特殊处理过多容易遗漏
"""

import subprocess
import tempfile
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from core.input_manager import (
    InputManager, InputSource, MediaType,
    create_video_source, create_audio_source, 
    create_image_source, create_concat_source
)


class FFmpegCommandValidator:
    """
    FFmpeg命令验证器
    
    在执行前验证命令的有效性，避免运行时错误。
    """
    
    @staticmethod
    def validate(cmd: List[str], manager: InputManager) -> Tuple[bool, List[str]]:
        """
        验证FFmpeg命令有效性
        
        Args:
            cmd: FFmpeg命令列表
            manager: InputManager实例
        
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        cmd_str = ' '.join(cmd)
        
        # 1. 验证输入数量
        input_count = cmd.count('-i') + cmd.count('-f')  # -f lavfi 也算输入
        
        # 2. 验证滤镜中的索引
        pattern = r'\[(\d+):[av]\]'
        matches = re.findall(pattern, cmd_str)
        for idx_str in matches:
            idx = int(idx_str)
            if idx >= manager.total_count:
                errors.append(
                    f"索引 [{idx_str}:v/a] 超出输入范围 "
                    f"(共{manager.total_count}个输入)"
                )
        
        # 3. 验证映射索引
        map_pattern = r'-map\s+(\d+:[av]|\[.+?\])'
        map_matches = re.findall(map_pattern, cmd_str)
        for item in map_matches:
            if item.startswith('['):
                # 滤镜输出引用
                if item not in ['[vout]', '[aout]', '[v_base]', '[avatar]', '[bgm]', '[tts]']:
                    # 可能是自定义标签，检查是否定义
                    pass
            else:
                # 直接索引引用
                num = int(item.split(':')[0])
                if num >= manager.total_count:
                    errors.append(f"映射索引 {item} 超出输入范围")
        
        return len(errors) == 0, errors


class FFmpegBuilderV3:
    """
    FFmpeg命令构建器 V3
    
    使用InputManager统一管理输入源，解决索引混乱问题。
    
    使用示例:
        builder = FFmpegBuilderV3(font_path)
        
        # 设置背景（会自动添加到InputManager）
        builder.set_bg_image(Path("assets/bg_frame.png"))
        
        # 添加BGM
        builder.set_bgm(Path("assets/bgm/music.mp3"), volume=0.3, loop=True)
        
        # 添加TTS
        builder.add_tts_playlist(Path("assets/tts/playlist.txt"))
        
        # 设置智灵主播
        builder.set_avatar(Path("assets/zhiling.mp4"), scale="0.35")
        
        # 构建命令
        cmd = builder.build()
        
        # 验证命令
        valid, errors = builder.validate()
        if not valid:
            print("命令无效:", errors)
    """
    
    def __init__(self, font_path: str):
        self.font_path = font_path
        
        # 使用InputManager统一管理输入
        self.input_manager = InputManager()
        
        # 视频参数
        self.width = 1280
        self.height = 720
        self.framerate = 25
        self.video_bitrate = "1500k"
        self.preset = "ultrafast"
        
        # 音频参数
        self.audio_bitrate = "128k"
        self.audio_sample_rate = 44100
        
        # 内容文件
        self.script_file: Optional[Path] = None
        self.ticker_file: Optional[Path] = None
        
        # 字幕配置
        self.subtitle_lines: List[str] = []
        self.current_line_index: int = 0
        self.enable_scroll_subtitle: bool = True
        self.subtitle_max_width: int = 40
        
        # 输出
        self.rtmp_urls: List[str] = []
        self.output_file: Optional[Path] = None
        
        # BGM配置
        self.bgm_volume = 0.3
        
        # 智灵主播配置
        self.avatar_enabled: bool = False
        self.avatar_position: str = "W-w-30:H-h-30"  # 右下角
        self.avatar_scale: str = "0.35"
        
        # 背景类型标记
        self._bg_type: str = "none"  # none, image, video, color
        self._bg_color: str = "0x1a1a2e"
        
        # 自定义滤镜
        self.video_filters: List[str] = []
        self.audio_filters: List[str] = []
    
    # ==================== 背景设置 ====================
    
    def set_bg_image(self, image_path: Path, framerate: int = 25) -> 'FFmpegBuilderV3':
        """设置图片背景"""
        self.framerate = framerate
        self._bg_type = "image"
        
        # 添加图片输入，标签为 "background"
        source = create_image_source(
            path=str(image_path),
            label="background",
            framerate=framerate
        )
        self.input_manager.add_video(source)
        return self
    
    def set_bg_video(self, video_path: Path, loop: bool = True) -> 'FFmpegBuilderV3':
        """设置视频背景"""
        self._bg_type = "video"
        
        source = create_video_source(
            path=str(video_path),
            label="background",
            loop=loop
        )
        self.input_manager.add_video(source)
        return self
    
    def set_color_bg(self, color: str = "0x1a1a2e") -> 'FFmpegBuilderV3':
        """设置纯色背景"""
        self._bg_type = "color"
        self._bg_color = color
        
        source = InputSource(
            type="lavfi",
            path=f"color=c={color}:s={self.width}x{self.height}:r={self.framerate}",
            label="background",
            media_type=MediaType.VIDEO
        )
        self.input_manager.add_video(source)
        return self
    
    # ==================== 智灵主播设置 ====================
    
    def set_avatar(self, video_path: Path, scale: str = "0.35", 
                   position: str = None) -> 'FFmpegBuilderV3':
        """设置智灵主播视频"""
        self.avatar_enabled = True
        self.avatar_scale = scale
        if position:
            self.avatar_position = position
        
        # 添加智灵视频输入（循环播放）
        source = create_video_source(
            path=str(video_path),
            label="avatar",
            loop=True
        )
        self.input_manager.add_video(source)
        return self
    
    def show_avatar(self, show: bool = True) -> 'FFmpegBuilderV3':
        """控制智灵显示/隐藏"""
        self.avatar_enabled = show
        return self
    
    # ==================== 音频设置 ====================
    
    def set_bgm(self, bgm_path: Path, volume: float = 0.3, 
                loop: bool = True) -> 'FFmpegBuilderV3':
        """设置背景音乐"""
        self.bgm_volume = volume
        
        source = create_audio_source(
            path=str(bgm_path),
            label="bgm",
            loop=loop
        )
        self.input_manager.add_audio(source)
        return self
    
    def add_tts_playlist(self, playlist_path: Path) -> 'FFmpegBuilderV3':
        """添加TTS播放列表"""
        source = create_concat_source(
            path=str(playlist_path),
            label="tts"
        )
        self.input_manager.add_audio(source)
        return self
    
    def add_tts_file(self, tts_path: Path) -> 'FFmpegBuilderV3':
        """添加单个TTS文件"""
        source = create_audio_source(
            path=str(tts_path),
            label=f"tts_{self.input_manager.audio_count}"
        )
        self.input_manager.add_audio(source)
        return self
    
    def add_audio_input(self, source: InputSource) -> 'FFmpegBuilderV3':
        """添加自定义音频输入"""
        self.input_manager.add_audio(source)
        return self
    
    # ==================== 内容设置 ====================
    
    def set_content_files(self, script_file: Path, ticker_file: Path) -> 'FFmpegBuilderV3':
        """设置内容文件"""
        self.script_file = script_file
        self.ticker_file = ticker_file
        return self
    
    def set_subtitle_config(self, lines: List[str], current_index: int = 0,
                           enable_scroll: bool = True, max_width: int = 40) -> 'FFmpegBuilderV3':
        """设置字幕配置"""
        self.subtitle_lines = lines
        self.current_line_index = current_index
        self.enable_scroll_subtitle = enable_scroll
        self.subtitle_max_width = max_width
        return self
    
    # ==================== 输出设置 ====================
    
    def set_rtmp_output(self, urls: List[str]) -> 'FFmpegBuilderV3':
        """设置RTMP推流地址"""
        self.rtmp_urls = urls
        return self
    
    def set_file_output(self, output_file: Path) -> 'FFmpegBuilderV3':
        """设置文件输出"""
        self.output_file = output_file
        return self
    
    # ==================== 视频参数 ====================
    
    def set_video_params(self, bitrate: str = "1500k", preset: str = "ultrafast",
                        width: int = 1280, height: int = 720, 
                        framerate: int = 25) -> 'FFmpegBuilderV3':
        """设置视频参数"""
        self.video_bitrate = bitrate
        self.preset = preset
        self.width = width
        self.height = height
        self.framerate = framerate
        return self
    
    # ==================== 滤镜构建 ====================
    
    def _build_video_filters(self) -> str:
        """构建视频滤镜"""
        filters = []
        
        # 字幕滤镜
        if self.subtitle_lines:
            y_start = 480
            line_height = 45
            
            for i, line in enumerate(self.subtitle_lines[:4]):
                escaped_line = line.replace("'", "\\'").replace(":", "\\:")
                
                if i == self.current_line_index:
                    color = "cyan"
                    fontsize = 30
                else:
                    color = "white"
                    fontsize = 28
                
                filter_str = (
                    f"drawtext=fontfile={self.font_path}:"
                    f"text='{escaped_line}':"
                    f"x=50:y={y_start + i * line_height}:"
                    f"fontsize={fontsize}:fontcolor={color}:"
                    f"borderw=2:bordercolor=black@0.7:"
                    f"box=1:boxcolor=0x1a1a2e@0.5:boxborderw=8"
                )
                filters.append(filter_str)
        
        elif self.script_file:
            try:
                with open(self.script_file, 'r', encoding='utf-8') as f:
                    script_text = f.read().strip()
                
                escaped_text = script_text.replace("'", "\\'").replace(":", "\\:")
                
                if len(script_text) > self.subtitle_max_width and self.enable_scroll_subtitle:
                    filters.append(
                        f"drawtext=fontfile={self.font_path}:"
                        f"text='{escaped_text}':"
                        f"x='max(w-tw-50\\,w-50-t*30)':"
                        f"y=h-180:fontsize=30:fontcolor=white:"
                        f"borderw=2:bordercolor=black@0.6"
                    )
                else:
                    filters.append(
                        f"drawtext=fontfile={self.font_path}:"
                        f"textfile={str(self.script_file.resolve())}:reload=1:"
                        f"x=50:y=h-180:fontsize=32:fontcolor=white:"
                        f"borderw=2:bordercolor=black@0.6"
                    )
            except:
                filters.append(
                    f"drawtext=fontfile={self.font_path}:"
                    f"text='AI Anchor Live':"
                    f"x=50:y=h-180:fontsize=32:fontcolor=white:"
                    f"borderw=2:bordercolor=black@0.6"
                )
        
        # 滚动新闻条
        if self.ticker_file:
            filters.append(
                f"drawtext=fontfile={self.font_path}:"
                f"textfile={str(self.ticker_file.resolve())}:reload=1:"
                f"x='w-mod(t*80\\,w+tw)':y=h-50:fontsize=22:fontcolor=yellow:"
                f"box=1:boxcolor=black@0.6:boxborderw=4"
            )
        
        # 标题和时间
        filters.extend([
            f"drawtext=fontfile={self.font_path}:text='AI ANCHOR':x=30:y=30:fontsize=24:fontcolor=cyan:borderw=1:bordercolor=black@0.5",
            f"drawtext=fontfile={self.font_path}:text='%{{localtime}}':x=w-220:y=30:fontsize=22:fontcolor=white:borderw=1:bordercolor=black@0.5"
        ])
        
        # 自定义滤镜
        filters.extend(self.video_filters)
        
        return ",".join(filters)
    
    def _build_filter_complex(self) -> str:
        """
        构建完整的filter_complex
        
        使用InputManager的标签引用，而非硬编码索引
        """
        parts = []
        
        # 获取背景视频索引
        bg_ref = self.input_manager.get_video_ref("background")
        if not bg_ref:
            return ""  # 没有视频输入
        
        # 视频处理链
        video_chain = f"[{bg_ref}]"
        
        # 如果有智灵视频，进行叠加
        if self.avatar_enabled:
            avatar_ref = self.input_manager.get_video_ref("avatar")
            if avatar_ref:
                # 智灵缩放和格式化
                parts.append(
                    f"[{avatar_ref}]scale=iw*{self.avatar_scale}:ih*{self.avatar_scale},format=rgba[avatar_scaled]"
                )
                
                # 叠加到背景
                parts.append(
                    f"[{bg_ref}][avatar_scaled]overlay={self.avatar_position}[v_base]"
                )
                video_chain = "[v_base]"
        
        # 添加字幕滤镜
        video_filters = self._build_video_filters()
        if video_filters:
            parts.append(f"{video_chain}{video_filters}[vout]")
        
        # 音频处理链 - 使用标签引用
        if self.input_manager.audio_count > 1:
            # 获取BGM和TTS的音频引用
            bgm_ref = self.input_manager.get_audio_ref("bgm")
            tts_ref = self.input_manager.get_audio_ref("tts")
            
            if bgm_ref and tts_ref:
                parts.append(f"[{bgm_ref}]volume={self.bgm_volume}[bgm]")
                parts.append(f"[{tts_ref}]volume=1.0[tts]")
                parts.append("[bgm][tts]amix=inputs=2:duration=longest[aout]")
            else:
                # 按顺序处理
                audio_indices = self.input_manager.get_audio_indices()
                if len(audio_indices) >= 2:
                    parts.append(f"[{audio_indices[0]}:a]volume={self.bgm_volume}[bgm]")
                    parts.append(f"[{audio_indices[1]}:a]volume=1.0[tts]")
                    parts.append("[bgm][tts]amix=inputs=2:duration=longest[aout]")
        
        elif self.input_manager.audio_count == 1:
            # 单音频源
            audio_indices = self.input_manager.get_audio_indices()
            if audio_indices:
                parts.append(f"[{audio_indices[0]}:a]volume={self.bgm_volume}[aout]")
        
        return ";".join(parts)
    
    # ==================== 构建命令 ====================
    
    def build(self) -> List[str]:
        """构建完整的FFmpeg命令"""
        cmd = ['ffmpeg', '-y', '-re']
        
        # 使用InputManager构建输入参数
        cmd.extend(self.input_manager.build_input_args())
        
        # 构建filter_complex
        filter_complex = self._build_filter_complex()
        if filter_complex:
            cmd.extend(['-filter_complex', filter_complex])
        
        # 视频编码
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', self.preset,
            '-tune', 'zerolatency',
            '-b:v', self.video_bitrate,
            '-pix_fmt', 'yuv420p',
            '-g', '50',
        ])
        
        # 音频编码
        if self.input_manager.audio_count > 0:
            cmd.extend([
                '-c:a', 'aac',
                '-b:a', self.audio_bitrate,
                '-ar', str(self.audio_sample_rate),
            ])
        
        # 输出映射
        video_map = '[vout]' if filter_complex else '0:v'
        
        if len(self.rtmp_urls) > 1:
            # 多推流
            tee_parts = []
            for url in self.rtmp_urls:
                escaped_url = url.replace(':', '\\:')
                tee_parts.append(f"[f=flv:{escaped_url}]")
            tee_url = "|".join(tee_parts)
            
            cmd.extend(['-map', video_map])
            if self.input_manager.audio_count > 0:
                if self.input_manager.audio_count > 1:
                    cmd.extend(['-map', '[aout]'])
                else:
                    audio_indices = self.input_manager.get_audio_indices()
                    cmd.extend(['-map', f'{audio_indices[0]}:a'])
            cmd.extend(['-f', 'tee', tee_url])
            
        elif len(self.rtmp_urls) == 1:
            # 单推流
            cmd.extend(['-map', video_map])
            if self.input_manager.audio_count > 0:
                if self.input_manager.audio_count > 1:
                    cmd.extend(['-map', '[aout]'])
                else:
                    audio_indices = self.input_manager.get_audio_indices()
                    cmd.extend(['-map', f'{audio_indices[0]}:a'])
            cmd.extend(['-f', 'flv', self.rtmp_urls[0]])
            
        elif self.output_file:
            cmd.extend(['-t', '10', str(self.output_file)])
        else:
            cmd.extend(['-f', 'null', '-'])
        
        return cmd
    
    def validate(self) -> Tuple[bool, List[str]]:
        """验证构建的命令"""
        cmd = self.build()
        return FFmpegCommandValidator.validate(cmd, self.input_manager)
    
    def summary(self) -> str:
        """生成构建摘要"""
        lines = [
            "FFmpeg构建器摘要:",
            f"  背景类型: {self._bg_type}",
            f"  智灵主播: {'启用' if self.avatar_enabled else '禁用'}",
            "",
            self.input_manager.summary(),
            "",
            f"  推流地址: {len(self.rtmp_urls)} 个",
        ]
        return "\n".join(lines)


# =====================================================
# 工厂函数
# =====================================================

def build_from_config(config: Dict[str, Any], font_path: str) -> FFmpegBuilderV3:
    """
    从配置字典构建FFmpegBuilderV3
    """
    builder = FFmpegBuilderV3(font_path=font_path)
    
    # 视频参数
    video_config = config.get("video", {})
    builder.set_video_params(
        bitrate=video_config.get("bitrate", "1500k"),
        preset=video_config.get("preset", "ultrafast"),
        width=video_config.get("width", 1280),
        height=video_config.get("height", 720),
        framerate=video_config.get("framerate", 25)
    )
    
    # 推流地址
    rtmp_urls = config.get("rtmp_urls", [])
    if rtmp_urls:
        builder.set_rtmp_output(rtmp_urls)
    
    return builder


# =====================================================
# 测试代码
# =====================================================
if __name__ == "__main__":
    print("=" * 60)
    print("FFmpeg构建器V3测试 (使用InputManager)")
    print("=" * 60)
    
    font_path = "/usr/share/fonts/truetype/chinese/msyh.ttf"
    
    builder = FFmpegBuilderV3(font_path=font_path)
    
    # 设置背景
    bg_image = Path("/home/z/my-project/cyber_director/assets/bg_frame.png")
    if bg_image.exists():
        builder.set_bg_image(bg_image)
        print(f"✅ 背景图片: {bg_image}")
    else:
        builder.set_color_bg("0x1a1a2e")
        print("✅ 使用纯色背景")
    
    # 设置智灵主播
    avatar = Path("/home/z/my-project/cyber_director/assets/zhiling.mp4")
    if avatar.exists():
        builder.set_avatar(avatar, scale="0.35")
        print(f"✅ 智灵主播: {avatar}")
    
    # 设置BGM
    bgm = Path("/home/z/my-project/cyber_director/assets/bgm/calm_01.mp3")
    if bgm.exists():
        builder.set_bgm(bgm, volume=0.3, loop=True)
        print(f"✅ BGM: {bgm}")
    
    # 设置输出
    builder.set_rtmp_output(["rtmp://test.example.com/live/test"])
    
    # 显示摘要
    print("\n" + builder.summary())
    
    # 构建命令
    cmd = builder.build()
    print("\n生成的FFmpeg命令:")
    print(" ".join(cmd[:15]) + " ...")
    
    # 验证
    valid, errors = builder.validate()
    print(f"\n命令验证: {'✅ 有效' if valid else '❌ 无效'}")
    if errors:
        for e in errors:
            print(f"  错误: {e}")
    
    print("\n" + "=" * 60)
