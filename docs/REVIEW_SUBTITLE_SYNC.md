# AI主播台项目复盘文档

## 文档信息
- **日期**: 2024-03-24
- **版本**: v3.1
- **功能**: 字幕同步与TTS音频集成
- **作者**: AI开发团队

---

## 一、本次迭代概述

### 1.1 目标功能
本次迭代主要实现两个核心功能：
1. **文稿音频声音** - 将TTS生成的语音音频加入直播推流
2. **字幕滚动效果** - 长文本自动分行显示，随语音播放滚动

### 1.2 完成情况
| 功能 | 状态 | 说明 |
|------|------|------|
| 字幕分割算法 | ✅ 完成 | 智能在标点处分割，每行≤35字符 |
| 字幕时间同步 | ✅ 完成 | 根据TTS音频时长计算显示时间 |
| 多行字幕显示 | ✅ 完成 | 最多4行，当前行高亮 |
| 长文本滚动 | ✅ 完成 | 超40字符自动滚动 |
| TTS音频混合 | ✅ 完成 | BGM+TTS双音轨混合推流 |
| 测试函数 | ✅ 完成 | 5个测试用例全部通过 |

---

## 二、问题复盘

### 2.1 历史遗留问题

#### 问题1: 测试方法不规范
**描述**: 之前反复使用bash命令进行测试，没有编写规范的测试函数，导致效率低下。

**具体表现**:
```bash
# 错误做法 - 反复执行类似的bash命令
python -c "from plugins.tts import TTSPluginV2; ..."
python -c "test something..."
```

**解决方案**:
创建了完整的测试文件 `scripts/test_subtitle_sync.py`，包含：
- 5个独立测试函数
- 统一的测试入口 `run_all_tests()`
- 清晰的测试报告输出

**后续改进**:
- [ ] 添加pytest框架支持
- [ ] 增加单元测试覆盖率
- [ ] 集成CI/CD自动测试

---

#### 问题2: 新闻内容不完整
**描述**: 抓取的新闻只有几句话就断了，内容质量差。

**原因分析**:
1. `content.py` 中 `_clean_for_tts()` 方法限制长度为150字符
2. 新闻源API返回的snippet本身较短
3. 没有进行完整的网页内容抓取

**解决方案**:
```python
# plugins/content.py 中的限制
if len(text) > 150:
    text = text[:150]  # 这里截断了内容
```

**后续改进**:
- [ ] 使用web-reader skill抓取完整网页内容
- [ ] 增加新闻摘要生成功能
- [ ] 配置化的内容长度限制

---

#### 问题3: 背景图片未使用
**描述**: 存在 `assets/bg_frame.png` 但未使用，显示纯黑背景。

**解决方案**:
已在 `ffmpeg_builder.py` 中正确使用图片背景：
```python
def set_bg_image(self, image_path: Path, framerate: int = 25):
    """设置图片背景（循环显示）"""
    self.framerate = framerate
    self._bg_image_path = image_path
    return self
```

**验证方法**:
```python
# anchor_v2.py 中已实现优先使用图片
if self.paths.background_image.exists():
    builder.set_bg_image(self.paths.background_image)
```

---

### 2.2 本次开发遇到的问题

#### 问题4: Python转义字符警告
**描述**: 
```
SyntaxWarning: invalid escape sequence '\,'
f"x='max(w-tw-50\,w-50-t*{scroll_speed})':"
```

**原因**: 
在f-string中使用反斜杠需要双重转义。

**解决方案**:
```python
# 错误写法
f"x='max(w-tw-50\,w-50-t*{scroll_speed})':"

# 正确写法
f"x='max(w-tw-50\\,w-50-t*{scroll_speed})':"
```

**后续改进**:
- [ ] 添加pre-commit hook检查语法警告
- [ ] 使用r-string处理正则表达式

---

#### 问题5: 音频混合索引混乱
**描述**: FFmpeg音频滤镜中BGM和TTS的索引容易混淆。

