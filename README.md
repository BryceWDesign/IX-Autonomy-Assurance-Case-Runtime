# IX-Autonomy-Assurance-Case-Runtime

**Trusted Autonomy T&E assurance-case runtime for evidence-backed AI/autonomous system evaluation.**

IX-Autonomy-Assurance-Case-Runtime is a local, open-source reference runtime for making AI/autonomy evaluation artifacts traceable, reviewable, bounded, evidence-backed, and defensible.

It is aimed at a practical assurance gap:

> When an AI/autonomous system acts, can the action be traced back through mission need, requirement, scenario, hazard/control, runtime telemetry, safety-gate decision, evidence bundle, assurance claim, human authority, ledger, and exportable review package?

This repository builds that chain as deterministic Python records, validators, readiness gates, rollups, and tests.

## Official Repository Notice

This repository is the official source for IX-Autonomy-Assurance-Case-Runtime.

Do not trust unofficial mirrors, ZIP files, installer downloads, or rehosted copies unless provenance is independently verified.

This project is an original work by **Bryce Lovell** and is licensed under the Apache License, Version 2.0.

## What This Is

This is a local reference implementation for Trusted Autonomy test, evaluation, assurance-case traceability, and review workflow experiments.

It provides:

- assurance-case domain records,
- mission-thread and scenario modeling,
- deterministic evidence bundles,
- traceability graph validation,
- runtime safety-gate decisions,
- human authority and review workflow records,
- degradation and monitoring records,
- telemetry source/schema/adapter records,
- scenario campaign planning and run reports,
- policy pack and waiver evidence checks,
- framework crosswalk and evidence coverage checks,
- signed provenance records and verification posture,
- export package and redaction validation,
- assurance dossier trace-closure checks,
- claim guardrails to prevent overstatement,
- federal/IC/DoD-style evaluation profile mapping,
- prototype maturity and readiness rollups,
- command-line interface,
- JSON schemas,
- synthetic examples,
- test coverage for the local runtime model.

## What This Is Not

This is not:

- an official government system,
- an official federal, IC, DoD, or agency-endorsed tool,
- a certified safety system,
- a production autonomy controller,
- a weapons-control system,
- a cybersecurity authorization package,
- an authority-to-operate package,
- a classified-data workflow,
- a procurement-acceptance package,
- a deployment-readiness claim,
- a replacement for formal test and evaluation,
- a replacement for legal, safety, security, or acquisition review,
- a replacement for human command authority,
- a claim that any real autonomous system is safe.

A passing report means the local runtime artifacts passed the implemented checks. It does **not** certify, authorize, approve, endorse, deploy, or accept a real-world system.

## Core Traceability Chain

The runtime is designed around this review chain:

```
mission need
  -> requirement
  -> scenario
  -> hazard / control
  -> runtime telemetry
  -> degradation / monitoring posture
  -> policy and safety-gate decision
  -> evidence bundle
  -> provenance record
  -> assurance claim
  -> human review / authority state
  -> ledger / report / export package
  -> assurance dossier / evaluation profile
```

The goal is not to make autonomy look trustworthy by assertion. The goal is to force the relevant records, links, checks, and limitations into reviewable form.

## Prototype Maturity Model

The repo includes a local maturity gate in `prototype_target.py`, `prototype_readiness.py`, and `prototype_rollup.py`.

The current model uses:

- **40% baseline local reference-runtime maturity** before the serious-prototype capability families are complete,
- **80% serious open-source prototype target** when the original nine required capability families are complete,
- **100% local prototype maturity ceiling** when all twelve local capability families are complete.

These percentages are internal project maturity markers only. They are not certification, authority to operate, operational deployment readiness, procurement acceptance, agency acceptance, or official endorsement.

### Original 80% Required Capability Path

The original serious-prototype target is reached by the following nine capability families:

1. `registry-layer`
2. `policy-pack-engine`
3. `framework-crosswalks`
4. `signed-provenance`
5. `telemetry-adapters`
6. `scenario-campaign-runner`
7. `monitoring-incidents`
8. `review-workflow`
9. `audit-report-export`

### Extended Local Hardening Path

The extended local model adds three hardening families:

10. `assurance-dossier`
11. `claim-guardrails`
12. `federal-evaluation-profile`

When all twelve are complete, the local prototype model can roll up to 100% local prototype maturity while still refusing claims of certification, authority, field readiness, procurement acceptance, or official agency acceptance.

## Current Capability Families

### 1. Registry Layer

Models systems, models, use cases, deployments, lifecycle state, risk tiers, telemetry source references, and evidence bundle references.

Readiness checks verify catalog consistency, required evidence, lifecycle posture, and whether the `registry-layer` capability can count toward prototype maturity.

### 2. Policy Pack Engine

Models policy packs, rules, decisions, subject/action categories, authority requirements, waivers, and waiver evidence.

Readiness checks evaluate policy requests, denial conditions, review/waiver requirements, waiver evidence coverage, and whether the `policy-pack-engine` capability is complete.

### 3. Framework Crosswalks

Models framework objectives, control mappings, coverage status, expected artifact types, and evidence expectations.

Evidence coverage checks verify referenced bundles and expected evidence kinds. Readiness checks prevent framework alignment from being treated as official compliance or endorsement.

### 4. Signed Provenance

Models artifact digests, signer identities, signatures, attestations, manifest verification, and provenance readiness.

Readiness checks require verified, audit-facing artifact provenance and preserve the boundary between local provenance and external trust authority.

### 5. Telemetry Adapters

