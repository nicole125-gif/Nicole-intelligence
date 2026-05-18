# 制药行业监测系统 - 定时任务配置

## 状态

- **脚本位置**: `~/.openclaw/workspace/scripts/pharma-monitor.js`
- **飞书 Bitable**: 通过环境变量配置（需要应用权限）
- **Obsidian 路径**: 通过 `OBSIDIAN_PATH` 配置，周报输出到该目录下的 `Pharma-Monitoring/`

## 定时任务

使用 OpenClaw heartbeat 配置（每周一 9:00）:

```json
{
  "schedule": "0 9 * * 1",
  "task": "pharma-monitor",
  "enabled": true
}
```

## 待办

1. **飞书应用权限**: 当前应用缺少 `bitable` 权限，需要在飞书开放平台为应用添加 Bitable 读写权限
2. **Bitable 创建**: 权限开通后，运行脚本会自动创建 Bitable
3. **字段配置**: 脚本会自动创建以下字段
   - 日期 (DateTime)
   - 标题 (Text)
   - 来源 (URL)
   - 摘要 (Text)
   - 行业分类 (SingleSelect)
   - 关键词 (Text)

## 使用方法

先配置运行环境:
```bash
export FEISHU_BITABLE_APP_TOKEN="your_app_token"
export FEISHU_BITABLE_TABLE_ID="your_table_id"
export OBSIDIAN_PATH="/path/to/Obsidian Vault"
```

手动运行:
```bash
node ~/.openclaw/workspace/scripts/pharma-monitor.js
```
