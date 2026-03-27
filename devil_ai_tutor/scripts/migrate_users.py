#!/usr/bin/env python3
from __future__ import annotations

from _bootstrap import ensure_package_root

ensure_package_root()

from devil_ai_tutor.scripts.lib.cli import run_payload_cli
from devil_ai_tutor.scripts.lib.operations import migrate_users


if __name__ == "__main__":
    raise SystemExit(
        run_payload_cli(
            schema_name="migrate_users.payload.schema.json",
            description="Canonicalize existing user files and report unresolved conflicts",
            handler=migrate_users,
        )
    )
