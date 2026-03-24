#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
============
职责：加载配置、验证配置、提供默认值
特点：可独立测试，不依赖其他模块
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List

class Config:
    """配置管理器"""
    
    # 项目根目录（绝对路径）
    PROJECT_DIR = Path(__file__).parent.parent.resolve()
    
    # 默认配置
    DEFAULTS = {
        "video": {
            "width": 1280,
            "height": 720,
            "bitrate": "1500k",
            "preset": "ultrafast"
        },
        "content": {
            "update_interval": 60
        }
    }
    
    def __init__(self, config_file: Optional[str] = None):
        self._config: Dict[str, Any] = {}
        self._errors: list = []
        
        # 配置文件路径（绝对路径）
        if config_file:
            self.config_path = Path(config_file)
        else:
            self.config_path = self.PROJECT_DIR / "config.json"
        
        self._load()
    
    def _load(self) -> bool:
        """加载配置文件"""
        if not self.config_path.exists():
            self._errors.append(f"配置文件不存在: {self.config_path}")
            return False
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            return True
        except json.JSONDecodeError as e:
            self._errors.append(f"配置文件格式错误: {e}")
            return False
        except Exception as e:
            self._errors.append(f"加载配置失败: {e}")
            return False
    
    def get(self, *keys, default=None):
        """获取配置值，支持嵌套访问"""
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                # 尝试从默认值获取
                default_value = self.DEFAULTS
                for k in keys:
                    if isinstance(default_value, dict) and k in default_value:
                        default_value = default_value[k]
                    else:
                        return default
                return default_value
        return value
    
    def get_rtmp_url(self) -> Optional[str]:
        """获取第一个启用的推流地址"""
        platforms = self._config.get("platforms", {})
        for platform_id, platform in platforms.items():
            if platform.get("enabled") and platform.get("rtmp_url"):
                return platform["rtmp_url"]
        return None
    
    def get_rtmp_urls(self) -> List[str]:
        """获取所有启用的推流地址"""
        urls = []
        platforms = self._config.get("platforms", {})
        for platform_id, platform in platforms.items():
            if platform.get("enabled") and platform.get("rtmp_url"):
                urls.append(platform["rtmp_url"])
        return urls
    
    def get_platform_names(self) -> List[str]:
        """获取所有启用的平台名称"""
        names = []
        platforms = self._config.get("platforms", {})
        for platform_id, platform in platforms.items():
            if platform.get("enabled"):
                names.append(platform.get("name", platform_id))
        return names
    
    def get_platform_name(self) -> str:
        """获取当前平台名称"""
        platforms = self._config.get("platforms", {})
        for platform_id, platform in platforms.items():
            if platform.get("enabled"):
                return platform.get("name", platform_id)
        return "未知平台"
    
    @property
    def errors(self) -> list:
        return self._errors
    
    def is_valid(self) -> bool:
        return len(self._errors) == 0 and bool(self._config)
    
    def validate(self) -> tuple:
        """验证配置完整性"""
        errors = []
        warnings = []
        
        # 检查推流地址
        if not self.get_rtmp_url():
            warnings.append("没有启用任何推流平台")
        
        # 检查视频参数
        video = self._config.get("video", {})
        if video.get("bitrate"):
            bitrate = video["bitrate"]
            if not bitrate.endswith('k') and not bitrate.endswith('M'):
                errors.append(f"码率格式错误: {bitrate}")
        
        return len(errors) == 0, errors, warnings


# =====================================================
# 单元测试（可直接运行此文件测试）
# =====================================================
if __name__ == "__main__":
    print("=" * 50)
    print("配置模块测试")
    print("=" * 50)
    
    config = Config()
    
    # 测试1：配置加载
    print(f"\n[测试1] 配置文件加载")
    print(f"  路径: {config.config_path}")
    print(f"  状态: {'✅ 成功' if config.is_valid() else '❌ 失败'}")
    if config.errors:
        for err in config.errors:
            print(f"  错误: {err}")
    
    # 测试2：推流地址
    print(f"\n[测试2] 推流配置")
    url = config.get_rtmp_url()
    print(f"  平台: {config.get_platform_name()}")
    if url:
        display = url.split('?')[0] if '?' in url else url
        print(f"  地址: {display}...")
    else:
        print(f"  状态: ⚠️ 未配置推流地址")
    
    # 测试3：配置验证
    print(f"\n[测试3] 配置验证")
    valid, errors, warnings = config.validate()
    print(f"  结果: {'✅ 通过' if valid else '❌ 失败'}")
    for err in errors:
        print(f"  错误: {err}")
    for warn in warnings:
        print(f"  警告: {warn}")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
