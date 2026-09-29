import json
from pathlib import Path

import pytest

from deterministic_calculation_toolkit import calculate


def _parse_unbounded_json_int(text: str) -> int:
    """Parse an arbitrary-width JSON integer without changing host digit limits."""
    negative = text.startswith("-")
    digits = text[1:] if negative else text
    value = 0
    for index in range(0, len(digits), 9):
        chunk = digits[index : index + 9]
        value = value * (10 ** len(chunk)) + int(chunk)
    return -value if negative else value


def _load_fixture(name: str):
    path = Path(__file__).parent / "fixtures" / name
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_int=_parse_unbounded_json_int,
    )


FIXTURES = _load_fixture("golden_v0.1.json") + _load_fixture("golden_v0.2.json")


@pytest.mark.parametrize("fixture", FIXTURES, ids=[x["name"] for x in FIXTURES])
def test_golden_fixture(fixture):
    result = calculate(fixture["request"])
    assert result["status"] == fixture["status"]
    if "result" in fixture:
        assert result["result"] == fixture["result"]
    else:
        assert "result" not in result
