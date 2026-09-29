from decimal import ROUND_FLOOR, localcontext
from fractions import Fraction
import sys

import pytest

from deterministic_calculation_toolkit import calculate


@pytest.mark.parametrize(
    ("value", "mode", "expected"),
    [
        ("2.5", "HALF_EVEN", "2"),
        ("3.5", "HALF_EVEN", "4"),
        ("2.5", "HALF_UP", "3"),
        ("2.5", "HALF_DOWN", "2"),
        ("2.1", "UP", "3"),
        ("2.9", "DOWN", "2"),
        ("-2.1", "CEILING", "-2"),
        ("-2.1", "FLOOR", "-3"),
    ],
)
def test_rounding_modes(value, mode, expected):
    out = calculate(
        {"operation": "round", "value": value, "scale": 0, "rounding": mode}
    )
    assert out["status"] == "OK"
    assert out["result"] == expected


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ({"operation": "floor", "value": "2.9"}, "2"),
        ({"operation": "floor", "value": "-2.1"}, "-3"),
        ({"operation": "ceil", "value": "2.1"}, "3"),
        ({"operation": "ceil", "value": "-2.9"}, "-2"),
        ({"operation": "abs", "value": "-0.000"}, "0"),
        ({"operation": "power_integer", "base": "2", "exponent": 10}, "1024"),
        ({"operation": "power_integer", "base": "2", "exponent": -3}, "0.125"),
    ],
)
def test_unary_and_power(case, expected):
    out = calculate(case)
    assert out["status"] == "OK"
    assert out["result"] == expected


def test_negative_power_repeating_requires_policy():
    out = calculate({"operation": "power_integer", "base": "3", "exponent": -1})
    assert out["status"] == "INVALID_INPUT"
    assert "result" not in out


def test_negative_power_repeating_with_policy():
    out = calculate(
        {
            "operation": "power_integer",
            "base": "3",
            "exponent": -1,
            "scale": 6,
            "rounding": "HALF_UP",
        }
    )
    assert out["status"] == "OK"
    assert out["result"] == "0.333333"


def test_zero_negative_power_domain_error():
    out = calculate({"operation": "power_integer", "base": "0", "exponent": -1})
    assert out["status"] == "DOMAIN_ERROR"


def test_optional_scale_requires_rounding():
    out = calculate({"operation": "add", "a": "1", "b": "2", "scale": 2})
    assert out["status"] == "INVALID_INPUT"


def test_optional_rounding_requires_scale():
    out = calculate(
        {"operation": "add", "a": "1", "b": "2", "rounding": "HALF_EVEN"}
    )
    assert out["status"] == "INVALID_INPUT"


def test_scale_preserves_trailing_zeroes():
    out = calculate(
        {
            "operation": "add",
            "a": "1",
            "b": "2",
            "scale": 2,
            "rounding": "HALF_EVEN",
        }
    )
    assert out["result"] == "3.00"
    assert out["scale"] == 2


def test_negative_zero_is_canonicalized():
    out = calculate({"operation": "add", "a": "-0.0", "b": "0"})
    assert out["result"] == "0"


def test_unknown_field_is_rejected():
    out = calculate({"operation": "add", "a": "1", "b": "2", "guess": True})
    assert out["status"] == "INVALID_INPUT"


def test_unknown_operation_is_explicit():
    out = calculate({"operation": "sqrt", "value": "4"})
    assert out["status"] == "UNSUPPORTED_OPERATION"
    assert "result" not in out


def test_missing_operation_is_invalid():
    out = calculate({"a": "1", "b": "2"})
    assert out["status"] == "INVALID_INPUT"


def test_non_object_request_is_invalid():
    out = calculate([1, 2, 3])
    assert out["status"] == "INVALID_INPUT"


def test_plain_decimal_not_exponent_notation():
    out = calculate({"operation": "add", "a": "1e-3", "b": "1"})
    assert out["status"] == "INVALID_INPUT"


def test_relative_error_repeating_requires_policy():
    out = calculate(
        {"operation": "relative_error", "expected": "3", "actual": "4"}
    )
    assert out["status"] == "INVALID_INPUT"


