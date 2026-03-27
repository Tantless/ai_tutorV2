#!/usr/bin/env python3
from __future__ import annotations

from _bootstrap import ensure_package_root

ensure_package_root()

from devil_ai_tutor.scripts.lib.cli import run_payload_cli
from devil_ai_tutor.scripts.lib.operations import update_heartbeat_state


if __name__ == "__main__":
    raise SystemExit(
        run_payload_cli(
            schema_name="update_heartbeat_state.payload.schema.json",
            description="Update heartbeat_state.json through a controlled payload",
            handler=update_heartbeat_state,
        )
    )
