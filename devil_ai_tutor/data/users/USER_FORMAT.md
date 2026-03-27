# 用户数据格式说明

> 本文件定义 `data/users/{username}.json` 的**规范化持久化模型**。  
> 规则判断可以由模型完成，但**所有落盘都必须经过脚本**。

---

## 1. 文件约定

- 位置：`./data/users/`
- 文件名：`{username}.json`
- 模板：`./data/users/user_template.json`
- 正式校验：`./schemas/user.schema.json`
- 模板校验：`./schemas/user_template.schema.json`

## 2. 规范字段

### 顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `telegram_id` | string | Telegram 目标 ID |
| `wechat_chat_id` | string \| null | 微信会话 ID，未绑定时为 null |
| `username` | string | 唯一用户名 |
| `display_name` | string | 展示名 |
| `enrollment_date` | string | 注册日期，`YYYY-MM-DD` |
| `level` | string | 规范段位名，见下表 |
| `actual_score` | number | 当前段位实际分 |
| `total_score` | number | 累计总分 |
| `current_week_state` | object | 当前段位周期状态 |
| `weekly_scores` | array | 历史晋级记录；正常晋级与 `try_it_mode` 晋级都要追加 |
| `knowledge_mastery` | object | 知识点掌握情况 |
| `weak_points_history` | array | 薄弱点历史 |
| `processed_operations` | array | 已处理的幂等操作记录 |
| `history_logs` | array | 操作历史 |

### 规范段位名

| 周次 | 规范值 | 课程键 |
|------|--------|--------|
| 1 | `L1_基础扫盲期` | `Week_1_基础扫盲期` |
| 2 | `L2_RAG与数据进阶` | `Week_2_RAG_与数据进阶` |
| 3 | `L3_Agent工作流与自动化` | `Week_3_Agent_工作流与自动化` |
| 4 | `L4_工程化与实战` | `Week_4_工程化与实战` |

### 历史别名兼容

迁移脚本会把以下别名归一化：

- `L2_进阶理解期` → `L2_RAG与数据进阶`
- `L2_进阶应用期` → `L2_RAG与数据进阶`
- `L3_深度应用期` → `L3_Agent工作流与自动化`
- `L4_专家实战期` → `L4_工程化与实战`

## 3. `current_week_state`

| 字段 | 类型 | 说明 |
|------|------|------|
| `week_number` | integer | 当前段位周，1-4 |
| `current_topic` | string | 当前知识点，`K{week}_{index}` 或 `EXAM_W{week}` |
| `estimated_score` | number | 平时预估分 |
| `interactive_bonus` | number | 互动附加分累计 |
| `daily_answered` | boolean | 今日是否已答题 |
| `daily_answered_date` | string\|null | 最后一次每日题答题日期 |
| `week_daily_record` | array[7] | 仅允许 0/1，表示当周每天是否完成答题 |
| `saturday_exam_answered` | boolean | 当前周大考是否已答 |
| `saturday_exam_answered_date` | string\|null | 大考作答日期 |
| `missed_days` | integer | 累计漏答次数 |
| `extra_practice_count` | integer | 本周主动加练次数 |
| `feynman_used_today` | boolean | 今日是否已使用费曼复述 |
| `feynman_used_date` | string\|null | 最近一次费曼复述日期 |
| `hidden_challenge_used_this_week` | boolean | 本周是否已触发隐藏挑战 |
| `early_exam_requested` | boolean | 是否已发起提前大考；`apply_early_exam_update.py` 的 `action=request` 只设置该字段 |
| `early_exam_taken` | boolean | 是否已参加过提前大考；`apply_early_exam_update.py` 的 `action=request` 必须保持 false，`action=pass` 必须落成 true |
| `try_it_mode` | boolean | 当前是否处于试一试模式 |
| `try_it_accumulated_score` | number | 试一试模式累计平时分 |
| `assignment_receipts` | array | 当前周发题/发卷回执，供补交、漏答、结算校验使用 |

### `week_daily_record` 约束

- 长度固定为 7
- 元素只能是 `0` 或 `1`
- **禁止**在此数组中存分数
- 迁移时，任意正数会被归一化成 `1`

## 4. `knowledge_mastery`

键格式：`K{week}_{index}`

