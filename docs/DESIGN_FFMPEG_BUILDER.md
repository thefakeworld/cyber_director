# FFmpeg构建器设计问题分析与重构方案

## 问题概述

问题7（FFmpeg音频索引错误）暴露了代码设计的根本问题。

---

## 一、现有设计问题

### 1.1 索引管理分散

```
问题：索引计算逻辑分散在多处

build() 方法中：
  input_index = 0
  if self._bg_image_path:
      input_index += 1          # 视频索引+1
  audio_start_index = input_index  # 计算了但没使用！

_build_audio_filters() 方法中：
  def _get_audio_input_index(self, audio_index):
      # 又重新计算了一遍！
      video_count = 1 if self._bg_image_path else len(self.video_inputs)
      return video_count + audio_index
```

**风险**：两处计算逻辑可能不同步，导致bug

### 1.2 隐式耦合

```
问题：视频输入数量影响音频索引，但关系是隐式的

当使用图片背景时：
  输入0: 图片背景 → 占用1个索引
  输入1: BGM音频
  输入2: TTS音频

当使用视频背景时：
  输入0: 视频背景 → 占用1个索引
  输入1: BGM音频
  输入2: TTS音频

当使用纯色背景时：
  输入0: lavfi color → 占用1个索引
  输入1: BGM音频
  输入2: TTS音频

代码没有统一处理这三种情况！
```

### 1.3 特殊处理过多

```python
# 图片背景特殊处理
if self._bg_image_path and self._bg_image_path.exists():
    cmd.extend(['-loop', '1', '-i', str(self._bg_image_path)])
else:
    # 视频输入
    for inp in self.video_inputs:
        ...

# 后面又要判断
video_count = 1 if self._bg_image_path else len(self.video_inputs)
```

**风险**：`_bg_image_path` 的判断分散多处，容易遗漏

### 1.4 缺少验证机制

```python
# 生成的命令没有验证
cmd = builder.build()
# 直接执行，可能索引错误
subprocess.Popen(cmd)
```

---

## 二、设计改进方案

### 2.1 方案A：输入源管理器（推荐）

**核心思想**：统一管理所有输入源及其索引

```python
class InputManager:
    """输入源管理器"""
    
    def __init__(self):
        self._inputs: List[InputSource] = []
        self._index_map: Dict[str, int] = {}  # label -> index
    
    def add_video(self, source: InputSource) -> int:
        """添加视频输入，返回索引"""
        index = len(self._inputs)
        self._inputs.append(source)
        if source.label:
            self._index_map[source.label] = index
        return index
    
    def add_audio(self, source: InputSource) -> int:
        """添加音频输入，返回索引"""
        index = len(self._inputs)
        self._inputs.append(source)
        if source.label:
            self._index_map[source.label] = index
        return index
    
    def get_index(self, label: str) -> int:
        """通过标签获取索引"""
        return self._index_map.get(label)
    
    def get_audio_index(self, label: str) -> str:
        """获取音频流引用，如 '1:a'"""
        index = self._index_map.get(label)
        if index is not None:
            return f"{index}:a"
        return None
    
    def build_input_args(self) -> List[str]:
        """构建所有输入参数"""
        args = []
        for inp in self._inputs:
            args.extend(self._build_input_arg(inp))
        return args
    
    def get_video_count(self) -> int:
        """获取视频输入数量"""
        return sum(1 for i in self._inputs if i.media_type == "video")
    
    def get_audio_count(self) -> int:
        """获取音频输入数量"""
        return sum(1 for i in self._inputs if i.media_type == "audio")
```

### 2.2 使用示例