def test_relative_error_repeating_with_policy():
    out = calculate(
        {
            "operation": "relative_error",
            "expected": "3",
            "actual": "4",
            "scale": 4,
            "rounding": "HALF_UP",
        }
    )
    assert out["status"] == "OK"
    assert out["result"] == "0.3333"


def test_equal_within_expected_zero_relative_only():
    out = calculate(
        {
            "operation": "equal_within",
            "expected": "0",
            "actual": "0",
            "relative_tolerance": "0.1",
        }
    )
    assert out["status"] == "OK"
    assert out["result"] is True


def test_equal_within_expected_zero_relative_only_nonzero_actual():
    out = calculate(
        {
            "operation": "equal_within",
            "expected": "0",
            "actual": "0.0001",
            "relative_tolerance": "0.1",
        }
    )
    assert out["status"] == "OK"
    assert out["result"] is False


def test_negative_tolerance_is_domain_error():
    out = calculate(
        {
            "operation": "equal_within",
            "expected": "1",
            "actual": "1",
            "absolute_tolerance": "-0.1",
        }
    )
    assert out["status"] == "DOMAIN_ERROR"


@pytest.mark.parametrize(
    ("from_unit", "to_unit", "value", "expected"),
    [
        ("GB", "MB", "1", "1000"),
        ("GiB", "MiB", "1", "1024"),
        ("minute", "second", "1.5", "90"),
        ("multiplier", "percent", "0.125", "12.5"),
        ("percent", "basis_points", "1", "100"),
    ],
)
def test_exact_conversions(from_unit, to_unit, value, expected):
    op = {
        ("GB", "MB"): "convert_data_size",
        ("GiB", "MiB"): "convert_data_size",
        ("minute", "second"): "convert_duration",
        ("multiplier", "percent"): "convert_ratio",
        ("percent", "basis_points"): "convert_ratio",
    }[(from_unit, to_unit)]
    out = calculate(
        {
            "operation": op,
            "value": value,
            "from_unit": from_unit,
            "to_unit": to_unit,
        }
    )
    assert out["status"] == "OK"
    assert out["result"] == expected


def test_temperature_c_to_f():
    out = calculate(
        {
            "operation": "convert_temperature",
            "value": "100",
            "from_unit": "Celsius",
            "to_unit": "Fahrenheit",
        }
    )
    assert out["status"] == "OK"
    assert out["result"] == "212"


def test_temperature_nonterminating_requires_rounding():
    out = calculate(
        {
            "operation": "convert_temperature",
            "value": "33",
            "from_unit": "Fahrenheit",
            "to_unit": "Celsius",
        }
    )
    assert out["status"] == "INVALID_INPUT"


def test_temperature_non_string_unit_is_invalid_input():
    out = calculate(
        {
            "operation": "convert_temperature",
            "value": "33",
            "from_unit": [],
            "to_unit": "Celsius",
        }
    )
    assert out["status"] == "INVALID_INPUT"
    assert "result" not in out


def test_large_repeating_division_keeps_integer_precision():
    numerator = "1" + ("0" * 120)
    out = calculate(
        {
            "operation": "divide",
            "a": numerator,
            "b": "3",
            "scale": 2,
            "rounding": "HALF_EVEN",
        }
    )
    assert out["status"] == "OK"
    assert out["result"] == (("3" * 120) + ".33")


def test_min_max():
    assert calculate(
        {"operation": "min", "values": ["3", "-1", "2"]}
    )["result"] == "-1"
    assert calculate(
        {"operation": "max", "values": ["3", "-1", "2"]}
    )["result"] == "3"


def test_median_odd():
    out = calculate({"operation": "median", "values": ["9", "1", "3"]})
    assert out["result"] == "3"


def test_median_empty_domain_error():
    out = calculate({"operation": "median", "values": []})
    assert out["status"] == "DOMAIN_ERROR"


def test_stats_float_member_rejected():
    out = calculate({"operation": "sum", "values": ["1", 2.0]})
    assert out["status"] == "INVALID_INPUT"


def test_factorial_negative_domain_error():
    out = calculate({"operation": "factorial", "n": -1})
    assert out["status"] == "DOMAIN_ERROR"


def test_combinatorics_bool_rejected_as_integer():
    out = calculate({"operation": "nCr", "n": True, "r": 1})
    assert out["status"] == "INVALID_INPUT"


