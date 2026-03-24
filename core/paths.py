#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径管理模块
============
职责：统一管理所有路径，确保使用绝对路径
特点：单一职责，消除路径相关bug
"""

import os
from pathlib import Path
from typing import Optional

class PathManager:
    """路径管理器 - 确保所有路径都是绝对路径"""
    
    def __init__(self, project_dir: Optional[Path] = None):
        # 项目根目录（绝对路径）
        self.project_dir = project_dir or Path(__file__).parent.parent.resolve()
        
        # 核心目录
        self.assets_dir = self.project_dir / "assets"
        self.data_dir = self.project_dir / "data"
        self.logs_dir = self.project_dir / "logs"
        self.output_dir = self.project_dir / "output"
        self.tts_dir = self.assets_dir / "tts"  # TTS音频目录
        
        # 确保目录存在
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保必要目录存在"""
        for dir_path in [self.data_dir, self.logs_dir, self.output_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    # ==================== 资源文件 ====================
    
    @property
    def background_video(self) -> Path:
        """背景视频路径"""
        return self.assets_dir / "background_loop.mp4"
    
    @property
    def background_image(self) -> Path:
        """背景图片路径"""
        return self.assets_dir / "bg_frame.png"
    
    @property
    def logo_image(self) -> Path:
        """Logo图片路径"""
        return self.assets_dir / "logo.png"
    
    # ==================== 数据文件 ====================
    
    @property
    def script_file(self) -> Path:
        """主播文本文件"""
        return self.data_dir / "script.txt"
    
    @property
    def ticker_file(self) -> Path:
        """滚动条文本文件"""
        return self.data_dir / "ticker.txt"
    
    @property
    def pid_file(self) -> Path:
        """PID文件"""
        return self.data_dir / "anchor.pid"
    
    @property
    def status_file(self) -> Path:
        """状态文件"""
        return self.data_dir / "status.json"
    
    # ==================== 日志文件 ====================
    
    def get_log_file(self, name: str = "anchor") -> Path:
        """获取日志文件路径"""
        from datetime import datetime
        date_str = datetime.now().strftime('%Y%m%d')
        return self.logs_dir / f"{name}_{date_str}.log"
    
    # ==================== 验证方法 ====================
    
    def check_requirements(self) -> tuple:
        """
        检查必要资源是否存在
        返回: (是否全部存在, 缺失列表)
        """
        missing = []
        
        # 必须存在的目录
        for dir_path in [self.assets_dir]:
            if not dir_path.exists():
                missing.append(f"目录: {dir_path}")
        
        # 背景视频可选（可以用纯色替代）
        if not self.background_video.exists():
            pass  # 不报错，会使用纯色背景
        
        return len(missing) == 0, missing
    
    def find_font(self) -> str:
        """查找可用字体"""
        font_candidates = [
            "/usr/share/fonts/truetype/chinese/msyh.ttf",      # 微软雅黑
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",    # 文泉驿
            "/usr/share/fonts/truetype/chinese/SimKai.ttf",    # 楷体
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
        
        for font in font_candidates:
            if os.path.exists(font):
                return font
        
        return "sans"  # 系统默认
    
    def check_font(self) -> tuple:
        """检查字体是否可用"""
        font = self.find_font()
        return font != "sans", font


# =====================================================
# 单元测试
# =====================================================
if __name__ == "__main__":
    print("=" * 50)
    print("路径模块测试")
    print("=" * 50)
    
    pm = PathManager()
    
    # 测试1：路径解析
    print(f"\n[测试1] 路径解析")
    print(f"  项目目录: {pm.project_dir}")
    print(f"  背景视频: {pm.background_video}")
    print(f"  主播文本: {pm.script_file}")
    
    # 测试2：资源检查
    print(f"\n[测试2] 资源检查")
    ok, missing = pm.check_requirements()
    print(f"  状态: {'✅ 完整' if ok else '❌ 缺失'}")
    for item in missing:
        print(f"  缺失: {item}")
    
    # 测试3：字体检查
    print(f"\n[测试3] 字体检查")
    has_font, font_path = pm.check_font()
    print(f"  状态: {'✅ 找到' if has_font else '⚠️ 使用默认'}")
    print(f"  字体: {font_path}")
    
    # 测试4：背景视频
    print(f"\n[测试4] 背景视频")
    if pm.background_video.exists():
        size = pm.background_video.stat().st_size / 1024
        print(f"  状态: ✅ 存在")
        print(f"  大小: {size:.1f} KB")
    else:
        print(f"  状态: ⚠️ 不存在（将使用纯色背景）")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
