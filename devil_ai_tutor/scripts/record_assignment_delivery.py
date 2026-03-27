#!/usr/bin/env python3
from __future__ import annotations

from _bootstrap import ensure_package_root

ensure_package_root()

from devil_ai_tutor.scripts.lib.cli import run_payload_cli
from devil_ai_tutor.scripts.lib.operations import record_assignment_delivery


if __name__ == "__main__":
    raise SystemExit(
        run_payload_cli(
            schema_name="record_assignment_delivery.payload.schema.json",
            description="Record a delivered quiz, exam, or consolidation assignment",
            handler=record_assignment_delivery,
        )
    )