def test_error_never_contains_fabricated_numeric_result():
    requests = [
        {"operation": "divide", "a": "1", "b": "0"},
        {"operation": "relative_error", "expected": "0", "actual": "1"},
        {"operation": "nCr", "n": 1, "r": 2},
        {
            "operation": "convert_data_size",
            "value": "1",
            "from_unit": "KB",
            "to_unit": "B",
        },
    ]
    for case in requests:
        out = calculate(case)
        assert out["status"] != "OK"
        assert "result" not in out


def test_large_multiply_identity_is_exact():
    value = "99999999999999.999999999999999"
    out = calculate({"operation": "multiply", "a": value, "b": "1"})
    assert out["status"] == "OK"
    assert out["result"] == value


def test_large_add_identity_is_exact():
    value = "99999999999999999999999999999"
    out = calculate({"operation": "add", "a": value, "b": "0"})
    assert out["status"] == "OK"
    assert out["result"] == value


def test_large_add_then_subtract_identity_is_exact():
    x = "12345678901234567890123456789.12345"
    y = "98765432109876543210987654321.54321"
    added = calculate({"operation": "add", "a": x, "b": y})
    assert added["status"] == "OK"
    restored = calculate({"operation": "subtract", "a": added["result"], "b": y})
    assert restored["status"] == "OK"
    assert restored["result"] == x


def test_large_subtract_is_exact():
    out = calculate(
        {
            "operation": "subtract",
            "a": "100000000000000000000000000000",
            "b": "1",
        }
    )
    assert out["status"] == "OK"
    assert out["result"] == "99999999999999999999999999999"


def test_large_sum_is_exact():
    out = calculate(
        {
            "operation": "sum",
            "values": ["100000000000000000000000000000", "1"],
        }
    )
    assert out["status"] == "OK"
    assert out["result"] == "100000000000000000000000000001"


def test_large_absolute_difference_is_exact():
    out = calculate(
        {
            "operation": "absolute_difference",
            "expected": "100000000000000000000000000000",
            "actual": "1",
        }
    )
    assert out["status"] == "OK"
    assert out["result"] == "99999999999999999999999999999"


def test_large_abs_is_exact():
    value = "-99999999999999.999999999999999"
    out = calculate({"operation": "abs", "value": value})
    assert out["status"] == "OK"
    assert out["result"] == "99999999999999.999999999999999"


def test_equal_within_large_boundary_does_not_flip_boolean():
    out = calculate(
        {
            "operation": "equal_within",
            "expected": "0",
            "actual": "10000000000000000000000000001",
            "absolute_tolerance": "10000000000000000000000000000",
        }
    )
    assert out["status"] == "OK"
    assert out["result"] is False


def test_rounding_near_half_boundary_uses_exact_fraction_comparison():
    magnitude = 10**200
    denominator = str(6 * magnitude)

    above_half = str(3 * magnitude + 2)
    for mode in ("HALF_EVEN", "HALF_DOWN"):
        out = calculate(
            {
                "operation": "divide",
                "a": above_half,
                "b": denominator,
                "scale": 0,
                "rounding": mode,
            }
        )
        assert out["status"] == "OK"
        assert out["result"] == "1"

    below_half = str(3 * magnitude - 2)
    out = calculate(
        {
            "operation": "divide",
            "a": below_half,
            "b": denominator,
            "scale": 0,
            "rounding": "HALF_UP",
        }
    )
    assert out["status"] == "OK"
    assert out["result"] == "0"


def test_fraction_differential_for_exact_core_operations():
    values = [
        "0",
        "1",
        "-1",
        "0.1",
        "-0.25",
        "99999999999999.999999999999999",
        "12345678901234567890123456789",
        "-98765432109876543210987654321.125",
    ]

    operations = {
        "add": lambda a, b: a + b,
        "subtract": lambda a, b: a - b,
        "multiply": lambda a, b: a * b,
    }

    for a_text in values:
        for b_text in values:
            a = Fraction(a_text)
            b = Fraction(b_text)
            for operation, reference in operations.items():
                out = calculate(
                    {"operation": operation, "a": a_text, "b": b_text}
                )
                assert out["status"] == "OK"
                assert Fraction(out["result"]) == reference(a, b)

            for operation in ("absolute_difference", "absolute_error"):
                out = calculate(
                    {
                        "operation": operation,
                        "expected": a_text,
                        "actual": b_text,
                    }
                )
                assert out["status"] == "OK"
                assert Fraction(out["result"]) == abs(b - a)

    samples = [
        ["100000000000000000000000000000", "1", "-0.25"],
        ["0.1", "0.2", "0.3", "-0.4"],
        values,
    ]
    for sample in samples:
        out = calculate({"operation": "sum", "values": sample})
        assert out["status"] == "OK"
        assert Fraction(out["result"]) == sum(
            (Fraction(x) for x in sample), Fraction(0, 1)
        )