```python
class FFmpegBuilderV3:
    """重构后的FFmpeg构建器"""
    
    def __init__(self, font_path: str):
        self.font_path = font_path
        self.input_manager = InputManager()
        # ...
    
    def set_bg_image(self, image_path: Path):
        """设置图片背景"""
        source = InputSource(
            type="image",
            path=str(image_path),
            label="video",
            media_type="video",
            options={"loop": 1}
        )
        self.input_manager.add_video(source)
        return self
    
    def add_bgm(self, bgm_path: Path, volume: float = 0.3):
        """添加BGM"""
        source = InputSource(
            type="file",
            path=str(bgm_path),
            label="bgm",
            media_type="audio",
            options={"stream_loop": -1}
        )
        self.input_manager.add_audio(source)
        self.bgm_volume = volume
        return self
    
    def add_tts(self, tts_playlist: Path):
        """添加TTS"""
        source = InputSource(
            type="concat",
            path=str(tts_playlist),
            label="tts",
            media_type="audio"
        )
        self.input_manager.add_audio(source)
        return self
    
    def _build_audio_filters(self) -> Optional[str]:
        """构建音频滤镜 - 使用标签引用"""
        if self.input_manager.get_audio_count() == 0:
            return None
        
        if self.input_manager.get_audio_count() > 1:
            # 使用标签引用，不再硬编码索引
            bgm_ref = self.input_manager.get_audio_index("bgm")  # "1:a"
            tts_ref = self.input_manager.get_audio_index("tts")  # "2:a"
            
            filters = [
                f"[{bgm_ref}]volume={self.bgm_volume}[bgm]",
                f"[{tts_ref}]volume=1.0[tts]",
                "[bgm][tts]amix=inputs=2:duration=longest[aout]"
            ]
            return ";".join(filters)
        
        return f"volume={self.bgm_volume}"
    
    def build(self) -> List[str]:
        """构建命令"""
        cmd = ['ffmpeg', '-y', '-re']
        
        # 统一构建输入参数
        cmd.extend(self.input_manager.build_input_args())
        
        # ... 其他构建逻辑
        
        return cmd
```

### 2.3 方案B：命令验证器

**核心思想**：生成命令后自动验证

```python
class FFmpegCommandValidator:
    """FFmpeg命令验证器"""
    
    @staticmethod
    def validate(cmd: List[str], inputs: List[InputSource]) -> Tuple[bool, List[str]]:
        """
        验证命令有效性
        
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        
        # 解析输入数量
        input_count = cmd.count('-i')
        
        # 解析滤镜中的索引
        cmd_str = ' '.join(cmd)
        filter_indices = re.findall(r'\[(\d+):[av]\]', cmd_str)
        
        # 检查索引是否超出范围
        for idx in filter_indices:
            if int(idx) >= input_count:
                errors.append(f"索引 [{idx}:a/v] 超出输入范围 (共{input_count}个输入)")
        
        # 检查映射
        map_indices = re.findall(r'-map\s+(\d+:[av]|\[.+?\])', cmd_str)
        for idx in map_indices:
            if idx.startswith('['):
                # 滤镜输出引用，检查是否存在
                if idx not in cmd_str:
                    errors.append(f"映射引用 {idx} 未在滤镜中定义")
            else:
                # 直接索引引用
                num = int(idx.split(':')[0])
                if num >= input_count:
                    errors.append(f"映射索引 {idx} 超出输入范围")
        
        return len(errors) == 0, errors


# 使用
builder = FFmpegBuilderV2(font_path)
cmd = builder.build()
valid, errors = FFmpegCommandValidator.validate(cmd, builder.audio_inputs)
if not valid:
    raise ValueError(f"FFmpeg命令无效: {errors}")
```

---

## 三、实施建议

### 3.1 短期修复（已完成）
- [x] 添加 `_get_audio_input_index()` 方法
- [x] 修复音频索引错误
- [x] 添加测试验证

### 3.2 中期重构
- [ ] 实现 `InputManager` 类
- [ ] 统一输入源管理
- [ ] 使用标签替代硬编码索引
- [ ] 添加命令验证器

### 3.3 长期优化
- [ ] 支持更复杂的输入组合
- [ ] 添加FFmpeg命令可视化调试
- [ ] 单元测试覆盖所有场景

---

## 四、经验教训

| 问题 | 教训 |
|------|------|
| 索引分散计算 | 集中管理，单一数据源 |
| 隐式耦合 | 显式声明依赖关系 |
| 特殊处理过多 | 统一抽象，减少分支 |
| 缺少验证 | 关键逻辑必须有验证 |

---

## 五、代码审查清单

新增代码需要检查：

- [ ] 输入索引是否统一管理？
- [ ] 视频输入变化是否影响音频逻辑？
- [ ] 是否有对应的测试用例？
- [ ] 生成的命令是否经过验证？

---

*文档创建: 2024-03-24*
