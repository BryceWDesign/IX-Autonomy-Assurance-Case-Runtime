# Threat Model

## Protected Properties

This runtime is designed to help protect:

- evidence integrity,
- traceability integrity,
- scenario-review visibility,
- safety-gate decision clarity,
- degraded-mode detection visibility,
- assurance-case reference consistency,
- ledger-chain continuity.

It is not designed to protect classified data, secrets, production networks, or real-world autonomous platforms.

## Primary Threats

### Fabricated Evidence

A user may provide evidence records that claim a scenario passed when no scenario was executed.

Current mitigation:

- deterministic evidence hashes,
- evidence status validation,
- verification checks,
- report warnings/errors,
- traceability requirements when enabled.

Remaining gap:

- the runtime cannot prove external telemetry was truthful.

### Tampered Evidence

A user may alter evidence after generation.

Current mitigation:

- record content hashes,
- bundle hashes,
- evidence-bundle integrity checks,
- ledger entry hashes,
- ledger previous-hash chain validation.

Remaining gap:

- hashes are local integrity checks, not signatures.

### Missing Evidence

A scenario may claim acceptance without evidence records.

Current mitigation:

- acceptance criteria can require evidence,
- verification checks required evidence,
- reports expose missing evidence,
- assurance-case validation exposes missing references.

### Broken Traceability

A scenario may not connect to claims, requirements, hazards, or evidence.

Current mitigation:

- traceability graph validation,
- orphan detection,
- scenario-to-claim path check,
- optional strict traceability requirement.

### Unsafe Authority Relaxation

A review decision may attempt to turn emergency safe-hold, veto, or denied authority into nominal autonomy.

Current mitigation:

- authority controller blocks unsafe relaxation unless the runtime was explicitly in defer-to-human approval state.

### Stale or Invalid Evidence

A stale or invalid record may be used to support a claim.

Current mitigation:

- evidence status modeling,
- bundle validation,
- degradation signals for stale/invalid evidence,
- verification warnings/errors,
- report exposure.

### Conflicting Telemetry

Telemetry sources may disagree.

Current mitigation:

- conflict checks,
- degradation signals,
- conservative recommended decision and authority state.

### Overclaiming

A report may be interpreted as certification.

Current mitigation:

- documentation states non-claims,
- reports describe runtime verification result only,
- security policy defines boundary.

## Assumptions

The runtime assumes:

- JSON files are local artifacts supplied by the user,
- examples are synthetic,
- hash algorithms operate correctly,
- Python runtime is not maliciously modified,
- local filesystem is not assumed immutable,
- users do not treat local hashes as legal certification.

## Out of Scope

Out of scope for the first release:

- PKI,
- signatures,
- HSM/KMS integration,
- remote attestation,
- immutable storage,
- classified workflows,
- network service hardening,
- model evaluation benchmarks,
- production autonomy control,
- formal accreditation package.

## Review Guidance

A valid report means:

> The runtime artifacts passed the implemented checks.

It does not mean:

> The autonomous system is safe for operational deployment.

A valid ledger means:

> The local ledger chain is internally consistent.

It does not mean:

> The underlying real-world event happened exactly as recorded.
