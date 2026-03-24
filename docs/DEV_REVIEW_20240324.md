# 开发过程复盘 - 2024-03-24

## 一、重复报错的命令

### 1.1 Python路径问题 ❌ 重复出现5次以上

```bash
# 错误命令（反复失败）
python anchor_v2.py
python scripts/test_avatar.py

# 错误输出
python: can't open file '/home/z/my-project/anchor_v2.py': [Errno 2] No such file or directory
```

**根本原因**: 当前工作目录不对

**正确做法**:
```bash
# 方法1: 使用完整路径
python /home/z/my-project/cyber_director/anchor_v2.py

# 方法2: 先切换目录
cd /home/z/my-project/cyber_director && python anchor_v2.py
```

**SOP建议**: 所有脚本第一行添加目录检查
```python
import os
os.chdir(Path(__file__).parent.parent)  # 自动切换到项目根目录
```

---

### 1.2 FFmpeg滤镜语法错误 ❌ 重复出现3次

```bash
# 错误1: drawtext重复
"[0:v]drawtext=drawtext=fontfile=..."  # 多了drawtext=

# 错误2: 输出标签未连接
"Filter 'drawtext:default' has output 0 (vout) unconnected"

# 错误3: 文件路径相对
"textfile=data/script.txt"  # 应该用绝对路径
```

**根本原因**: 滤镜字符串拼接逻辑错误

**SOP建议**: 使用结构化滤镜构建器，而不是字符串拼接

---

### 1.3 Git命令路径问题 ❌ 重复出现4次

```bash
# 错误命令
git status
git add .

# 错误输出
fatal: not a git repository
```

**正确做法**:
```bash
# 使用 -C 参数指定目录
git -C /home/z/my-project/cyber_director status
git -C /home/z/my-project/cyber_director add .
```

---

### 1.4 文件权限问题 ❌ 出现2次

```bash
# 错误
PermissionError: [Errno 13] Permission denied: '.../tts_playlist.txt'
```

**正确做法**:
```bash
# 修复权限
chmod 666 assets/tts/*.txt
# 或删除重建
rm -f assets/tts/tts_playlist.txt && touch assets/tts/tts_playlist.txt
```

---

## 二、测试命令沉淀

### 2.1 核心测试命令（应保存为脚本）

#### 测试1: 智灵视频叠加
```bash
# 文件: scripts/test_avatar_overlay.sh
mkdir -p output && \
ffmpeg -y -nostdin -re \
  -loop 1 -i assets/bg_frame.png -r 25 \
  -stream_loop -1 -i assets/avatar.mp4 \
  -stream_loop -1 -i assets/bgm/calm_01.mp3 \
  -i assets/tts/breaking_news_001.mp3 \
  -filter_complex "
    [1:v]scale=iw*0.35:ih*0.35,format=rgba[avatar];
    [0:v][avatar]overlay=W-w-30:H-h-30,format=yuv420p[vout];
    [2:a]volume=0.3[bgm];
    [3:a]volume=1.0[tts];
    [bgm][tts]amix=inputs=2:duration=longest[aout]" \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -preset ultrafast -b:v 1500k \
  -c:a aac -b:a 128k \
  -t 15 \
  output/avatar_test.mp4
```

#### 测试2: 音频索引验证
```bash
# 文件: scripts/test_audio_index.py
python scripts/test_ffmpeg_audio.py
```

#### 测试3: 热插拔新闻
```bash
# 文件: scripts/test_hot_news.py
python scripts/hot_news.py
```

#### 测试4: 字幕同步
```bash
# 文件: scripts/test_subtitle.py
python scripts/test_subtitle_sync.py
```

---

## 三、SOP标准化建议

### 3.1 项目启动SOP

```bash
#!/bin/bash
# scripts/start.sh - 标准启动流程

set -e  # 遇错即停

# 1. 确保在正确目录
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "📁 项目目录: $PROJECT_ROOT"

# 2. 清理旧进程
pkill -f "anchor_v2.py" 2>/dev/null || true
pkill -f ffmpeg 2>/dev/null || true
sleep 2

# 3. 检查环境
echo "🔍 环境检查..."
command -v ffmpeg >/dev/null || { echo "❌ FFmpeg未安装"; exit 1; }
command -v python3 >/dev/null || { echo "❌ Python3未安装"; exit 1; }

# 4. 检查必要文件
for f in config.json assets/bg_frame.png; do
    [ -f "$f" ] || { echo "❌ 缺少文件: $f"; exit 1; }
done

# 5. 启动
echo "🚀 启动服务..."
nohup python3 anchor_v2.py > logs/console.log 2>&1 &
sleep 5

# 6. 验证
if pgrep -f "anchor_v2.py" > /dev/null; then
    echo "✅ 启动成功"
    echo "📺 斗鱼: https://www.douyu.com/12898962"
else
    echo "❌ 启动失败，查看日志: tail -50 logs/console.log"
    exit 1
fi
```

