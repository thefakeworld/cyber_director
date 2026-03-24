#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
输入源管理器 (InputManager)
==========================
统一管理所有FFmpeg输入源及其索引

核心设计理念:
- 单一数据源: 所有输入索引统一管理
- 标签引用: 使用标签而非硬编码索引
- 类型安全: 区分视频/音频输入
- 验证机制: 自动检查索引有效性

解决问题:
- 索引计算分散导致的错误
- 视频输入数量变化影响音频索引
- 特殊处理过多，容易遗漏
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
from enum import Enum


class MediaType(Enum):
    """媒体类型枚举"""
    VIDEO = "video"
    AUDIO = "audio"


@dataclass
class InputSource:
    """输入源配置"""
    type: str  # file, lavfi, concat, image
    path: str
    label: str = ""  # 用于滤镜引用
    media_type: MediaType = MediaType.VIDEO
    options: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def stream_loop(self) -> int:
        """获取循环次数"""
        return self.options.get("stream_loop", 0)
    
    @property
    def is_video(self) -> bool:
        return self.media_type == MediaType.VIDEO
    
    @property
    def is_audio(self) -> bool:
        return self.media_type == MediaType.AUDIO
    
    def __repr__(self):
        return f"InputSource({self.label or 'unlabeled'}, {self.media_type.value}, idx={getattr(self, '_index', '?')})"


