#!/usr/bin/env python3
from __future__ import annotations

from _bootstrap import ensure_package_root

ensure_package_root()

from devil_ai_tutor.scripts.lib.cli import run_payload_cli
from devil_ai_tutor.scripts.lib.operations import apply_interaction_result


if __name__ == "__main__":
    raise SystemExit(
        run_payload_cli(
            schema_name="apply_interaction_result.payload.schema.json",
            description="Apply a model-evaluated interaction result to a user state",
            handler=apply_interaction_result,
        )
    )