def test_v020_modulo_integer_contract():
    out = calculate({"operation": "modulo_integer", "dividend": 17, "divisor": 5})
    assert out == {
        "schema_version": "0.1",
        "tool_version": "0.2.0",
        "operation": "modulo_integer",
        "operation_version": "1",
        "inputs": {"dividend": 17, "divisor": 5},
        "numeric_type": "INTEGER",
        "result": 2,
        "status": "OK",
    }


@pytest.mark.parametrize(
    ("dividend", "divisor", "expected"),
    [
        (0, 7, 0),
        (3, 5, 3),
        (20, 5, 0),
        (999, 1, 0),
    ],
)
def test_v020_modulo_integer_edges(dividend, divisor, expected):
    out = calculate(
        {"operation": "modulo_integer", "dividend": dividend, "divisor": divisor}
    )
    assert out["status"] == "OK"
    assert out["result"] == expected


def test_v020_divmod_integer_contract_and_invariant():
    out = calculate(
        {"operation": "divmod_integer", "dividend": 123456789, "divisor": 97}
    )
    assert out["status"] == "OK"
    assert out["numeric_type"] == "INTEGER_PAIR"
    assert set(out["result"]) == {"quotient", "remainder"}
    q = out["result"]["quotient"]
    r = out["result"]["remainder"]
    assert 123456789 == q * 97 + r
    assert q >= 0
    assert 0 <= r < 97
    assert set(out) == {
        "schema_version",
        "tool_version",
        "operation",
        "operation_version",
        "inputs",
        "numeric_type",
        "result",
        "status",
    }


@pytest.mark.parametrize(
    "operation",
    ["modulo_integer", "divmod_integer"],
)
def test_v020_integer_validation_precedence_bool_before_domain(operation):
    out = calculate(
        {"operation": operation, "dividend": -5, "divisor": True}
    )
    assert out["status"] == "INVALID_INPUT"
    assert "result" not in out


@pytest.mark.parametrize(
    "operation",
    ["modulo_integer", "divmod_integer"],
)
def test_v020_integer_validation_precedence_forbidden_field_before_domain(operation):
    out = calculate(
        {"operation": operation, "dividend": -1, "divisor": 3, "scale": 2}
    )
    assert out["status"] == "INVALID_INPUT"
    assert "result" not in out


@pytest.mark.parametrize(
    ("operation", "case"),
    [
        ("modulo_integer", {"dividend": -1, "divisor": 3}),
        ("modulo_integer", {"dividend": 1, "divisor": 0}),
        ("modulo_integer", {"dividend": 1, "divisor": -3}),
        ("divmod_integer", {"dividend": -1, "divisor": 3}),
        ("divmod_integer", {"dividend": 1, "divisor": 0}),
        ("divmod_integer", {"dividend": 1, "divisor": -3}),
    ],
)
def test_v020_integer_domain_errors(operation, case):
    out = calculate({"operation": operation, **case})
    assert out["status"] == "DOMAIN_ERROR"
    assert "result" not in out


@pytest.mark.parametrize(
    "operation",
    ["modulo_integer", "divmod_integer"],
)
def test_v020_integer_unknown_and_policy_fields_rejected(operation):
    for extra in (
        {"unknown": 1},
        {"rounding": "HALF_EVEN"},
        {"tolerance": "0"},
        {"method": "x"},
    ):
        out = calculate(
            {
                "operation": operation,
                "dividend": 17,
                "divisor": 5,
                **extra,
            }
        )
        assert out["status"] == "INVALID_INPUT"
        assert "result" not in out