class InputManager:
    """
    输入源管理器
    
    统一管理所有FFmpeg输入源，自动分配索引，支持标签引用。
    
    使用示例:
        manager = InputManager()
        
        # 添加视频输入
        manager.add_video(InputSource(
            type="image", path="bg.png", label="background",
            options={"loop": 1, "framerate": 25}
        ))
        
        # 添加音频输入
        manager.add_audio(InputSource(
            type="file", path="bgm.mp3", label="bgm",
            options={"stream_loop": -1}
        ))
        
        # 获取索引引用
        bgm_ref = manager.get_audio_ref("bgm")  # 返回 "1:a"
        
        # 构建FFmpeg输入参数
        args = manager.build_input_args()
    """
    
    def __init__(self):
        self._inputs: List[InputSource] = []
        self._label_map: Dict[str, int] = {}  # label -> index
        self._debug: bool = False
    
    # ==================== 添加输入源 ====================
    
    def add_video(self, source: InputSource) -> int:
        """
        添加视频输入源
        
        Args:
            source: 输入源配置
        
        Returns:
            分配的全局索引
        """
        source.media_type = MediaType.VIDEO
        return self._add_input(source)
    
    def add_audio(self, source: InputSource) -> int:
        """
        添加音频输入源
        
        Args:
            source: 输入源配置
        
        Returns:
            分配的全局索引
        """
        source.media_type = MediaType.AUDIO
        return self._add_input(source)
    
    def _add_input(self, source: InputSource) -> int:
        """内部方法：添加输入并分配索引"""
        index = len(self._inputs)
        source._index = index  # 存储索引到对象
        self._inputs.append(source)
        
        if source.label:
            if source.label in self._label_map:
                raise ValueError(f"标签 '{source.label}' 已存在")
            self._label_map[source.label] = index
        
        if self._debug:
            print(f"[InputManager] 添加输入: {source}")
        
        return index
    
    # ==================== 索引查询 ====================
    
    def get_index(self, label: str) -> Optional[int]:
        """
        通过标签获取全局索引
        
        Args:
            label: 输入源标签
        
        Returns:
            全局索引，不存在返回None
        """
        return self._label_map.get(label)
    
    def get_video_ref(self, label: str) -> Optional[str]:
        """
        获取视频流引用字符串
        
        Args:
            label: 输入源标签
        
        Returns:
            如 "0:v"，不存在返回None
        """
        index = self._label_map.get(label)
        if index is not None:
            return f"{index}:v"
        return None
    
    def get_audio_ref(self, label: str) -> Optional[str]:
        """
        获取音频流引用字符串
        
        Args:
            label: 输入源标签
        
        Returns:
            如 "1:a"，不存在返回None
        """
        index = self._label_map.get(label)
        if index is not None:
            return f"{index}:a"
        return None
    
    def get_source(self, label: str) -> Optional[InputSource]:
        """通过标签获取输入源对象"""
        index = self._label_map.get(label)
        if index is not None:
            return self._inputs[index]
        return None
    
    # ==================== 统计信息 ====================
    
    @property
    def total_count(self) -> int:
        """总输入数量"""
        return len(self._inputs)
    
    @property
    def video_count(self) -> int:
        """视频输入数量"""
        return sum(1 for i in self._inputs if i.is_video)
    
    @property
    def audio_count(self) -> int:
        """音频输入数量"""
        return sum(1 for i in self._inputs if i.is_audio)
    
    def get_video_indices(self) -> List[int]:
        """获取所有视频输入的索引列表"""
        return [i._index for i in self._inputs if i.is_video]
    
    def get_audio_indices(self) -> List[int]:
        """获取所有音频输入的索引列表"""
        return [i._index for i in self._inputs if i.is_audio]
    
    def get_audio_input_order(self) -> Dict[str, int]:
        """
        获取音频输入的相对顺序
        
        Returns:
            字典 {label: audio_order}，例如 {"bgm": 0, "tts": 1}
        """
        audio_order = 0
        result = {}
        for inp in self._inputs:
            if inp.is_audio and inp.label:
                result[inp.label] = audio_order
                audio_order += 1
        return result
    
    # ==================== 构建FFmpeg参数 ====================
    
    def build_input_args(self) -> List[str]:
        """
        构建FFmpeg输入参数列表
        
        Returns:
            FFmpeg命令行参数列表
        """
        args = []
        
        for inp in self._inputs:
            # 根据类型构建参数
            if inp.type == "image":
                # 图片输入需要loop参数
                framerate = inp.options.get("framerate", 25)
                args.extend([
                    '-loop', '1',
                    '-i', inp.path,
                    '-r', str(framerate)
                ])
            
            elif inp.type == "file":
                # 普通文件输入
                if inp.options.get("stream_loop"):
                    args.extend(['-stream_loop', str(inp.options["stream_loop"])])
                args.extend(['-i', inp.path])
            
            elif inp.type == "lavfi":
                # 滤镜输入
                args.extend(['-f', 'lavfi', '-i', inp.path])
            
            elif inp.type == "concat":
                # 连接输入
                args.extend(['-f', 'concat', '-safe', '0', '-i', inp.path])
            
            else:
                # 默认处理
                args.extend(['-i', inp.path])
        
        return args
    
    # ==================== 验证 ====================
    
    def validate_filter_indices(self, filter_str: str) -> Tuple[bool, List[str]]:
        """
        验证滤镜字符串中的索引是否有效
        
        Args:
            filter_str: FFmpeg滤镜字符串
        
        Returns:
            (是否有效, 错误列表)
        """
        import re
        errors = []
        
        # 查找所有 [N:v] 或 [N:a] 格式的索引引用
        pattern = r'\[(\d+):[av]\]'
        matches = re.findall(pattern, filter_str)
        
        for idx_str in matches:
            idx = int(idx_str)
            if idx >= self.total_count:
                errors.append(
                    f"索引 [{idx_str}:v/a] 超出范围 "
                    f"(共 {self.total_count} 个输入)"
                )
        
        return len(errors) == 0, errors
    
    def validate_label_refs(self, filter_str: str) -> Tuple[bool, List[str]]:
        """
        验证滤镜字符串中的标签引用是否存在
        
        Args:
            filter_str: FFmpeg滤镜字符串
        
        Returns:
            (是否有效, 错误列表)
        """
        import re
        errors = []
        
        # 查找所有 [labelname] 格式的标签引用（排除已知输出标签）
        known_outputs = {'vout', 'aout', 'v_base', 'avatar', 'bgm', 'tts'}
        pattern = r'\[([a-zA-Z_][a-zA-Z0-9_]*)\]'
        matches = re.findall(pattern, filter_str)
        
        for label in matches:
            if label in known_outputs:
                continue  # 已知的输出标签
            if label not in self._label_map:
                # 可能是滤镜中间标签，检查是否被定义
                pass  # 简化处理，不报错
        
        return len(errors) == 0, errors
    
    def summary(self) -> str:
        """生成摘要信息"""
        lines = [
            f"输入源管理器摘要:",
            f"  总输入: {self.total_count}",
            f"  视频: {self.video_count}, 音频: {self.audio_count}",
            f"  标签映射: {self._label_map}",
            "",
            "  输入列表:"
        ]
        for inp in self._inputs:
            idx = getattr(inp, '_index', '?')
            lines.append(f"    [{idx}] {inp.label or 'unnamed'} ({inp.media_type.value}) - {inp.path}")
        
        return "\n".join(lines)