Models telemetry sources, schemas, schema fields, replay records, normalized envelopes, adapter policies, and adapter reports.

Readiness checks require at least one accepted runtime-usable normalized envelope and validate that telemetry can support reviewable runtime evaluation.

### 6. Scenario Campaign Runner

Models scenario campaigns, campaign objectives, scenario roles, tags, acceptance thresholds, stop rules, run inputs, run reports, and campaign evidence.

Readiness checks require run evidence and acceptance posture strong enough to support the `scenario-campaign-runner` capability.

### 7. Monitoring and Incidents

Models monitoring snapshots, drift records, incidents, revalidation triggers, and evidence-backed monitoring trails.

Readiness checks ensure current snapshots, handled incidents, satisfied revalidation triggers, and evidence coverage exist before monitoring can count as complete.

### 8. Review Workflow

Models human review workflows, findings, signoffs, dissent, authority posture, and review evidence.

Readiness checks ensure human authority and review state remain visible rather than being hidden behind automated outputs.

### 9. Audit Report Export

Models export package manifests, artifact references, redaction rules, package status, package format, evidence references, provenance references, and disclaimers.

Readiness checks require machine-readable review packages with evidence, provenance, redaction coverage, and clear non-official prototype language.

### 10. Assurance Dossier

Models trace-closure packages that connect mission threads, requirements, scenarios, hazards, controls, evidence, human review, export packages, and provenance references.

Readiness checks verify whether the review trail is closed enough to support local dossier-level assurance claims.

### 11. Claim Guardrails

Models evidence-backed claims, audiences, risk levels, review status, prohibited phrase rules, release packages, and non-endorsement limitations.

Readiness checks prevent the repo from overstating what local evidence can prove.

### 12. Federal Evaluation Profile

Models public-sector evaluation concerns, profile mappings, required artifacts, completed capabilities, evidence references, and disclaimer posture.

Readiness checks map local prototype artifacts to federal/IC/DoD-style evaluation concerns without claiming official acceptance or endorsement.

## Runtime Flow

A simplified runtime path looks like this:

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

The expanded assurance path adds:

```
Registry + Policy + Framework Crosswalks
        |
        v
Telemetry Adapter + Campaign Runner + Monitoring Trail
        |
        v
Review Workflow + Export Package
        |
        v
Assurance Dossier + Claim Guardrails + Federal Evaluation Profile
        |
        v
Prototype Readiness / Rollup Gate
```

## Command-Line Interface

Install the package in editable mode, then use the `ix-assurance` command.

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

## Install

```
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run Tests

```
python -m ruff check .
python -m mypy src tests
python -m pytest
```

The local test suite is intended to keep the runtime deterministic, typed, and conservative about claims.

## Example Scenario

The included synthetic example uses a degraded-navigation case.

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
  assurance_dossier.py
  assurance_dossier_validation.py
  assurance_dossier_readiness.py
  authority.py
  claim_guardrails.py
  claim_guardrails_validation.py
  claim_guardrails_readiness.py
  cli.py
  contracts.py
  degradation.py
  evidence.py
  export_package.py
  export_package_validation.py
  export_package_readiness.py
  federal_evaluation_profile.py
  federal_evaluation_profile_validation.py
  federal_evaluation_profile_readiness.py
  framework_crosswalk.py
  framework_crosswalk_evidence.py
  framework_crosswalk_readiness.py
  ledger.py
  monitoring.py
  monitoring_validation.py
  monitoring_readiness.py
  policy.py
  policy_evaluator.py
  policy_waiver_evidence.py
  policy_readiness.py
  prototype_target.py
  prototype_readiness.py
  prototype_rollup.py
  provenance.py
  provenance_verifier.py
  provenance_readiness.py
  registry.py
  registry_catalog.py
  registry_evidence.py
  registry_readiness.py
  reporting.py
  review_workflow.py
  review_workflow_validation.py
  review_workflow_readiness.py
  runner.py
  safety_gate.py
  scenario_campaigns.py
  scenario_campaign_validation.py
  scenario_campaign_runner.py
  scenario_campaign_readiness.py
  scenarios.py
  telemetry.py
  telemetry_adapter.py
  telemetry_readiness.py
  traceability.py
  verification.py

examples/
  degraded-navigation-case.json
  degraded-navigation-catalog.json
  evidence-bundle.json
  mission-need.json
  report.json
  requirements.json
  run-ledger.json
  telemetry-degraded-navigation.json

schemas/
  assurance-case.schema.json
  evidence-bundle.schema.json
  report.schema.json
  run-ledger.schema.json
  scenario-catalog.schema.json

docs/
  ARCHITECTURE.md
  TESTING.md
  THREAT_MODEL.md
  USAGE.md
```

## Design Principles

1. **Evidence over assertion.**
   Claims need support paths, evidence records, and validation surfaces.

2. **Conservative under uncertainty.**
   Missing, stale, invalid, or degraded data should not quietly become approval.

3. **Traceability is first-class.**
   Runtime behavior should connect back to mission need, requirement, hazard, control, scenario, evidence, review, and claim.

4. **Human authority remains visible.**
   The system models when autonomy may act, when review is required, when dissent exists, and when authority is denied.

5. **Claims stay bounded.**
   Local prototype maturity is not certification, authority to operate, deployment readiness, procurement acceptance, agency acceptance, or official endorsement.

6. **Integrity is local and explicit.**
   Hashes, signatures, ledgers, and provenance records support local review. They do not replace external accreditation, legal review, or formal safety certification.

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
