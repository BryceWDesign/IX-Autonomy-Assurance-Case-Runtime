# Architecture

## Purpose

IX-Autonomy-Assurance-Case-Runtime is a Trusted Autonomy T&E assurance-case runtime.

It turns autonomy evaluation artifacts into a structured runtime loop:

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
  -> hash-chained ledger
```

The project is designed around one core principle:

Autonomous or AI-enabled behavior should not be trusted because a model, tool, or test script says it worked. It should be reviewed through traceable requirements, hazards, scenarios, evidence, verification, and human authority.

Core Modules
contracts.py

Defines stable domain vocabulary:

assurance-case status,
evidence status,
hazard severity,
autonomy decision type,
runtime authority state,
verification result,
review disposition.

These values are intentionally explicit because they become wire values in reports, CLI output, schemas, and evidence records.

assurance_case.py

Defines the assurance-case spine:

claims,
subclaims,
evidence links,
assumptions,
hazards,
controls,
mitigations,
verification criteria.

The assurance case validates internal references and flags unresolved severe hazards, unsupported claims, missing evidence, and review-blocking errors.

scenarios.py

Defines the scenario catalog:

operational contexts,
autonomy functions,
operating conditions,
stressors,
expected safe behavior,
acceptance criteria,
mission threads,
executable scenarios.

A scenario is not merely prose. It is a structured test/evaluation artifact that can be executed by the runtime.

evidence.py

Defines deterministic evidence records and bundles.

It provides:

canonical JSON serialization,
SHA-256 record hashes,
SHA-256 bundle hashes,
evidence integrity validation,
stale/invalid/missing status handling.

This is integrity support, not a signing system.

traceability.py

Builds an inspectable graph linking:

```
mission need -> requirement -> hazard -> control -> scenario -> evidence -> assurance claim
```

It supports:

node validation,
edge validation,
orphan detection,
directed path checks,
connected path checks.
safety_gate.py

Evaluates runtime telemetry against explicit safety rules and scenario expectations.

The safety gate emits:

allow,
clamp,
defer,
veto,
safe_hold.

It also emits the required runtime authority state, operator-review flag, degraded-mode flag, triggered rule IDs, and rationale.

authority.py

Models human authority review.

It prevents review decisions from silently relaxing highly restrictive runtime states. A human review may release a defer-to-human path when the runtime explicitly requested human approval, but it must not silently convert emergency safe-hold, veto, or denied authority into nominal autonomy.

degradation.py

Detects runtime degradation signals from telemetry and evidence state.

Covered categories include:

sensor drift,
communications loss,
navigation uncertainty,
power degradation,
conflicting telemetry,
timing degradation,
stale or invalid evidence.

The degradation engine recommends a conservative autonomy decision and authority state.

runner.py

Runs one scenario through the runtime pipeline:
```
scenario catalog
  -> telemetry
  -> degradation assessment
  -> safety gate
  -> final runtime decision
  -> evidence bundle
```

The runner produces a structured scenario-run result and hashed evidence bundle.

verification.py

Independently verifies scenario-run output.

It checks:

assurance-case validity,
scenario-catalog validity,
expected safe behavior,
acceptance criteria,
required evidence,
evidence bundle integrity,
severe hazard coverage,
operator-review consistency,
traceability presence and scenario-to-claim connection.
reporting.py

Generates machine-readable and Markdown reports from runtime and verification artifacts.

Reports include:

executive summary,
runtime outcome,
verification checks,
assurance gaps,
claim posture,
acceptance criteria,
evidence integrity,
traceability status.
ledger.py

Provides hash-chained ledger entries for runtime artifacts.

The ledger detects:

missing entry hashes,
tampered entry payloads,
broken previous-hash links,
out-of-order sequence numbers,
duplicate entry IDs,
duplicate run IDs when strict run uniqueness is enabled.

This is not a transparency log or PKI-backed signature system.

cli.py

Provides command-line access:
```
ix-assurance validate-case
ix-assurance run-scenario
ix-assurance verify-bundle
ix-assurance validate-ledger
ix-assurance export-report
ix-assurance audit-traceability
```

Trust Boundary

The runtime treats these as untrusted inputs:

telemetry,
scenario files,
evidence files,
human-authored JSON,
generated reports,
prior bundles,
ledger files.

The runtime provides deterministic validation and integrity checks over those inputs. It does not prove that the external world was truthful.

Non-Claims

This project does not claim:

government approval,
operational certification,
safety certification,
cybersecurity authorization,
real-world mission readiness,
replacement of human test authority,
replacement of legal review,
replacement of classified evaluation,
production autonomy control.
Design Posture

The runtime is intentionally conservative:

missing evidence blocks or warns,
invalid evidence fails,
severe hazards require controls or mitigations,
severe scenario stressors require restrictive behavior,
emergency safe-hold cannot be silently relaxed,
traceability gaps remain visible,
verification can return inconclusive instead of pretending success.
First-Release Boundary

The first release is a local reference runtime. It is suitable for:

synthetic examples,
architecture review,
software validation,
evidence-flow demonstration,
T&E workflow prototyping,
assurance-case modeling.

It is not suitable by itself for production deployment into a real autonomous system.
