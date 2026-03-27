from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

from .context import schemas_dir
from .result import OperationError


@lru_cache(maxsize=None)
def load_schema(schema_name: str) -> dict[str, Any]:
    schema_path = schemas_dir() / schema_name
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_schema_payload(schema_name: str, payload: Any) -> None:
    schema = load_schema(schema_name)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema, format_checker=jsonschema.FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if errors:
        rendered = []
        for error in errors:
            path = ".".join(str(part) for part in error.absolute_path) or "$"
            rendered.append(f"{path}: {error.message}")
        raise OperationError(
            f"schema validation failed for {schema_name}",
            errors=rendered,
        )
