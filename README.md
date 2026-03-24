# AI主播台 - AI助手操作手册

## 项目概述

AI主播台是一个全自动化的直播推流系统，具备以下特性：
- 📺 **双平台推流**：斗鱼 + YouTube
- 🎙️ **TTS语音播报**：多风格语音合成
- 📝 **实时新闻抓取**：自动获取热点新闻
- 🎵 **背景音乐**：自动播放BGM
- 📄 **字幕同步**：多行字幕滚动显示

## ⚠️ 重要：启动流程规范

### 禁止事项
```
❌ 禁止使用 timeout 命令测试服务进程
❌ 禁止前台运行等待输出
❌ 禁止反复执行相同命令
❌ 禁止用bash命令测试，必须写测试函数
```

### 唯一正确的启动方式
```bash
cd /home/z/my-project/cyber_director
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
| 启动 | `./start.sh start` |
| 状态 | `./start.sh status` |
| 停止 | `./start.sh stop` |
| 日志 | `./start.sh log` |
| 重启 | `./start.sh restart` |

## 一键检查

```bash
# 只需要这一个命令就能知道完整状态
./start.sh status
```

## 项目结构

```
cyber_director/
├── anchor_v2.py          # 主程序（插件化）
├── config.json           # 配置文件
├── start.sh              # 启动脚本
├── core/
│   ├── plugin_base.py    # 插件基类
│   ├── ffmpeg_builder.py # FFmpeg构建器
│   ├── subtitle_manager.py # 字幕同步管理器
│   └── script_manager.py # 文稿管理
├── plugins/
│   ├── bgm.py           # 背景音乐插件
│   ├── tts.py           # TTS语音插件
│   ├── content.py       # 内容生成插件
│   └── news_fetcher.py  # 新闻抓取插件
├── data/
│   └── scripts.json     # 节目文稿配置
├── assets/
│   ├── bgm/             # 背景音乐
│   └── bg_frame.png     # 背景图片
├── docs/
│   ├── ARCHITECTURE.md  # 架构文档
│   ├── REVIEW_SUBTITLE_SYNC.md  # 复盘文档
│   └── DEV_CHECKLIST.md # 开发规范
└── scripts/
    └── test_subtitle_sync.py  # 测试脚本
```

## 日志位置

```
logs/anchor.log          # 主日志
logs/ffmpeg_*.log        # FFmpeg推流日志
data/status.json         # 状态文件
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
python scripts/test_subtitle_sync.py

# 错误方式
python -c "from xxx import yyy; ..."
```

### 进程管理
```bash
# 启动前检查残留进程
pgrep -f "anchor_v2.py" && pkill -f "anchor_v2.py"
```

## 最近更新

### v3.1 (2024-03-24)
- ✅ 添加字幕同步管理器
- ✅ 实现多行字幕滚动效果
- ✅ TTS音频集成推流
- ✅ 完善测试套件
- ✅ 项目复盘文档

### v3.0
- 插件化架构重构
- 多平台推流支持
