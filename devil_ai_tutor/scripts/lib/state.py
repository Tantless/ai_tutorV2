from __future__ import annotations

from copy import deepcopy
from typing import Any

from .catalog import first_topic_for_week, knowledge_topics_for_week
from .constants import canonical_level_name, week_number_for_level
from .context import heartbeat_state_path, user_path, user_template_path, users_dir
from .io import load_json, save_json
from .normalization import normalize_user_payload
from .result import OperationError
from .schema_utils import validate_schema_payload


def iter_usernames() -> list[str]:
    usernames = []
    for path in users_dir().glob("*.json"):
        if path.name == "user_template.json":
            continue
        usernames.append(path.stem)
    return sorted(usernames)


def ensure_week_knowledge_entries(user_data: dict[str, Any], week_number: int) -> list[str]:
    changes: list[str] = []
    knowledge_mastery = user_data.setdefault("knowledge_mastery", {})
    for topic in knowledge_topics_for_week(week_number):
        if topic["id"] not in knowledge_mastery:
            knowledge_mastery[topic["id"]] = {
                "status": "not_started",
                "mastery_level": 0,
                "last_tested": None,
            }
            changes.append(f"initialized knowledge_mastery for {topic['id']}")
    return changes


def load_user_raw(username: str) -> dict[str, Any]:
    path = user_path(username)
    if not path.exists():
        raise OperationError(
            f"user file not found for {username}",
            entity={"type": "user", "id": username},
        )
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise OperationError(
            f"user payload must be a JSON object for {username}",
            entity={"type": "user", "id": username},
        )
    return payload


def load_user(username: str) -> tuple[dict[str, Any], list[str]]:
    raw_payload = load_user_raw(username)
    normalized, changes, conflicts = normalize_user_payload(raw_payload)
    if conflicts:
        raise OperationError(
            f"user data has unresolved conflicts for {username}",
            errors=conflicts,
            entity={"type": "user", "id": username},
        )
    validate_schema_payload("user.schema.json", normalized)
    return normalized, changes


def save_user(username: str, user_data: dict[str, Any]) -> None:
    normalized, _, conflicts = normalize_user_payload(user_data)
    if conflicts:
        raise OperationError(
            f"user data has unresolved conflicts for {username}",
            errors=conflicts,
            entity={"type": "user", "id": username},
        )
    validate_schema_payload("user.schema.json", normalized)
    save_json(user_path(username), normalized)


def load_user_template() -> dict[str, Any]:
    template = load_json(user_template_path())
    validate_schema_payload("user_template.schema.json", template)
    return template


def build_user_from_template(
    username: str,
    display_name: str,
    enrollment_date: str,
    telegram_id: str | None,
    wechat_chat_id: str | None,
    level: str,
) -> dict[str, Any]:
    template = deepcopy(load_user_template())
    canonical_level = canonical_level_name(level)
    week_number = week_number_for_level(canonical_level)

    template["telegram_id"] = telegram_id or ""
    template["wechat_chat_id"] = wechat_chat_id
    template["username"] = username
    template["display_name"] = display_name
    template["enrollment_date"] = enrollment_date
    template["level"] = canonical_level
    template["current_week_state"]["week_number"] = week_number
    template["current_week_state"]["current_topic"] = first_topic_for_week(week_number)
    template["history_logs"][0]["date"] = enrollment_date
    template["history_logs"][0]["event"] = "注册魔鬼 AI 导师训练营"
    template["history_logs"][0]["action"] = "enrollment"

    template["knowledge_mastery"] = {}
    template["current_week_state"]["assignment_receipts"] = []
    template["processed_operations"] = []
    ensure_week_knowledge_entries(template, week_number)
    validate_schema_payload("user.schema.json", template)
    return template


def load_heartbeat_state() -> dict[str, Any]:
    payload = load_json(heartbeat_state_path())
    validate_schema_payload("heartbeat_state.schema.json", payload)
    return payload


def save_heartbeat_state(payload: dict[str, Any]) -> None:
    validate_schema_payload("heartbeat_state.schema.json", payload)
    save_json(heartbeat_state_path(), payload)