### 3.2 测试SOP

```bash
#!/bin/bash
# scripts/run_all_tests.sh - 统一测试入口

set -e
cd "$(dirname "$0")/.."

echo "=========================================="
echo "🧪 AI主播台测试套件"
echo "=========================================="

# 测试计数
PASSED=0
FAILED=0

run_test() {
    local name=$1
    local cmd=$2
    echo ""
    echo "▶ $name"
    if eval "$cmd"; then
        echo "  ✅ 通过"
        ((PASSED++))
    else
        echo "  ❌ 失败"
        ((FAILED++))
    fi
}

# 1. 音频索引测试
run_test "音频索引" "python3 scripts/test_ffmpeg_audio.py"

# 2. 字幕同步测试
run_test "字幕同步" "python3 scripts/test_subtitle_sync.py"

# 3. 智灵叠加测试（生成测试视频）
run_test "智灵叠加" "ffmpeg -y -nostdin -re -loop 1 -i assets/bg_frame.png -r 25 -stream_loop -1 -i assets/avatar.mp4 -filter_complex '[1:v]scale=iw*0.3:ih*0.3[av];[0:v][av]overlay=W-w-30:H-h-30[vout]' -map '[vout]' -c:v libx264 -preset ultrafast -t 3 output/test_avatar.mp3"

# 4. 热插拔新闻测试
run_test "热插拔新闻" "python3 scripts/hot_news.py"

echo ""
echo "=========================================="
echo "📊 测试结果: ✅ $PASSED / ❌ $FAILED"
echo "=========================================="

[ $FAILED -eq 0 ] || exit 1
```

### 3.3 添加突发新闻SOP

```bash
#!/bin/bash
# scripts/breaking_news.sh - 快速添加突发新闻

cd "$(dirname "$0")/.."

if [ -z "$1" ]; then
    echo "用法: $0 '新闻标题'"
    echo "示例: $0 '张雪峰心脏骤停抢救中'"
    exit 1
fi

TITLE="$1"
python3 -c "
from scripts.hot_news import add_breaking_news
add_breaking_news(
    title='$TITLE',
    content='详情请关注官方消息',
    source='紧急插播'
)
"

echo "✅ 突发新闻已添加: $TITLE"
```

---

## 四、错误模式总结

| 错误类型 | 出现次数 | 根本原因 | 解决方案 |
|---------|---------|---------|---------|
| 路径错误 | 5+ | 工作目录不对 | 脚本开头cd到项目目录 |
| FFmpeg滤镜 | 3 | 字符串拼接错误 | 使用结构化构建器 |
| Git路径 | 4 | 当前目录不对 | 使用git -C参数 |
| 权限问题 | 2 | root创建文件 | 统一用户权限 |

---

## 五、改进措施

### 5.1 代码层面

1. **所有脚本添加目录初始化**
```python
# 每个脚本开头
import os
from pathlib import Path
os.chdir(Path(__file__).parent.parent)
```

2. **统一日志输出**
```python
# 使用项目根目录的logs
LOG_DIR = Path(__file__).parent.parent / "logs"
```

3. **错误处理包装**
```python
def safe_run(cmd, error_msg="命令执行失败"):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logging.error(f"{error_msg}: {result.stderr}")
            return None
        return result
    except Exception as e:
        logging.error(f"{error_msg}: {e}")
        return None
```

### 5.2 流程层面

1. **开发前检查清单**
   - [ ] 当前目录是否正确
   - [ ] 是否有残留进程
   - [ ] 文件权限是否正常

2. **提交前检查清单**
   - [ ] 所有测试通过
   - [ ] 无语法警告
   - [ ] 日志输出正常

3. **部署前检查清单**
   - [ ] 配置文件正确
   - [ ] 推流地址有效
   - [ ] 资源文件存在

---

## 六、可复用资源

### 6.1 测试脚本

| 脚本 | 功能 | 状态 |
|------|------|------|
| `scripts/test_ffmpeg_audio.py` | 音频索引测试 | ✅ |
| `scripts/test_subtitle_sync.py` | 字幕同步测试 | ✅ |
| `scripts/test_avatar.py` | 智灵叠加测试 | ✅ |
| `scripts/hot_news.py` | 热插拔新闻 | ✅ |

### 6.2 文档

| 文档 | 内容 |
|------|------|
| `docs/REVIEW_SUBTITLE_SYNC.md` | 问题复盘 |
| `docs/DEV_CHECKLIST.md` | 开发规范 |
| `docs/DESIGN_FFMPEG_BUILDER.md` | 架构设计 |

---

*文档创建: 2024-03-24*
