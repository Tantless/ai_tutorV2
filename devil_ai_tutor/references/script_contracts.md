# Script Contracts

> 本文件说明 `devil_ai_tutor` 的正式写入入口。  
> 每个脚本的输入都必须满足对应 `schemas/*.json`。

## 调用约定

- 推荐：把 JSON payload 写到标准输入
- 备选：`--payload-json '{...}'`
- 备选：`--payload-file payload.json`
- 返回统一 JSON：
  - `status`: `ok` / `error`
  - `entity`
  - `changes`
  - `logs`
  - `errors`

### PowerShell 示例

```powershell
@'
{
  "username": "neo",
  "display_name": "Neo",
  "enrollment_date": "2026-03-25"
}
'@ | python {SKILL_DIR}/scripts/register_user.py
```

## 场景脚本

| 场景 | 脚本 | Schema |
|------|------|--------|
| 解析唯一合法题目 | `scripts/resolve_assignment.py` | `schemas/resolve_assignment.payload.schema.json` |
| 注册新用户 | `scripts/register_user.py` | `schemas/register_user.payload.schema.json` |
| 记录发题/发卷/发巩固题 | `scripts/record_assignment_delivery.py` | `schemas/record_assignment_delivery.payload.schema.json` |
| 写入互动评分结果 | `scripts/apply_interaction_result.py` | `schemas/apply_interaction_result.payload.schema.json` |
| 提前大考 / 试一试状态切换 | `scripts/apply_early_exam_update.py` | `schemas/apply_early_exam_update.payload.schema.json` |
| 00:00 每日重置与扣分 | `scripts/handle_midnight_reset.py` | `schemas/handle_midnight_reset.payload.schema.json` |
| 周结算 | `scripts/settle_week.py` | `schemas/settle_week.payload.schema.json` |
| 心跳状态写入 | `scripts/update_heartbeat_state.py` | `schemas/update_heartbeat_state.payload.schema.json` |
| 用户数据修复 | `scripts/repair_user_data.py` | `schemas/repair_user_data.payload.schema.json` |
| 一次性迁移 | `scripts/migrate_users.py` | `schemas/migrate_users.payload.schema.json` |
| 管理员调分 | `scripts/adjust_score.py` | `schemas/adjust_score.payload.schema.json` |
| 管理员晋级 | `scripts/promote_level.py` | `schemas/promote_level.payload.schema.json` |

## 推荐负载示例

### 1. 注册

```json
{
  "username": "neo",
  "display_name": "Neo",
  "enrollment_date": "2026-03-25",
  "telegram_id": "123456",
  "wechat_chat_id": null
}
```

### 2. 记录每日题已下发

先解析：

```json
{
  "username": "neo",
  "delivery_type": "daily_quiz"
}
```

解析返回的 `assignment.topic_id` 才是允许发送的题目。

然后记录下发：

```json
{
  "username": "neo",
  "date": "2026-03-25",
  "delivery_type": "daily_quiz",
  "topic_id": "K1_1",
  "advance_topic": true,
  "event": "下发今日考题（K1_1）",
  "action": "daily_quiz_sent",
  "delivery_status": "delivered"
}
```

### 3. 落盘一次互动结果

```json
{
  "username": "neo",
  "date": "2026-03-25",
  "question_type": "daily_quiz",
  "topic_id": "K1_1",
  "score": 86,
  "score_change": 8,
  "mark_daily_answered": true,
  "week_daily_record_index": 2,
  "knowledge_update": {
    "topic_id": "K1_1",
    "status": "mastered",
    "mastery_level": 0.86,
    "last_tested": "2026-03-25"
  },
  "history": {
    "event": "K1_1 提交 86/100，+8",
    "action": "daily_quiz_answered"
  }
}
```

### 4. 周结算

```json
{
  "username": "neo",
  "date": "2026-03-29",
  "exam_score": 80
}
```

### 5. 调分

```json
{
  "username": "neo",
  "score_type": "estimated_score",
  "new_score": 88
}
```

## 兼容说明

- `adjust_score.py` 兼容旧形式：
  - `python adjust_score.py neo 平时分 88`
- `promote_level.py` 兼容旧形式：
  - `python promote_level.py neo L2`

## 顺序要求

- 发题类任务必须是：
  1. `resolve_assignment.py`
  2. 发送消息
  3. `record_assignment_delivery.py`
- 禁止先猜题再发送，再让落盘脚本兜底。

## 迁移说明

- `migrate_users.py` 只会自动应用确定性归一化。
- 遇到 `level / week_number / current_topic` 冲突会直接报错，不猜测目标状态。
