#!/usr/bin/env python3
from __future__ import annotations

import sys

from _bootstrap import ensure_package_root

ensure_package_root()

from devil_ai_tutor.scripts.lib.cli import run_payload_cli
from devil_ai_tutor.scripts.lib.operations import register_user


if __name__ == "__main__":
    raise SystemExit(
        run_payload_cli(
            schema_name="register_user.payload.schema.json",
            description="Register a new devil_ai_tutor user",
            handler=register_user,
        )
    )
