from __future__ import annotations

from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
)
from fractions import Fraction
from math import comb, factorial, perm
import re
from typing import Any, Mapping

SCHEMA_VERSION = "0.1"
TOOL_VERSION = "0.2.0"
OPERATION_VERSION = "1"

STATUS_OK = "OK"
STATUS_INVALID_INPUT = "INVALID_INPUT"
STATUS_DOMAIN_ERROR = "DOMAIN_ERROR"
STATUS_UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
STATUS_UNSUPPORTED_METHOD = "UNSUPPORTED_METHOD"

_DECIMAL_RE = re.compile(r"^[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")

_COMPARE_DECIMAL_RE = re.compile(r"[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_COMPARE_OPERATORS = {"LT", "LE", "EQ", "NE", "GE", "GT"}

ROUNDING_MODES = {
    "HALF_EVEN": ROUND_HALF_EVEN,
    "HALF_UP": ROUND_HALF_UP,
    "HALF_DOWN": ROUND_HALF_DOWN,
    "UP": ROUND_UP,
    "DOWN": ROUND_DOWN,
    "CEILING": ROUND_CEILING,
    "FLOOR": ROUND_FLOOR,
}

_DATA_SIZE_FACTORS = {
    "B": 1,
    "kB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "KiB": 1024,
    "MiB": 1024**2,
    "GiB": 1024**3,
}

_DURATION_FACTORS = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
}

_RATIO_FACTORS = {
    "multiplier": Fraction(1, 1),
    "percent": Fraction(1, 100),
    "basis_points": Fraction(1, 10_000),
}


class ToolkitInputError(ValueError):
    pass


class ToolkitDomainError(ValueError):
    pass


def _error(operation: str | None, status: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "operation": operation,
        "operation_version": OPERATION_VERSION,
        "status": status,
        "error": {"code": status, "message": message},
    }


def _ok(
    operation: str,
    inputs: Mapping[str, Any],
    result: Any,
    numeric_type: str,
    *,
    scale: int | None = None,
    rounding: str | None = None,
    tolerance: Mapping[str, Any] | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "operation": operation,
        "operation_version": OPERATION_VERSION,
        "inputs": dict(inputs),
        "numeric_type": numeric_type,
        "result": result,
        "status": STATUS_OK,
    }
    if scale is not None:
        out["scale"] = scale
    if rounding is not None:
        out["rounding"] = rounding
    if tolerance is not None:
        out["tolerance"] = dict(tolerance)
    if method is not None:
        out["method"] = method
    return out


def _validate_keys(payload: Mapping[str, Any], allowed: set[str], required: set[str]) -> None:
    missing = required - payload.keys()
    if missing:
        raise ToolkitInputError(f"missing required field(s): {', '.join(sorted(missing))}")
    unknown = set(payload) - allowed
    if unknown:
        raise ToolkitInputError(f"unknown field(s): {', '.join(sorted(unknown))}")


def _parse_decimal(value: Any, field: str) -> Decimal:
    if not isinstance(value, str):
        raise ToolkitInputError(f"{field} must be a canonical decimal string")
    if not _DECIMAL_RE.fullmatch(value):
        raise ToolkitInputError(f"{field} must use plain base-10 decimal notation")
    try:
        d = Decimal(value)
    except InvalidOperation as exc:
        raise ToolkitInputError(f"{field} is not a valid decimal") from exc
    if not d.is_finite():
        raise ToolkitInputError(f"{field} must be finite")
    return d


def _parse_nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolkitInputError(f"{field} must be an integer")
    if value < 0:
        raise ToolkitDomainError(f"{field} must be non-negative")
    return value


def _parse_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolkitInputError(f"{field} must be an integer")
    return value


def _parse_scale(payload: Mapping[str, Any], *, required: bool = False) -> int | None:
    if "scale" not in payload:
        if required:
            raise ToolkitInputError("scale is required")
        return None
    scale = payload["scale"]
    if isinstance(scale, bool) or not isinstance(scale, int):
        raise ToolkitInputError("scale must be a non-negative integer")
    if scale < 0:
        raise ToolkitInputError("scale must be a non-negative integer")
    return scale


