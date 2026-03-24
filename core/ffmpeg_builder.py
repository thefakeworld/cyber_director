#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFmpeg命令构建器（重构版）
=========================
支持：
- 多输入源（视频、音频）
- 插件化的滤镜链
- 音频混合（BGM + TTS）
- 多平台推流
"""

import subprocess
import tempfile
import os
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field


@dataclass
class InputSource:
    """输入源配置"""
    type: str  # file, lavfi, concat
    path: str
    label: str = ""  # 用于滤镜引用
    options: Dict[str, Any] = field(default_factory=dict)
    
    # 常用选项快捷方式
    @property
    def stream_loop(self) -> int:
        return self.options.get("stream_loop", 0)


class FFmpegBuilderV2:
    """
    FFmpeg命令构建器 V2
    
    设计理念：
    1. 输入源管理 - 支持多种输入类型
    2. 滤镜链构建 - 分离视频/音频滤镜
    3. 音频混合 - 支持多音轨合并
    4. 输出管理 - 支持多目标推流
    """
    
    def __init__(self, font_path: str):
        self.font_path = font_path
        
        # 输入源
        self.video_inputs: List[InputSource] = []
        self.audio_inputs: List[InputSource] = []
        
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
        self.subtitle_lines: List[str] = []  # 多行字幕
        self.current_line_index: int = 0     # 当前高亮行
        self.enable_scroll_subtitle: bool = True  # 启用滚动字幕
        self.subtitle_max_width: int = 40   # 字幕每行最大字符数
        
        # 输出
        self.rtmp_urls: List[str] = []
        self.output_file: Optional[Path] = None
        
        # 滤镜
        self.video_filters: List[str] = []
        self.audio_filters: List[str] = []
        
        # BGM配置
        self.bgm_volume = 0.3
        self.bgm_path: Optional[Path] = None
        
        # 图片背景
        self._bg_image_path: Optional[Path] = None
        
        # 智灵主播视频
        self.avatar_video: Optional[Path] = None
        self.avatar_enabled: bool = False
        self.avatar_position: str = "main_w-overlay_w-30:main_h-overlay_h-30"  # 右下角
        self.avatar_scale: str = "0.4"  # 缩放比例
        self.avatar_showing: bool = False  # 是否正在显示

    # ==================== 智灵主播设置 ====================
    
    def set_avatar(self, video_path: Path, scale: str = "0.4", position: str = None):
        """
        设置智灵主播视频
        
        Args:
            video_path: 智灵视频文件路径
            scale: 缩放比例，如 "0.4" 表示40%
            position: 位置表达式，默认右下角
        """
        if video_path and video_path.exists():
            self.avatar_video = video_path
            self.avatar_enabled = True
            self.avatar_scale = scale
            if position:
                self.avatar_position = position
        return self
    
    def show_avatar(self, show: bool = True):
        """控制智灵显示/隐藏"""
        self.avatar_showing = show
        return self
    
    def toggle_avatar(self):
        """切换智灵显示状态"""
        self.avatar_showing = not self.avatar_showing
        return self.avatar_showing
    
    # ==================== 输入源管理 ====================
    
    def set_video_input(self, source: InputSource):
        """设置视频输入源"""
        self.video_inputs = [source]
        return self
    
    def add_video_input(self, source: InputSource):
        """添加视频输入源"""
        self.video_inputs.append(source)
        return self
    
    def set_bg_video(self, video_path: Path, loop: bool = True):
        """设置背景视频"""
        self.video_inputs = [InputSource(
            type="file",
            path=str(video_path),
            label="video",
            options={"stream_loop": -1} if loop else {}
        )]
        return self
    
    def set_color_bg(self, color: str = "0x1a1a2e"):
        """设置纯色背景"""
        self.video_inputs = [InputSource(
            type="lavfi",
            path=f"color=c={color}:s={self.width}x{self.height}:r={self.framerate}",
            label="video"
        )]
        return self
    
    def set_bg_image(self, image_path: Path, framerate: int = 25):
        """设置图片背景（循环显示）"""
        self.framerate = framerate
        # 使用loop滤镜循环图片
        self.video_inputs = [InputSource(
            type="lavfi",
            path=f"loop=-1:1:0,format=yuv420p",
            label="video"
        )]
        # 单独添加图片输入
        self._bg_image_path = image_path
        return self
    
    def set_bgm(self, bgm_path: Path, volume: float = 0.3, loop: bool = True):
        """设置背景音乐"""
        self.bgm_path = bgm_path
        self.bgm_volume = volume
        self.audio_inputs.append(InputSource(
            type="file",
            path=str(bgm_path),
            label="bgm",
            options={"stream_loop": -1} if loop else {}
        ))
        return self
    
    def add_audio_input(self, source: InputSource):
        """添加音频输入源"""
        self.audio_inputs.append(source)
        return self
    
    # ==================== 内容设置 ====================
    
    def set_content_files(self, script_file: Path, ticker_file: Path):
        """设置内容文件"""
        self.script_file = script_file
        self.ticker_file = ticker_file
        return self
    
    # ==================== 输出设置 ====================
    
    def set_rtmp_output(self, urls: List[str]):
        """设置RTMP推流地址"""
        self.rtmp_urls = urls
        return self
    
    def set_file_output(self, output_file: Path):
        """设置文件输出"""
        self.output_file = output_file
        return self
    
    # ==================== 视频参数 ====================
    
    def set_video_params(self, bitrate: str = "1500k", preset: str = "ultrafast",
                         width: int = 1280, height: int = 720, framerate: int = 25):
        """设置视频参数"""
        self.video_bitrate = bitrate
        self.preset = preset
        self.width = width
        self.height = height
        self.framerate = framerate
        return self
    
    # ==================== 滤镜管理 ====================
    
    def add_video_filter(self, filter_str: str):
        """添加视频滤镜"""
        self.video_filters.append(filter_str)
        return self
    
    def add_audio_filter(self, filter_str: str):
        """添加音频滤镜"""
        self.audio_filters.append(filter_str)
        return self
    
    def set_subtitle_config(self, lines: List[str], current_index: int = 0, 
                             enable_scroll: bool = True, max_width: int = 40):
        """设置字幕配置"""
        self.subtitle_lines = lines
        self.current_line_index = current_index
        self.enable_scroll_subtitle = enable_scroll
        self.subtitle_max_width = max_width
        return self
    
    def _build_video_filters(self) -> str:
        """构建视频滤镜链 - 支持多行字幕和滚动效果"""
        filters = []
        
        # ===== 主字幕区域（支持多行显示）=====
        if self.subtitle_lines:
            # 多行字幕显示（最多显示4行）
            y_start = 480  # 起始Y坐标
            line_height = 45  # 行高
            
            for i, line in enumerate(self.subtitle_lines[:4]):
                # 转义特殊字符
                escaped_line = line.replace("'", "\\'").replace(":", "\\:")
                
                # 当前行高亮（青色），其他行白色
                if i == self.current_line_index:
                    color = "cyan"
                    fontsize = 30
                else:
                    color = "white"
                    fontsize = 28
                
                # 添加半透明背景框效果（通过box参数）
                filter_str = (
                    f"drawtext=fontfile={self.font_path}:"
                    f"text='{escaped_line}':"
                    f"x=50:y={y_start + i * line_height}:"
                    f"fontsize={fontsize}:fontcolor={color}:"
                    f"borderw=2:bordercolor=black@0.7:"
                    f"box=1:boxcolor=0x1a1a2e@0.5:boxborderw=8"
                )
                filters.append(filter_str)
        
        # 如果有字幕文件但无多行字幕，使用传统方式
        elif self.script_file:
            # 检测文本长度，长文本使用滚动效果
            try:
                with open(self.script_file, 'r', encoding='utf-8') as f:
                    script_text = f.read().strip()
                
                if len(script_text) > self.subtitle_max_width and self.enable_scroll_subtitle:
                    # 长文本滚动显示
                    scroll_speed = 30  # 滚动速度(像素/秒)
                    escaped_text = script_text.replace("'", "\\'").replace(":", "\\:")
                    filter_str = (
                        f"drawtext=fontfile={self.font_path}:"
                        f"text='{escaped_text}':"
                        f"x='max(w-tw-50\\,w-50-t*{scroll_speed})':"
                        f"y=h-180:fontsize=30:fontcolor=white:"
                        f"borderw=2:bordercolor=black@0.6"
                    )
                    filters.append(filter_str)
                else:
                    # 短文本静态显示
                    filters.append(
                        f"drawtext=fontfile={self.font_path}:"
                        f"textfile={self.script_file}:reload=1:"
                        f"x=50:y=h-180:fontsize=32:fontcolor=white:"
                        f"borderw=2:bordercolor=black@0.6"
                    )
            except:
                # 文件读取失败，使用默认方式
                filters.append(
                    f"drawtext=fontfile={self.font_path}:"
                    f"textfile={self.script_file}:reload=1:"
                    f"x=50:y=h-180:fontsize=32:fontcolor=white:"
                    f"borderw=2:bordercolor=black@0.6"
                )
        
        # ===== 底部滚动新闻条 =====
        if self.ticker_file:
            filters.append(
                f"drawtext=fontfile={self.font_path}:"
                f"textfile={self.ticker_file}:reload=1:"
                f"x='w-mod(t*80\\,w+tw)':y=h-50:fontsize=22:fontcolor=yellow:"
                f"box=1:boxcolor=black@0.6:boxborderw=4"
            )
        
        # ===== 左上角标题 =====
        filters.append(
            f"drawtext=fontfile={self.font_path}:"
            f"text='AI ANCHOR':"
            f"x=30:y=30:fontsize=24:fontcolor=cyan:"
            f"borderw=1:bordercolor=black@0.5"
        )
        
        # ===== 右上角时间 =====
        filters.append(
            f"drawtext=fontfile={self.font_path}:"
            f"text='%{{localtime}}':"
            f"x=w-220:y=30:fontsize=22:fontcolor=white:"
            f"borderw=1:bordercolor=black@0.5"
        )
        
        # ===== 添加自定义滤镜 =====
        filters.extend(self.video_filters)
        
        return ",".join(filters)
    
    def _get_audio_input_index(self, audio_index: int) -> int:
        """
        获取音频输入的全局索引
        
        当使用图片背景时：
        - 输入0: 图片背景（视频）
        - 输入1: BGM音频
        - 输入2: TTS音频
        
        所以音频索引需要加上视频输入数量
        """
        video_count = 1 if self._bg_image_path and self._bg_image_path.exists() else len(self.video_inputs)
        return video_count + audio_index
    
    def _build_audio_filters(self) -> Optional[str]:
        """构建音频滤镜链"""
        if not self.audio_inputs:
            return None
        
        filters = []
        
        # 如果有多个音频源，使用amix混合
        if len(self.audio_inputs) > 1:
            # 获取正确的音频索引
            bgm_idx = self._get_audio_input_index(0)
            tts_idx = self._get_audio_input_index(1)
            
            # BGM音量控制
            filters.append(f"[{bgm_idx}:a]volume={self.bgm_volume}[bgm]")
            # TTS保持原音量
            filters.append(f"[{tts_idx}:a]volume=1.0[tts]")
            # 混合
            filters.append(f"[bgm][tts]amix=inputs=2:duration=longest[aout]")
            return ";".join(filters)
        elif len(self.audio_inputs) == 1:
            # 只有一个音频源（BGM）- 使用简单滤镜
            return f"volume={self.bgm_volume}"
        
        return None
    
    def _build_filter_complex(self, avatar_index: Optional[int] = None) -> Optional[str]:
        """
        构建 filter_complex（支持智灵视频叠加和音频混合）
        
        这是替代简单 -vf 和 -af 的完整滤镜链
        """
        parts = []
        
        # ===== 视频处理部分 =====
        video_chain = "[0:v]"
        
        # 如果有智灵视频，进行叠加
        if avatar_index is not None and self.avatar_enabled:
            # 智灵视频处理：缩放 + 循环
            avatar_filter = f"[{avatar_index}:v]scale=iw*{self.avatar_scale}:ih*{self.avatar_scale},format=rgba[avatar]"
            parts.append(avatar_filter)
            
            # 叠加智灵到背景
            overlay_filter = f"[0:v][avatar]overlay={self.avatar_position}[v_base]"
            parts.append(overlay_filter)
            video_chain = "[v_base]"
        
        # 添加字幕
        subtitle_filters = self._build_subtitle_filters(video_chain)
        if subtitle_filters:
            parts.append(subtitle_filters)
        
        # ===== 音频处理部分 =====
        if self.audio_inputs:
            audio_filters = self._build_audio_mix_filters(avatar_index)
            if audio_filters:
                parts.append(audio_filters)
        
        return ";".join(parts) if parts else None
    
    def _build_subtitle_filters(self, video_input: str = "[0:v]") -> str:
        """构建字幕滤镜"""
        filters = []
        
        # 主字幕（支持滚动）
        if self.script_file:
            try:
                with open(self.script_file, 'r', encoding='utf-8') as f:
                    script_text = f.read().strip()
                
                # 更彻底的转义
                escaped_text = script_text.replace("'", "'").replace(":", "\\:")
                escaped_text = escaped_text.replace("[", "\\[").replace("]", "\\]")
                
                if len(script_text) > self.subtitle_max_width and self.enable_scroll_subtitle:
                    # 长文本滚动
                    filters.append(
                        f"drawtext=fontfile={self.font_path}:"
                        f"text='{escaped_text}':"
                        f"x='max(w-tw-50\\,w-50-t*30)':"
                        f"y=h-180:fontsize=30:fontcolor=white:"
                        f"borderw=2:bordercolor=black@0.6"
                    )
                else:
                    # 短文本静态 - 使用绝对路径
                    filters.append(
                        f"drawtext=fontfile={self.font_path}:"
                        f"textfile={str(self.script_file.resolve())}:reload=1:"
                        f"x=50:y=h-180:fontsize=32:fontcolor=white:"
                        f"borderw=2:bordercolor=black@0.6"
                    )
            except Exception as e:
                # 如果出错，使用默认文本
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
        
        # 组合滤镜 - 正确格式: [input]filter1,filter2[vout]
        if filters:
            return f"{video_input}{','.join(filters)}[vout]"
        
        return ""
    
    def _build_audio_mix_filters(self, avatar_index: Optional[int] = None) -> Optional[str]:
        """构建音频混合滤镜"""
        if not self.audio_inputs:
            return None
        
        # 计算音频起始索引
        audio_base = 1  # 视频输入占1个
        if avatar_index is not None:
            audio_base = 2  # 视频输入 + 智灵视频输入
        
        filters = []
        
        if len(self.audio_inputs) > 1:
            # 多音频混合
            bgm_idx = audio_base
            tts_idx = audio_base + 1
            
            filters.append(f"[{bgm_idx}:a]volume={self.bgm_volume}[bgm]")
            filters.append(f"[{tts_idx}:a]volume=1.0[tts]")
            filters.append(f"[bgm][tts]amix=inputs=2:duration=longest[aout]")
        else:
            # 单音频
            filters.append(f"[{audio_base}:a]volume={self.bgm_volume}[aout]")
        
        return ";".join(filters)
    
    # ==================== 构建命令 ====================
    
    def build(self) -> List[str]:
        """构建完整的FFmpeg命令"""
        cmd = ['ffmpeg', '-y', '-re']
        
        # ===== 输入源 =====
        input_index = 0
        video_input_count = 0
        
        # 图片背景特殊处理
        if self._bg_image_path and self._bg_image_path.exists():
            # 使用图片作为背景，通过loop无限循环
            cmd.extend([
                '-loop', '1',
                '-i', str(self._bg_image_path),
                '-r', str(self.framerate)
            ])
            input_index += 1
            video_input_count = 1
        else:
            # 视频输入
            for inp in self.video_inputs:
                if inp.type == "file":
                    if inp.options.get("stream_loop"):
                        cmd.extend(['-stream_loop', str(inp.options["stream_loop"])])
                    cmd.extend(['-i', inp.path])
                elif inp.type == "lavfi":
                    cmd.extend(['-f', 'lavfi', '-i', inp.path])
                input_index += 1
                video_input_count += 1
        
        # 智灵视频输入（如果启用）
        avatar_index = None
        if self.avatar_enabled and self.avatar_video and self.avatar_video.exists():
            cmd.extend(['-stream_loop', '-1', '-i', str(self.avatar_video)])
            avatar_index = input_index
            input_index += 1
        
        # 音频输入
        audio_start_index = input_index
        for inp in self.audio_inputs:
            if inp.type == "file":
                if inp.options.get("stream_loop"):
                    cmd.extend(['-stream_loop', str(inp.options["stream_loop"])])
                cmd.extend(['-i', inp.path])
            elif inp.type == "concat":
                cmd.extend(['-f', 'concat', '-safe', '0', '-i', inp.path])
            input_index += 1
        
        # ===== 构建 filter_complex（支持智灵叠加）=====
        filter_complex = self._build_filter_complex(avatar_index)
        has_video_filter = filter_complex is not None
        if filter_complex:
            cmd.extend(['-filter_complex', filter_complex])
        
        # ===== 视频编码 =====
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', self.preset,
            '-tune', 'zerolatency',
            '-b:v', self.video_bitrate,
            '-pix_fmt', 'yuv420p',
            '-g', '50',
        ])
        
        # ===== 音频编码 =====
        if self.audio_inputs:
            cmd.extend([
                '-c:a', 'aac',
                '-b:a', self.audio_bitrate,
                '-ar', str(self.audio_sample_rate),
            ])
        
        # ===== 输出 =====
        # 决定视频映射：有滤镜时映射[vout]，否则映射原始输入
        video_map = '[vout]' if has_video_filter else '0:v'
        
        if len(self.rtmp_urls) > 1:
            # 多推流：使用tee滤镜
            tee_parts = []
            for url in self.rtmp_urls:
                escaped_url = url.replace(':', '\\:')
                tee_parts.append(f"[f=flv:{escaped_url}]")
            tee_url = "|".join(tee_parts)
            # 映射视频和音频
            cmd.extend(['-map', video_map])
            if len(self.audio_inputs) > 1:
                cmd.extend(['-map', '[aout]'])
            elif len(self.audio_inputs) == 1:
                audio_idx = self._get_audio_input_index(0)
                cmd.extend(['-map', f'{audio_idx}:a'])
            cmd.extend(['-f', 'tee', tee_url])
        elif len(self.rtmp_urls) == 1:
            # 单推流
            cmd.extend(['-map', video_map])
            if len(self.audio_inputs) > 1:
                cmd.extend(['-map', '[aout]'])
            elif len(self.audio_inputs) == 1:
                audio_idx = self._get_audio_input_index(0)
                cmd.extend(['-map', f'{audio_idx}:a'])
            cmd.extend(['-f', 'flv', self.rtmp_urls[0]])
        elif self.output_file:
            cmd.extend(['-t', '10', str(self.output_file)])
        else:
            cmd.extend(['-f', 'null', '-'])
        
        return cmd
    
    def build_simple(self) -> List[str]:
        """
        构建简化版命令（用于测试）
        只输出5秒到临时文件
        """
        cmd = ['ffmpeg', '-y']
        
        # 视频输入
        if self.video_inputs:
            inp = self.video_inputs[0]
            if inp.type == "file":
                cmd.extend(['-i', inp.path])
            elif inp.type == "lavfi":
                cmd.extend(['-f', 'lavfi', '-i', inp.path])
        else:
            cmd.extend(['-f', 'lavfi', '-i', f"color=c=black:s={self.width}x{self.height}:d=5"])
        
        # 音频输入
        if self.audio_inputs:
            inp = self.audio_inputs[0]
            cmd.extend(['-i', inp.path])
        
        # 滤镜
        vf = self._build_video_filters()
        if vf:
            cmd.extend(['-vf', vf])
        
        af = self._build_audio_filters()
        if af:
            cmd.extend(['-filter_complex', af])
        
        # 编码
        cmd.extend([
            '-c:v', 'libx264', '-preset', 'ultrafast',
            '-c:a', 'aac',
            '-t', '5',
        ])
        
        # 输出
        if self.output_file:
            cmd.append(str(self.output_file))
        else:
            cmd.extend(['-f', 'null', '-'])
        
        return cmd
    
    # ==================== 测试方法 ====================
    
    def test_syntax(self, duration: float = 1.0) -> Tuple[bool, str]:
        """测试命令语法"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp_output = Path(tmp.name)
        
        try:
            cmd = ['ffmpeg', '-y', '-f', 'lavfi', 
                   '-i', f"color=c=0x1a1a2e:s=320x240:d=2"]
            vf = f"drawtext=fontfile={self.font_path}:text='TEST':x=10:y=10:fontsize=20:fontcolor=white"
            cmd.extend(['-vf', vf, '-c:v', 'libx264', '-preset', 'ultrafast',
                       '-t', str(duration), str(tmp_output)])
            
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            
            if result.returncode != 0:
                return False, result.stderr.decode('utf-8', errors='ignore')[-500:]
            
            if tmp_output.exists() and tmp_output.stat().st_size > 0:
                return True, "OK"
            return False, "输出文件为空"
                
        except subprocess.TimeoutExpired:
            return False, "超时"
        except Exception as e:
            return False, str(e)
        finally:
            if tmp_output.exists():
                tmp_output.unlink()
    
    def test_network(self, rtmp_url: str, timeout: int = 10) -> Tuple[bool, str]:
        """测试RTMP连接"""
        try:
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', 'color=c=black:s=320x240:d=1',
                '-c:v', 'libx264', '-preset', 'ultrafast',
                '-t', '2', '-f', 'flv', rtmp_url
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=timeout + 5)
            
            if result.returncode == 0:
                return True, "连接成功"
            
            stderr = result.stderr.decode('utf-8', errors='ignore')
            if 'Connection refused' in stderr:
                return False, "连接被拒绝"
            elif 'Network' in stderr:
                return False, "网络错误"
            return False, stderr[-300:]
                    
        except subprocess.TimeoutExpired:
            return False, "连接超时"
        except Exception as e:
            return False, str(e)


