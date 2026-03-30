from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from devil_ai_tutor.scripts.lib import context
from devil_ai_tutor.scripts.lib.normalization import normalize_user_payload
from devil_ai_tutor.scripts.lib.operations import (
    apply_interaction_result,
    record_assignment_delivery,
    register_user,
    resolve_assignment,
    settle_week,
)
from devil_ai_tutor.scripts.lib.result import OperationError


EXPECTED_HISTORY_KEYS = [
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
]


@pytest.fixture
def isolated_skill_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    sandbox_root = tmp_path / "skill"
    shutil.copytree(repo_root / "data", sandbox_root / "data")
    shutil.copytree(repo_root / "schemas", sandbox_root / "schemas")
    monkeypatch.setenv("DEVIL_AI_TUTOR_ROOT", str(sandbox_root))
    context.skill_root.cache_clear()
    yield sandbox_root
    context.skill_root.cache_clear()


def test_normalize_user_payload_canonicalizes_history_log_shape_and_order() -> None:
    template_path = Path(__file__).resolve().parents[1] / "data" / "users" / "user_template.json"
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    payload["username"] = "history_case"
    payload["display_name"] = "History Case"
    payload["enrollment_date"] = "2026-03-27"
    payload["history_logs"] = [
        json.loads(
            '{"event":"提交日题","action":"daily_quiz_answered","date":"2026-03-27","score":86}'
        )
    ]

    normalized, changes, conflicts = normalize_user_payload(payload)

    assert conflicts == []
    assert changes
    assert list(normalized["history_logs"][0].keys()) == EXPECTED_HISTORY_KEYS
    assert normalized["history_logs"][0]["topic"] is None
    assert normalized["history_logs"][0]["status"] is None
    assert normalized["history_logs"][0]["score"] == 86
    assert normalized["history_logs"][0]["promotion"] is None


def test_register_and_delivery_save_canonical_history_logs(isolated_skill_root: Path) -> None:
    register_user(
        {
            "username": "history_case",
            "display_name": "History Case",
            "enrollment_date": "2026-03-27",
            "telegram_id": "",
            "wechat_chat_id": None,
            "level": "L1",
        }
    )
    record_assignment_delivery(
        {
            "username": "history_case",
            "date": "2026-03-28",
            "delivery_type": "daily_quiz",
            "topic_id": "K1_1",
            "advance_topic": True,
        }
    )

    saved_path = isolated_skill_root / "data" / "users" / "history_case.json"
    saved_user = json.loads(saved_path.read_text(encoding="utf-8"))

    assert len(saved_user["history_logs"]) == 2
    for entry in saved_user["history_logs"]:
        assert list(entry.keys()) == EXPECTED_HISTORY_KEYS

    assert saved_user["history_logs"][0]["date"] == "2026-03-27"
    assert saved_user["history_logs"][0]["event"] == "注册魔鬼 AI 导师训练营"
    assert saved_user["history_logs"][0]["topic"] is None
    assert saved_user["history_logs"][0]["score"] is None

    assert saved_user["history_logs"][1]["date"] == "2026-03-28"
    assert saved_user["history_logs"][1]["topic"] == "K1_1"
    assert saved_user["history_logs"][1]["status"] == "delivered"
    assert saved_user["history_logs"][1]["exam_score"] is None


def test_delivery_allows_stage_topic_that_is_not_current_topic(
    isolated_skill_root: Path,
) -> None:
    register_user(
        {
            "username": "stage_delivery_case",
            "display_name": "Stage Delivery Case",
            "enrollment_date": "2026-03-27",
            "telegram_id": "",
            "wechat_chat_id": None,
            "level": "L2",
        }
    )

    result = record_assignment_delivery(
        {
            "username": "stage_delivery_case",
            "date": "2026-03-27",
            "delivery_type": "daily_quiz",
            "topic_id": "K2_4",
            "advance_topic": True,
        }
    )

    assert result["status"] == "ok"


