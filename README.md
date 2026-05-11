# IX-Autonomy-Assurance-Case-Runtime

**Trusted Autonomy T&E assurance-case runtime for evidence-backed AI/autonomous system evaluation.**

IX-Autonomy-Assurance-Case-Runtime is a reference implementation for building a living assurance-case loop around AI/autonomous system behavior.

It connects:

```
mission need
  -> requirement
  -> hazard
  -> control / mitigation
  -> scenario
  -> telemetry
  -> degradation assessment
  -> safety gate
  -> evidence bundle
  -> verification summary
  -> assurance report
  -> tamper-evident run ledger
```

The core purpose is simple:

> Convert AI/autonomous behavior into traceable hazards, scenarios, runtime decisions, test evidence, safety gates, and reviewable assurance records.

## Official Repository Notice

This repository is the official source for IX-Autonomy-Assurance-Case-Runtime.

Do not trust unofficial mirrors, ZIP files, installer downloads, or rehosted copies unless provenance is independently verified.

This project is an original work by **Bryce Lovell** and is licensed under the Apache License, Version 2.0.

## What This Is

This is a local reference runtime for Trusted Autonomy T&E workflows.

It provides:

- assurance-case domain model,
- mission-thread and scenario model,
- deterministic evidence bundles,
- traceability graph,
- runtime safety gate,
- human authority review model,
- fault/degradation engine,
- scenario runner,
- independent verification engine,
- assurance report generator,
- tamper-evident run ledger,
- command-line interface,
- JSON schemas,
- synthetic examples,
- acceptance tests.

## What This Is Not

This is not:

- an official government system,
- a certified safety system,
- a production autonomy controller,
- a weapons-control system,
- a cybersecurity authorization package,
- a classified-data workflow,
- a replacement for formal test and evaluation,
- a replacement for legal review,
- a replacement for human command authority,
- a claim that any real autonomous system is safe.

A passing report means the local runtime artifacts passed the implemented checks. It does **not** certify a real-world system.

## Why This Exists

AI/autonomous systems create a hard trust problem:

```
What did the system perceive?
What did it decide?
Was that decision allowed?
Which hazard did it touch?
Which control constrained it?
Which scenario tested it?
What evidence supports the result?
Can a reviewer trace the decision back to the mission requirement?
Can tampering or missing evidence be detected?
```

This repo creates a software structure for answering those questions with evidence rather than vibes.

## Runtime Flow

```
Scenario Catalog + Runtime Telemetry
        |
        v
Degradation Engine
        |
        v
Runtime Safety Gate
        |
        v
Scenario Runner
        |
        v
Evidence Bundle
        |
        v
Verification Engine
        |
        v
Assurance Report
        |
        v
Run Ledger
```

## Current Capabilities

### Assurance Case

Models:

- claims,
- subclaims,
- assumptions,
- hazards,
- controls,
- mitigations,
- evidence links,
- verification criteria.

Validation catches:

- missing references,
- duplicate identifiers,
- unsupported claims,
- unresolved severe hazards,
- review-blocking errors.

### Scenario Catalog

Models:

- operational contexts,
- autonomy functions,
- operating conditions,
- stressors,
- expected safe behavior,
- acceptance criteria,
- mission threads,
- scenarios.

Validation catches:

- broken references,
- severe stressors without restrictive expected behavior,
- evidence-required scenarios without evidence identifiers.

### Evidence Bundles

Supports:

- deterministic canonical JSON,
- SHA-256 record hashes,
- SHA-256 bundle hashes,
- integrity validation,
- stale/invalid/missing evidence posture.

### Runtime Safety Gate

Emits:

- `allow`,
- `clamp`,
- `defer`,
- `veto`,
- `safe_hold`.

The gate evaluates telemetry rules and scenario expected behavior. Severe stressors can force restrictive behavior.

### Degradation Engine

Detects:

- sensor drift,
- communications loss,
- navigation uncertainty,
- power degradation,
- conflicting telemetry,
- timing degradation,
- stale or invalid evidence.

### Verification Engine

Checks:

- assurance-case validity,
- scenario-catalog validity,
- expected safe behavior,
- acceptance criteria,
- required evidence,
- evidence integrity,
- severe hazard coverage,
- traceability graph validity,
- scenario-to-claim trace path.

