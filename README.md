# 协商群巡检器

自动发现飞书中以"协商"开头的群聊，拉入 legal 助手机器人，并巡检法务确认状态。

## 文件说明

| 文件 | 用途 | 默认行为 |
|------|------|---------|
| `inspector_sync.py` | **同步脚本**：发现新群 → 新增 Bitable → 拉机器人 | 同时查待处理和未确认 |
| `inspector_check.py` | **巡检脚本**：查 Bitable → 读消息 → 判断确认状态 | 同时查待处理和未确认 |
| `inspector_common.py` | 共享配置 + 工具函数 | 被上面两个引用 |

## 快速开始

### 第一步：安装 lark-cli

```bash
# macOS（推荐）
brew install lark-cli

# 或用 npm
npm install -g @larksuite/cli
```

### 第二步：下载脚本

```bash
curl -O https://raw.githubusercontent.com/zzp5292/contract-group-inspector/main/inspector_common.py
curl -O https://raw.githubusercontent.com/zzp5292/contract-group-inspector/main/inspector_sync.py
curl -O https://raw.githubusercontent.com/zzp5292/contract-group-inspector/main/inspector_check.py
```

三个文件必须在**同一个目录**下。

### 第三步：登录飞书（只需一次，7 天有效）

```bash
lark-cli auth login --domain im
```

终端会显示一个二维码和验证链接。用手机飞书扫码授权，授权完成后就可以使用。

### 第四步：运行

```bash
# 同步（发现新群 + 拉机器人）
python3 inspector_sync.py

# 巡检（判断确认状态）
python3 inspector_check.py
```

## 使用流程

### 日常巡检

任何时候想看法务确认状态，跑巡检脚本：

```bash
python3 inspector_check.py
```

它会查 Bitable 中所有"待处理"和"❌ 未确认"的群，读取群消息，通过关键词匹配判断你是否已确认，并更新 Bitable。

### 新群同步

法务创建了新群时，跑同步脚本：

```bash
python3 inspector_sync.py
```

它会搜索所有"协商"开头的群，发现新群则自动新增到 Bitable、并邀请 legal 助手进群。

### 定时自动同步（可选）

设置 crontab 每 10 分钟自动跑同步脚本：

```bash
# 先建日志目录
mkdir -p ~/feishu_oauth/logs

# 编辑 crontab
crontab -e
```

添加一行：

```
*/10 * * * * /usr/bin/python3 /path/to/inspector_sync.py >> ~/feishu_oauth/logs/sync.log 2>&1
```

保存后即生效。之后每 10 分钟自动检查一次新群，不需手动执行。

### 重新授权

lark-cli 的 user 授权有效期为 7 天。过期后运行脚本会报错，重新扫码即可：

```bash
lark-cli auth login --domain im
```

## 更新脚本

```bash
curl -O https://raw.githubusercontent.com/zzp5292/contract-group-inspector/main/inspector_common.py
curl -O https://raw.githubusercontent.com/zzp5292/contract-group-inspector/main/inspector_sync.py
curl -O https://raw.githubusercontent.com/zzp5292/contract-group-inspector/main/inspector_check.py
```

## 配置说明

配置集中在 `inspector_common.py` 头部，如需修改可按需调整：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `BOT_APP_ID` | `"cli_a8e50c6e3c7f900b"` | 新群自动邀请的机器人 App ID，设为 `None` 则不邀请 |
| `PAGE_SIZE` | `5` | 每批处理群数 |

## Bitable 字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 群名 | 文本 | 群聊名称 |
| chat_id | 文本 | 飞书群 ID |
| 法务确认状态 | 状态/单选 | ✅ 已确认 / ❌ 未确认 / 待处理 |
| 是否已拉机器人 | 复选框 | 是否已拉入 legal 助手 |
