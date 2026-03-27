from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def skill_root() -> Path:
    override = os.environ.get("DEVIL_AI_TUTOR_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return skill_root() / "data"


def users_dir() -> Path:
    return data_dir() / "users"


def schemas_dir() -> Path:
    return skill_root() / "schemas"


def references_dir() -> Path:
    return skill_root() / "references"


def heartbeat_state_path() -> Path:
    return data_dir() / "heartbeat_state.json"


def syllabus_path() -> Path:
    return data_dir() / "syllabus.json"


def user_template_path() -> Path:
    return users_dir() / "user_template.json"


def user_path(username: str) -> Path:
    return users_dir() / f"{username}.json"
