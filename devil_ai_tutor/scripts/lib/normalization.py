from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from .catalog import topic_exists, topic_week
from .constants import (
    KNOWLEDGE_STATUS_ALIASES,
    LEVELS,
    UNDERSTANDING_LEVEL_ALIASES,
    canonical_level_name,
    canonical_level_for_week,
    week_number_for_level,
)

CURRENT_WEEK_DEFAULTS = {
    "interactive_bonus": 0,
    "daily_answered": False,
    "daily_answered_date": None,
    "week_daily_record": [0, 0, 0, 0, 0, 0, 0],
    "saturday_exam_answered": False,
    "saturday_exam_answered_date": None,
    "missed_days": 0,
    "extra_practice_count": 0,
    "supplementary_reward_count": 0,
    "active_weak_points": [],
    "feynman_used_today": False,
    "feynman_used_date": None,
    "hidden_challenge_used_this_week": False,
    "early_exam_requested": False,
    "early_exam_taken": False,
    "try_it_mode": False,
    "try_it_accumulated_score": 0,
    "assignment_receipts": [],
}

HISTORY_LOG_FIELD_ORDER = (
    "date",
    "event",
    "action",
    "topic",
    "status",
    "score",
    "score_change",
    "current_estimated_score",
    "new_estimated_score",
    "feedback",
    "exam_score",
    "actual_score",
    "grade",
    "promotion",
    "new_level",
    "total_score_contribution",
    "new_total_score",
)

HISTORY_LOG_DEFAULTS = {
    "date": None,
    "event": None,
    "action": None,
    "topic": None,
    "status": None,
    "score": None,
    "score_change": None,
    "current_estimated_score": None,
    "new_estimated_score": None,
    "feedback": None,
    "exam_score": None,
    "actual_score": None,
    "grade": None,
    "promotion": None,
    "new_level": None,
    "total_score_contribution": None,
    "new_total_score": None,
}


