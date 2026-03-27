from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OperationError(Exception):
    message: str
    errors: list[str] = field(default_factory=list)
    entity: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        super().__init__(self.message)
        if not self.errors:
            self.errors = [self.message]


def ok_result(
    entity: dict[str, Any],
    changes: list[str] | None = None,
    logs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "entity": entity,
        "changes": changes or [],
        "logs": logs or [],
        "errors": [],
    }


def error_result(
    message: str,
    entity: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": "error",
        "entity": entity or {"type": "unknown", "id": None},
        "changes": [],
        "logs": [],
        "errors": errors or [message],
    }
