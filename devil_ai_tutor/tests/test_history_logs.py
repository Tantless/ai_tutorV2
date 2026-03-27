from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from devil_ai_tutor.scripts.lib import context
from devil_ai_tutor.scripts.lib.normalization import normalize_user_payload
from devil_ai_tutor.scripts.lib.operations import record_assignment_delivery, register_user


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
