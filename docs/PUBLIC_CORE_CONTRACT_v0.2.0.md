# Deterministic Calculation Toolkit

## Public Core Contract v0.2.0

Status: PUBLIC-READY CONTRACT / PROMOTION HOLD

## 1. Responsibility Boundary

The public core accepts explicit structured numeric requests and executes a selected deterministic operation.

```text
Interpretation != Calculation
Reasoning != Arithmetic
Meaning != Numeric Evaluation
```

The caller is responsible for selecting the operation and supplying all required mathematical conventions.

The core does not infer:
- units
- rounding policy
- tolerance
- statistical convention
- business meaning
- workflow authorization
- objective selection

## 2. Canonical Numeric Inputs

### INTEGER

JSON / Python integer values excluding booleans.

For the v0.2 integer modulo operations:
- `dividend >= 0`
- `divisor > 0`

A host runtime's configurable/default integer-string conversion limit is not a mathematical INTEGER domain rule.

### DECIMAL

Canonical DECIMAL input is a plain base-10 string:

```text
[+-]?(0|[1-9][0-9]*)(\.[0-9]+)?
```

The entire string must match. Whitespace, exponent notation, commas, underscores, a missing integer part, a trailing decimal point, and terminal newline characters are rejected.

Examples accepted:

```text
0
-1
0.1
+12.500
```

Examples rejected:

```text
NaN
Infinity
1e-3
1,000.0
.5
5.
JSON float 0.1
```

## 3. Exactness and Rounding

If a mathematically exact result has a finite base-10 expansion, the core may return it exactly without a rounding policy.

If an operation requires rounded decimal output for a non-terminating result, both are explicit:
- `scale`
- `rounding`

The core has no implicit default scale or rounding policy.

When `scale` is supplied, emitted trailing zeroes are preserved to that scale.

## 4. Rounding Modes

Supported explicit modes:

```text
HALF_EVEN
HALF_UP
HALF_DOWN
UP
DOWN
CEILING
FLOOR
```

Tie handling is deterministic and based on exact arithmetic.

## 5. Operations

### Arithmetic

```text
add(a, b)
subtract(a, b)
multiply(a, b)
divide(a, b)
abs(value)
floor(value)
ceil(value)
round(value, scale, rounding)
power_integer(base, exponent)
```

Division by zero is `DOMAIN_ERROR`.

Zero raised to a negative integer exponent is `DOMAIN_ERROR`.

### Difference / tolerance comparison

```text
absolute_difference(expected, actual)
absolute_error(expected, actual)
relative_error(expected, actual)
equal_within(expected, actual, tolerance...)
```

Relative error:

```text
abs(actual - expected) / abs(expected)
```

`expected = 0` is `DOMAIN_ERROR`.

`equal_within` requires one or both of:
- `absolute_tolerance`
- `relative_tolerance`

The comparison rule is:

```text
absolute_difference <= max(
    absolute_tolerance,
    relative_tolerance * abs(expected)
)
```

### Exact decimal comparison — v0.2.0

Request fields:

```text
operation = "compare_exact"
a = canonical DECIMAL string
b = canonical DECIMAL string
operator = LT | LE | EQ | NE | GE | GT
```

Operator tokens are case-sensitive and are not trimmed.

Comparison is numeric rather than textual.

Therefore:

```text
"1.0" EQ "1.00"     → true
"+12.500" EQ "12.5" → true
"-0" EQ "0"         → true
```

Caller-supplied textual forms are preserved in the success `inputs` payload.

The result type is `BOOLEAN`.

The comparison result must not depend on:
- Decimal context precision
- rounding context
- binary floating point
- host integer/string conversion digit defaults

### Integer modulo — v0.2.0

```text
modulo_integer(dividend, divisor)
```

Domain:

```text
dividend >= 0
divisor > 0
```

Result:

```text
0 <= remainder < divisor
```

The result type is `INTEGER`.

### Integer divmod — v0.2.0

```text
divmod_integer(dividend, divisor)
```

Domain:

```text
dividend >= 0
divisor > 0
```

Result:

```text
dividend = quotient * divisor + remainder
0 <= remainder < divisor
```

Success `result` is exactly:

```json
{"quotient":0,"remainder":0}
```

with integer values.

