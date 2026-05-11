# Usage

## Install for Local Development

```
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Validate an Assurance Case

```
ix-assurance validate-case --case examples/degraded-navigation-case.json
```

Expected result: JSON showing whether the case references are valid.

## Run a Scenario

```
ix-assurance run-scenario \
  --catalog examples/degraded-navigation-catalog.json \
  --telemetry examples/telemetry-degraded-navigation.json \
  --case-id CASE-NAV-001 \
  --scenario-id SCN-NAV-001 \
  --run-id RUN-NAV-001
```

This executes the scenario through:

```
scenario catalog
  -> runtime telemetry
  -> degradation assessment
  -> safety gate
  -> runtime result
  -> evidence bundle
```

## Run a Scenario with Built-In Degradation Rules

```
ix-assurance run-scenario \
  --catalog examples/degraded-navigation-catalog.json \
  --telemetry examples/telemetry-degraded-navigation.json \
  --case-id CASE-NAV-001 \
  --scenario-id SCN-NAV-001 \
  --run-id RUN-NAV-001 \
  --default-degradation
```

The built-in degradation rules evaluate common telemetry such as:

- navigation confidence,
- communications-link presence,
- power margin,
- sensor drift,
- control-loop latency.

## Verify an Evidence Bundle

```
ix-assurance verify-bundle --bundle examples/evidence-bundle.json
```

This checks record hashes, bundle hash, duplicate identifiers, and invalid/stale evidence posture.

## Validate a Run Ledger

```
ix-assurance validate-ledger --ledger examples/run-ledger.json
```

Strict duplicate run-ID mode:

```
ix-assurance validate-ledger \
  --ledger examples/run-ledger.json \
  --require-unique-run-ids
```

## Audit Traceability

```
ix-assurance audit-traceability \
  --case examples/degraded-navigation-case.json \
  --catalog examples/degraded-navigation-catalog.json \
  --mission-need examples/mission-need.json \
  --requirements examples/requirements.json \
  --scenario-id SCN-NAV-001 \
  --claim-id CLM-NAV-001
```

This builds a traceability graph and reports whether the scenario has a connected path to the claim.

## Export a Report

```
ix-assurance export-report \
  --report examples/report.json \
  --format markdown
```

JSON output:

```
ix-assurance export-report \
  --report examples/report.json \
  --format json
```

## Programmatic Use

Minimal scenario-run pattern:

```
from ix_autonomy_assurance_case_runtime.cli import load_scenario_catalog
from ix_autonomy_assurance_case_runtime.runner import ScenarioRunInput, ScenarioRunner
from ix_autonomy_assurance_case_runtime.safety_gate import RuntimeTelemetry

catalog = load_scenario_catalog(Path("examples/degraded-navigation-catalog.json"))

result = ScenarioRunner().run(
    catalog=catalog,
    run_input=ScenarioRunInput(
        run_id="RUN-001",
        case_id="CASE-NAV-001",
        scenario_id="SCN-NAV-001",
        telemetry=RuntimeTelemetry(
            values={
                "navigation_confidence": 0.92,
                "power_margin_pct": 76.0,
                "comms_link_active": True,
            }
        ),
    ),
)
```

## Expected Runtime Outcomes

The runtime can produce:

- `allow`,
- `clamp`,
- `defer`,
- `veto`,
- `safe_hold`.

Restrictive outputs are not failures by themselves. In autonomy T&E, a restrictive output may be the correct safe behavior.

## Interpreting Verification

`pass` means the implemented runtime checks passed for the supplied artifacts.

`fail` means at least one blocking check failed.

`inconclusive` means the runtime found follow-up items, missing traceability, warnings, or insufficient evidence.

`not_run` means an expected verification activity was not executed.
