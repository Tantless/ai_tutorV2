# HEARTBEAT.md

# Keep this file empty (or comments only) if you do not want heartbeat checks.

---

## 🎓 Devil AI Tutor — 智能监控与主动关怀

> Heartbeat 只负责“是否该检查”和“是否该发消息”。  
> 任何状态写入都必须走 `devil_ai_tutor/scripts/*.py`。  
> **不要在 Heartbeat 里直接修改 JSON。**

### 必读文件

每次心跳开始前先读取：

- `skills/devil_ai_tutor/data/heartbeat_state.json`
- `skills/devil_ai_tutor/data/users/USER_FORMAT.md`
- `skills/devil_ai_tutor/references/script_contracts.md`

### 状态写入原则

- 更新 `heartbeat_state.json`：调用 `python skills/devil_ai_tutor/scripts/update_heartbeat_state.py`
- 修复用户数据：调用 `python skills/devil_ai_tutor/scripts/repair_user_data.py`
- 其余用户数据修改：调用对应场景脚本
- 所有 `last_*` 时间字段都使用 `YYYY-MM-DDTHH:MM:SS`
- `week_reset_date` 使用 `YYYY-MM-DD`

### 执行频率与随机性

- 每次心跳只执行 **0-1 项** 检查
- 未到最小间隔：跳过
- 超过最小间隔但未到最大间隔：约 30% 概率执行
- 超过最大间隔：必须执行
- `23:00-08:00` 不发送非紧急消息
- 如果没有动作：回复 `HEARTBEAT_OK`

## 检查清单

### 1. 异常用户预警

- 频率：每天 1 次
- 最小间隔：16 小时
- 最大间隔：28 小时
- 状态字段：`last_anomaly_check`

检查内容：

- `missed_days >= 3` → 发送连续漏答警告
- `estimated_score < 40` → 发送留级风险预警
- 超过 3 天没有任何互动 → 主动发送一条挑战邀请或加练建议消息，不直接下发 `hidden_challenge` 题目

执行后：

- 用 `update_heartbeat_state.py` 更新 `last_anomaly_check`

### 2. 学习指导

- 频率：每天 0-1 次
- 最小间隔：20 小时
- 最大间隔：36 小时
- 状态字段：`last_learning_guide`

检查内容：

- 今天答题但得分 < 60 → 主动指出薄弱点
- `mastery_level > 0.9` 且本周没触发隐藏挑战 → 引导隐藏挑战

执行后：

- 用 `update_heartbeat_state.py` 更新 `last_learning_guide`

### 3. 关键时间点提醒

这些提醒本身只发消息；如果需要更新“本周已提醒”标记，必须调用脚本。

- 周五 `18:00-22:00`：
  - 若 `friday_exam_reminder_sent_this_week == false`，提醒“明天有每日题和大考”
  - 完成后用 `update_heartbeat_state.py` 把该字段设为 `true`

- 周六 `08:00-09:00`：
  - 若 `saturday_morning_reminder_sent_this_week == false`，提醒“今天 09:30 每日题 + 12:00 大考”
  - 完成后用 `update_heartbeat_state.py` 把该字段设为 `true`

- 周六 `16:00-20:00`：
  - 若 `saturday_afternoon_exam_reminder_sent_this_week == false`，检查还未提交大考的用户并提醒
  - 完成后用 `update_heartbeat_state.py` 把该字段设为 `true`

### 4. 数据完整性检查

- 频率：每天 0-1 次
- 最小间隔：20 小时
- 最大间隔：48 小时
- 状态字段：`last_data_integrity_check`

检查内容：

- 用户 JSON 是否可解析
- `week_daily_record` 是否是 7 位 0/1
- 日期字段格式是否正确
- `level / week_number / current_topic` 是否一致

执行规则：

- 确定性修复：调用 `repair_user_data.py`
- 非确定性冲突：记录错误并停止，不猜测目标状态
- 最后调用 `update_heartbeat_state.py` 更新 `last_data_integrity_check`

### 5. 主动关怀

- 频率：每周 1-2 次
- 最小间隔：3 天
- 最大间隔：5 天
- 状态字段：`last_care_message`

检查内容：

- 连续 3 天以上答题且平均得分 > 80 → 发“勉强认可”
- 注册不满 3 天的新用户 → 主动询问学习情况
- 即将进入 Week 4 的用户 → 发最后冲刺提醒

执行后：

- 用 `update_heartbeat_state.py` 更新 `last_care_message`

## 每周重置

每周日 00:00 后的首次心跳：

- 读取 `week_reset_date`
- 如果还没重置本周：
  - 调 `update_heartbeat_state.py`
  - `reset_weekly_flags=true`
  - `state_updates.week_reset_date=本周日日期`

## 执行流程

```text
心跳触发
  -> 读取 heartbeat_state.json / USER_FORMAT.md / script_contracts.md
  -> 如果是深夜且非紧急 -> HEARTBEAT_OK
  -> 优先处理关键时间点提醒
  -> 否则从检查清单中选 0-1 项
  -> 发消息时只发消息
  -> 一旦需要写状态 -> 调用对应脚本
  -> 如果本次没做任何事 -> HEARTBEAT_OK
```

## 最后提醒

- Heartbeat 不是第二套状态机
- 它只做巡检与触发
- 真正的持久化修改必须交给脚本