The result type is `INTEGER_PAIR`.

### Data-size conversion

SI:

```text
B
kB = 1000 B
MB = 1000^2 B
GB = 1000^3 B
```

IEC:

```text
KiB = 1024 B
MiB = 1024^2 B
GiB = 1024^3 B
```

Ambiguous `KB` is rejected.

### Duration conversion

Fixed-ratio only:

```text
second
minute = 60 second
hour = 3600 second
```

Calendar arithmetic is outside the contract.

### Ratio representation

```text
multiplier
percent
basis_points
```

### Temperature

```text
Celsius
Fahrenheit
```

### Basic statistics

```text
count
sum
min
max
mean
median
```

`count([])` returns 0. Other currently supported statistics return `DOMAIN_ERROR` on empty input.

### Combinatorics

```text
factorial(n)
nCr(n, r)
nPr(n, r)
```

Inputs are non-negative integers.

`r > n` is `DOMAIN_ERROR`.

Outputs are exact integers.

## 6. Request Validation and Error Precedence

Each request must be an object containing an operation.

Operation-specific required and allowed fields are validated exactly.

Unknown or forbidden fields are rejected with `INVALID_INPUT`.

For the v0.2 integer modulo/divmod operations, request shape/type/representation validation occurs before mathematical domain validation.

Therefore a request containing both an invalid type and a mathematical domain violation returns `INVALID_INPUT`, not `DOMAIN_ERROR`.

```text
Validation Failure
precedes
Domain Failure
```

## 7. Result Contract

Every result contains:

```text
schema_version
tool_version
operation
operation_version
status
```

Successful results additionally contain:

```text
inputs
numeric_type
result
```

Current versions:

```text
schema_version = "0.1"
tool_version = "0.2.0"
operation_version = "1"
```

`numeric_type` is operation-scoped. v0.2.0 includes `BOOLEAN` and `INTEGER_PAIR` where defined above.

For the three v0.2 operations, success payloads do not add:
- scale
- rounding
- tolerance
- method

## 8. Error Contract

Status vocabulary:

```text
OK
INVALID_INPUT
DOMAIN_ERROR
UNSUPPORTED_OPERATION
UNSUPPORTED_METHOD
```

Non-OK results contain structured error information.

A non-OK result does not contain a fabricated numeric result.

```text
Error != Fabricated Result
```

## 9. Deterministic Payload Boundary

Canonical calculation payloads do not include:
- execution timestamp
- random request ID
- hostname
- PID
- wall-clock runtime duration

```text
Calculation Result
!=
Execution Metadata
```

## 10. Runtime Dependency Boundary

The standalone calculation core uses Python standard-library facilities and does not require third-party numeric libraries at runtime.

Test tooling may use pytest.

For supported Python runtimes that expose an integer/string conversion digit-limit API, the CLI implementation may adjust that host policy so admitted large INTEGER requests are not rejected solely by the runtime default.

That host-policy change is process-global Python behavior.

Consumers embedding the CLI module in a larger process should account for it explicitly.

## 11. Explicit Exclusions

The public v0.2.0 core does not provide:
- probability distributions
- Bayes update
- quantile / percentile
- variance / standard deviation
- datetime / timezone / calendar arithmetic
- business-day calculation
- px / pt conversion
- transcendental functions
- arbitrary roots
- automatic formula parsing
- symbolic algebra
- model fitting
- optimization
- prediction
- semantic probability estimation
- automatic operation selection
- policy / authority decisions
- workflow continuation decisions
- AI/MCP orchestration
- hosted service/API semantics

## 12. Resource Bounds

The standalone core does not define service-style hard limits for every input class.

Potentially expensive inputs include:
- very large factorial input
- very large integer exponents
- very large decimal scale
- very large integer payloads

Integrators operating a shared or always-on service should apply explicit resource-admission limits outside the calculation core.

## 13. Separation From External Decisions

The core may calculate a numeric fact.

It does not decide:
- whether a business process is correct
- whether an artifact is authoritative
- whether a file has integrity
- whether a user is authorized
- whether a workflow may continue
- which operation should be selected
- what a scientific result means

```text
Numeric Result
!=
Verification Verdict
!=
Authorization Decision
!=
Scientific Interpretation
```

End of Public Core Contract v0.2.0