```json
"knowledge_mastery": {
  "K1_1": {
    "status": "mastered",
    "mastery_level": 0.82,
    "last_tested": "2026-03-25"
  }
}
```

### `status` 规范值

- `not_started`
- `learning`
- `mastered`

### 历史别名兼容

- `not_tested` → `not_started`
- `learned` → `mastered`

## 5. `weak_points_history`

```json
{
  "date": "2026-03-25",
  "topic_id": "K1_2",
  "topic_name": "提示词工程",
  "question_type": "daily_quiz",
  "score": 63,
  "max_score": 100,
  "score_percentage": 63.0,
  "understanding_level": "moderate",
  "weak_points": [
    "Few-shot 示例过短",
    "没有解释为什么需要结构化输出"
  ]
}
```

### `understanding_level` 规范值

- `critical`
- `weak`
- `moderate`

### 历史别名兼容

- `good` → `moderate`

## 6. `history_logs`

固定字段顺序：

```json
{
  "date": "2026-03-25",
  "event": "K1_1 提交 86/100，+8",
  "action": "daily_quiz_answered",
  "topic": "K1_1",
  "status": null,
  "score": 86,
  "score_change": 8,
  "current_estimated_score": null,
  "new_estimated_score": null,
  "feedback": null,
  "exam_score": null,
  "actual_score": null,
  "grade": null,
  "promotion": null,
  "new_level": null,
  "total_score_contribution": null,
  "new_total_score": null
}
```

规则：

- 每条 `history_logs` 都必须使用相同字段集合
- 每条 `history_logs` 都必须使用相同字段顺序
- `date`、`event`、`action` 为必填语义字段
- 不适用的扩展字段必须显式写为 `null`

## 7. `processed_operations`

用于幂等写入。每个元素至少包含：

```json
{
  "operation_id": "op-settle-1",
  "action": "weekly_settlement|exam_score=80, exam_topic_id='EXAM_W1', history_action='weekly_settlement', history_event='EXAM_W1 大考结算，得分 80/100'",
  "date": "2026-03-29",
  "topic_id": "EXAM_W1"
}
```

持久化允许的字段只有 `operation_id`、`action`、`date`，以及可选的 `delivery_type`、`topic_id`、`advance_topic`。需要额外做重放校验时，应把校验签名编码进 `action`，并且只编码该分支真正影响可见副作用的字段，例如实际写入的历史 `event/action`、结算分数、目标 topic；分支忽略的字段不应参与重放比较。重复提交相同 `operation_id` 时，脚本应返回 `ok`，并在 `changes` 中写入 `already_applied: <operation_id>`，且不得重复追加分数、周结算记录、历史日志或其他副作用。

- `apply_interaction_result.py` 的幂等签名必须基于**最终真正写入**的互动历史与状态变更，例如 `daily_answered` / `week_daily_record` / `feynman` / `saturday_exam` 标记、知识掌握更新、薄弱点追加；未产生持久化效果的输入字段不应参与重放比较。
- `record_assignment_delivery.py` 的幂等签名必须覆盖真正持久化的下发语义，包括 `delivery_type`、`advance_topic`，以及最终写入历史日志的 `event/action`；这样相同 `operation_id` 的改写重放不会悄悄放过历史文本差异。

## 8. `assignment_receipts`

```json
[
  {
    "delivery_type": "daily_quiz",
    "topic_id": "K1_1",
    "date": "2026-03-26",
    "status": "delivered"
  }
]
```

约定：

- `delivery_type` 目前用于 `daily_quiz`、`saturday_exam`、`consolidation_practice`、`early_exam`
- `status` 目前使用 `delivered`、`answered`、`missed`
- `handle_midnight_reset.py` 在 `penalize=true` 且提供 `penalty_topic_id` 时，应优先把对应作业的原始 `daily_quiz` 回执更新为 `missed`；只有找不到原始回执时才创建新的 `missed` 回执
- 已标记为 `missed` 的 `daily_quiz` 回执仍然允许后续 `makeup_exam` 消耗，并在补考成功后改写为 `answered`
- `settle_week.py` 成功结算后必须清空 `current_week_state.assignment_receipts`
- `record_assignment_delivery.py` 若已通过 `processed_operations` 记录成功下发，后续相同 `operation_id` 的重放即使发生在 `settle_week.py` 清空回执之后，也必须返回 `already_applied: <operation_id>`