def test_v020_large_integer_core_surfaces_and_invariants():
    samples = [
        (2**53 + 123, 97),
        (2**63 + 123, 101),
        (2**64 + 123, 103),
        (10**300 + 12345, 107),
        (10**1150 + 12345, 109),
        (10**4999 + 12345, 113),
    ]
    for dividend, divisor in samples:
        mod = calculate(
            {"operation": "modulo_integer", "dividend": dividend, "divisor": divisor}
        )
        dm = calculate(
            {"operation": "divmod_integer", "dividend": dividend, "divisor": divisor}
        )
        assert mod["status"] == "OK"
        assert dm["status"] == "OK"
        q = dm["result"]["quotient"]
        r = dm["result"]["remainder"]
        assert r == mod["result"]
        assert dividend == q * divisor + r
        assert 0 <= r < divisor


@pytest.mark.parametrize(
    ("operator", "expected"),
    [
        ("LT", True),
        ("LE", True),
        ("EQ", False),
        ("NE", True),
        ("GE", False),
        ("GT", False),
    ],
)
def test_v020_compare_exact_all_operators(operator, expected):
    out = calculate(
        {"operation": "compare_exact", "a": "-1.25", "b": "2.5", "operator": operator}
    )
    assert out["status"] == "OK"
    assert out["result"] is expected
    assert out["numeric_type"] == "BOOLEAN"
    assert set(out) == {
        "schema_version",
        "tool_version",
        "operation",
        "operation_version",
        "inputs",
        "numeric_type",
        "result",
        "status",
    }


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("1.0", "1.00"),
        ("+12.500", "12.5"),
        ("-0", "0"),
        ("-0.00", "0.0"),
    ],
)
def test_v020_compare_exact_numeric_equality_and_input_echo(a, b):
    out = calculate({"operation": "compare_exact", "a": a, "b": b, "operator": "EQ"})
    assert out["status"] == "OK"
    assert out["result"] is True
    assert out["inputs"] == {"a": a, "b": b, "operator": "EQ"}


@pytest.mark.parametrize(
    "operator",
    ["lt", " LT", "<", "==", "GE "],
)
def test_v020_compare_exact_operator_is_exact_token(operator):
    out = calculate(
        {"operation": "compare_exact", "a": "1", "b": "2", "operator": operator}
    )
    assert out["status"] == "INVALID_INPUT"


@pytest.mark.parametrize(
    "bad",
    [
        " 1.5",
        "1.5 ",
        "1e3",
        "1_000",
        "1,000",
        ".5",
        "5.",
        "1x5",
        "1.5\n",
        "01",
    ],
)
def test_v020_compare_exact_canonical_decimal_rejections(bad):
    out = calculate(
        {"operation": "compare_exact", "a": bad, "b": "1", "operator": "EQ"}
    )
    assert out["status"] == "INVALID_INPUT"


@pytest.mark.parametrize("field_value", [True, 1, 1.0, None, [], {}])
def test_v020_compare_exact_non_string_decimal_rejected(field_value):
    out = calculate(
        {"operation": "compare_exact", "a": field_value, "b": "1", "operator": "EQ"}
    )
    assert out["status"] == "INVALID_INPUT"


def test_v020_compare_exact_large_decimal_digit_runs_without_integer_conversion():
    large_integer = "1" + ("0" * 4999)
    slightly_smaller = "9" * 4999
    out = calculate(
        {
            "operation": "compare_exact",
            "a": large_integer,
            "b": slightly_smaller,
            "operator": "GT",
        }
    )
    assert out["status"] == "OK"
    assert out["result"] is True

    tiny = "0." + ("0" * 4999) + "1"
    out = calculate(
        {"operation": "compare_exact", "a": tiny, "b": "0", "operator": "GT"}
    )
    assert out["status"] == "OK"
    assert out["result"] is True


def _reference_decimal_fraction(text: str) -> Fraction:
    sign = -1 if text.startswith("-") else 1
    unsigned = text[1:] if text[:1] in {"+", "-"} else text
    if "." in unsigned:
        integer_part, fractional_part = unsigned.split(".", 1)
    else:
        integer_part, fractional_part = unsigned, ""

    numerator = 0
    for ch in integer_part + fractional_part:
        numerator = numerator * 10 + (ord(ch) - ord("0"))
    denominator = 10 ** len(fractional_part)
    return Fraction(sign * numerator, denominator)


