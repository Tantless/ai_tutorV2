#!/usr/bin/env python3
from __future__ import annotations

from _bootstrap import ensure_package_root

ensure_package_root()

from devil_ai_tutor.scripts.lib.cli import run_payload_cli
from devil_ai_tutor.scripts.lib.operations import settle_week


if __name__ == "__main__":
    raise SystemExit(
        run_payload_cli(
            schema_name="settle_week.payload.schema.json",
            description="Settle a weekly exam and roll the user into the next state",
            handler=settle_week,
        )
    )
