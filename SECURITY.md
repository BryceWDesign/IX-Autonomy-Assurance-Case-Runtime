# Security Policy

## Scope

This project is a reference implementation for a Trusted Autonomy T&E assurance-case runtime. It is designed to make autonomy/AI evaluation artifacts more traceable, reviewable, and evidence-backed.

It is **not** a certified safety system, production command-and-control system, weapons-control system, flight-critical runtime, autonomous vehicle controller, cybersecurity authorization package, or substitute for qualified human review.

## Official Source

The official repository is:

`IX-Autonomy-Assurance-Case-Runtime`

Use repository provenance, commit history, release signatures when available, and maintainer identity checks before trusting any copy, mirror, binary, or ZIP archive.

Do not run unofficial binaries or installer-style downloads claiming to represent this project unless their provenance is independently verified.

## Supported Security Posture

The current implementation provides:

- deterministic evidence records,
- SHA-256 evidence bundle hashing,
- hash-chained run ledger entries,
- strict reference validation,
- scenario-catalog validation,
- safety-gate decision records,
- degradation assessment records,
- independent verification summaries,
- machine-readable reports,
- human-readable reports,
- CLI validation paths.

The current implementation does **not** provide:

- cryptographic signatures,
- public-key infrastructure,
- hardware security module integration,
- immutable storage backend,
- transparency log,
- network service authentication,
- classified-data handling,
- production authorization workflow,
- formal safety certification,
- formal accreditation.

## Reporting Security Issues

Please report security issues privately to the maintainer instead of opening a public issue with exploit details.

Include:

- affected file or command,
- reproduction steps,
- expected behavior,
- actual behavior,
- whether data integrity, command execution, evidence validation, or ledger integrity is affected.

## Handling Sensitive Data

Do not place classified, controlled, export-restricted, proprietary, personal, credential, key, token, or operationally sensitive data into example evidence bundles or reports.

The examples in this repository are synthetic and intended for software validation only.

## Integrity Expectations

Treat evidence and ledger outputs as integrity aids, not proof of absolute truth.

A valid hash chain means the local records are internally consistent. It does not prove that the underlying telemetry, operator input, source system, test environment, or reviewer action was truthful.

## Safe Use Boundary

Do not use this project to authorize real-world autonomous action without qualified engineering review, safety review, cybersecurity review, legal review, operational approval, and domain-specific test authority.
