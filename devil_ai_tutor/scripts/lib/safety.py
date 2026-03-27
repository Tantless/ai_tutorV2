from __future__ import annotations

from typing import Any

from .result import OperationError


def processed_operations(user_data: dict[str, Any]) -> list[dict[str, Any]]:
    return user_data.setdefault("processed_operations", [])


def get_processed_operation(user_data: dict[str, Any], operation_id: str) -> dict[str, Any] | None:
    return next(
        (entry for entry in processed_operations(user_data) if entry.get("operation_id") == operation_id),
        None,
    )


def is_operation_processed(user_data: dict[str, Any], operation_id: str) -> bool:
    return get_processed_operation(user_data, operation_id) is not None


def mark_operation_processed(
    user_data: dict[str, Any],
    operation_id: str,
    action: str,
    date: str,
    **metadata: Any,
) -> dict[str, Any]:
    existing = get_processed_operation(user_data, operation_id)
    if existing is not None:
        return existing

    entry = {
        "operation_id": operation_id,
        "action": action,
        "date": date,
    }
    for key, value in metadata.items():
        if value is not None:
            entry[key] = value
    processed_operations(user_data).append(entry)
    return entry


def assignment_receipts(user_data: dict[str, Any]) -> list[dict[str, Any]]:
    current_week_state = user_data.setdefault("current_week_state", {})
    return current_week_state.setdefault("assignment_receipts", [])


def upsert_assignment_receipt(
    user_data: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    receipts = assignment_receipts(user_data)
    match = next(
        (
            entry
            for entry in receipts
            if entry.get("delivery_type") == receipt["delivery_type"]
            and entry.get("topic_id") == receipt["topic_id"]
            and entry.get("date") == receipt["date"]
        ),
        None,
    )
    if match is None:
        receipts.append(receipt)
        return receipt

    match.update(receipt)
    return match


def require_receipt(
    user_data: dict[str, Any],
    *,
    delivery_type: str,
    topic_id: str,
    date: str,
) -> dict[str, Any]:
    for receipt in assignment_receipts(user_data):
        if (
            receipt.get("delivery_type") == delivery_type
            and receipt.get("topic_id") == topic_id
            and receipt.get("date") == date
        ):
            return receipt
    raise OperationError(
        f"missing assignment receipt for {delivery_type}:{topic_id}:{date}",
    )


def clear_assignment_receipts(user_data: dict[str, Any]) -> list[dict[str, Any]]:
    current_week_state = user_data.setdefault("current_week_state", {})
    current_week_state["assignment_receipts"] = []
    return current_week_state["assignment_receipts"]
