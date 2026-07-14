# 协商群巡检器

## 文件说明

| 文件 | 用途 | 运行方式 |
|------|------|---------|
| `inspector_sync.py` | 轮询用：发现新群 → 新增 Bitable → 拉机器人 | `python3 inspector_sync.py` |
| `inspector_check.py` | 巡检用：查 Bitable → 读消息 → 判断确认状态 | `python3 inspector_check.py` |
| `inspector_common.py` | 共享配置 + 工具函数 | 被上面两个脚本引用 |

## 使用

```bash
# 轮询（同步 + 拉机器人）
python3 inspector_sync.py

# 巡检（只查待处理群）
python3 inspector_check.py

# 巡检（也查已标记为未确认的群）
python3 inspector_check.py --include-unconfirmed
```

## 定时任务

```bash
# crontab，每 10 分钟跑一次同步
*/10 * * * * cd /path && python3 inspector_sync.py

# 每天凌晨 2 点跑一次巡检
0 2 * * * cd /path && python3 inspector_check.py --include-unconfirmed
```
