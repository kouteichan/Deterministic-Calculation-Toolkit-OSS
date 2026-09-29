import json
import subprocess
import sys


def test_module_cli_json_output_is_canonical_and_successful():
    request = '{"operation":"add","a":"0.1","b":"0.2"}'
    proc = subprocess.run(
        [sys.executable, "-m", "deterministic_calculation_toolkit", "--json", request],
        text=True,
        capture_output=True,
        env={**__import__("os").environ, "PYTHONPATH": "src"},
        check=False,
    )
    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result["status"] == "OK"
    assert result["result"] == "0.3"
    assert proc.stdout.strip() == json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def test_module_cli_error_exit_code():
    request = '{"operation":"divide","a":"1","b":"0"}'
    proc = subprocess.run(
        [sys.executable, "-m", "deterministic_calculation_toolkit", "--json", request],
        text=True,
        capture_output=True,
        env={**__import__("os").environ, "PYTHONPATH": "src"},
        check=False,
    )
    assert proc.returncode == 2
    result = json.loads(proc.stdout)
    assert result["status"] == "DOMAIN_ERROR"
    assert "result" not in result



def _decimal_divmod_text(digits: str, divisor: int) -> tuple[str, int]:
    quotient_digits = []
    remainder = 0
    for ch in digits:
        remainder = remainder * 10 + (ord(ch) - ord("0"))
        q_digit, remainder = divmod(remainder, divisor)
        if quotient_digits or q_digit:
            quotient_digits.append(str(q_digit))
    return "".join(quotient_digits) or "0", remainder


def _run_cli_raw(request: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "deterministic_calculation_toolkit", "--json", request],
        text=True,
        capture_output=True,
        env={
            **__import__("os").environ,
            "PYTHONPATH": "src",
            "PYTHONINTMAXSTRDIGITS": "4300",
        },
        check=False,
    )


def test_v020_cli_large_integer_decode_and_encode_modulo():
    digits = "1" + ("0" * 4999)
    divisor = 97
    _, remainder = _decimal_divmod_text(digits, divisor)
    request = (
        '{"operation":"modulo_integer","dividend":'
        + digits
        + ',"divisor":'
        + str(divisor)
        + "}"
    )
    proc = _run_cli_raw(request)
    assert proc.returncode == 0
    assert '"status":"OK"' in proc.stdout
    assert '"tool_version":"0.2.0"' in proc.stdout
    assert f'"result":{remainder}' in proc.stdout
    assert f'"dividend":{digits}' in proc.stdout


def test_v020_cli_large_integer_decode_and_encode_divmod():
    digits = "1" + ("0" * 4999)
    divisor = 113
    quotient, remainder = _decimal_divmod_text(digits, divisor)
    request = (
        '{"operation":"divmod_integer","dividend":'
        + digits
        + ',"divisor":'
        + str(divisor)
        + "}"
    )
    proc = _run_cli_raw(request)
    assert proc.returncode == 0
    assert '"status":"OK"' in proc.stdout
    assert f'"dividend":{digits}' in proc.stdout
    assert f'"result":{{"quotient":{quotient},"remainder":{remainder}}}' in proc.stdout


def test_v020_cli_compare_exact_large_decimal_without_integer_conversion():
    large = "1" + ("0" * 4999)
    request = (
        '{"operation":"compare_exact","a":"'
        + large
        + '","b":"9","operator":"GT"}'
    )
    proc = _run_cli_raw(request)
    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result["status"] == "OK"
    assert result["result"] is True
    assert result["inputs"]["a"] == large


def test_v020_cli_invalid_json_uses_current_tool_version():
    proc = _run_cli_raw("{")
    assert proc.returncode == 2
    result = json.loads(proc.stdout)
    assert result["status"] == "INVALID_INPUT"
    assert result["tool_version"] == "0.2.0"
