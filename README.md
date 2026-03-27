# 魔鬼 AI 导师

> 30 天魔鬼训练营，从 AI 门外汉到 AI 应用工程师

一个严格监督学习的 AI 导师 Skill，采用三轨制计分系统和费曼学习法，通过每日练习和周考实现快速进阶。当前版本已经重构为**脚本驱动写入**：模型负责判断，脚本负责唯一数据落盘。

## ✨ 特性

- 严厉导师人设：毒舌但专业的 The Auditor，拒绝浅表学习
- 三轨制计分：平时分 + 段位分 + 总分
- 30 天课程：LLM 基础 → RAG → Agent → 工程化
- 自动化监督：每日 9:30 出题，周六大考，自动晋级
- 脚本驱动持久化：所有用户状态写入、cron 写入、heartbeat 写入都经由 Python 脚本和 JSON Schema

## 🚀 快速开始

### 1. 安装

将此 Skill 放入 OpenClaw 的 skills 目录：

```bash
.openclaw/workspace/skills/devil_ai_tutor/
```

### 2. 注册

在 Telegram 上向 OpenClaw 说：

```
我想注册 tutor 计划
```

确认注册成功：检查 `skills/devil_ai_tutor/data/users/` 目录下是否生成了以你名字命名的 JSON 文件。

### 3. 配置定时任务

**方式一：自动配置**（推荐）

在 Telegram 上向 OpenClaw 说：
```
请将 HEARTBEAT-example.md 添加到 openclaw 的 HEARTBEAT.md 之中
请将 jobs-example.json 添加到 openclaw 的 cron 配置
```

**方式二：手动配置**
- 复制 `HEARTBEAT-example.md` 内容到 `.openclaw/workspace/HEARTBEAT.md`
- 复制 `jobs-example.json` 到 `.openclaw/cron/jobs.json`

## 📊 计分系统

| 类型 | 说明 | 规则 |
|------|------|------|
| **平时分** | 日常练习积累 | 答题 +5，加练 +2，复述 +3~8，超时 -10 |
| **段位分** | 每周六结算 | `大考 × 0.7 + 平时 × 0.3`，≥60 晋级 |
| **总分** | 整体能力 | 晋级时 `+= 段位分 / 4`，满分 100 |

## 📚 课程大纲

| 周次 | 主题 | 内容 |
|------|------|------|
| Week 1 | LLM 基础 | 核心原理、Prompt 工程、Function Calling |
| Week 2 | RAG 系统 | 向量数据库、文档切分、检索优化 |
| Week 3 | Agent 开发 | 多代理协同、持久化记忆、工具调用 |
| Week 4 | 工程化 | 评估、微调、部署监控、未来趋势 |

## 📁 项目结构

```
devil_ai_tutor/
├── SKILL.md                     # Skill 主规则
├── prompt.md                    # 角色人设
├── examples.md                  # 对话示例
├── references/
│   └── script_contracts.md      # 脚本与 payload 契约
├── schemas/                     # JSON Schema 契约
├── scripts/                     # 唯一允许的数据写入口
├── data/
│   ├── syllabus.json            # 课程大纲
│   ├── heartbeat_state.json     # 心跳状态
│   └── users/
│       ├── USER_FORMAT.md       # 用户数据规范
│       ├── user_template.json   # 新用户模板
│       └── {username}.json      # 用户状态
├── HEARTBEAT-example.md         # 心跳示例
└── jobs-example.json            # Cron 示例
```

## ⚠️ 注意事项

- 导师风格严厉，适合自律学习者
- 详细规则见 [SKILL.md](devil_ai_tutor/SKILL.md)
- 数据模型见 [USER_FORMAT.md](devil_ai_tutor/data/users/USER_FORMAT.md)
- 脚本契约见 [script_contracts.md](devil_ai_tutor/references/script_contracts.md)

## 📄 License

MIT
