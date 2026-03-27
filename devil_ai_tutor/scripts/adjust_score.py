#!/usr/bin/env python3
from __future__ import annotations

import argparse

from _bootstrap import ensure_package_root

ensure_package_root()

from devil_ai_tutor.scripts.lib.cli import run_payload_cli
from devil_ai_tutor.scripts.lib.operations import adjust_score

LEGACY_SCORE_TYPES = {
    "平时分": "estimated_score",
    "实际段位分": "actual_score",
    "总分": "total_score",
}


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("username", nargs="?")
    parser.add_argument("score_type", nargs="?")
    parser.add_argument("new_score", nargs="?")


def legacy_loader(args: argparse.Namespace) -> dict:
    if not args.username or not args.score_type or args.new_score is None:
        raise ValueError("legacy mode requires: <username> <score_type> <new_score>")
    return {
        "username": args.username,
        "score_type": LEGACY_SCORE_TYPES.get(args.score_type, args.score_type),
        "new_score": float(args.new_score),
    }


if __name__ == "__main__":
    raise SystemExit(
        run_payload_cli(
            schema_name="adjust_score.payload.schema.json",
            description="Adjust one score field through a validated payload",
            handler=adjust_score,
            configure_parser=configure_parser,
            legacy_loader=legacy_loader,
        )
    )