# =====================================================
# 工厂函数：从插件构建FFmpeg命令
# =====================================================
def build_from_plugins(
    font_path: str,
    video_input: Optional[InputSource],
    audio_inputs: List[InputSource],
    video_filters: List[str],
    script_file: Path,
    ticker_file: Path,
    rtmp_urls: List[str],
    bgm_volume: float = 0.3
) -> List[str]:
    """
    从插件配置构建FFmpeg命令
    """
    builder = FFmpegBuilderV2(font_path=font_path)
    
    # 设置视频输入
    if video_input:
        builder.video_inputs = [video_input]
    else:
        builder.set_color_bg()
    
    # 设置音频输入
    builder.audio_inputs = audio_inputs
    builder.bgm_volume = bgm_volume
    
    # 设置内容
    builder.set_content_files(script_file, ticker_file)
    
    # 添加自定义滤镜
    for vf in video_filters:
        builder.add_video_filter(vf)
    
    # 设置输出
    builder.set_rtmp_output(rtmp_urls)
    
    return builder.build()


# =====================================================
# 测试代码
# =====================================================
if __name__ == "__main__":
    print("=" * 60)
    print("FFmpeg构建器V2测试")
    print("=" * 60)
    
    builder = FFmpegBuilderV2(font_path="/usr/share/fonts/truetype/chinese/msyh.ttf")
    
    # 设置视频输入 - 使用图片背景
    bg_image = Path("/home/z/my-project/cyber_director/assets/bg_frame.png")
    if bg_image.exists():
        builder.set_bg_image(bg_image)
        print(f"✅ 使用图片背景: {bg_image}")
    else:
        builder.set_color_bg("0x1a1a2e")
        print("✅ 使用纯色背景")
    
    # 设置内容
    builder.set_content_files(
        Path("/home/z/my-project/cyber_director/data/script.txt"),
        Path("/home/z/my-project/cyber_director/data/ticker.txt")
    )
    
    # 设置输出
    builder.set_rtmp_output(["rtmp://test.example.com/live/test"])
    
    # 构建命令
    cmd = builder.build()
    
    print("\n生成的FFmpeg命令:")
    print(" ".join(cmd[:10]) + " ...")
    
    print(f"\n视频输入: {len(builder.video_inputs)}")
    print(f"音频输入: {len(builder.audio_inputs)}")
    print(f"推流地址: {len(builder.rtmp_urls)}")
    
    print("=" * 60)
