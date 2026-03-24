# AI主播台开发规范 Checklist

## 开发前检查
- [ ] 确认当前分支
- [ ] 拉取最新代码
- [ ] 阅读相关文档

## 编码规范

### 禁止事项
- ❌ 不要反复用bash命令测试，必须写测试函数
- ❌ 不要硬编码路径和配置
- ❌ 不要忽略语法警告
- ❌ 不要在循环中创建重复对象

### 必须事项
- ✅ 写代码前先写测试
- ✅ 使用类型注解
- ✅ 添加文档字符串
- ✅ 处理异常情况

## 测试规范

### 测试文件命名
```
scripts/test_xxx.py     # 功能测试
tests/test_unit_xxx.py  # 单元测试
```

### 测试函数模板
```python
def test_feature_name():
    """测试描述"""
    # 1. 准备数据
    # 2. 执行测试
    # 3. 验证结果
    # 4. 清理资源
    pass

def run_all_tests():
    """运行所有测试"""
    tests = [
        ("测试名称", test_func),
    ]
    results = []
    for name, func in tests:
        try:
            passed = func()
            results.append((name, passed))
        except Exception as e:
            print(f"错误: {e}")
            results.append((name, False))
    return all(p for _, p in results)
```

### 执行测试
```bash
# 正确方式
python scripts/test_xxx.py

# 错误方式
python -c "from xxx import yyy; ..."
```

## 常见问题速查

### 进程残留问题 ⚠️ 重要
```bash
# 启动前检查
pgrep -f "anchor_v2.py" && echo "发现残留进程"

# 清理残留进程
pkill -f "ffmpeg.*rtmp"
pkill -f "anchor_v2.py"

# 强制终止
pkill -9 -f "anchor_v2.py"
```

```python
# 主程序启动检查
def check_existing_process(self):
    pid_file = self.paths.pid_file
    if pid_file.exists():
        old_pid = int(pid_file.read_text().strip())
        try:
            os.kill(old_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    pid_file.write_text(str(os.getpid()))
```

### Python转义警告
```python
# 错误
f"x='max(w-tw-50\,w+tw)'"

# 正确
f"x='max(w-tw-50\\,w+tw)'"
```

### FFmpeg音频混合
```python
# BGM在索引0，TTS在索引1
filters.append(f"[0:a]volume={bgm_vol}[bgm]")
filters.append(f"[1:a]volume=1.0[tts]")
filters.append(f"[bgm][tts]amix=inputs=2:duration=longest[aout]")
```

### 文件路径处理
```python
# 正确 - 使用Path对象
from pathlib import Path
path = Path("data/file.txt")
path.parent.mkdir(parents=True, exist_ok=True)

# 错误 - 硬编码路径
path = "/home/user/project/data/file.txt"
```

## 提交规范

### Commit Message
```
feat: 新功能
fix: 修复bug
test: 添加测试
docs: 文档更新
refactor: 重构
style: 格式调整
```

### 提交前检查
- [ ] 所有测试通过
- [ ] 无语法警告
- [ ] 无未使用的导入
- [ ] 无调试代码

## 问题记录模板

### 问题
描述遇到的问题

### 原因
分析问题原因

### 解决方案
```python
# 代码示例
```

### 预防措施
- [ ] 检查项1
- [ ] 检查项2