def _parse_rounding(payload: Mapping[str, Any], *, required: bool = False) -> str | None:
    if "rounding" not in payload:
        if required:
            raise ToolkitInputError("rounding is required")
        return None
    mode = payload["rounding"]
    if not isinstance(mode, str):
        raise ToolkitInputError("rounding must be a string")
    if mode not in ROUNDING_MODES:
        raise ToolkitInputError(f"unsupported rounding mode: {mode}")
    return mode


def _require_scale_rounding_pair(payload: Mapping[str, Any]) -> tuple[int | None, str | None]:
    has_scale = "scale" in payload
    has_rounding = "rounding" in payload
    if has_scale != has_rounding:
        raise ToolkitInputError("scale and rounding must be provided together")
    return _parse_scale(payload), _parse_rounding(payload)


def _format_decimal(d: Decimal, scale: int | None = None) -> str:
    if d.is_zero():
        d = abs(d)
    text = format(d, "f")
    if scale is not None:
        if scale == 0:
            return text.split(".", 1)[0]
        if "." not in text:
            text = text + "." + ("0" * scale)
        else:
            whole, frac = text.split(".", 1)
            text = whole + "." + frac.ljust(scale, "0")[:scale]
        return text
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _decimal_to_fraction(d: Decimal) -> Fraction:
    sign, digits, exponent = d.as_tuple()
    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit
    if sign:
        coefficient = -coefficient
    if exponent >= 0:
        return Fraction(coefficient * (10**exponent), 1)
    return Fraction(coefficient, 10 ** (-exponent))


def _fraction_exact_decimal(frac: Fraction) -> Decimal | None:
    if frac.numerator == 0:
        return Decimal(0)
    den = frac.denominator
    twos = 0
    fives = 0
    while den % 2 == 0:
        den //= 2
        twos += 1
    while den % 5 == 0:
        den //= 5
        fives += 1
    if den != 1:
        return None
    k = max(twos, fives)
    scaled_num = frac.numerator * (2 ** (k - twos)) * (5 ** (k - fives))
    sign = "-" if scaled_num < 0 else ""
    digits = str(abs(scaled_num))
    if k == 0:
        return Decimal(sign + digits)
    digits = digits.rjust(k + 1, "0")
    text = sign + digits[:-k] + "." + digits[-k:]
    return Decimal(text)


def _fraction_quantized_decimal(frac: Fraction, scale: int, rounding: str) -> Decimal:
    """Round an exact Fraction to decimal scale using integer arithmetic only."""
    scaled = frac * (10**scale)
    negative = scaled < 0
    numerator = abs(scaled.numerator)
    denominator = scaled.denominator
    quotient, remainder = divmod(numerator, denominator)

    increment = False
    if remainder:
        if rounding == "DOWN":
            increment = False
        elif rounding == "UP":
            increment = True
        elif rounding == "CEILING":
            increment = not negative
        elif rounding == "FLOOR":
            increment = negative
        else:
            twice_remainder = 2 * remainder
            if twice_remainder > denominator:
                increment = True
            elif twice_remainder < denominator:
                increment = False
            elif rounding == "HALF_UP":
                increment = True
            elif rounding == "HALF_DOWN":
                increment = False
            elif rounding == "HALF_EVEN":
                increment = quotient % 2 == 1
            else:
                raise ToolkitInputError(f"unsupported rounding mode: {rounding}")

    rounded_abs = quotient + (1 if increment else 0)
    rounded_int = -rounded_abs if negative else rounded_abs
    sign = 1 if rounded_int < 0 else 0
    digits = tuple(int(ch) for ch in str(abs(rounded_int)))
    return Decimal((sign, digits, -scale))


