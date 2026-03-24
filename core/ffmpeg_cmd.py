#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFmpeg 命令构建模块
===================
职责：构建和验证FFmpeg命令
支持：多平台同时推流（使用tee滤镜）
"""

import subprocess
import tempfile
import os
from pathlib import Path
from typing import List, Optional, Tuple

class FFmpegBuilder:
    """FFmpeg命令构建器"""
    
    def __init__(self, font_path: str, bg_video: Optional[Path] = None):
        self.font_path = font_path
        self.bg_video = bg_video
        self.script_file = None
        self.ticker_file = None
        self.rtmp_urls = []  # 支持多推流地址
        self.bitrate = "1500k"
        self.preset = "ultrafast"
        self.width = 1280
        self.height = 720
    
    def set_content_files(self, script_file: Path, ticker_file: Path):
        """设置内容文件"""
        self.script_file = script_file
        self.ticker_file = ticker_file
        return self
    
    def set_output(self, rtmp_urls: List[str] = None, output_file: Optional[Path] = None):
        """设置输出目标（支持多推流地址）"""
        self.rtmp_urls = rtmp_urls or []
        self.output_file = output_file
        return self
    
    def set_video_params(self, bitrate: str = "1500k", preset: str = "ultrafast"):
        """设置视频参数"""
        self.bitrate = bitrate
        self.preset = preset
        return self
    
    def build(self) -> List[str]:
        """构建完整的FFmpeg命令"""
        cmd = ['ffmpeg', '-y', '-re']
        
        # 输入源
        if self.bg_video and self.bg_video.exists():
            cmd.extend(['-stream_loop', '-1', '-i', str(self.bg_video)])
        else:
            cmd.extend([
                '-f', 'lavfi',
                '-i', f"color=c=0x1a1a2e:s={self.width}x{self.height}:r=25"
            ])
        
        # 构建滤镜
        vf_filter = self._build_filter()
        cmd.extend(['-vf', vf_filter])
        
        # 视频编码
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', self.preset,
            '-tune', 'zerolatency',
            '-b:v', self.bitrate,
            '-pix_fmt', 'yuv420p',
            '-g', '50',
        ])
        
        # 输出
        if len(self.rtmp_urls) > 1:
            # 多推流：使用tee滤镜
            # 格式: [f=flv:rtmp_url1]|[f=flv:rtmp_url2]
            tee_parts = []
            for url in self.rtmp_urls:
                # 对URL中的特殊字符进行转义
                escaped_url = url.replace(':', '\\:')
                tee_parts.append(f"[f=flv:{escaped_url}]")
            tee_url = "|".join(tee_parts)
            cmd.extend(['-f', 'tee', '-map', '0:v', tee_url])
        elif len(self.rtmp_urls) == 1:
            # 单推流
            cmd.extend(['-f', 'flv', self.rtmp_urls[0]])
        elif hasattr(self, 'output_file') and self.output_file:
            cmd.extend(['-t', '5', str(self.output_file)])
        else:
            cmd.extend(['-f', 'null', '-'])
        
        return cmd
    
    def _build_filter(self) -> str:
        """构建滤镜链"""
        filters = []
        
        if self.script_file:
            filters.append(
                f"drawtext=fontfile={self.font_path}:"
                f"textfile={self.script_file}:reload=1:"
                f"x=50:y=h-180:fontsize=32:fontcolor=white:"
                f"borderw=2:bordercolor=black@0.6"
            )
        
        if self.ticker_file:
            filters.append(
                f"drawtext=fontfile={self.font_path}:"
                f"textfile={self.ticker_file}:reload=1:"
                f"x='w-mod(t*80\\,w+tw)':y=h-50:fontsize=22:fontcolor=yellow:"
                f"box=1:boxcolor=black@0.6:boxborderw=4"
            )
        
        filters.append(
            f"drawtext=fontfile={self.font_path}:"
            f"text='AI ANCHOR':"
            f"x=30:y=30:fontsize=24:fontcolor=cyan:"
            f"borderw=1:bordercolor=black@0.5"
        )
        
        filters.append(
            f"drawtext=fontfile={self.font_path}:"
            f"text='%{{localtime}}':"
            f"x=w-220:y=30:fontsize=22:fontcolor=white:"
            f"borderw=1:bordercolor=black@0.5"
        )
        
        return ",".join(filters)
    
    def test_syntax(self, duration: float = 1.0) -> Tuple[bool, str]:
        """测试命令语法"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp_output = Path(tmp.name)
        
        try:
            cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', f"color=c=0x1a1a2e:s=320x240:d=2"]
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


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from paths import PathManager
    from config import Config
    
    print("=" * 50)
    print("FFmpeg模块测试")
    print("=" * 50)
    
    pm = PathManager()
    config = Config()
    font = pm.find_font()
    
    # 获取所有启用的推流地址
    rtmp_urls = []
    for p in config._config.get("platforms", {}).values():
        if p.get("enabled") and p.get("rtmp_url"):
            rtmp_urls.append(p["rtmp_url"])
    
    print(f"\n推流目标: {len(rtmp_urls)} 个平台")
    for url in rtmp_urls:
        print(f"  - {url.split('?')[0]}")
    
    builder = FFmpegBuilder(font_path=font, bg_video=pm.background_video)
    builder.set_content_files(pm.script_file, pm.ticker_file)
    builder.set_output(rtmp_urls=rtmp_urls)
    
    print(f"\n命令测试:")
    ok, msg = builder.test_syntax()
    print(f"  语法: {'✅' if ok else '❌'} {msg}")
    
    print("\n" + "=" * 50)
