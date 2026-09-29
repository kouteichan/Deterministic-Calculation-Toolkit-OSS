# Deterministic Calculation Toolkit

Deterministic numeric utilities for AI agents, automated workflows, and ordinary software.

> Do not ask the model to be exact where ordinary code can be exact.

## Why this exists

Language models are useful for interpretation and reasoning, but exact arithmetic should not depend on probabilistic text generation when ordinary deterministic code can perform the calculation.

This toolkit separates those responsibilities:

```text
Interpretation
!=
Calculation

Reasoning
!=
Arithmetic

Meaning
!=
Numeric Evaluation
```

The caller chooses an explicit operation and supplies the required parameters. The toolkit validates that contract and returns a deterministic result.

```text
Explicit Input
→ Explicit Operation
→ Deterministic Result
```

The toolkit does not infer missing mathematical conventions.

## Public status

Current public target:

```text
v0.2.0 Core
```

The public OSS repository distributes the generic deterministic core.

Private development governance, review history, company-specific integration architecture, and private workflow artifacts are not part of the public distribution.

## Numeric boundary

Canonical decimal values are supplied as plain base-10 strings.

Example:

```json
{"operation":"add","a":"0.1","b":"0.2"}
```

Binary floating-point values are not accepted as canonical DECIMAL inputs.

```text
Numeric Value
!=
Precision
!=
Scale
!=
Rounding Policy
```

If an exact result has a non-terminating decimal expansion, the caller must explicitly provide both `scale` and `rounding` for operations that support rounded decimal output.

## Supported operations

### Arithmetic

- `add`
- `subtract`
- `multiply`
- `divide`
- `abs`
- `floor`
- `ceil`
- `round`
- `power_integer`

### Comparison and error

- `absolute_difference`
- `absolute_error`
- `relative_error`
- `equal_within`

### Exact comparison — v0.2.0

`compare_exact` compares two canonical decimal strings numerically without binary floating point.

Allowed operators:

- `LT`
- `LE`
- `EQ`
- `NE`
- `GE`
- `GT`

Example:

```json
{"operation":"compare_exact","a":"+12.500","b":"12.5","operator":"EQ"}
```

returns `true`.

The caller-supplied decimal text is preserved in the success `inputs` payload.

### Integer modulo — v0.2.0

`modulo_integer` accepts:

- non-negative integer `dividend`
- positive integer `divisor`

Example:

```json
{"operation":"modulo_integer","dividend":17,"divisor":5}
```

returns remainder `2`.

### Integer divmod — v0.2.0

`divmod_integer` uses the same integer domain and returns:

```json
{"quotient":3,"remainder":2}
```

for `17 / 5`.

The result numeric type is `INTEGER_PAIR`.

### Conversion

- `convert_data_size`
- `convert_duration`
- `convert_ratio`
- `convert_temperature`

Data-size units are explicit:

```text
kB != KiB
MB != MiB
GB != GiB
```

Ambiguous `KB` is rejected.

### Basic statistics

- `count`
- `sum`
- `min`
- `max`
- `mean`
- `median`

Population/sample variance and standard deviation are intentionally outside the current core because the toolkit does not silently choose statistical conventions.

### Combinatorics

- `factorial`
- `nCr`
- `nPr`

Outputs are exact integers.

## Rounding modes

Supported explicit modes:

- `HALF_EVEN`
- `HALF_UP`
- `HALF_DOWN`
- `UP`
- `DOWN`
- `CEILING`
- `FLOOR`

There is no implicit default rounding mode.

## Python API

```python
from deterministic_calculation_toolkit import calculate

result = calculate({
    "operation": "add",
    "a": "0.1",
    "b": "0.2"
})
```

## CLI

JSON argument:

```bash
python -m deterministic_calculation_toolkit \
  --json '{"operation":"modulo_integer","dividend":17,"divisor":5}'
```

Or pipe a JSON request on stdin.

The CLI emits sorted compact JSON and does not include timestamp, random request ID, hostname, PID, or runtime duration in the canonical calculation payload.

### Large-integer runtime note

On supported Python runtimes that expose `sys.set_int_max_str_digits`, importing the CLI module configures the process-wide integer/string conversion limit so admitted large INTEGER requests are not silently rejected by the host default.

This is process-global Python runtime behavior.

If you embed the CLI module in a larger long-running process, account for that behavior explicitly. Shared or always-on services should apply their own request/resource admission limits at the integration boundary.

The calculation core itself does not choose those service policies.

## Result contract

Current versions:

```text
schema_version = "0.1"
tool_version = "0.2.0"
operation_version = "1"
```

Every result contains:

- `schema_version`
- `tool_version`
- `operation`
- `operation_version`
- `status`

Successful results additionally contain:

- `inputs`
- `numeric_type`
- `result`

v0.2.0 may return `BOOLEAN` for `compare_exact` and `INTEGER_PAIR` for `divmod_integer`.

Non-OK results contain structured error information and do not contain a fabricated numeric result.

Status vocabulary:

```text
OK
INVALID_INPUT
DOMAIN_ERROR
UNSUPPORTED_OPERATION
UNSUPPORTED_METHOD
```

## Design rule

```text
INTERPRET OUTSIDE
VALIDATE EXPLICITLY
CALCULATE DETERMINISTICALLY
REPORT WITHOUT GUESSING
```

## Explicit exclusions

The public core does not provide:

- probability distributions
- Bayes update
- quantile / percentile
- variance / standard deviation
- datetime / timezone / calendar arithmetic
- business-day calculation
- px / pt conversion
- transcendental functions
- arbitrary roots
- formula parsing
- symbolic algebra
- model fitting
- optimization
- prediction
- semantic probability estimation
- automatic operation selection
- policy / authorization decisions
- AI/MCP orchestration
- hosted service/API semantics

## Resource-bound note

The standalone core does not impose service-style resource limits for every large input class.

Examples include:

- very large `factorial(n)`
- very large integer exponents
- very large decimal scale
- very large integer payloads admitted by v0.2 operations

If embedding the toolkit in an always-on or multi-user service, apply appropriate resource limits outside the calculation core.

## Public contract

The public numeric behavior is documented in:

```text
docs/PUBLIC_CORE_CONTRACT_v0.2.0.md
```

## License

Apache License 2.0.

See `LICENSE` for the complete terms.

## Project boundary

This repository publishes the generic deterministic calculation core.

```text
Public Core
!=
Company-specific Policy
!=
Workflow Authorization
!=
AI Interpretation
```

The toolkit calculates explicit numeric requests. It does not decide what a result means, why an operation should be selected, or whether an external workflow is authorized to proceed.