def _fraction_result(
    frac: Fraction,
    *,
    scale: int | None,
    rounding: str | None,
) -> tuple[Decimal, int | None, str | None]:
    exact = _fraction_exact_decimal(frac)
    if scale is None or rounding is None:
        if exact is not None:
            return exact, None, None
        raise ToolkitInputError("non-terminating decimal result requires explicit scale and rounding")
    return _fraction_quantized_decimal(frac, scale, rounding), scale, rounding


def _calc_binary(operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    _validate_keys(payload, {"operation", "a", "b", "scale", "rounding"}, {"operation", "a", "b"})
    a = _parse_decimal(payload["a"], "a")
    b = _parse_decimal(payload["b"], "b")
    a_frac = _decimal_to_fraction(a)
    b_frac = _decimal_to_fraction(b)
    if operation == "add":
        frac = a_frac + b_frac
    elif operation == "subtract":
        frac = a_frac - b_frac
    elif operation == "multiply":
        frac = a_frac * b_frac
    else:
        raise AssertionError(operation)
    scale, rounding = _require_scale_rounding_pair(payload)
    result, scale, rounding = _fraction_result(frac, scale=scale, rounding=rounding)
    return _ok(
        operation,
        {"a": payload["a"], "b": payload["b"]},
        _format_decimal(result, scale),
        "DECIMAL",
        scale=scale,
        rounding=rounding,
    )


def _calc_divide(payload: Mapping[str, Any]) -> dict[str, Any]:
    operation = "divide"
    _validate_keys(payload, {"operation", "a", "b", "scale", "rounding"}, {"operation", "a", "b"})
    a = _parse_decimal(payload["a"], "a")
    b = _parse_decimal(payload["b"], "b")
    if b == 0:
        raise ToolkitDomainError("division by zero")
    scale, rounding = _require_scale_rounding_pair(payload)
    frac = _decimal_to_fraction(a) / _decimal_to_fraction(b)
    result, out_scale, out_rounding = _fraction_result(frac, scale=scale, rounding=rounding)
    return _ok(
        operation,
        {"a": payload["a"], "b": payload["b"]},
        _format_decimal(result, out_scale),
        "DECIMAL",
        scale=out_scale,
        rounding=out_rounding,
    )


def _calc_unary(operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    _validate_keys(payload, {"operation", "value", "scale", "rounding"}, {"operation", "value"})
    value = _parse_decimal(payload["value"], "value")
    if operation == "abs":
        scale, rounding = _require_scale_rounding_pair(payload)
        result, scale, rounding = _fraction_result(
            abs(_decimal_to_fraction(value)),
            scale=scale,
            rounding=rounding,
        )
        return _ok(
            operation,
            {"value": payload["value"]},
            _format_decimal(result, scale),
            "DECIMAL",
            scale=scale,
            rounding=rounding,
        )
    if operation == "floor":
        _validate_keys(payload, {"operation", "value"}, {"operation", "value"})
        result = value.to_integral_value(rounding=ROUND_FLOOR)
        return _ok(operation, {"value": payload["value"]}, _format_decimal(result), "DECIMAL")
    if operation == "ceil":
        _validate_keys(payload, {"operation", "value"}, {"operation", "value"})
        result = value.to_integral_value(rounding=ROUND_CEILING)
        return _ok(operation, {"value": payload["value"]}, _format_decimal(result), "DECIMAL")
    raise AssertionError(operation)


def _calc_round(payload: Mapping[str, Any]) -> dict[str, Any]:
    operation = "round"
    _validate_keys(
        payload,
        {"operation", "value", "scale", "rounding"},
        {"operation", "value", "scale", "rounding"},
    )
    value = _parse_decimal(payload["value"], "value")
    scale = _parse_scale(payload, required=True)
    rounding = _parse_rounding(payload, required=True)
    assert scale is not None and rounding is not None
    result = _fraction_quantized_decimal(_decimal_to_fraction(value), scale, rounding)
    return _ok(
        operation,
        {"value": payload["value"]},
        _format_decimal(result, scale),
        "DECIMAL",
        scale=scale,
        rounding=rounding,
    )


def _calc_power_integer(payload: Mapping[str, Any]) -> dict[str, Any]:
    operation = "power_integer"
    _validate_keys(
        payload,
        {"operation", "base", "exponent", "scale", "rounding"},
        {"operation", "base", "exponent"},
    )
    base = _parse_decimal(payload["base"], "base")
    exponent = _parse_integer(payload["exponent"], "exponent")
    if base == 0 and exponent < 0:
        raise ToolkitDomainError("zero cannot be raised to a negative exponent")
    scale, rounding = _require_scale_rounding_pair(payload)
    frac = _decimal_to_fraction(base) ** exponent
    result, out_scale, out_rounding = _fraction_result(frac, scale=scale, rounding=rounding)
    return _ok(
        operation,
        {"base": payload["base"], "exponent": exponent},
        _format_decimal(result, out_scale),
        "DECIMAL",
        scale=out_scale,
        rounding=out_rounding,
    )


def _compare_difference(operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    _validate_keys(
        payload,
        {"operation", "expected", "actual", "scale", "rounding"},
        {"operation", "expected", "actual"},
    )
    expected = _parse_decimal(payload["expected"], "expected")
    actual = _parse_decimal(payload["actual"], "actual")
    frac = abs(_decimal_to_fraction(actual) - _decimal_to_fraction(expected))
    scale, rounding = _require_scale_rounding_pair(payload)
    result, scale, rounding = _fraction_result(frac, scale=scale, rounding=rounding)
    return _ok(
        operation,
        {"expected": payload["expected"], "actual": payload["actual"]},
        _format_decimal(result, scale),
        "DECIMAL",
        scale=scale,
        rounding=rounding,
    )


def _compare_relative_error(payload: Mapping[str, Any]) -> dict[str, Any]:
    operation = "relative_error"
    _validate_keys(
        payload,
        {"operation", "expected", "actual", "scale", "rounding"},
        {"operation", "expected", "actual"},
    )
    expected = _parse_decimal(payload["expected"], "expected")
    actual = _parse_decimal(payload["actual"], "actual")
    if expected == 0:
        raise ToolkitDomainError("relative_error is undefined when expected is zero")
    scale, rounding = _require_scale_rounding_pair(payload)
    frac = abs(_decimal_to_fraction(actual) - _decimal_to_fraction(expected)) / abs(
        _decimal_to_fraction(expected)
    )
    result, out_scale, out_rounding = _fraction_result(frac, scale=scale, rounding=rounding)
    return _ok(
        operation,
        {"expected": payload["expected"], "actual": payload["actual"]},
        _format_decimal(result, out_scale),
        "DECIMAL",
        scale=out_scale,
        rounding=out_rounding,
    )


def _compare_equal_within(payload: Mapping[str, Any]) -> dict[str, Any]:
    operation = "equal_within"
    allowed = {"operation", "expected", "actual", "absolute_tolerance", "relative_tolerance"}
    _validate_keys(payload, allowed, {"operation", "expected", "actual"})
    if "absolute_tolerance" not in payload and "relative_tolerance" not in payload:
        raise ToolkitInputError("at least one tolerance must be provided")
    expected = _parse_decimal(payload["expected"], "expected")
    actual = _parse_decimal(payload["actual"], "actual")
    absolute_tolerance = None
    relative_tolerance = None
    if "absolute_tolerance" in payload:
        absolute_tolerance = _parse_decimal(payload["absolute_tolerance"], "absolute_tolerance")
        if absolute_tolerance < 0:
            raise ToolkitDomainError("absolute_tolerance must be non-negative")
    if "relative_tolerance" in payload:
        relative_tolerance = _parse_decimal(payload["relative_tolerance"], "relative_tolerance")
        if relative_tolerance < 0:
            raise ToolkitDomainError("relative_tolerance must be non-negative")
    expected_frac = _decimal_to_fraction(expected)
    actual_frac = _decimal_to_fraction(actual)
    absolute_difference = abs(actual_frac - expected_frac)
    candidates: list[Fraction] = []
    if absolute_tolerance is not None:
        candidates.append(_decimal_to_fraction(absolute_tolerance))
    if relative_tolerance is not None:
        candidates.append(
            _decimal_to_fraction(relative_tolerance) * abs(expected_frac)
        )
    threshold = max(candidates)
    tolerance = {}
    if absolute_tolerance is not None:
        tolerance["absolute_tolerance"] = payload["absolute_tolerance"]
    if relative_tolerance is not None:
        tolerance["relative_tolerance"] = payload["relative_tolerance"]
    return _ok(
        operation,
        {"expected": payload["expected"], "actual": payload["actual"]},
        absolute_difference <= threshold,
        "BOOLEAN",
        tolerance=tolerance,
        method="max(absolute_tolerance, relative_tolerance * abs(expected))",
    )




def _validate_new_integer_operands(payload: Mapping[str, Any]) -> tuple[int, int]:
    """Validate v0.2 integer types before any domain rule is applied."""
    dividend = payload["dividend"]
    divisor = payload["divisor"]

    invalid_fields: list[str] = []
    if isinstance(dividend, bool) or not isinstance(dividend, int):
        invalid_fields.append("dividend")
    if isinstance(divisor, bool) or not isinstance(divisor, int):
        invalid_fields.append("divisor")
    if invalid_fields:
        raise ToolkitInputError(
            f"{', '.join(invalid_fields)} must be integer value(s)"
        )

    if dividend < 0:
        raise ToolkitDomainError("dividend must be non-negative")
    if divisor <= 0:
        raise ToolkitDomainError("divisor must be positive")
    return dividend, divisor


def _calc_modulo_integer(payload: Mapping[str, Any]) -> dict[str, Any]:
    operation = "modulo_integer"
    _validate_keys(
        payload,
        {"operation", "dividend", "divisor"},
        {"operation", "dividend", "divisor"},
    )
    dividend, divisor = _validate_new_integer_operands(payload)
    return _ok(
        operation,
        {"dividend": payload["dividend"], "divisor": payload["divisor"]},
        dividend % divisor,
        "INTEGER",
    )


def _parse_compare_decimal_text(value: Any, field: str) -> tuple[int, str, str]:
    if not isinstance(value, str):
        raise ToolkitInputError(f"{field} must be a canonical decimal string")
    if _COMPARE_DECIMAL_RE.fullmatch(value) is None:
        raise ToolkitInputError(
            f"{field} must use canonical plain base-10 decimal notation"
        )

    sign = -1 if value.startswith("-") else 1
    unsigned = value[1:] if value[:1] in {"+", "-"} else value
    if "." in unsigned:
        integer_part, fractional_part = unsigned.split(".", 1)
    else:
        integer_part, fractional_part = unsigned, ""

    if integer_part == "0" and (
        not fractional_part or all(ch == "0" for ch in fractional_part)
    ):
        sign = 1
    return sign, integer_part, fractional_part


def _compare_decimal_parts(
    left: tuple[int, str, str],
    right: tuple[int, str, str],
) -> int:
    left_sign, left_int, left_frac = left
    right_sign, right_int, right_frac = right

    if left_sign != right_sign:
        return -1 if left_sign < right_sign else 1

    magnitude = 0
    if len(left_int) != len(right_int):
        magnitude = -1 if len(left_int) < len(right_int) else 1
    elif left_int != right_int:
        magnitude = -1 if left_int < right_int else 1
    else:
        width = max(len(left_frac), len(right_frac))
        left_padded = left_frac.ljust(width, "0")
        right_padded = right_frac.ljust(width, "0")
        if left_padded != right_padded:
            magnitude = -1 if left_padded < right_padded else 1

    return magnitude if left_sign > 0 else -magnitude


def _calc_compare_exact(payload: Mapping[str, Any]) -> dict[str, Any]:
    operation = "compare_exact"
    _validate_keys(
        payload,
        {"operation", "a", "b", "operator"},
        {"operation", "a", "b", "operator"},
    )

    # All type failures remain INVALID_INPUT and are checked before
    # representation / operator-vocabulary evaluation.
    if not isinstance(payload["a"], str):
        raise ToolkitInputError("a must be a canonical decimal string")
    if not isinstance(payload["b"], str):
        raise ToolkitInputError("b must be a canonical decimal string")
    if not isinstance(payload["operator"], str):
        raise ToolkitInputError("operator must be a string")

    a_parts = _parse_compare_decimal_text(payload["a"], "a")
    b_parts = _parse_compare_decimal_text(payload["b"], "b")
    operator = payload["operator"]
    if operator not in _COMPARE_OPERATORS:
        raise ToolkitInputError(f"unsupported exact comparison operator: {operator}")

    comparison = _compare_decimal_parts(a_parts, b_parts)
    predicates = {
        "LT": comparison < 0,
        "LE": comparison <= 0,
        "EQ": comparison == 0,
        "NE": comparison != 0,
        "GE": comparison >= 0,
        "GT": comparison > 0,
    }
    return _ok(
        operation,
        {"a": payload["a"], "b": payload["b"], "operator": operator},
        predicates[operator],
        "BOOLEAN",
    )


def _calc_divmod_integer(payload: Mapping[str, Any]) -> dict[str, Any]:
    operation = "divmod_integer"
    _validate_keys(
        payload,
        {"operation", "dividend", "divisor"},
        {"operation", "dividend", "divisor"},
    )
    dividend, divisor = _validate_new_integer_operands(payload)
    quotient, remainder = divmod(dividend, divisor)
    return _ok(
        operation,
        {"dividend": payload["dividend"], "divisor": payload["divisor"]},
        {"quotient": quotient, "remainder": remainder},
        "INTEGER_PAIR",
    )


def _convert_by_factor(
    operation: str,
    payload: Mapping[str, Any],
    factors: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_keys(
        payload,
        {"operation", "value", "from_unit", "to_unit", "scale", "rounding"},
        {"operation", "value", "from_unit", "to_unit"},
    )
    value = _parse_decimal(payload["value"], "value")
    from_unit = payload["from_unit"]
    to_unit = payload["to_unit"]
    if not isinstance(from_unit, str) or not isinstance(to_unit, str):
        raise ToolkitInputError("from_unit and to_unit must be strings")
    if from_unit not in factors or to_unit not in factors:
        raise ToolkitInputError("unsupported unit")
    scale, rounding = _require_scale_rounding_pair(payload)
    from_factor = factors[from_unit]
    to_factor = factors[to_unit]
    if isinstance(from_factor, Fraction):
        frac = _decimal_to_fraction(value) * from_factor / to_factor
    else:
        frac = _decimal_to_fraction(value) * Fraction(from_factor, to_factor)
    result, out_scale, out_rounding = _fraction_result(frac, scale=scale, rounding=rounding)
    return _ok(
        operation,
        {"value": payload["value"], "from_unit": from_unit, "to_unit": to_unit},
        _format_decimal(result, out_scale),
        "DECIMAL",
        scale=out_scale,
        rounding=out_rounding,
    )


def _convert_temperature(payload: Mapping[str, Any]) -> dict[str, Any]:
    operation = "convert_temperature"
    _validate_keys(
        payload,
        {"operation", "value", "from_unit", "to_unit", "scale", "rounding"},
        {"operation", "value", "from_unit", "to_unit"},
    )
    value = _parse_decimal(payload["value"], "value")
    from_unit = payload["from_unit"]
    to_unit = payload["to_unit"]
    if not isinstance(from_unit, str) or not isinstance(to_unit, str):
        raise ToolkitInputError("from_unit and to_unit must be strings")
    if from_unit not in {"Celsius", "Fahrenheit"} or to_unit not in {"Celsius", "Fahrenheit"}:
        raise ToolkitInputError("temperature units must be Celsius or Fahrenheit")
    scale, rounding = _require_scale_rounding_pair(payload)
    frac = _decimal_to_fraction(value)
    if from_unit == to_unit:
        out_frac = frac
    elif from_unit == "Celsius":
        out_frac = frac * Fraction(9, 5) + 32
    else:
        out_frac = (frac - 32) * Fraction(5, 9)
    result, out_scale, out_rounding = _fraction_result(out_frac, scale=scale, rounding=rounding)
    return _ok(
        operation,
        {"value": payload["value"], "from_unit": from_unit, "to_unit": to_unit},
        _format_decimal(result, out_scale),
        "DECIMAL",
        scale=out_scale,
        rounding=out_rounding,
    )


def _parse_decimal_list(value: Any, field: str = "values") -> list[Decimal]:
    if not isinstance(value, list):
        raise ToolkitInputError(f"{field} must be a list")
    return [_parse_decimal(v, f"{field}[{i}]") for i, v in enumerate(value)]


def _stats(operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    _validate_keys(
        payload,
        {"operation", "values", "scale", "rounding"},
        {"operation", "values"},
    )
    values_raw = payload["values"]
    values = _parse_decimal_list(values_raw)
    if operation == "count":
        _validate_keys(payload, {"operation", "values"}, {"operation", "values"})
        return _ok(operation, {"values": values_raw}, len(values), "INTEGER")
    if not values:
        raise ToolkitDomainError(f"{operation} is undefined for an empty input")
    if operation == "sum":
        frac = sum((_decimal_to_fraction(v) for v in values), Fraction(0, 1))
        scale, rounding = _require_scale_rounding_pair(payload)
        result, scale, rounding = _fraction_result(frac, scale=scale, rounding=rounding)
        return _ok(
            operation,
            {"values": values_raw},
            _format_decimal(result, scale),
            "DECIMAL",
            scale=scale,
            rounding=rounding,
        )
    if operation == "min":
        _validate_keys(payload, {"operation", "values"}, {"operation", "values"})
        return _ok(operation, {"values": values_raw}, _format_decimal(min(values)), "DECIMAL")
    if operation == "max":
        _validate_keys(payload, {"operation", "values"}, {"operation", "values"})
        return _ok(operation, {"values": values_raw}, _format_decimal(max(values)), "DECIMAL")
    if operation == "mean":
        scale, rounding = _require_scale_rounding_pair(payload)
        frac = sum((_decimal_to_fraction(v) for v in values), Fraction(0, 1)) / len(values)
        result, out_scale, out_rounding = _fraction_result(
            frac,
            scale=scale,
            rounding=rounding,
        )
        return _ok(
            operation,
            {"values": values_raw},
            _format_decimal(result, out_scale),
            "DECIMAL",
            scale=out_scale,
            rounding=out_rounding,
        )
    if operation == "median":
        scale, rounding = _require_scale_rounding_pair(payload)
        ordered = sorted(values)
        n = len(ordered)
        if n % 2:
            frac = _decimal_to_fraction(ordered[n // 2])
        else:
            frac = (
                _decimal_to_fraction(ordered[n // 2 - 1])
                + _decimal_to_fraction(ordered[n // 2])
            ) / 2
        result, out_scale, out_rounding = _fraction_result(
            frac,
            scale=scale,
            rounding=rounding,
        )
        return _ok(
            operation,
            {"values": values_raw},
            _format_decimal(result, out_scale),
            "DECIMAL",
            scale=out_scale,
            rounding=out_rounding,
        )
    raise AssertionError(operation)


def _combinatorics(operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if operation == "factorial":
        _validate_keys(payload, {"operation", "n"}, {"operation", "n"})
        n = _parse_nonnegative_int(payload["n"], "n")
        return _ok(operation, {"n": n}, factorial(n), "INTEGER")
    _validate_keys(payload, {"operation", "n", "r"}, {"operation", "n", "r"})
    n = _parse_nonnegative_int(payload["n"], "n")
    r = _parse_nonnegative_int(payload["r"], "r")
    if r > n:
        raise ToolkitDomainError("r must not exceed n")
    if operation == "nCr":
        result = comb(n, r)
    elif operation == "nPr":
        result = perm(n, r)
    else:
        raise AssertionError(operation)
    return _ok(operation, {"n": n, "r": r}, result, "INTEGER")


_SUPPORTED = {
    "add",
    "subtract",
    "multiply",
    "divide",
    "abs",
    "floor",
    "ceil",
    "round",
    "power_integer",
    "absolute_difference",
    "absolute_error",
    "relative_error",
    "equal_within",
    "convert_data_size",
    "convert_duration",
    "convert_ratio",
    "convert_temperature",
    "count",
    "sum",
    "min",
    "max",
    "mean",
    "median",
    "factorial",
    "nCr",
    "nPr",
    "modulo_integer",
    "compare_exact",
    "divmod_integer",
}


def calculate(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Execute one explicit deterministic calculation request.

    The function does not interpret natural language or choose mathematical
    conventions. It validates an explicit operation contract and returns a
    structured result with stable status semantics.
    """
    if not isinstance(payload, Mapping):
        return _error(None, STATUS_INVALID_INPUT, "request must be an object")
    operation = payload.get("operation")
    if not isinstance(operation, str) or not operation:
        return _error(None, STATUS_INVALID_INPUT, "operation must be a non-empty string")
    if operation not in _SUPPORTED:
        return _error(
            operation,
            STATUS_UNSUPPORTED_OPERATION,
            f"unsupported operation: {operation}",
        )
    try:
        if operation in {"add", "subtract", "multiply"}:
            return _calc_binary(operation, payload)
        if operation == "divide":
            return _calc_divide(payload)
        if operation in {"abs", "floor", "ceil"}:
            return _calc_unary(operation, payload)
        if operation == "round":
            return _calc_round(payload)
        if operation == "power_integer":
            return _calc_power_integer(payload)
        if operation in {"absolute_difference", "absolute_error"}:
            return _compare_difference(operation, payload)
        if operation == "relative_error":
            return _compare_relative_error(payload)
        if operation == "equal_within":
            return _compare_equal_within(payload)
        if operation == "convert_data_size":
            return _convert_by_factor(operation, payload, _DATA_SIZE_FACTORS)
        if operation == "convert_duration":
            return _convert_by_factor(operation, payload, _DURATION_FACTORS)
        if operation == "convert_ratio":
            return _convert_by_factor(operation, payload, _RATIO_FACTORS)
        if operation == "convert_temperature":
            return _convert_temperature(payload)
        if operation in {"count", "sum", "min", "max", "mean", "median"}:
            return _stats(operation, payload)
        if operation in {"factorial", "nCr", "nPr"}:
            return _combinatorics(operation, payload)
        if operation == "modulo_integer":
            return _calc_modulo_integer(payload)
        if operation == "compare_exact":
            return _calc_compare_exact(payload)
        if operation == "divmod_integer":
            return _calc_divmod_integer(payload)
        return _error(
            operation,
            STATUS_UNSUPPORTED_OPERATION,
            f"unsupported operation: {operation}",
        )
    except ToolkitInputError as exc:
        return _error(operation, STATUS_INVALID_INPUT, str(exc))
    except ToolkitDomainError as exc:
        return _error(operation, STATUS_DOMAIN_ERROR, str(exc))
    except (InvalidOperation, ArithmeticError) as exc:
        return _error(
            operation,
            STATUS_DOMAIN_ERROR,
            str(exc) or exc.__class__.__name__,
        )
