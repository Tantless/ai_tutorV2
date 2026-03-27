from __future__ import annotations

import re
from functools import lru_cache

from .constants import LEVELS
from .context import syllabus_path
from .io import load_json

TOPIC_RE = re.compile(r"^K(?P<week>\d+)_(?P<index>\d+)$")
EXAM_RE = re.compile(r"^EXAM_W(?P<week>\d+)$")


@lru_cache(maxsize=1)
def load_syllabus() -> dict:
    return load_json(syllabus_path())


@lru_cache(maxsize=1)
def topics_by_week() -> dict[int, list[dict]]:
    syllabus = load_syllabus()
    topics: dict[int, list[dict]] = {}
    for week_number, level_config in LEVELS.items():
        topics[week_number] = list(syllabus["levels"][level_config["syllabus_key"]])
    return topics


def knowledge_topics_for_week(week_number: int) -> list[dict]:
    return [topic for topic in topics_by_week()[week_number] if topic["id"].startswith("K")]


def all_topic_ids() -> set[str]:
    return {topic["id"] for week in topics_by_week().values() for topic in week}


def topic_exists(topic_id: str) -> bool:
    return topic_id in all_topic_ids()


def topic_week(topic_id: str) -> int | None:
    if match := TOPIC_RE.match(topic_id):
        return int(match.group("week"))
    if match := EXAM_RE.match(topic_id):
        return int(match.group("week"))
    return None


def is_exam_topic(topic_id: str) -> bool:
    return bool(EXAM_RE.match(topic_id))


def exam_topic_for_week(week_number: int) -> str:
    return f"EXAM_W{week_number}"


def first_topic_for_week(week_number: int) -> str:
    return knowledge_topics_for_week(week_number)[0]["id"]


def next_topic_in_week(topic_id: str) -> str | None:
    week_number = topic_week(topic_id)
    if week_number is None or is_exam_topic(topic_id):
        return None

    topic_ids = [topic["id"] for topic in knowledge_topics_for_week(week_number)]
    try:
        index = topic_ids.index(topic_id)
    except ValueError:
        return None

    next_index = index + 1
    if next_index >= len(topic_ids):
        return None
    return topic_ids[next_index]


def topic_name(topic_id: str) -> str | None:
    for topics in topics_by_week().values():
        for topic in topics:
            if topic["id"] == topic_id:
                return topic["topic"]
    return None
