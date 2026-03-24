# AI主播台 - AI助手操作手册

## ⚠️ 重要：启动流程规范

### 禁止事项
```
❌ 禁止使用 timeout 命令测试服务进程
❌ 禁止前台运行等待输出
❌ 禁止反复执行相同命令
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

## 日志位置

```
logs/anchor.log          # 主日志
data/status.json         # 状态文件
```

## 直播间地址

```
https://www.douyu.com/12898962
```