def test_resolve_assignment_returns_earliest_unanswered_topic_within_stage(
    isolated_skill_root: Path,
) -> None:
    register_user(
        {
            "username": "stage_queue_case",
            "display_name": "Stage Queue Case",
            "enrollment_date": "2026-03-27",
            "telegram_id": "",
            "wechat_chat_id": None,
            "level": "L2",
        }
    )

    record_assignment_delivery(
        {
            "username": "stage_queue_case",
            "date": "2026-03-27",
            "delivery_type": "daily_quiz",
            "topic_id": "K2_3",
            "advance_topic": True,
        }
    )
    apply_interaction_result(
        {
            "username": "stage_queue_case",
            "date": "2026-03-27",
            "question_type": "daily_quiz",
            "topic_id": "K2_3",
            "score": 88,
            "score_change": 5,
            "mark_daily_answered": True,
            "week_daily_record_index": 0,
            "history": {
                "event": "K2_3 提交 88/100，+5",
                "action": "daily_quiz_answered",
            },
        }
    )

    resolved = resolve_assignment(
        {
            "username": "stage_queue_case",
            "delivery_type": "daily_quiz",
        }
    )

    assert resolved["assignment"]["topic_id"] == "K2_1"


def test_after_filling_earlier_gaps_resolver_skips_already_answered_future_topic(
    isolated_skill_root: Path,
) -> None:
    register_user(
        {
            "username": "stage_skip_case",
            "display_name": "Stage Skip Case",
            "enrollment_date": "2026-03-27",
            "telegram_id": "",
            "wechat_chat_id": None,
            "level": "L2",
        }
    )

    for date, topic_id, day_index in [
        ("2026-03-27", "K2_3", 0),
        ("2026-03-28", "K2_1", 1),
        ("2026-03-29", "K2_2", 2),
    ]:
        record_assignment_delivery(
            {
                "username": "stage_skip_case",
                "date": date,
                "delivery_type": "daily_quiz",
                "topic_id": topic_id,
                "advance_topic": True,
            }
        )
        apply_interaction_result(
            {
                "username": "stage_skip_case",
                "date": date,
                "question_type": "daily_quiz",
                "topic_id": topic_id,
                "score": 86,
                "score_change": 5,
                "mark_daily_answered": True,
                "week_daily_record_index": day_index,
                "history": {
                    "event": f"{topic_id} 提交 86/100，+5",
                    "action": "daily_quiz_answered",
                },
            }
        )

    resolved = resolve_assignment(
        {
            "username": "stage_skip_case",
            "delivery_type": "daily_quiz",
        }
    )

    assert resolved["assignment"]["topic_id"] == "K2_4"


def _complete_week_mainline(username: str, base_date: str = "2026-03-27") -> None:
    deliveries = [
        ("2026-03-27", "K1_1", 0),
        ("2026-03-28", "K1_2", 1),
        ("2026-03-29", "K1_3", 2),
        ("2026-03-30", "K1_4", 3),
    ]
    for date, topic_id, day_index in deliveries:
        record_assignment_delivery(
            {
                "username": username,
                "date": date,
                "delivery_type": "daily_quiz",
                "topic_id": topic_id,
                "advance_topic": True,
            }
        )
        apply_interaction_result(
            {
                "username": username,
                "date": date,
                "question_type": "daily_quiz",
                "topic_id": topic_id,
                "score": 86,
                "score_change": 20,
                "mark_daily_answered": True,
                "week_daily_record_index": day_index,
                "history": {
                    "event": f"{topic_id} ?? 86/100?+20",
                    "action": "daily_quiz_answered",
                },
            }
        )


def test_supplementary_resolver_prefers_active_weak_points_and_removes_them_when_resolved(
    isolated_skill_root: Path,
) -> None:
    register_user(
        {
            "username": "supplementary_weak_case",
            "display_name": "Supplementary Weak Case",
            "enrollment_date": "2026-03-27",
            "telegram_id": "",
            "wechat_chat_id": None,
            "level": "L1",
        }
    )
    _complete_week_mainline("supplementary_weak_case")

    saved_path = isolated_skill_root / "data" / "users" / "supplementary_weak_case.json"
    user_data = json.loads(saved_path.read_text(encoding="utf-8"))
    user_data["current_week_state"]["active_weak_points"] = [
        {"topic_id": "K1_4", "weak_point": "??????"}
    ]
    saved_path.write_text(json.dumps(user_data, ensure_ascii=False, indent=2), encoding="utf-8")

    resolved = resolve_assignment(
        {
            "username": "supplementary_weak_case",
            "delivery_type": "supplementary_task",
        }
    )

    assert resolved["assignment"]["delivery_type"] == "consolidation_practice"
    assert resolved["assignment"]["topic_id"] == "K1_4"
    assert resolved["assignment"]["focus"] == "??????"

    record_assignment_delivery(
        {
            "username": "supplementary_weak_case",
            "date": "2026-04-01",
            "delivery_type": "consolidation_practice",
            "topic_id": "K1_4",
            "advance_topic": False,
        }
    )
    apply_interaction_result(
        {
            "username": "supplementary_weak_case",
            "date": "2026-04-01",
            "question_type": "consolidation_practice",
            "topic_id": "K1_4",
            "score": 96,
            "score_change": 25,
            "history": {
                "event": "????????",
                "action": "supplementary_weak_point_answered",
            },
            "resolved_weak_points": ["??????"]
        }
    )

    resolved_after = resolve_assignment(
        {
            "username": "supplementary_weak_case",
            "delivery_type": "supplementary_task",
        }
    )

    assert resolved_after["assignment"]["delivery_type"] != "consolidation_practice"


