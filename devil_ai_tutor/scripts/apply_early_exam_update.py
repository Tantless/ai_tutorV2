#!/usr/bin/env python3
from __future__ import annotations

from _bootstrap import ensure_package_root

ensure_package_root()

from devil_ai_tutor.scripts.lib.cli import run_payload_cli
from devil_ai_tutor.scripts.lib.operations import apply_early_exam_update


if __name__ == "__main__":
    raise SystemExit(
        run_payload_cli(
            schema_name="apply_early_exam_update.payload.schema.json",
            description="Apply an early-exam or try-it mode transition",
            handler=apply_early_exam_update,
        )
    )
