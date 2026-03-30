from __future__ import annotations

LEVELS = {
    1: {
        "code": "L1",
        "name": "L1_基础扫盲期",
        "syllabus_key": "Week_1_基础扫盲期",
    },
    2: {
        "code": "L2",
        "name": "L2_RAG与数据进阶",
        "syllabus_key": "Week_2_RAG_与数据进阶",
    },
    3: {
        "code": "L3",
        "name": "L3_Agent工作流与自动化",
        "syllabus_key": "Week_3_Agent_工作流与自动化",
    },
    4: {
        "code": "L4",
        "name": "L4_工程化与实战",
        "syllabus_key": "Week_4_工程化与实战",
    },
}

LEVEL_ALIASES = {
    "L1": LEVELS[1]["name"],
    "L1_基础扫盲期": LEVELS[1]["name"],
    "L2": LEVELS[2]["name"],
    "L2_RAG与数据进阶": LEVELS[2]["name"],
    "L2_进阶理解期": LEVELS[2]["name"],
    "L2_进阶应用期": LEVELS[2]["name"],
    "L3": LEVELS[3]["name"],
    "L3_Agent工作流与自动化": LEVELS[3]["name"],
    "L3_深度应用期": LEVELS[3]["name"],
    "L4": LEVELS[4]["name"],
    "L4_工程化与实战": LEVELS[4]["name"],
    "L4_专家实战期": LEVELS[4]["name"],
}

KNOWLEDGE_STATUS_ALIASES = {
    "not_started": "not_started",
    "not_tested": "not_started",
    "learning": "learning",
    "learned": "mastered",
    "mastered": "mastered",
}

UNDERSTANDING_LEVEL_ALIASES = {
    "critical": "critical",
    "weak": "weak",
    "moderate": "moderate",
    "good": "moderate",
}

QUESTION_TYPES = {
    "daily_quiz",
    "makeup_exam",
    "extra_practice",
    "consolidation_practice",
    "feynman",
    "hidden_challenge",
    "saturday_exam",
}

DELIVERY_TYPES = {
    "daily_quiz",
    "saturday_exam",
    "consolidation_practice",
    "extra_practice",
    "early_exam",
}

EARLY_EXAM_ACTIONS = {
    "request",
    "pass",
    "fail",
    "enable_try_it",
    "disable_try_it",
}

HEARTBEAT_WEEKLY_FLAGS = (
    "friday_exam_reminder_sent_this_week",
    "saturday_morning_reminder_sent_this_week",
    "saturday_afternoon_exam_reminder_sent_this_week",
)


def canonical_level_name(level: str) -> str:
    try:
        return LEVEL_ALIASES[level]
    except KeyError as exc:
        raise ValueError(f"unknown level alias: {level}") from exc


def canonical_level_code(level: str) -> str:
    canonical_name = canonical_level_name(level)
    for config in LEVELS.values():
        if config["name"] == canonical_name:
            return config["code"]
    raise ValueError(f"missing level code for {level}")


def week_number_for_level(level: str) -> int:
    canonical_name = canonical_level_name(level)
    for week_number, config in LEVELS.items():
        if config["name"] == canonical_name:
            return week_number
    raise ValueError(f"missing week number for {level}")


def canonical_level_for_week(week_number: int) -> str:
    return LEVELS[week_number]["name"]


def grade_for_actual_score(actual_score: float) -> str:
    if actual_score >= 90:
        return "S"
    if actual_score >= 80:
        return "A"
    if actual_score >= 70:
        return "B"
    if actual_score >= 60:
        return "C"
    return "不及格"
