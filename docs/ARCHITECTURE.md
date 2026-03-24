# AI主播台 - 插件化架构设计

## 📋 架构概览

```
cyber_director/
├── anchor_v2.py          # 主程序入口
├── config.json           # 配置文件
├── start.sh              # 启动脚本
│
├── core/                 # 核心模块
│   ├── config.py         # 配置管理
│   ├── paths.py          # 路径管理
│   ├── plugin_base.py    # 插件基类 + 事件总线
│   └── ffmpeg_builder.py # FFmpeg命令构建器
│
├── plugins/              # 插件目录
│   ├── __init__.py
│   ├── bgm.py            # 背景音乐插件
│   ├── tts.py            # TTS语音插件
│   └── content.py        # 内容生成插件
│
└── assets/               # 资源文件
    ├── bgm/              # 背景音乐
    ├── tts/              # TTS语音缓存
    └── background_loop.mp4
```

## 🔌 插件系统

### 事件驱动模型

```python
from core.plugin_base import PluginBase, Event, EventType

class MyPlugin(PluginBase):
    name = "my_plugin"
    version = "1.0.0"
    description = "我的插件"

    async def on_event(self, event: Event) -> Optional[Event]:
        if event.type == EventType.ON_START:
            # 主程序启动时初始化
            pass
        elif event.type == EventType.ON_CONTENT_UPDATE:
            # 内容更新时处理
            pass
        return None  # 或返回新事件触发链式反应

    def get_ffmpeg_inputs(self) -> List[Dict]:
        # 返回需要的FFmpeg输入源
        return []

    def get_ffmpeg_filters(self) -> List[str]:
        # 返回需要的滤镜
        return []
```

### 可用事件类型

| 事件 | 触发时机 |
|------|----------|
| `ON_START` | 主程序启动 |
| `ON_STOP` | 主程序停止 |
| `ON_CONTENT_UPDATE` | 定时内容更新 |
| `ON_NEWS_GENERATED` | 新闻生成完成 |
| `ON_TTS_REQUIRED` | 需要生成TTS |
| `ON_TTS_READY` | TTS文件就绪 |
| `ON_STREAM_START` | 推流开始 |
| `ON_STREAM_ERROR` | 推流错误 |

### FFmpeg集成

插件可以通过两种方式影响FFmpeg：

1. **输入源** (`get_ffmpeg_inputs`)
```python
def get_ffmpeg_inputs(self):
    return [{
        "type": "file",          # file, lavfi, concat
        "path": "/path/to/audio.mp3",
        "label": "bgm",          # 用于滤镜引用
        "options": {
            "stream_loop": -1    # 循环播放
        }
    }]
```

2. **滤镜** (`get_ffmpeg_filters`)
```python
def get_ffmpeg_filters(self):
    return ["overlay=x=10:y=10"]  # 视频滤镜
```

## 🎵 BGM插件

### 配置
```json
{
    "plugins": {
        "bgm": {
            "enabled": true,
            "dir": "assets/bgm",
            "volume": 0.3,
            "shuffle": true,
            "fade_in": 2,
            "fade_out": 2
        }
    }
}
```

### 添加自定义BGM
将MP3文件放入 `assets/bgm/` 目录即可自动发现和播放。

### 支持格式
- MP3
- WAV
- AAC
- FLAC
- OGG
- M4A

## 🗣️ TTS插件

### 配置
```json
{
    "plugins": {
        "tts": {
            "enabled": true,
            "output_dir": "assets/tts",
            "voice": "alloy",
            "speed": 1.0,
            "auto_play": true
        }
    }
}
```

### 工作流程
1. 内容插件生成新闻文本
2. 触发 `ON_NEWS_GENERATED` 事件
3. TTS插件接收事件，调用z-ai-sdk生成语音
4. 生成的音频加入播放队列

## 📰 内容插件

### 配置
```json
{
    "plugins": {
        "content": {
            "enabled": true,
            "update_interval": 60,
            "news_sources": [
                "AI技术突破：大模型推理速度提升10倍",
                "科技前沿：量子计算进入实用阶段"
            ]
        }
    }
}
```

### 扩展内容源
```python
class CustomContentPlugin(ContentPlugin):
    async def fetch_news(self):
        # 从API获取新闻
        response = await aiohttp.get("https://api.news.com/latest")
        return response.json()
```

## 🔧 FFmpeg构建器

### 基本使用
```python
from core.ffmpeg_builder import FFmpegBuilderV2, InputSource

builder = FFmpegBuilderV2(font_path="/path/to/font.ttf")

# 设置视频输入
builder.set_bg_video(Path("background.mp4"), loop=True)
# 或纯色背景
# builder.set_color_bg("0x1a1a2e")

# 设置BGM
builder.set_bgm(Path("bgm.mp3"), volume=0.3)

# 设置内容
builder.set_content_files(script_file, ticker_file)

# 设置输出
builder.set_rtmp_output(["rtmp://example.com/live/stream"])

# 构建命令
cmd = builder.build()
```

### 多音轨混合
```python
# 添加多个音频源
builder.add_audio_input(InputSource(
    type="file",
    path="bgm.mp3",
    label="bgm"
))
builder.add_audio_input(InputSource(
    type="file",
    path="voice.mp3",
    label="voice"
))

# FFmpeg会自动使用amix滤镜混合
```

## 📦 扩展新插件

### 创建新插件

1. 在 `plugins/` 目录创建文件
```python
# plugins/weather.py
from core.plugin_base import PluginBase, Event, EventType

class WeatherPlugin(PluginBase):
    name = "weather"
    version = "1.0.0"
    description = "天气播报插件"

    async def on_event(self, event):
        if event.type == EventType.ON_START:
            # 初始化天气API
            pass
        elif event.type == EventType.ON_CONTENT_UPDATE:
            # 返回天气信息
            weather = await self.fetch_weather()
            return Event(EventType.ON_NEWS_GENERATED, {
                "text": f"今日天气: {weather}"
            })
        return None

    def get_ffmpeg_inputs(self):
        return []

    def get_ffmpeg_filters(self):
        return []
```

2. 在 `plugins/__init__.py` 注册
```python
from .weather import WeatherPlugin
__all__ = [..., "WeatherPlugin"]
```

3. 在配置中启用
```json
{
    "plugins": {
        "weather": {
            "enabled": true,
            "api_key": "your_api_key"
        }
    }
}
```

4. 在主程序中加载
```python
# anchor_v2.py
from plugins.weather import WeatherPlugin
if plugin_configs.get("weather", {}).get("enabled"):
    self.plugins["weather"] = WeatherPlugin(plugin_configs.get("weather", {}))
    self.event_bus.register(self.plugins["weather"])
```

## 🚀 运维命令

```bash
# 启动
./start.sh start

# 停止
./start.sh stop

# 重启
./start.sh restart

# 状态
./start.sh status

# 日志
./start.sh log

# 测试插件
./start.sh test
```

## 📊 性能考虑

1. **BGM循环播放**：使用 `-stream_loop -1` 避免重复读取文件
2. **TTS缓存**：相同文本复用已生成的语音文件
3. **滤镜链**：FFmpeg原生滤镜链比Python帧处理快10x+
4. **多进程推流**：每个平台独立进程，避免单点故障

## 🔮 未来扩展

- [ ] AI视频生成插件
- [ ] 实时字幕插件
- [ ] 观众互动插件（弹幕互动）
- [ ] 多语言TTS切换
- [ ] 动态背景生成
- [ ] 虚拟形象驱动
