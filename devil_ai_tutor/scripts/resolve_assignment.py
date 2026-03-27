#!/usr/bin/env python3
from __future__ import annotations

from _bootstrap import ensure_package_root

ensure_package_root()

from devil_ai_tutor.scripts.lib.cli import run_payload_cli
from devil_ai_tutor.scripts.lib.operations import resolve_assignment


if __name__ == "__main__":
    raise SystemExit(
        run_payload_cli(
            schema_name="resolve_assignment.payload.schema.json",
            description="Resolve the only valid assignment topic for a user and delivery type",
            handler=resolve_assignment,
        )
    )
