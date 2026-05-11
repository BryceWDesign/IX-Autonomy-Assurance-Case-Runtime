# Contributing

## Project Intent

IX-Autonomy-Assurance-Case-Runtime is built to support evidence-backed evaluation of AI/autonomous system behavior.

Contributions should strengthen one or more of these goals:

- traceability,
- safety-gate correctness,
- evidence integrity,
- scenario testability,
- degradation reasoning,
- verification clarity,
- report usefulness,
- human review visibility,
- auditability,
- deterministic behavior.

## Ground Rules

Contributions must not add hype, unsupported claims, fake certification language, or language implying official government endorsement.

Do not add:

- autonomous weapons-control behavior,
- real operational tactics,
- classified examples,
- exploit instructions,
- credential-handling shortcuts,
- hidden network calls,
- opaque model calls,
- hard-coded secrets,
- unverifiable “pass” states,
- placeholder safety claims.

## Code Standards

All code should be:

- typed,
- deterministic,
- test-covered,
- explicit about failure states,
- conservative under uncertainty,
- readable before clever,
- free of duplicate imports,
- free of unused public APIs.

Run before submitting:

```
python -m ruff check src tests
python -m mypy src tests
python -m pytest
```
Evidence Rules

Evidence-related code must preserve these properties:

deterministic serialization,
stable content hashes,
explicit invalid/stale/missing states,
no silent acceptance of missing evidence,
no unverifiable success state,
no automatic claim acceptance without checks.
Review Rules

Human review code must not silently relax restrictive runtime decisions.

A review path may release a defer-to-human condition only when the runtime decision was explicitly waiting for human approval. It must not turn emergency safe-hold, veto, or denied authority into nominal autonomy without a separate, explicit, domain-approved process outside this reference runtime.

Documentation Rules

Documentation must distinguish clearly between:

what the runtime currently implements,
what it verifies internally,
what remains outside scope,
what requires human authority,
what would require external certification or accreditation.

License

By contributing, you agree that your contribution is provided under the Apache License, Version 2.0.
