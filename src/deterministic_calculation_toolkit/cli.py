from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import OPERATION_VERSION, SCHEMA_VERSION, TOOL_VERSION, calculate


def _configure_integer_string_policy() -> None:
    """Make CLI JSON admission match the frozen v0.2 INTEGER contract.

    Python runtimes that expose an integer/string conversion digit limit use
    that limit as a configurable safety policy. The frozen DCT v0.2 contract
    does not treat that host default as a numeric-domain restriction.
    """

    setter = getattr(sys, "set_int_max_str_digits", None)
    if setter is not None:
        setter(0)


_configure_integer_string_policy()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_request(args: argparse.Namespace) -> Any:
    if args.json is not None:
        return json.loads(args.json)
    if args.file is not None:
        return json.loads(Path(args.file).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic Calculation Toolkit CLI")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", help="calculation request as JSON text")
    group.add_argument("--file", help="path to a UTF-8 JSON request file")
    args = parser.parse_args(argv)

    try:
        request = _load_request(args)
    except (json.JSONDecodeError, OSError) as exc:
        result = {
            "schema_version": SCHEMA_VERSION,
            "tool_version": TOOL_VERSION,
            "operation": None,
            "operation_version": OPERATION_VERSION,
            "status": "INVALID_INPUT",
            "error": {"code": "INVALID_INPUT", "message": f"invalid JSON request: {exc}"},
        }
    else:
        result = calculate(request)

    sys.stdout.write(canonical_json(result) + "\n")
    return 0 if result.get("status") == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
