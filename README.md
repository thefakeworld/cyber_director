# AI主播台 - AI助手操作手册

## 项目概述

AI主播台是一个全自动化的直播推流系统，具备以下特性：
- 📺 **双平台推流**：斗鱼 + YouTube
- 🎙️ **TTS语音播报**：多风格语音合成
- 📝 **实时新闻抓取**：自动获取热点新闻
- 🎵 **背景音乐**：自动播放BGM
- 📄 **字幕同步**：多行字幕滚动显示
- 🎭 **智灵主播**：AI虚拟形象叠加

## ⚠️ 重要：启动流程规范

### 禁止事项
```
❌ 禁止使用 timeout 命令测试服务进程
❌ 禁止前台运行等待输出
❌ 禁止反复执行相同命令
❌ 禁止用bash命令测试，必须写测试函数
```

### 标准启动方式
```bash
cd /home/z/my-project/cyber_director

# 方式1: 使用快速启动脚本（推荐）
bash scripts/quick_start.sh

# 方式2: 使用原有启动脚本
./start.sh start    # 启动
./start.sh status   # 查看状态
./start.sh stop     # 停止
```

### 判断标准
```
脚本输出 "✅ 运行中" = 成功
脚本输出 "❌ 未运行" = 失败，查看日志
```

## 快速命令

| 操作 | 命令 |
|------|------|
| 快速启动 | `bash scripts/quick_start.sh` |
| 运行测试 | `bash scripts/run_tests.sh` |
| 启动 | `./start.sh start` |
| 状态 | `./start.sh status` |
| 停止 | `./start.sh stop` |
| 日志 | `tail -f logs/console.log` |

## 测试套件

```bash
# 运行所有测试
bash scripts/run_tests.sh

# 运行单项测试
bash scripts/run_tests.sh audio     # 音频索引测试
bash scripts/run_tests.sh subtitle  # 字幕同步测试
bash scripts/run_tests.sh avatar    # 智灵叠加测试
bash scripts/run_tests.sh news      # 热插拔新闻测试
```

## 热插拔新闻（突发新闻）

```bash
# 添加突发新闻
cd /home/z/my-project/cyber_director
python3 scripts/hot_news.py

# 或自定义新闻
python3 -c "
from scripts.hot_news import add_breaking_news
add_breaking_news(
    title='新闻标题',
    content='新闻内容',
    source='来源'
)
"
```

## 项目结构

```
cyber_director/
├── anchor_v2.py          # 主程序（插件化）
├── config.json           # 配置文件
├── start.sh              # 启动脚本
├── scripts/
│   ├── quick_start.sh    # 快速启动（推荐）
│   ├── run_tests.sh      # 测试套件
│   ├── hot_news.py       # 热插拔新闻
│   └── test_*.py         # 各项测试
├── core/
│   ├── plugin_base.py    # 插件基类
│   ├── ffmpeg_builder.py # FFmpeg构建器
│   ├── subtitle_manager.py # 字幕同步管理器
│   └── hot_news.py       # 热插拔新闻管理
├── plugins/
│   ├── bgm.py           # 背景音乐插件
│   ├── tts.py           # TTS语音插件
│   ├── content.py       # 内容生成插件
│   └── news_fetcher.py  # 新闻抓取插件
├── assets/
│   ├── bgm/             # 背景音乐
│   ├── avatar.mp4       # 智灵视频
│   └── bg_frame.png     # 背景图片
└── docs/
    ├── ARCHITECTURE.md  # 架构文档
    ├── DEV_CHECKLIST.md # 开发规范
    ├── DEV_REVIEW_20240324.md # 复盘文档
    └── REVIEW_SUBTITLE_SYNC.md # 详细复盘
```

## 日志位置

```
logs/anchor.log          # 主日志
logs/ffmpeg_*.log        # FFmpeg推流日志
logs/console.log         # 控制台输出
```

## 直播间地址

```
斗鱼: https://www.douyu.com/12898962
```

## 开发规范

详见 [DEV_CHECKLIST.md](docs/DEV_CHECKLIST.md)

### 测试规范
```bash
# 正确方式 - 运行测试脚本
bash scripts/run_tests.sh

# 错误方式
python -c "from xxx import yyy; ..."
```

### 进程管理
```bash
# 检查残留进程
pgrep -f "anchor_v2.py" && echo "发现残留进程"

# 清理残留进程
pkill -f "anchor_v2.py"
pkill -f "ffmpeg.*rtmp"
```

## 常见问题

### 1. 启动失败
```bash
# 检查日志
tail -50 logs/console.log
tail -50 logs/ffmpeg_斗鱼直播.log
```

### 2. 无声音
```bash
# 运行音频测试
bash scripts/run_tests.sh audio
```

### 3. 进程残留
```bash
# 强制清理
pkill -9 -f anchor_v2.py
pkill -9 -f ffmpeg
```

## 最近更新

### v3.2 (2024-03-24)
- ✅ 智灵主播视频叠加
- ✅ 热插拔新闻系统
- ✅ 统一测试套件
- ✅ 快速启动脚本
- ✅ 开发复盘文档

### v3.1 (2024-03-24)
- ✅ 添加字幕同步管理器
- ✅ 实现多行字幕滚动效果
- ✅ TTS音频集成推流
- ✅ 完善测试套件

### v3.0
- 插件化架构重构
- 多平台推流支持