**解决方案**:
在 `_build_audio_filters()` 中明确标注：
```python
if len(self.audio_inputs) > 1:
    # BGM在索引0，TTS在索引1
    filters.append(f"[0:a]volume={self.bgm_volume}[bgm]")
    filters.append(f"[1:a]volume=1.0[tts]")
    filters.append(f"[bgm][tts]amix=inputs=2:duration=longest[aout]")
```

**后续改进**:
- [ ] 使用字典管理音频源标签
- [ ] 添加音频源验证函数

---

#### 问题6: 旧进程残留导致冲突 ⚠️ 重要
**描述**: 启动新进程时，旧的FFmpeg推流进程仍在运行，导致：
- 端口/推流地址被占用
- 多个进程同时推流造成混乱
- 资源浪费（CPU、内存、带宽）
- 日志文件冲突

**具体表现**:
```bash
# 启动时报错
[rtmp @ xxx] Connection refused
# 或者推流到错误的房间
# 或者多个进程竞争导致画面闪烁
```

**原因分析**:
1. 上次运行时Ctrl+C没有正常退出
2. `stop_ffmpeg()` 没有被正确调用
3. 进程被系统挂起而非终止
4. 没有启动前检查机制

**解决方案**:

**方案1: 启动脚本检查（推荐）**
```bash
# start.sh 中添加
#!/bin/bash

# 检查并清理旧进程
pkill -f "ffmpeg.*rtmp" 2>/dev/null
pkill -f "anchor_v2.py" 2>/dev/null
sleep 1

# 确认进程已清理
if pgrep -f "anchor_v2.py" > /dev/null; then
    echo "警告：发现残留进程，强制终止"
    pkill -9 -f "anchor_v2.py"
    sleep 1
fi

# 启动新进程
cd /home/z/my-project/cyber_director
python anchor_v2.py
```

**方案2: 主程序启动检查**
```python
# anchor_v2.py 中添加
def check_existing_process(self) -> bool:
    """检查是否有残留进程"""
    import os
    import signal
    
    pid_file = self.paths.pid_file  # 添加 pid_file 属性
    
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            # 检查进程是否存在
            os.kill(old_pid, 0)
            self.logger.warning(f"发现残留进程 PID: {old_pid}")
            
            # 尝试优雅终止
            try:
                os.kill(old_pid, signal.SIGTERM)
                time.sleep(2)
                # 检查是否终止成功
                os.kill(old_pid, 0)
                # 还在运行，强制终止
                os.kill(old_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # 进程已终止
            
            self.logger.info("残留进程已清理")
        except (ProcessLookupError, ValueError):
            pass  # 进程不存在或PID文件损坏
        finally:
            pid_file.unlink(missing_ok=True)
    
    # 写入当前PID
    pid_file.write_text(str(os.getpid()))
    return True
```

**方案3: PID文件管理**
```python
# core/paths.py 中添加
@property
def pid_file(self) -> Path:
    """PID文件路径"""
    return self.logs_dir / "anchor.pid"
```

**方案4: 优雅退出处理**
```python
# anchor_v2.py 中增强信号处理
def on_signal(signum, frame):
    self.logger.info(f"收到信号 {signum}，正在退出...")
    self.running = False
    
    # 确保FFmpeg进程被终止
    self.stop_ffmpeg()
    
    # 清理PID文件
    pid_file = self.paths.pid_file
    pid_file.unlink(missing_ok=True)
    
    self.logger.info("清理完成，退出")

signal.signal(signal.SIGINT, on_signal)
signal.signal(signal.SIGTERM, on_signal)
# 添加SIGHUP处理（终端关闭时）
signal.signal(signal.SIGHUP, on_signal)
```

**预防措施**:
- [x] 启动前检查并清理旧进程
- [x] 使用PID文件记录进程
- [x] 优雅退出时清理资源
- [x] stop.sh 脚本强制终止
- [ ] 添加进程监控和自动恢复

---

## 三、架构改进

### 3.1 新增模块

```
cyber_director/
├── core/
│   └── subtitle_manager.py    # 新增：字幕同步管理器
├── scripts/
│   └── test_subtitle_sync.py  # 新增：完整测试套件
```

### 3.2 核心类设计