### Reports

Generates:

- machine-readable report dictionaries,
- Markdown reports,
- failed check summaries,
- follow-up summaries,
- assurance-gap summaries,
- evidence-integrity posture,
- traceability posture.

### Run Ledger

Provides hash-chained ledger integrity for runtime artifacts.

Detects:

- tampered entry payloads,
- missing entry hashes,
- broken previous-hash links,
- out-of-order sequence numbers,
- duplicate entry identifiers,
- duplicate run IDs when strict mode is enabled.

## Install

```
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run Tests

```
python -m ruff check src tests
python -m mypy src tests
python -m pytest
```

## CLI

### Validate an Assurance Case

```
ix-assurance validate-case --case examples/degraded-navigation-case.json
```

### Run a Scenario

```
ix-assurance run-scenario \
  --catalog examples/degraded-navigation-catalog.json \
  --telemetry examples/telemetry-degraded-navigation.json \
  --case-id CASE-NAV-001 \
  --scenario-id SCN-NAV-001 \
  --run-id RUN-NAV-001
```

### Run with Built-In Degradation Rules

```
ix-assurance run-scenario \
  --catalog examples/degraded-navigation-catalog.json \
  --telemetry examples/telemetry-degraded-navigation.json \
  --case-id CASE-NAV-001 \
  --scenario-id SCN-NAV-001 \
  --run-id RUN-NAV-001 \
  --default-degradation
```

### Verify an Evidence Bundle

```
ix-assurance verify-bundle --bundle examples/evidence-bundle.json
```

### Validate a Run Ledger

```
ix-assurance validate-ledger --ledger examples/run-ledger.json
```

### Audit Traceability

```
ix-assurance audit-traceability \
  --case examples/degraded-navigation-case.json \
  --catalog examples/degraded-navigation-catalog.json \
  --mission-need examples/mission-need.json \
  --requirements examples/requirements.json \
  --scenario-id SCN-NAV-001 \
  --claim-id CLM-NAV-001
```

### Export a Report

```
ix-assurance export-report \
  --report examples/report.json \
  --format markdown
```

## Example Scenario

The included example uses a synthetic degraded-navigation case.

It asks whether a reference autonomy function enters safe-hold when navigation confidence becomes unsafe.

The scenario links:

```
mission need
  -> requirement
  -> critical navigation hazard
  -> navigation confidence gate
  -> degraded-navigation scenario
  -> runtime telemetry
  -> safe-hold evidence
  -> assurance claim
```

## Repository Layout

```
src/ix_autonomy_assurance_case_runtime/
  assurance_case.py
  authority.py
  cli.py
  contracts.py
  degradation.py
  evidence.py
  ledger.py
  project.py
  reporting.py
  runner.py
  safety_gate.py
  scenarios.py
  traceability.py
  verification.py

examples/
  degraded-navigation-case.json
  degraded-navigation-catalog.json
  mission-need.json
  requirements.json
  telemetry-degraded-navigation.json
  evidence-bundle.json
  run-ledger.json
  report.json

schemas/
  assurance-case.schema.json
  scenario-catalog.schema.json
  evidence-bundle.schema.json
  run-ledger.schema.json
  report.schema.json

docs/
  ARCHITECTURE.md
  THREAT_MODEL.md
  USAGE.md
  TESTING.md
```

## Design Principles

1. **Evidence over assertion.**  
   Claims require support paths.

2. **Conservative under uncertainty.**  
   Missing or degraded data should not quietly become approval.

3. **Traceability is first-class.**  
   Runtime behavior should connect back to mission need, requirement, hazard, control, scenario, evidence, and claim.

4. **Human authority remains visible.**  
   The system models when autonomy may act, when review is required, and when authority is denied.

5. **Integrity is local and explicit.**  
   Hashes and ledgers detect local tampering; they do not pretend to be certification or external truth.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Usage](docs/USAGE.md)
- [Testing](docs/TESTING.md)
- [Security Policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## License

Apache License, Version 2.0.

See `LICENSE` and `NOTICE`.

## Maintainer

Bryce Lovell
