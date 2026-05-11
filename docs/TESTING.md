# Testing

## Test Command

Run the full local test suite:

```
python -m pytest
```

Run linting:

```
python -m ruff check src tests
```

Run typing:

```
python -m mypy src tests
```

## CI Command Set

The CI workflow runs:

```
python -m ruff check src tests
python -m mypy src tests
python -m pytest
```

against Python 3.11 and Python 3.12.

## Test Coverage Intent

The tests cover:

- package import foundation,
- domain contracts,
- assurance-case reference validation,
- scenario-catalog validation,
- evidence hashing and bundle integrity,
- traceability graph construction,
- safety-gate decision behavior,
- authority review behavior,
- degradation detection,
- scenario runner output,
- verification engine summaries,
- report generation,
- ledger hash-chain validation,
- CLI commands,
- JSON example acceptance flow.

## What Passing Tests Mean

Passing tests mean the reference runtime behaves as implemented against the included synthetic scenarios and unit tests.

Passing tests do not mean:

- operational safety,
- mission suitability,
- cybersecurity authorization,
- government approval,
- certification,
- accreditation,
- autonomous-system readiness.

## Acceptance Runtime Test

The acceptance test exercises the full synthetic flow:

```
example assurance case
  -> example scenario catalog
  -> mission need
  -> requirements
  -> traceability graph
  -> scenario runner
  -> verification engine
  -> report generator
  -> run ledger
```

It verifies that the runtime can produce a coherent assurance evidence path for the degraded-navigation example.

## Failure-Path Test

The failure-path test intentionally supplies clean telemetry against a scenario expecting safe-hold behavior. This confirms that the runtime does not silently accept a scenario when expected safe behavior is not satisfied.

## Adding Tests

New code should include tests for:

- valid path,
- invalid input,
- boundary condition,
- missing evidence,
- bad reference,
- stale or invalid evidence,
- conservative failure behavior.

Do not add tests that only prove the happy path.
