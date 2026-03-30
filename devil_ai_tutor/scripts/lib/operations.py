from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .catalog import (
    exam_topic_for_week,
    first_topic_for_week,
    is_exam_topic,
    next_topic_in_week,
    topic_exists,
    topic_name,
    topic_week,
)
from .constants import (
    HEARTBEAT_WEEKLY_FLAGS,
    canonical_level_name,
    canonical_level_for_week,
    grade_for_actual_score,
    week_number_for_level,
)
from .normalization import normalize_history_log_entry, normalize_user_payload
from .result import OperationError, ok_result
from .safety import (
    assignment_receipts,
    clear_assignment_receipts,
    get_processed_operation,
    is_operation_processed,
    mark_operation_processed,
    require_receipt,
    upsert_assignment_receipt,
)
from .schema_utils import validate_schema_payload
from .state import (
    build_user_from_template,
    ensure_week_knowledge_entries,
    iter_usernames,
    load_heartbeat_state,
    load_user,
    load_user_raw,
    save_heartbeat_state,
    save_user,
)


def _entity_user(username: str) -> dict[str, Any]:
    return {"type": "user", "id": username}


def _history_summary(entry: dict[str, Any]) -> str:
    return f"{entry['date']} {entry['action']}: {entry['event']}"


def _append_history(user_data: dict[str, Any], entry: dict[str, Any]) -> str:
    normalized_entry = normalize_history_log_entry(entry)
    user_data.setdefault("history_logs", []).append(normalized_entry)
    return _history_summary(normalized_entry)