def _is_iso_date(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _normalize_week_daily_record(record: Any) -> tuple[list[int] | Any, list[str]]:
    changes: list[str] = []
    if isinstance(record, list) and len(record) == 7:
        normalized = []
        for item in record:
            if isinstance(item, bool):
                normalized.append(1 if item else 0)
            elif isinstance(item, (int, float)):
                normalized.append(1 if item > 0 else 0)
            else:
                return record, changes
        if normalized != record:
            changes.append("normalized week_daily_record entries to 0/1")
        return normalized, changes
    return record, changes


def normalize_history_log_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for field_name in HISTORY_LOG_FIELD_ORDER:
        normalized[field_name] = entry.get(field_name, HISTORY_LOG_DEFAULTS[field_name])
    return normalized


def normalize_user_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    data = deepcopy(payload)
    changes: list[str] = []
    conflicts: list[str] = []

    if "wechat_chat_id" not in data:
        data["wechat_chat_id"] = None
        changes.append("added missing wechat_chat_id=null")

    if "processed_operations" not in data:
        data["processed_operations"] = []
        changes.append("added missing processed_operations=[]")

    current_week_state = data.setdefault("current_week_state", {})
    for key, default_value in CURRENT_WEEK_DEFAULTS.items():
        if key not in current_week_state:
            current_week_state[key] = deepcopy(default_value)
            changes.append(f"added missing current_week_state.{key}")

    try:
        canonical_level = canonical_level_name(data["level"])
    except (KeyError, ValueError):
        canonical_level = None
        conflicts.append(f"unknown level value: {data.get('level')}")
    else:
        if data["level"] != canonical_level:
            data["level"] = canonical_level
            changes.append("canonicalized level alias")

    if canonical_level is not None:
        try:
            expected_week_number = week_number_for_level(canonical_level)
        except ValueError:
            expected_week_number = None
        if (
            expected_week_number is not None
            and current_week_state.get("week_number") != expected_week_number
        ):
            conflicts.append(
                "level/current_week_state.week_number mismatch: "
                f"{canonical_level} expects week {expected_week_number}, "
                f"found {current_week_state.get('week_number')}"
            )

    week_daily_record, record_changes = _normalize_week_daily_record(
        current_week_state.get("week_daily_record")
    )
    current_week_state["week_daily_record"] = week_daily_record
    changes.extend(record_changes)
    if not (
        isinstance(current_week_state["week_daily_record"], list)
        and len(current_week_state["week_daily_record"]) == 7
        and all(item in (0, 1) for item in current_week_state["week_daily_record"])
    ):
        conflicts.append("current_week_state.week_daily_record must be a 7-item 0/1 array")

    knowledge_mastery = data.setdefault("knowledge_mastery", {})
    for topic_id, topic_state in list(knowledge_mastery.items()):
        raw_status = topic_state.get("status")
        canonical_status = KNOWLEDGE_STATUS_ALIASES.get(raw_status)
        if canonical_status is None:
            conflicts.append(f"unknown knowledge_mastery status for {topic_id}: {raw_status}")
        elif canonical_status != raw_status:
            topic_state["status"] = canonical_status
            changes.append(f"canonicalized knowledge_mastery.{topic_id}.status")

    weak_points_history = data.setdefault("weak_points_history", [])
    for index, entry in enumerate(weak_points_history):
        raw_level = entry.get("understanding_level")
        canonical_understanding = UNDERSTANDING_LEVEL_ALIASES.get(raw_level)
        if canonical_understanding is None:
            conflicts.append(
                "unknown weak_points_history understanding_level at index "
                f"{index}: {raw_level}"
            )
        elif canonical_understanding != raw_level:
            entry["understanding_level"] = canonical_understanding
            changes.append(
                f"canonicalized weak_points_history[{index}].understanding_level"
            )

    current_topic = current_week_state.get("current_topic")
    if not isinstance(current_topic, str) or not topic_exists(current_topic):
        conflicts.append(f"unknown current_topic: {current_topic}")
    elif canonical_level is not None and topic_week(current_topic) != week_number_for_level(canonical_level):
        conflicts.append(
            "level/current_topic mismatch: "
            f"{canonical_level} expects week {week_number_for_level(canonical_level)}, "
            f"found topic {current_topic}"
        )

    for field_name in ("daily_answered_date", "saturday_exam_answered_date", "feynman_used_date"):
        if not _is_iso_date(current_week_state.get(field_name)):
            conflicts.append(f"invalid date format for current_week_state.{field_name}")

    history_logs = data.setdefault("history_logs", [])
    normalized_history_logs: list[dict[str, Any]] = []
    for log_index, log_entry in enumerate(history_logs):
        normalized_entry = normalize_history_log_entry(log_entry)
        if list(log_entry.keys()) != list(normalized_entry.keys()) or log_entry != normalized_entry:
            changes.append(f"normalized history_logs[{log_index}] shape")
        normalized_history_logs.append(normalized_entry)
    data["history_logs"] = normalized_history_logs

    for log_index, log_entry in enumerate(data["history_logs"]):
        if not isinstance(log_entry.get("date"), str) or not _is_iso_date(log_entry.get("date")):
            conflicts.append(f"invalid date format for history_logs[{log_index}].date")
        if not isinstance(log_entry.get("event"), str) or not log_entry.get("event"):
            conflicts.append(f"missing event for history_logs[{log_index}]")
        if not isinstance(log_entry.get("action"), str) or not log_entry.get("action"):
            conflicts.append(f"missing action for history_logs[{log_index}]")

    for score_index, weekly_score in enumerate(data.setdefault("weekly_scores", [])):
        if not _is_iso_date(weekly_score.get("date")):
            conflicts.append(f"invalid date format for weekly_scores[{score_index}].date")

    for entry_index, weak_entry in enumerate(weak_points_history):
        if not _is_iso_date(weak_entry.get("date")):
            conflicts.append(f"invalid date format for weak_points_history[{entry_index}].date")

    if canonical_level is not None:
        expected_level = canonical_level_for_week(week_number_for_level(canonical_level))
        if expected_level != canonical_level:
            conflicts.append(f"internal level mapping mismatch for {canonical_level}")

    return data, changes, conflicts
