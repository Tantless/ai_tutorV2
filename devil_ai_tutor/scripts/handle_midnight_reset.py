#!/usr/bin/env python3
from __future__ import annotations

from _bootstrap import ensure_package_root

ensure_package_root()

from devil_ai_tutor.scripts.lib.cli import run_payload_cli
from devil_ai_tutor.scripts.lib.operations import handle_midnight_reset


if __name__ == "__main__":
    raise SystemExit(
        run_payload_cli(
            schema_name="handle_midnight_reset.payload.schema.json",
            description="Reset daily state and optionally apply a missed-deadline penalty",
            handler=handle_midnight_reset,
        )
    )
