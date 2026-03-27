#!/usr/bin/env python3
from __future__ import annotations

from _bootstrap import ensure_package_root

ensure_package_root()

from devil_ai_tutor.scripts.lib.cli import run_payload_cli
from devil_ai_tutor.scripts.lib.operations import repair_user_data


if __name__ == "__main__":
    raise SystemExit(
        run_payload_cli(
            schema_name="repair_user_data.payload.schema.json",
            description="Apply deterministic repairs to one user file",
            handler=repair_user_data,
        )
    )