def _resolve_user(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    return load_user(payload["username"])


def _operation_signature(action_name: str, **metadata: Any) -> str:
    parts = [f"{key}={metadata[key]!r}" for key in sorted(metadata)]
    if not parts:
        return action_name
    return f"{action_name}|{', '.join(parts)}"


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _normalized_midnight_history(payload: dict[str, Any], penalty_amount: float) -> dict[str, Any] | None:
    if not payload["penalize"]:
        return None

    return {
        "event": payload.get("event")
        or f"{payload.get('penalty_topic_id') or '昨日考题'} 漏答扣 {abs(penalty_amount)} 分",
        "action": payload.get("action", "penalty"),
    }


def _midnight_replay_signature(payload: dict[str, Any], penalty_amount: float, missed_days_increment: int) -> str:
    metadata: dict[str, Any] = {"penalize": payload["penalize"]}
    if payload["penalize"]:
        metadata.update(
            {
                "penalty_amount": penalty_amount,
                "missed_days_increment": missed_days_increment,
                "penalty_topic_id": payload.get("penalty_topic_id"),
            }
        )
        history_fields = _normalized_midnight_history(payload, penalty_amount)
        if history_fields is not None:
            metadata["history_action"] = history_fields["action"]
            metadata["history_event"] = history_fields["event"]
    return _operation_signature("midnight_reset", **metadata)


def _midnight_replay_topic_id(payload: dict[str, Any]) -> str | None:
    if payload["penalize"]:
        return payload.get("penalty_topic_id")
    return None


def _normalized_settlement_history(
    payload: dict[str, Any],
    exam_topic_id: str,
    exam_score: float,
) -> dict[str, Any]:
    return {
        "event": payload.get("event") or f"{exam_topic_id} 大考结算，得分 {exam_score}/100",
        "action": payload.get("action", "weekly_settlement"),
    }


def _settlement_replay_signature(payload: dict[str, Any], exam_topic_id: str, exam_score: float) -> str:
    history_fields = _normalized_settlement_history(payload, exam_topic_id, exam_score)
    return _operation_signature(
        "weekly_settlement",
        exam_score=exam_score,
        exam_topic_id=exam_topic_id,
        history_action=history_fields["action"],
        history_event=history_fields["event"],
    )


def _normalized_delivery_history(payload: dict[str, Any], topic_id: str) -> dict[str, Any]:
    return {
        "event": payload.get("event")
        or f"下发{payload['delivery_type']}（{topic_id} {topic_name(topic_id) or ''}）".strip(),
        "action": payload.get("action") or f"{payload['delivery_type']}_sent",
    }


def _delivery_replay_signature(
    payload: dict[str, Any],
    *,
    topic_id: str,
    advance_topic: bool,
) -> str:
    history_fields = _normalized_delivery_history(payload, topic_id)
    return _operation_signature(
        "assignment_delivery",
        advance_topic=advance_topic,
        delivery_type=payload["delivery_type"],
        history_action=history_fields["action"],
        history_event=history_fields["event"],
    )


def _early_exam_replay_signature(
    *,
    action: str,
    history: dict[str, Any],
    target_level: str | None,
    target_topic_id: str | None,
    enable_try_it: bool | None,
    try_it_accumulated_score: float | None,
    estimated_score_override: float | None,
) -> str:
    metadata: dict[str, Any] = {
        "early_exam_action": action,
        "history_action": history["action"],
        "history_event": history["event"],
    }
    if "new_level" in history:
        metadata["history_new_level"] = history["new_level"]
    if action == "pass":
        metadata["target_level"] = target_level
        metadata["target_topic_id"] = target_topic_id
        metadata["enable_try_it"] = enable_try_it if enable_try_it is not None else False
        if try_it_accumulated_score is not None:
            metadata["try_it_accumulated_score"] = try_it_accumulated_score
        if estimated_score_override is not None:
            metadata["estimated_score_override"] = estimated_score_override
    elif action == "enable_try_it":
        metadata["try_it_accumulated_score"] = try_it_accumulated_score
    elif action == "disable_try_it" and try_it_accumulated_score is not None:
        metadata["try_it_accumulated_score"] = try_it_accumulated_score
    return _operation_signature("early_exam_update", **metadata)


def _effective_early_exam_history(
    *,
    action: str,
    payload_history: dict[str, Any],
    promoted_level: str | None,
) -> dict[str, Any]:
    history = {
        "event": payload_history["event"],
        "action": payload_history["action"],
    }
    if action == "pass" and promoted_level is not None:
        history["new_level"] = promoted_level
    return history


def _early_exam_replay_topic_id(action: str, target_topic_id: str | None) -> str | None:
    if action == "pass":
        return target_topic_id
    return None


def _effective_interaction_history(payload: dict[str, Any]) -> dict[str, Any]:
    history = deepcopy(payload["history"])
    topic_id = payload.get("topic_id")
    if topic_id:
        history.setdefault("topic", topic_id)
    if "score" in payload:
        history.setdefault("score", payload["score"])
    if "score_change" in payload:
        history.setdefault("score_change", payload["score_change"])
    if "feedback" in payload:
        history.setdefault("feedback", payload["feedback"])
    return history


def _interaction_replay_signature(
    *,
    payload: dict[str, Any],
    effective_history: dict[str, Any],
    effective_mark_daily_answered: bool,
    effective_mark_feynman_used: bool,
    effective_mark_saturday_exam_answered: bool,
) -> str:
    metadata: dict[str, Any] = {
        "question_type": payload["question_type"],
        "history": _stable_json(effective_history),
    }
    if effective_mark_daily_answered:
        metadata["mark_daily_answered"] = True
        day_index = payload.get("week_daily_record_index")
        if day_index is not None:
            metadata["week_daily_record_index"] = day_index
    if effective_mark_feynman_used:
        metadata["mark_feynman_used"] = True
    if effective_mark_saturday_exam_answered:
        metadata["mark_saturday_exam_answered"] = True
    if payload.get("increment_extra_practice_count", 0):
        metadata["increment_extra_practice_count"] = payload["increment_extra_practice_count"]
    if payload.get("set_hidden_challenge_used"):
        metadata["set_hidden_challenge_used"] = True
    if knowledge_update := payload.get("knowledge_update"):
        metadata["knowledge_update"] = _stable_json(
            {
                "topic_id": knowledge_update["topic_id"],
                "status": knowledge_update["status"],
                "mastery_level": knowledge_update["mastery_level"],
                "last_tested": knowledge_update["last_tested"],
            }
        )
    if weak_point_entry := payload.get("weak_point_entry"):
        metadata["weak_point_entry"] = _stable_json(weak_point_entry)
    return _operation_signature("interaction_result", **metadata)


def _find_latest_daily_receipt(
    user_data: dict[str, Any],
    *,
    topic_id: str,
    on_or_before: str,
    allowed_statuses: set[str],
) -> dict[str, Any] | None:
    candidates = [
        receipt
        for receipt in assignment_receipts(user_data)
        if receipt.get("delivery_type") == "daily_quiz"
        and receipt.get("topic_id") == topic_id
        and receipt.get("date") <= on_or_before
        and receipt.get("status") in allowed_statuses
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda receipt: receipt["date"], reverse=True)
    return candidates[0]


def _replay_result(
    *,
    user_data: dict[str, Any],
    username: str,
    operation_id: str | None,
    normalization_changes: list[str],
    expected_state: dict[str, Any],
    state_label: str,
) -> dict[str, Any] | None:
    if not operation_id or not is_operation_processed(user_data, operation_id):
        return None

    processed_operation = get_processed_operation(user_data, operation_id)
    stored_state = {
        key: processed_operation.get(key) if processed_operation is not None else None
        for key in expected_state
    }
    if stored_state != expected_state:
        raise OperationError(
            f"replayed operation_id {operation_id} does not match stored {state_label} state",
            entity=_entity_user(username),
        )

    if normalization_changes:
        save_user(username, user_data)
    return ok_result(
        _entity_user(username),
        changes=list(normalization_changes) + [f"already_applied: {operation_id}"],
        logs=[],
    )


def register_user(payload: dict[str, Any]) -> dict[str, Any]:
    username = payload["username"]
    try:
        load_user_raw(username)
    except OperationError:
        pass
    else:
        raise OperationError(
            f"user already exists: {username}",
            entity=_entity_user(username),
        )

    user_data = build_user_from_template(
        username=username,
        display_name=payload["display_name"],
        enrollment_date=payload["enrollment_date"],
        telegram_id=payload.get("telegram_id"),
        wechat_chat_id=payload.get("wechat_chat_id"),
        level=payload.get("level", "L1"),
    )
    save_user(username, user_data)

    return ok_result(
        _entity_user(username),
        changes=[
            f"created user file for {username}",
            f"initialized {user_data['level']} at {user_data['current_week_state']['current_topic']}",
        ],
        logs=[_history_summary(user_data["history_logs"][0])],
    )


def record_assignment_delivery(payload: dict[str, Any]) -> dict[str, Any]:
    user_data, normalization_changes = _resolve_user(payload)
    username = payload["username"]
    operation_id = payload.get("operation_id")
    advance_topic = bool(payload.get("advance_topic", False))

    week_number = user_data["current_week_state"]["week_number"]
    topic_id = payload["topic_id"]
    current_topic = user_data["current_week_state"]["current_topic"]

    replay_result = _replay_result(
        user_data=user_data,
        username=username,
        operation_id=operation_id,
        normalization_changes=normalization_changes,
        expected_state={
            "delivery_type": payload["delivery_type"],
            "topic_id": topic_id,
            "date": payload["date"],
            "advance_topic": advance_topic,
            "action": _delivery_replay_signature(
                payload,
                topic_id=topic_id,
                advance_topic=advance_topic,
            ),
        },
        state_label="delivery state",
    )
    if replay_result is not None:
        return replay_result

    if not topic_exists(topic_id):
        raise OperationError(
            f"unknown topic_id: {topic_id}",
            entity=_entity_user(username),
        )
    if topic_week(topic_id) != week_number:
        raise OperationError(
            f"topic {topic_id} does not belong to user week {week_number}",
            entity=_entity_user(username),
        )

    if payload["delivery_type"] == "daily_quiz":
        if is_exam_topic(topic_id):
            raise OperationError(
                f"daily_quiz cannot use exam topic {topic_id}",
                entity=_entity_user(username),
            )
        if topic_id != current_topic:
            raise OperationError(
                f"daily_quiz topic must match current_topic {current_topic}, got {topic_id}",
                entity=_entity_user(username),
            )
    elif payload["delivery_type"] in {"saturday_exam", "early_exam"}:
        expected_exam_topic = exam_topic_for_week(week_number)
        if topic_id != expected_exam_topic:
            raise OperationError(
                f"{payload['delivery_type']} topic must be {expected_exam_topic}, got {topic_id}",
                entity=_entity_user(username),
            )
    elif payload["delivery_type"] == "consolidation_practice" and is_exam_topic(topic_id):
        raise OperationError(
            f"consolidation_practice cannot use exam topic {topic_id}",
            entity=_entity_user(username),
        )

    changes = list(normalization_changes)
    logs: list[str] = []

    if payload["delivery_type"] == "daily_quiz" and advance_topic:
        next_topic = next_topic_in_week(topic_id)
        if next_topic:
            user_data["current_week_state"]["current_topic"] = next_topic
            changes.append(f"advanced current_topic to {next_topic}")

    upsert_assignment_receipt(
        user_data,
        {
            "delivery_type": payload["delivery_type"],
            "topic_id": topic_id,
            "date": payload["date"],
            "status": "delivered",
        },
    )
    changes.append("recorded assignment receipt as delivered")

    if operation_id:
        mark_operation_processed(
            user_data,
            operation_id,
            _delivery_replay_signature(
                payload,
                topic_id=topic_id,
                advance_topic=advance_topic,
            ),
            payload["date"],
            delivery_type=payload["delivery_type"],
            topic_id=topic_id,
            advance_topic=advance_topic,
        )

    history_fields = _normalized_delivery_history(payload, topic_id)
    history_entry = {
        "date": payload["date"],
        "event": history_fields["event"],
        "action": history_fields["action"],
        "topic": topic_id,
        "status": "delivered",
    }
    logs.append(_append_history(user_data, history_entry))
    save_user(username, user_data)

    return ok_result(_entity_user(username), changes=changes, logs=logs)


def apply_interaction_result(payload: dict[str, Any]) -> dict[str, Any]:
    user_data, normalization_changes = _resolve_user(payload)
    username = payload["username"]
    operation_id = payload.get("operation_id")
    changes = list(normalization_changes)
    logs: list[str] = []

    question_type = payload["question_type"]
    topic_id = payload.get("topic_id")
    effective_history = _effective_interaction_history(payload)
    effective_mark_daily_answered = bool(payload.get("mark_daily_answered"))
    effective_mark_feynman_used = question_type == "feynman" or bool(payload.get("mark_feynman_used"))
    effective_mark_saturday_exam_answered = bool(payload.get("mark_saturday_exam_answered"))
    current_week = user_data["current_week_state"]["week_number"]
    enhancement_types = {
        "feynman",
        "consolidation_practice",
        "extra_practice",
        "hidden_challenge",
    }
    receipt_required_types = {
        "daily_quiz",
        "makeup_exam",
        "saturday_exam",
        "consolidation_practice",
    }
    mutation_type_allowlist = {
        "mark_daily_answered": {"daily_quiz"},
        "week_daily_record_index": {"daily_quiz"},
        "mark_feynman_used": {"feynman"},
        "mark_saturday_exam_answered": {"saturday_exam"},
        "increment_extra_practice_count": {"extra_practice"},
        "set_hidden_challenge_used": {"hidden_challenge"},
    }
    receipt_to_answer: dict[str, Any] | None = None

    replay_result = _replay_result(
        user_data=user_data,
        username=username,
        operation_id=operation_id,
        normalization_changes=normalization_changes,
        expected_state={
            "date": payload["date"],
            "action": _interaction_replay_signature(
                payload=payload,
                effective_history=effective_history,
                effective_mark_daily_answered=effective_mark_daily_answered,
                effective_mark_feynman_used=effective_mark_feynman_used,
                effective_mark_saturday_exam_answered=effective_mark_saturday_exam_answered,
            ),
            "topic_id": topic_id,
        },
        state_label="interaction result",
    )
    if replay_result is not None:
        return replay_result

    if question_type == "feynman" and topic_id is not None:
        raise OperationError(
            "feynman must not carry topic_id",
            entity=_entity_user(username),
        )

    if topic_id is not None:
        if not topic_exists(topic_id):
            raise OperationError(
                f"unknown topic_id: {topic_id}",
                entity=_entity_user(username),
            )
        if topic_week(topic_id) != current_week:
            raise OperationError(
                f"topic {topic_id} does not belong to current week",
                entity=_entity_user(username),
            )
        if question_type == "saturday_exam" and not is_exam_topic(topic_id):
            raise OperationError(
                f"saturday_exam must use exam topic, got {topic_id}",
                entity=_entity_user(username),
            )
        if (
            question_type not in enhancement_types
            and question_type != "saturday_exam"
            and is_exam_topic(topic_id)
        ):
            raise OperationError(
                f"{question_type} cannot use exam topic {topic_id}",
                entity=_entity_user(username),
            )

    if question_type in enhancement_types and payload.get("knowledge_update"):
        raise OperationError(
            f"enhancement question_type {question_type} cannot update knowledge_update",
            entity=_entity_user(username),
        )

    if question_type in enhancement_types and payload.get("weak_point_entry"):
        raise OperationError(
            f"enhancement question_type {question_type} cannot update weak_point_entry",
            entity=_entity_user(username),
        )

    if question_type in enhancement_types and (
        payload.get("mark_daily_answered")
        or "week_daily_record_index" in payload
        or payload.get("mark_saturday_exam_answered")
    ):
        raise OperationError(
            f"enhancement question_type {question_type} cannot update mainline progress",
            entity=_entity_user(username),
        )

    for field_name, allowed_question_types in mutation_type_allowlist.items():
        if field_name == "week_daily_record_index":
            if field_name in payload and question_type not in allowed_question_types:
                raise OperationError(
                    f"{field_name} is only allowed for daily_quiz",
                    entity=_entity_user(username),
                )
            continue

        if payload.get(field_name) and question_type not in allowed_question_types:
            raise OperationError(
                f"{field_name} is only allowed for {', '.join(sorted(allowed_question_types))}",
                entity=_entity_user(username),
            )

    if question_type in receipt_required_types and topic_id is not None:
        if question_type == "makeup_exam":
            receipt_to_answer = _find_latest_daily_receipt(
                user_data,
                topic_id=topic_id,
                on_or_before=payload["date"],
                allowed_statuses={"delivered", "missed"},
            )
            if receipt_to_answer is not None and receipt_to_answer.get("date") >= payload["date"]:
                receipt_to_answer = None
            if receipt_to_answer is None:
                raise OperationError(
                    f"missing assignment receipt for makeup_exam:{topic_id}:{payload['date']}",
                    entity=_entity_user(username),
                )
        else:
            receipt_to_answer = require_receipt(
                user_data,
                delivery_type=question_type,
                topic_id=topic_id,
                date=payload["date"],
            )

    if "score_change" in payload:
        old_score = user_data["current_week_state"]["estimated_score"]
        user_data["current_week_state"]["estimated_score"] = round(
            old_score + payload["score_change"], 2
        )
        changes.append(
            "updated current_week_state.estimated_score "
            f"from {old_score} to {user_data['current_week_state']['estimated_score']}"
        )

    if effective_mark_daily_answered:
        user_data["current_week_state"]["daily_answered"] = True
        user_data["current_week_state"]["daily_answered_date"] = payload["date"]
        day_index = payload.get("week_daily_record_index")
        if day_index is not None:
            user_data["current_week_state"]["week_daily_record"][day_index] = 1
            changes.append(f"marked week_daily_record[{day_index}] = 1")
        changes.append("marked daily answer state for today")

    if effective_mark_feynman_used:
        user_data["current_week_state"]["feynman_used_today"] = True
        user_data["current_week_state"]["feynman_used_date"] = payload["date"]
        changes.append("marked feynman usage for today")

    if effective_mark_saturday_exam_answered:
        user_data["current_week_state"]["saturday_exam_answered"] = True
        user_data["current_week_state"]["saturday_exam_answered_date"] = payload["date"]
        changes.append("marked saturday exam as answered")

    if payload.get("increment_extra_practice_count", 0):
        old_count = user_data["current_week_state"]["extra_practice_count"]
        user_data["current_week_state"]["extra_practice_count"] = (
            old_count + payload["increment_extra_practice_count"]
        )
        changes.append(
            "incremented extra_practice_count "
            f"from {old_count} to {user_data['current_week_state']['extra_practice_count']}"
        )

    if payload.get("set_hidden_challenge_used"):
        user_data["current_week_state"]["hidden_challenge_used_this_week"] = True
        changes.append("marked hidden challenge as used this week")

    if knowledge_update := payload.get("knowledge_update"):
        if topic_id and knowledge_update["topic_id"] != topic_id:
            raise OperationError(
                "knowledge_update.topic_id must match topic_id",
                entity=_entity_user(username),
            )
        user_data.setdefault("knowledge_mastery", {})[knowledge_update["topic_id"]] = {
            "status": knowledge_update["status"],
            "mastery_level": knowledge_update["mastery_level"],
            "last_tested": knowledge_update["last_tested"],
        }
        changes.append(f"updated knowledge_mastery for {knowledge_update['topic_id']}")

    if weak_point_entry := payload.get("weak_point_entry"):
        if topic_id and weak_point_entry["topic_id"] != topic_id:
            raise OperationError(
                "weak_point_entry.topic_id must match topic_id",
                entity=_entity_user(username),
            )
        user_data.setdefault("weak_points_history", []).append(weak_point_entry)
        changes.append(f"appended weak_points_history for {weak_point_entry['topic_id']}")

    history_entry = deepcopy(effective_history)
    history_entry["date"] = payload["date"]
    logs.append(_append_history(user_data, history_entry))

    if receipt_to_answer is not None and receipt_to_answer.get("status") != "answered":
        receipt_to_answer["status"] = "answered"
        changes.append("marked assignment receipt as answered")

    if operation_id:
        mark_operation_processed(
            user_data,
            operation_id,
            _interaction_replay_signature(
                payload=payload,
                effective_history=effective_history,
                effective_mark_daily_answered=effective_mark_daily_answered,
                effective_mark_feynman_used=effective_mark_feynman_used,
                effective_mark_saturday_exam_answered=effective_mark_saturday_exam_answered,
            ),
            payload["date"],
            topic_id=topic_id,
        )

    save_user(username, user_data)
    return ok_result(_entity_user(username), changes=changes, logs=logs)


def apply_early_exam_update(payload: dict[str, Any]) -> dict[str, Any]:
    user_data, normalization_changes = _resolve_user(payload)
    username = payload["username"]
    action = payload["action"]
    operation_id = payload.get("operation_id")
    changes = list(normalization_changes)
    logs: list[str] = []
    current_state = user_data["current_week_state"]

    if action == "pass":
        replay_target_level = canonical_level_name(payload["target_level"])
        replay_target_week = week_number_for_level(replay_target_level)
        replay_target_topic = payload.get("target_topic_id") or first_topic_for_week(replay_target_week)
    else:
        replay_target_level = payload.get("target_level")
        replay_target_topic = payload.get("target_topic_id")
    effective_history = _effective_early_exam_history(
        action=action,
        payload_history=payload["history"],
        promoted_level=replay_target_level if action == "pass" else None,
    )

    replay_result = _replay_result(
        user_data=user_data,
        username=username,
        operation_id=operation_id,
        normalization_changes=normalization_changes,
        expected_state={
            "date": payload["date"],
            "action": _early_exam_replay_signature(
                action=action,
                history=effective_history,
                target_level=replay_target_level,
                target_topic_id=replay_target_topic,
                enable_try_it=payload.get("enable_try_it"),
                try_it_accumulated_score=payload.get("try_it_accumulated_score"),
                estimated_score_override=payload.get("estimated_score_override"),
            ),
            "topic_id": _early_exam_replay_topic_id(action, replay_target_topic),
        },
        state_label="early exam update",
    )
    if replay_result is not None:
        return replay_result

    if action == "request":
        current_state["early_exam_requested"] = True
        changes.append("marked early_exam_requested=true")
    elif action == "pass":
        target_level = canonical_level_name(payload["target_level"])
        target_week = week_number_for_level(target_level)
        current_week = current_state["week_number"]
        if current_week >= 4:
            raise OperationError(
                "early exam pass is not valid at week 4",
                entity=_entity_user(username),
            )
        if target_week != current_week + 1:
            raise OperationError(
                f"early exam pass must promote exactly one week: expected week {current_week + 1}, got {target_week}",
                entity=_entity_user(username),
            )
        current_topic = payload.get("target_topic_id") or first_topic_for_week(target_week)
        if topic_week(current_topic) != target_week:
            raise OperationError(
                f"target_topic_id {current_topic} does not belong to target week {target_week}",
                entity=_entity_user(username),
            )
        user_data["level"] = target_level
        current_state["week_number"] = target_week
        current_state["current_topic"] = current_topic
        current_state["early_exam_requested"] = False
        current_state["early_exam_taken"] = True
        current_state["try_it_mode"] = payload.get("enable_try_it", False)
        if "try_it_accumulated_score" in payload:
            current_state["try_it_accumulated_score"] = payload["try_it_accumulated_score"]
        if "estimated_score_override" in payload:
            current_state["estimated_score"] = payload["estimated_score_override"]
        ensure_week_knowledge_entries(user_data, target_week)
        changes.extend(
            [
                f"promoted user to {target_level}",
                f"set current_topic to {current_topic}",
                "marked early_exam_taken=true",
                f"set try_it_mode={current_state['try_it_mode']}",
            ]
        )
    elif action == "fail":
        current_state["early_exam_requested"] = False
        changes.append("reset early_exam_requested=false")
    elif action == "enable_try_it":
        current_state["try_it_mode"] = True
        current_state["try_it_accumulated_score"] = payload["try_it_accumulated_score"]
        changes.append("enabled try_it_mode")
    elif action == "disable_try_it":
        current_state["try_it_mode"] = False
        current_state["try_it_accumulated_score"] = payload.get("try_it_accumulated_score", 0)
        changes.append("disabled try_it_mode")
    else:  # pragma: no cover
        raise OperationError(f"unsupported early exam action: {action}", entity=_entity_user(username))

    history_entry = deepcopy(effective_history)
    history_entry["date"] = payload["date"]
    logs.append(_append_history(user_data, history_entry))
    if operation_id:
        mark_operation_processed(
            user_data,
            operation_id,
            _early_exam_replay_signature(
                action=action,
                history=effective_history,
                target_level=replay_target_level,
                target_topic_id=replay_target_topic,
                enable_try_it=payload.get("enable_try_it"),
                try_it_accumulated_score=payload.get("try_it_accumulated_score"),
                estimated_score_override=payload.get("estimated_score_override"),
            ),
            payload["date"],
            topic_id=_early_exam_replay_topic_id(action, replay_target_topic),
        )
    save_user(username, user_data)
    return ok_result(_entity_user(username), changes=changes, logs=logs)


def resolve_assignment(payload: dict[str, Any]) -> dict[str, Any]:
    user_data, normalization_changes = _resolve_user(payload)
    username = payload["username"]
    week_number = user_data["current_week_state"]["week_number"]

    if payload["delivery_type"] == "daily_quiz":
        topic_id = user_data["current_week_state"]["current_topic"]
        if is_exam_topic(topic_id):
            raise OperationError(
                f"current_topic {topic_id} is an exam topic and cannot be used as daily_quiz",
                entity=_entity_user(username),
            )
        advance_topic = True
    elif payload["delivery_type"] in {"saturday_exam", "early_exam"}:
        topic_id = exam_topic_for_week(week_number)
        advance_topic = False
    else:  # pragma: no cover
        raise OperationError(
            f"unsupported delivery_type for resolver: {payload['delivery_type']}",
            entity=_entity_user(username),
        )

    return {
        "status": "ok",
        "entity": {"type": "assignment", "id": f"{username}:{payload['delivery_type']}"},
        "assignment": {
            "username": username,
            "week_number": week_number,
            "level": user_data["level"],
            "delivery_type": payload["delivery_type"],
            "topic_id": topic_id,
            "topic_name": topic_name(topic_id),
            "advance_topic": advance_topic,
        },
        "changes": normalization_changes,
        "logs": [],
        "errors": [],
    }


def handle_midnight_reset(payload: dict[str, Any]) -> dict[str, Any]:
    user_data, normalization_changes = _resolve_user(payload)
    username = payload["username"]
    operation_id = payload.get("operation_id")
    changes = list(normalization_changes)
    logs: list[str] = []
    current_state = user_data["current_week_state"]
    penalty_amount = -abs(payload.get("penalty_amount", -10))
    missed_days_increment = payload.get("missed_days_increment", 1)

    replay_result = _replay_result(
        user_data=user_data,
        username=username,
        operation_id=operation_id,
        normalization_changes=normalization_changes,
        expected_state={
            "date": payload["date"],
            "action": _midnight_replay_signature(payload, penalty_amount, missed_days_increment),
            "topic_id": _midnight_replay_topic_id(payload),
        },
        state_label="midnight reset",
    )
    if replay_result is not None:
        return replay_result

    if payload["penalize"]:
        old_score = current_state["estimated_score"]
        current_state["estimated_score"] = round(old_score + penalty_amount, 2)
        current_state["missed_days"] += missed_days_increment
        changes.append(
            "applied midnight penalty "
            f"{penalty_amount}; estimated_score {old_score} -> {current_state['estimated_score']}"
        )
        if payload.get("penalty_topic_id"):
            existing_receipt = _find_latest_daily_receipt(
                user_data,
                topic_id=payload["penalty_topic_id"],
                on_or_before=payload["date"],
                allowed_statuses={"delivered", "missed"},
            )
            if existing_receipt is not None:
                existing_receipt["status"] = "missed"
            else:
                upsert_assignment_receipt(
                    user_data,
                    {
                        "delivery_type": "daily_quiz",
                        "topic_id": payload["penalty_topic_id"],
                        "date": payload["date"],
                        "status": "missed",
                    },
                )
            changes.append("marked assignment receipt as missed")
        history_fields = _normalized_midnight_history(payload, penalty_amount)
        assert history_fields is not None
        history_entry = {
            "date": payload["date"],
            "event": history_fields["event"],
            "action": history_fields["action"],
            "score_change": penalty_amount,
        }
        if payload.get("penalty_topic_id"):
            history_entry["topic"] = payload["penalty_topic_id"]
        logs.append(_append_history(user_data, history_entry))

    current_state["daily_answered"] = False
    current_state["feynman_used_today"] = False
    changes.append("reset daily_answered=false")
    changes.append("reset feynman_used_today=false")

    if operation_id:
        mark_operation_processed(
            user_data,
            operation_id,
            _midnight_replay_signature(payload, penalty_amount, missed_days_increment),
            payload["date"],
            topic_id=_midnight_replay_topic_id(payload),
        )

    save_user(username, user_data)
    return ok_result(_entity_user(username), changes=changes, logs=logs)


def _reset_week_state(user_data: dict[str, Any], next_week_number: int, estimated_score: float) -> list[str]:
    current_state = user_data["current_week_state"]
    current_state["week_number"] = next_week_number
    current_state["current_topic"] = first_topic_for_week(next_week_number)
    current_state["estimated_score"] = round(estimated_score, 2)
    current_state["interactive_bonus"] = 0
    current_state["daily_answered"] = False
    current_state["daily_answered_date"] = None
    current_state["week_daily_record"] = [0, 0, 0, 0, 0, 0, 0]
    current_state["saturday_exam_answered"] = False
    current_state["saturday_exam_answered_date"] = None
    current_state["extra_practice_count"] = 0
    current_state["feynman_used_today"] = False
    current_state["feynman_used_date"] = None
    current_state["hidden_challenge_used_this_week"] = False
    current_state["early_exam_requested"] = False
    current_state["early_exam_taken"] = False
    current_state["try_it_mode"] = False
    current_state["try_it_accumulated_score"] = 0
    return [
        f"reset weekly state to week {next_week_number}",
        f"set current_topic to {current_state['current_topic']}",
        f"seeded estimated_score to {current_state['estimated_score']}",
    ]


def settle_week(payload: dict[str, Any]) -> dict[str, Any]:
    user_data, normalization_changes = _resolve_user(payload)
    username = payload["username"]
    operation_id = payload.get("operation_id")
    processed_operation = get_processed_operation(user_data, operation_id) if operation_id else None
    current_state = user_data["current_week_state"]
    current_week = current_state["week_number"]
    current_level = user_data["level"]
    exam_score = payload["exam_score"]
    estimated_score = current_state["estimated_score"]
    logs: list[str] = []
    changes = list(normalization_changes)
    actual_score: float | None = None
    promotion = False
    record_actual_score = False
    exam_topic_id = (
        payload.get("exam_topic_id")
        or (processed_operation.get("topic_id") if processed_operation is not None else None)
        or f"EXAM_W{current_week}"
    )

    replay_result = _replay_result(
        user_data=user_data,
        username=username,
        operation_id=operation_id,
        normalization_changes=normalization_changes,
        expected_state={
            "date": payload["date"],
            "action": _settlement_replay_signature(payload, exam_topic_id, exam_score),
            "topic_id": exam_topic_id,
        },
        state_label="weekly settlement",
    )
    if replay_result is not None:
        return replay_result

    if "final_estimated_score_assert" in payload and payload["final_estimated_score_assert"] != estimated_score:
        raise OperationError(
            "final_estimated_score_assert does not match persisted estimated_score",
            entity=_entity_user(username),
        )

    if current_state["try_it_mode"]:
        actual_score = round(
            exam_score * 0.7 + (current_state["try_it_accumulated_score"] + estimated_score) * 0.3,
            2,
        )
        if actual_score >= 60:
            promotion = True
            record_actual_score = True
            user_data["actual_score"] = actual_score
            user_data["total_score"] = round(user_data["total_score"] + actual_score / 4, 2)
            user_data.setdefault("weekly_scores", []).append(
                {
                    "week": current_week,
                    "actual_score": actual_score,
                    "exam_score": exam_score,
                    "final_estimated_score": estimated_score,
                    "date": payload["date"],
                }
            )
            next_week = min(current_week + 1, 4)
            user_data["level"] = canonical_level_for_week(next_week)
            ensure_week_knowledge_entries(user_data, next_week)
            changes.append(f"applied try-it settlement actual_score={actual_score}")
            changes.extend(_reset_week_state(user_data, next_week, actual_score * 0.1))
        else:
            current_state["try_it_accumulated_score"] = round(
                current_state["try_it_accumulated_score"] + estimated_score, 2
            )
            current_state["try_it_mode"] = False
            changes.append(
                "try-it attempt failed without promotion; "
                f"carry try_it_accumulated_score={current_state['try_it_accumulated_score']}"
            )
    else:
        actual_score = round(exam_score * 0.7 + estimated_score * 0.3, 2)
        grade = grade_for_actual_score(actual_score)
        promotion = actual_score >= 60
        record_actual_score = True
        user_data["actual_score"] = actual_score
        changes.append(f"computed actual_score={actual_score}")
        if promotion:
            user_data["total_score"] = round(user_data["total_score"] + actual_score / 4, 2)
            user_data.setdefault("weekly_scores", []).append(
                {
                    "week": current_week,
                    "actual_score": actual_score,
                    "exam_score": exam_score,
                    "final_estimated_score": estimated_score,
                    "date": payload["date"],
                }
            )
            next_week = min(current_week + 1, 4)
            user_data["level"] = canonical_level_for_week(next_week)
            ensure_week_knowledge_entries(user_data, next_week)
            changes.append(
                f"promotion achieved with grade {grade}; total_score={user_data['total_score']}"
            )
            changes.extend(_reset_week_state(user_data, next_week, actual_score * 0.1))
        else:
            changes.append(f"retained current level with grade {grade}")
            changes.extend(_reset_week_state(user_data, current_week, actual_score * 0.1))

    clear_assignment_receipts(user_data)
    changes.append("cleared current_week_state.assignment_receipts")

    settlement_history = _normalized_settlement_history(payload, exam_topic_id, exam_score)
    history_entry = {
        "date": payload["date"],
        "event": settlement_history["event"],
        "action": settlement_history["action"],
        "topic": exam_topic_id,
        "exam_score": exam_score,
        "promotion": promotion,
    }
    if actual_score is not None and record_actual_score:
        history_entry["actual_score"] = actual_score
        history_entry["grade"] = grade_for_actual_score(actual_score)
    if promotion and user_data["level"] != current_level:
        history_entry["new_level"] = user_data["level"]
    logs.append(_append_history(user_data, history_entry))

    if operation_id:
        mark_operation_processed(
            user_data,
            operation_id,
            _settlement_replay_signature(payload, exam_topic_id, exam_score),
            payload["date"],
            topic_id=exam_topic_id,
        )

    save_user(username, user_data)
    return ok_result(_entity_user(username), changes=changes, logs=logs)


def update_heartbeat_state(payload: dict[str, Any]) -> dict[str, Any]:
    state = load_heartbeat_state()
    changes: list[str] = []

    if payload.get("reset_weekly_flags"):
        for field_name in HEARTBEAT_WEEKLY_FLAGS:
            if state.get(field_name):
                state[field_name] = False
                changes.append(f"reset {field_name}=false")

    for key, value in payload.get("state_updates", {}).items():
        old_value = state.get(key)
        state[key] = value
        changes.append(f"updated heartbeat_state.{key} from {old_value} to {value}")

    save_heartbeat_state(state)
    return ok_result({"type": "heartbeat_state", "id": "default"}, changes=changes, logs=[])


def repair_user_data(payload: dict[str, Any]) -> dict[str, Any]:
    username = payload["username"]
    raw_payload = load_user_raw(username)
    normalized, changes, conflicts = normalize_user_payload(raw_payload)
    if conflicts:
        raise OperationError(
            f"user data repair blocked for {username}",
            errors=conflicts,
            entity=_entity_user(username),
        )

    validate_schema_payload("user.schema.json", normalized)
    save_user(username, normalized)
    return ok_result(_entity_user(username), changes=changes or ["no deterministic repairs needed"], logs=[])


def migrate_users(payload: dict[str, Any]) -> dict[str, Any]:
    usernames = payload.get("usernames") or iter_usernames()
    migrated: list[str] = []
    errors: list[str] = []
    changes: list[str] = []

    for username in usernames:
        raw_payload = load_user_raw(username)
        normalized, item_changes, conflicts = normalize_user_payload(raw_payload)
        if conflicts:
            errors.append(f"{username}: " + "; ".join(conflicts))
            if payload.get("stop_on_conflict", False):
                raise OperationError(
                    "migration stopped on conflict",
                    entity={"type": "migration", "id": "users"},
                    errors=errors,
                )
            continue

        validate_schema_payload("user.schema.json", normalized)
        save_user(username, normalized)
        migrated.append(username)
        if item_changes:
            changes.append(f"{username}: " + ", ".join(item_changes))
        else:
            changes.append(f"{username}: already canonical")

    if errors:
        raise OperationError(
            "migration finished with conflicts",
            entity={"type": "migration", "id": "users"},
            errors=errors,
        )

    return ok_result(
        {"type": "migration", "id": "users"},
        changes=changes or ["no users found"],
        logs=[f"migrated users: {', '.join(migrated)}"] if migrated else [],
    )


def adjust_score(payload: dict[str, Any]) -> dict[str, Any]:
    user_data, normalization_changes = _resolve_user(payload)
    username = payload["username"]
    changes = list(normalization_changes)
    score_type = {
        "平时分": "estimated_score",
        "实际段位分": "actual_score",
        "总分": "total_score",
    }.get(payload["score_type"], payload["score_type"])
    new_score = payload["new_score"]

    if score_type == "estimated_score":
        old_score = user_data["current_week_state"]["estimated_score"]
        user_data["current_week_state"]["estimated_score"] = new_score
        changes.append(f"estimated_score {old_score} -> {new_score}")
    elif score_type == "actual_score":
        old_score = user_data["actual_score"]
        user_data["actual_score"] = new_score
        changes.append(f"actual_score {old_score} -> {new_score}")
    elif score_type == "total_score":
        old_score = user_data["total_score"]
        user_data["total_score"] = new_score
        changes.append(f"total_score {old_score} -> {new_score}")
    else:  # pragma: no cover
        raise OperationError(f"unsupported score_type: {score_type}", entity=_entity_user(username))

    logs: list[str] = []
    if payload.get("date"):
        history_entry = {
            "date": payload["date"],
            "event": payload.get("reason") or f"管理员调整 {score_type} 为 {new_score}",
            "action": "admin_adjust_score",
        }
        logs.append(_append_history(user_data, history_entry))

    save_user(username, user_data)
    return ok_result(_entity_user(username), changes=changes, logs=logs)


def promote_level(payload: dict[str, Any]) -> dict[str, Any]:
    user_data, normalization_changes = _resolve_user(payload)
    username = payload["username"]
    target_level = canonical_level_name(payload["target_level"])
    target_week = week_number_for_level(target_level)
    target_topic_id = payload.get("target_topic_id") or first_topic_for_week(target_week)

    if topic_week(target_topic_id) != target_week:
        raise OperationError(
            f"target_topic_id {target_topic_id} does not belong to target level {target_level}",
            entity=_entity_user(username),
        )

    user_data["level"] = target_level
    user_data["current_week_state"]["week_number"] = target_week
    user_data["current_week_state"]["current_topic"] = target_topic_id
    user_data["current_week_state"]["estimated_score"] = payload.get("estimated_score", 10)
    ensure_week_knowledge_entries(user_data, target_week)

    changes = list(normalization_changes)
    changes.extend(
        [
            f"promoted user to {target_level}",
            f"set week_number={target_week}",
            f"set current_topic={target_topic_id}",
            f"set estimated_score={user_data['current_week_state']['estimated_score']}",
        ]
    )

    logs: list[str] = []
    if payload.get("date"):
        history_entry = {
            "date": payload["date"],
            "event": payload.get("reason") or f"管理员晋级到 {target_level}",
            "action": "admin_promote_level",
            "new_level": target_level,
        }
        logs.append(_append_history(user_data, history_entry))

    save_user(username, user_data)
    return ok_result(_entity_user(username), changes=changes, logs=logs)