## 9. 互动写入语义

- `feynman` 不要求 `topic_id`
- `consolidation_practice` / `extra_practice` 可以携带 `topic_id`
- `feynman` / `consolidation_practice` / `extra_practice` / `hidden_challenge` 不写入 `knowledge_mastery`
- `feynman` / `consolidation_practice` / `extra_practice` / `hidden_challenge` 不写入 `weak_points_history`

## 10. 一致性规则

脚本和迁移都必须检查下列一致性：

1. `level` 与 `current_week_state.week_number` 必须对应同一周
2. `current_week_state.current_topic` 必须存在于 `syllabus.json`
3. `current_topic` 的周次必须与 `level` / `week_number` 一致
4. `week_daily_record` 必须是 7 位 0/1 数组
5. 日期字段必须是 `YYYY-MM-DD` 或 null

### 冲突处理

- **确定性问题**：直接归一化
  - `learned` → `mastered`
  - `not_tested` → `not_started`
  - `good` → `moderate`
  - `week_daily_record` 中正数 → `1`
- **非确定性问题**：报错，不猜
  - 例如：`level=L2` 但 `current_topic=K3_1`
  - 例如：`week_number=2` 但 `level=L3`

## 11. 脚本写入规则

### 唯一允许的写入口

- `register_user.py`
- `record_assignment_delivery.py`
- `apply_interaction_result.py`
- `apply_early_exam_update.py`
- `handle_midnight_reset.py`
- `settle_week.py`
- `repair_user_data.py`
- `migrate_users.py`
- `adjust_score.py`
- `promote_level.py`

### 强制要求

- 模型不能直接编辑用户 JSON
- 任何定时任务、管理员后门、心跳修复都必须走脚本
- 脚本输入必须先通过对应 JSON Schema

## 12. 规范示例

```json
{
  "telegram_id": "8606010466",
  "wechat_chat_id": "example@im.wechat",
  "username": "tantless",
  "display_name": "Tantless",
  "enrollment_date": "2026-03-12",
  "level": "L2_RAG与数据进阶",
  "actual_score": 64.2,
  "total_score": 16.05,
  "current_week_state": {
    "week_number": 2,
    "current_topic": "K2_4",
    "estimated_score": 12.5,
    "interactive_bonus": 0,
    "daily_answered": false,
    "daily_answered_date": "2026-03-22",
    "week_daily_record": [1, 0, 1, 0, 0, 1, 0],
    "saturday_exam_answered": false,
    "saturday_exam_answered_date": null,
    "missed_days": 4,
    "extra_practice_count": 1,
    "feynman_used_today": false,
    "feynman_used_date": null,
    "hidden_challenge_used_this_week": false,
    "early_exam_requested": false,
    "early_exam_taken": false,
    "try_it_mode": false,
    "try_it_accumulated_score": 0,
    "assignment_receipts": []
  },
  "weekly_scores": [
    {
      "week": 1,
      "actual_score": 64.2,
      "exam_score": 66,
      "final_estimated_score": 60,
      "date": "2026-03-14"
    }
  ],
  "knowledge_mastery": {
    "K1_1": {
      "status": "mastered",
      "mastery_level": 0.55,
      "last_tested": "2026-03-13"
    },
    "K2_4": {
      "status": "learning",
      "mastery_level": 0.77,
      "last_tested": "2026-03-22"
    }
  },
  "weak_points_history": [],
  "processed_operations": [
    {
      "operation_id": "op-settle-1",
      "action": "weekly_settlement|exam_score=66, exam_topic_id='EXAM_W1', history_action='weekly_settlement', history_event='EXAM_W1 大考结算，得分 66/100'",
      "date": "2026-03-14",
      "topic_id": "EXAM_W1"
    }
  ],
  "history_logs": [
    {
      "date": "2026-03-12",
      "event": "注册魔鬼 AI 导师训练营",
      "action": "enrollment"
    }
  ]
}
```

---

**最后更新**：2026-03-25  
**维护方式**：脚本驱动，schema 校验，冲突显式报错