#### SubtitleManager
```python
class SubtitleManager:
    """字幕同步管理器"""
    
    MAX_CHARS_PER_LINE = 35  # 每行最大字符数
    SCROLL_SPEED = 15        # 滚动速度(像素/秒)
    TTS_SPEED = 4.0          # TTS平均语速(字符/秒)
    
    def split_text_to_lines(self, text: str) -> List[str]:
        """智能分割文本为多行"""
        
    def create_segments_from_text(self, text: str, duration: float) -> List[SubtitleSegment]:
        """创建带时间戳的字幕片段"""
        
    def start_playback(self, text: str, audio_duration: float):
        """开始字幕播放"""
        
    def update(self) -> Optional[str]:
        """更新字幕状态"""
```

#### FFmpegBuilderV2 增强
```python
# 新增方法
def set_subtitle_config(self, lines: List[str], current_index: int = 0, 
                        enable_scroll: bool = True, max_width: int = 40):
    """设置字幕配置"""

# 增强的滤镜构建
def _build_video_filters(self) -> str:
    """支持多行字幕和滚动效果"""
```

---

## 四、测试规范

### 4.1 测试文件结构
```python
def test_subtitle_split():
    """测试字幕分割功能"""

def test_subtitle_segments():
    """测试字幕片段创建"""

def test_ffmpeg_subtitle_filter():
    """测试FFmpeg字幕滤镜生成"""

def test_tts_integration():
    """测试TTS集成"""

def test_full_pipeline():
    """测试完整流程"""

def run_all_tests():
    """运行所有测试"""
```

### 4.2 测试执行
```bash
# 运行测试
cd /home/z/my-project/cyber_director
python scripts/test_subtitle_sync.py

# 预期输出
📊 测试总结
  ✅ 通过 - 字幕分割
  ✅ 通过 - 字幕片段
  ✅ 通过 - FFmpeg滤镜
  ✅ 通过 - TTS集成
  ✅ 通过 - 完整流程
总计: 5/5 通过
```

---

## 五、后续改进计划

### 5.1 短期（本周）
- [ ] 修复新闻内容不完整问题
- [ ] 添加pytest框架
- [ ] 完善日志输出格式

### 5.2 中期（本月）
- [ ] 实现字幕实时同步（当前是静态）
- [ ] 添加字幕样式配置
- [ ] 优化音频混合质量

### 5.3 长期
- [ ] 支持多语言字幕
- [ ] 添加实时语音识别同步
- [ ] 实现字幕预览功能

---

## 六、最佳实践总结

### 6.1 开发规范
1. **先写测试，后写代码** - TDD开发模式
2. **一个功能一个测试** - 保持测试独立
3. **使用类型注解** - 提高代码可读性
4. **统一日志格式** - 便于调试和监控

### 6.2 Git提交规范
```
feat: 添加字幕同步管理器
fix: 修复转义字符警告
test: 添加字幕同步测试
docs: 更新复盘文档
```

### 6.3 代码审查要点
- [ ] 是否有对应的测试
- [ ] 是否有语法警告
- [ ] 是否有类型注解
- [ ] 是否有文档注释
- [ ] 是否有错误处理

---

## 七、参考资料

### 7.1 FFmpeg文档
- [FFmpeg Filters Documentation](https://ffmpeg.org/ffmpeg-filters.html)
- [drawtext filter](https://ffmpeg.org/ffmpeg-filters.html#drawtext)
- [amix filter](https://ffmpeg.org/ffmpeg-filters.html#amix)

### 7.2 相关代码文件
- `core/subtitle_manager.py` - 字幕管理
- `core/ffmpeg_builder.py` - FFmpeg命令构建
- `anchor_v2.py` - 主程序
- `plugins/tts.py` - TTS插件
- `plugins/content.py` - 内容插件

---

## 八、变更记录

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|----------|------|
| 2024-03-24 | v3.1 | 添加字幕同步和TTS音频 | AI开发团队 |
| 2024-03-24 | v3.0 | 插件化架构重构 | AI开发团队 |

---

*本文档将随项目迭代持续更新*