def _reference_compare(operator: str, a: str, b: str) -> bool:
    left = _reference_decimal_fraction(a)
    right = _reference_decimal_fraction(b)
    return {
        "LT": left < right,
        "LE": left <= right,
        "EQ": left == right,
        "NE": left != right,
        "GE": left >= right,
        "GT": left > right,
    }[operator]


def test_v020_compare_exact_independent_reference_differential():
    values = [
        "-999999999999999999999999999999.5",
        "-100.25",
        "-10.5000",
        "-2",
        "-1.00",
        "-0.000",
        "0",
        "0.0001",
        "1",
        "1.00",
        "2",
        "10.500",
        "999999999999999999999999999999.5",
    ]
    operators = ["LT", "LE", "EQ", "NE", "GE", "GT"]

    for a in values:
        for b in values:
            for operator in operators:
                out = calculate(
                    {
                        "operation": "compare_exact",
                        "a": a,
                        "b": b,
                        "operator": operator,
                    }
                )
                assert out["status"] == "OK"
                assert out["result"] is _reference_compare(operator, a, b)

    # Direct regression for the mutation found during independent review.
    out = calculate(
        {"operation": "compare_exact", "a": "-2", "b": "-1", "operator": "LT"}
    )
    assert out["result"] is True


def test_v020_compare_exact_is_independent_of_decimal_context_and_digit_limit():
    request = {
        "operation": "compare_exact",
        "a": "-" + ("9" * 5000) + ".1",
        "b": "-" + ("9" * 5000) + ".2",
        "operator": "GT",
    }
    baseline = calculate(request)
    assert baseline["status"] == "OK"
    assert baseline["result"] is True

    with localcontext() as context:
        context.prec = 1
        context.rounding = ROUND_FLOOR
        changed_context = calculate(request)
    assert changed_context["result"] is baseline["result"]

    getter = getattr(sys, "get_int_max_str_digits", None)
    setter = getattr(sys, "set_int_max_str_digits", None)
    if getter is not None and setter is not None:
        original = getter()
        try:
            setter(640)
            changed_limit = calculate(request)
            assert changed_limit["result"] is baseline["result"]
        finally:
            setter(original)


@pytest.mark.parametrize(
    "extra",
    [
        {"unknown": 1},
        {"scale": 2},
        {"rounding": "HALF_EVEN"},
        {"tolerance": "0"},
        {"method": "x"},
    ],
)
def test_v020_compare_exact_unknown_and_forbidden_fields_rejected(extra):
    out = calculate(
        {
            "operation": "compare_exact",
            "a": "1",
            "b": "2",
            "operator": "LT",
            **extra,
        }
    )
    assert out["status"] == "INVALID_INPUT"
    assert "result" not in out



def test_v020_compare_exact_relational_invariants():
    values = [
        "-100.25",
        "-0",
        "0",
        "0.0001",
        "1",
        "1.00",
        "999999999999999999999999999999.5",
    ]
    for a in values:
        for b in values:
            eq = calculate(
                {"operation": "compare_exact", "a": a, "b": b, "operator": "EQ"}
            )["result"]
            ne = calculate(
                {"operation": "compare_exact", "a": a, "b": b, "operator": "NE"}
            )["result"]
            lt = calculate(
                {"operation": "compare_exact", "a": a, "b": b, "operator": "LT"}
            )["result"]
            le = calculate(
                {"operation": "compare_exact", "a": a, "b": b, "operator": "LE"}
            )["result"]
            gt = calculate(
                {"operation": "compare_exact", "a": a, "b": b, "operator": "GT"}
            )["result"]
            ge = calculate(
                {"operation": "compare_exact", "a": a, "b": b, "operator": "GE"}
            )["result"]
            gt_reverse = calculate(
                {"operation": "compare_exact", "a": b, "b": a, "operator": "GT"}
            )["result"]
            assert ne is (not eq)
            assert lt is gt_reverse
            assert le is (lt or eq)
            assert ge is (gt or eq)


def test_v020_existing_operation_semantics_preserved_with_new_tool_version():
    out = calculate({"operation": "add", "a": "0.1", "b": "0.2"})
    assert out["status"] == "OK"
    assert out["result"] == "0.3"
    assert out["tool_version"] == "0.2.0"