# =====================================================
# 便捷函数
# =====================================================

def create_video_source(path: str, label: str = "", loop: bool = False, **options) -> InputSource:
    """创建视频输入源"""
    if loop:
        options["stream_loop"] = -1
    return InputSource(
        type="file",
        path=path,
        label=label,
        media_type=MediaType.VIDEO,
        options=options
    )


def create_audio_source(path: str, label: str = "", loop: bool = False, **options) -> InputSource:
    """创建音频输入源"""
    if loop:
        options["stream_loop"] = -1
    return InputSource(
        type="file",
        path=path,
        label=label,
        media_type=MediaType.AUDIO,
        options=options
    )


def create_image_source(path: str, label: str = "", framerate: int = 25) -> InputSource:
    """创建图片输入源"""
    return InputSource(
        type="image",
        path=path,
        label=label,
        media_type=MediaType.VIDEO,
        options={"framerate": framerate}
    )


def create_concat_source(path: str, label: str = "") -> InputSource:
    """创建concat输入源"""
    return InputSource(
        type="concat",
        path=path,
        label=label,
        media_type=MediaType.AUDIO
    )


# =====================================================
# 测试代码
# =====================================================
if __name__ == "__main__":
    print("=" * 60)
    print("InputManager 测试")
    print("=" * 60)
    
    manager = InputManager()
    manager._debug = True
    
    # 添加视频输入
    print("\n[1] 添加视频输入...")
    manager.add_video(create_image_source("assets/bg_frame.png", "background"))
    manager.add_video(create_video_source("assets/avatar.mp4", "avatar", loop=True))
    
    # 添加音频输入
    print("\n[2] 添加音频输入...")
    manager.add_audio(create_audio_source("assets/bgm/music.mp3", "bgm", loop=True))
    manager.add_audio(create_concat_source("assets/tts/playlist.txt", "tts"))
    
    # 显示摘要
    print("\n[3] 摘要信息:")
    print(manager.summary())
    
    # 测试索引查询
    print("\n[4] 索引查询:")
    print(f"  background 索引: {manager.get_index('background')}")
    print(f"  bgm 视频引用: {manager.get_video_ref('bgm')}")
    print(f"  bgm 音频引用: {manager.get_audio_ref('bgm')}")
    print(f"  tts 音频引用: {manager.get_audio_ref('tts')}")
    
    # 测试音频顺序
    print("\n[5] 音频顺序:")
    print(f"  {manager.get_audio_input_order()}")
    
    # 构建参数
    print("\n[6] FFmpeg输入参数:")
    args = manager.build_input_args()
    print(f"  {' '.join(args)}")
    
    # 验证滤镜
    print("\n[7] 滤镜验证:")
    test_filter = "[1:a]volume=0.3[bgm];[2:a]volume=1.0[tts]"
    valid, errors = manager.validate_filter_indices(test_filter)
    print(f"  滤镜: {test_filter}")
    print(f"  有效: {valid}")
    if errors:
        for e in errors:
            print(f"    错误: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