def test_supplementary_resolver_falls_back_to_extra_practice_then_feynman(
    isolated_skill_root: Path,
) -> None:
    register_user(
        {
            "username": "supplementary_fallback_case",
            "display_name": "Supplementary Fallback Case",
            "enrollment_date": "2026-03-27",
            "telegram_id": "",
            "wechat_chat_id": None,
            "level": "L1",
        }
    )
    _complete_week_mainline("supplementary_fallback_case")

    resolved = resolve_assignment(
        {
            "username": "supplementary_fallback_case",
            "delivery_type": "supplementary_task",
        }
    )
    assert resolved["assignment"]["delivery_type"] == "extra_practice"

    saved_path = isolated_skill_root / "data" / "users" / "supplementary_fallback_case.json"
    user_data = json.loads(saved_path.read_text(encoding="utf-8"))
    user_data["current_week_state"]["extra_practice_count"] = 5
    saved_path.write_text(json.dumps(user_data, ensure_ascii=False, indent=2), encoding="utf-8")

    resolved_after = resolve_assignment(
        {
            "username": "supplementary_fallback_case",
            "delivery_type": "supplementary_task",
        }
    )
    assert resolved_after["assignment"]["delivery_type"] == "feynman"


def test_extra_practice_requires_delivery_receipt(isolated_skill_root: Path) -> None:
    register_user(
        {
            "username": "supplementary_receipt_case",
            "display_name": "Supplementary Receipt Case",
            "enrollment_date": "2026-03-27",
            "telegram_id": "",
            "wechat_chat_id": None,
            "level": "L1",
        }
    )
    _complete_week_mainline("supplementary_receipt_case")

    with pytest.raises(OperationError, match="missing assignment receipt"):
        apply_interaction_result(
            {
                "username": "supplementary_receipt_case",
                "date": "2026-04-01",
                "question_type": "extra_practice",
                "topic_id": "K1_4",
                "score": 92,
                "score_change": 25,
                "increment_extra_practice_count": 1,
                "history": {
                    "event": "K1_4 ?? 92/100?+25",
                    "action": "extra_practice_answered",
                },
            }
        )


def test_supplementary_rewards_are_capped_at_five_successes(
    isolated_skill_root: Path,
) -> None:
    register_user(
        {
            "username": "supplementary_reward_cap_case",
            "display_name": "Supplementary Reward Cap Case",
            "enrollment_date": "2026-03-27",
            "telegram_id": "",
            "wechat_chat_id": None,
            "level": "L1",
        }
    )
    _complete_week_mainline("supplementary_reward_cap_case")

    saved_path = isolated_skill_root / "data" / "users" / "supplementary_reward_cap_case.json"
    initial_user = json.loads(saved_path.read_text(encoding="utf-8"))
    initial_score = initial_user["current_week_state"]["estimated_score"]

    for day in range(6):
        date = f"2026-04-0{day + 1}"
        record_assignment_delivery(
            {
                "username": "supplementary_reward_cap_case",
                "date": date,
                "delivery_type": "extra_practice",
                "topic_id": "K1_4",
                "advance_topic": False,
            }
        )
        apply_interaction_result(
            {
                "username": "supplementary_reward_cap_case",
                "date": date,
                "question_type": "extra_practice",
                "topic_id": "K1_4",
                "score": 95,
                "score_change": 25,
                "increment_extra_practice_count": 1,
                "history": {
                    "event": f"? {day + 1} ???",
                    "action": "extra_practice_answered",
                },
            }
        )

    final_user = json.loads(saved_path.read_text(encoding="utf-8"))
    assert final_user["current_week_state"]["supplementary_reward_count"] == 5
    assert final_user["current_week_state"]["estimated_score"] == initial_score + 125
