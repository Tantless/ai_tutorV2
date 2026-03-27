from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from .result import OperationError, error_result
from .schema_utils import validate_schema_payload


Handler = Callable[[dict[str, Any]], dict[str, Any]]
LegacyPayloadLoader = Callable[[argparse.Namespace], dict[str, Any]]


def _parse_payload_argument(value: str) -> dict[str, Any]:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    return payload


def _load_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "payload_json", None):
        return _parse_payload_argument(args.payload_json)

    if getattr(args, "payload_file", None):
        with open(args.payload_file, "r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("payload file must contain a JSON object")
        return payload

    raw_stdin = sys.stdin.read().lstrip("\ufeff").strip()
    if not raw_stdin:
        raise ValueError("missing JSON payload")
    payload = json.loads(raw_stdin)
    if not isinstance(payload, dict):
        raise ValueError("stdin payload must be a JSON object")
    return payload


def run_payload_cli(
    *,
    schema_name: str,
    description: str,
    handler: Handler,
    configure_parser: Callable[[argparse.ArgumentParser], None] | None = None,
    legacy_loader: LegacyPayloadLoader | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--payload-json", help="Inline JSON payload")
    parser.add_argument("--payload-file", help="Path to a JSON payload file")
    if configure_parser:
        configure_parser(parser)
    args = parser.parse_args()

    try:
        arg_values = vars(args)
        has_payload_args = any([args.payload_json, args.payload_file])
        has_legacy_args = any(
            value is not None
            for key, value in arg_values.items()
            if key not in {"payload_json", "payload_file"}
        )

        if legacy_loader and not has_payload_args and has_legacy_args:
            payload = legacy_loader(args)
        else:
            payload = _load_payload_from_args(args)

        validate_schema_payload(schema_name, payload)
        result = handler(payload)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") == "ok" else 1
    except OperationError as exc:
        print(
            json.dumps(
                error_result(exc.message, entity=exc.entity, errors=exc.errors),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    except Exception as exc:  # pragma: no cover - top-level safety net
        print(json.dumps(error_result(str(exc)), ensure_ascii=False, indent=2))
        return 1
