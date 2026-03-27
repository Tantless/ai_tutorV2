#!/usr/bin/env python3
from __future__ import annotations

import argparse

from _bootstrap import ensure_package_root

ensure_package_root()

from devil_ai_tutor.scripts.lib.cli import run_payload_cli
from devil_ai_tutor.scripts.lib.operations import promote_level


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("username", nargs="?")
    parser.add_argument("target_level", nargs="?")


def legacy_loader(args: argparse.Namespace) -> dict:
    if not args.username or not args.target_level:
        raise ValueError("legacy mode requires: <username> <target_level>")
    return {
        "username": args.username,
        "target_level": args.target_level,
    }


if __name__ == "__main__":
    raise SystemExit(
        run_payload_cli(
            schema_name="promote_level.payload.schema.json",
            description="Promote a user to a validated target level",
            handler=promote_level,
            configure_parser=configure_parser,
            legacy_loader=legacy_loader,
        )
    )
