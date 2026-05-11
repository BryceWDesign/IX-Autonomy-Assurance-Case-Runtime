"""Tamper-evident run ledger for assurance runtime artifacts.

The ledger provides hash-chained integrity for runtime artifacts produced by the
assurance-case runtime. It is intentionally scoped: this is a deterministic
hash-chain ledger, not a signing system, PKI, transparency log, or immutable
storage backend.

It detects tampering, broken ordering, duplicate entry identifiers, missing
hashes, and broken previous-entry links. Later systems can persist these ledger
objects to append-only storage or attach signatures without changing the core
ledger semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ix_autonomy_assurance_case_runtime.evidence import (
    EvidenceBundle,
    JSONValue,
    canonical_json_bytes,
    sha256_canonical_json,
)


class LedgerRuntimeError(ValueError):
    """Raised when a ledger artifact is malformed."""


class LedgerRecordType(StrEnum):
    """Artifact types that can be recorded in the run ledger."""

    SCENARIO_RUN = "scenario_run"
    EVIDENCE_BUNDLE = "evidence_bundle"
    VERIFICATION_SUMMARY = "verification_summary"
    ASSURANCE_REPORT = "assurance_report"
    HUMAN_REVIEW = "human_review"
    MANUAL_NOTE = "manual_note"


def _empty_payload() -> dict[str, JSONValue]:
    return {}


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise LedgerRuntimeError(f"{field_name} must not be blank.")
    return normalized


def _require_optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field_name)


def _require_prefixed_hash(value: str, field_name: str) -> str:
    normalized = _require_text(value, field_name)
    if not normalized.startswith("sha256:"):
        raise LedgerRuntimeError(f"{field_name} must use the 'sha256:' prefix.")
    return normalized


def _require_optional_prefixed_hash(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_prefixed_hash(value, field_name)


def _normalize_payload(value: dict[str, JSONValue]) -> dict[str, JSONValue]:
    canonical_json_bytes(value)
    return value


def _normalize_tags(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(_require_text(value, "tags") for value in values)
    if len(normalized) != len(set(normalized)):
        raise LedgerRuntimeError("tags must not contain duplicate values.")
    return tuple(sorted(normalized))


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One hash-chained ledger entry."""

    entry_id: str
    sequence_number: int
    record_type: LedgerRecordType
    case_id: str
    artifact_id: str
    artifact_hash: str
    payload: dict[str, JSONValue] = field(default_factory=_empty_payload)
    run_id: str | None = None
    scenario_id: str | None = None
    previous_entry_hash: str | None = None
    created_by: str = "ix-run-ledger"
    tags: tuple[str, ...] = field(default_factory=tuple)
    entry_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", _require_text(self.entry_id, "entry_id"))
        object.__setattr__(self, "case_id", _require_text(self.case_id, "case_id"))
        object.__setattr__(self, "artifact_id", _require_text(self.artifact_id, "artifact_id"))
        object.__setattr__(
            self,
            "artifact_hash",
            _require_prefixed_hash(self.artifact_hash, "artifact_hash"),
        )
        object.__setattr__(
            self,
            "payload",
            _normalize_payload(self.payload),
        )
        object.__setattr__(self, "run_id", _require_optional_text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "scenario_id",
            _require_optional_text(self.scenario_id, "scenario_id"),
        )
        object.__setattr__(
            self,
            "previous_entry_hash",
            _require_optional_prefixed_hash(
                self.previous_entry_hash,
                "previous_entry_hash",
            ),
        )
        object.__setattr__(self, "created_by", _require_text(self.created_by, "created_by"))
        object.__setattr__(self, "tags", _normalize_tags(self.tags))
        object.__setattr__(
            self,
            "entry_hash",
            _require_optional_prefixed_hash(self.entry_hash, "entry_hash"),
        )

        if self.sequence_number < 1:
            raise LedgerRuntimeError("sequence_number must be greater than or equal to 1.")

    def hash_material(self) -> dict[str, JSONValue]:
        """Return deterministic material used to calculate the ledger entry hash."""

        return {
            "artifact_hash": self.artifact_hash,
            "artifact_id": self.artifact_id,
            "case_id": self.case_id,
            "created_by": self.created_by,
            "entry_id": self.entry_id,
            "payload": self.payload,
            "previous_entry_hash": self.previous_entry_hash,
            "record_type": self.record_type.value,
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "sequence_number": self.sequence_number,
            "tags": list(self.tags),
        }

    def calculate_entry_hash(self) -> str:
        """Calculate the deterministic SHA-256 hash for this ledger entry."""

        return sha256_canonical_json(self.hash_material())

    def has_valid_entry_hash(self) -> bool:
        """Return whether the stored entry hash matches current entry content."""

        return self.entry_hash == self.calculate_entry_hash()

    def with_computed_hash(self) -> LedgerEntry:
        """Return a copy of this entry with its deterministic entry hash set."""

        return LedgerEntry(
            entry_id=self.entry_id,
            sequence_number=self.sequence_number,
            record_type=self.record_type,
            case_id=self.case_id,
            artifact_id=self.artifact_id,
            artifact_hash=self.artifact_hash,
            payload=self.payload,
            run_id=self.run_id,
            scenario_id=self.scenario_id,
            previous_entry_hash=self.previous_entry_hash,
            created_by=self.created_by,
            tags=self.tags,
            entry_hash=self.calculate_entry_hash(),
        )

    def to_dict(self, *, include_computed_hash: bool = True) -> dict[str, JSONValue]:
        """Return a deterministic JSON-compatible ledger-entry dictionary."""

        entry_hash = self.entry_hash
        if entry_hash is None and include_computed_hash:
            entry_hash = self.calculate_entry_hash()

        return {
            "artifact_hash": self.artifact_hash,
            "artifact_id": self.artifact_id,
            "case_id": self.case_id,
            "created_by": self.created_by,
            "entry_hash": entry_hash,
            "entry_id": self.entry_id,
            "payload": self.payload,
            "previous_entry_hash": self.previous_entry_hash,
            "record_type": self.record_type.value,
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "sequence_number": self.sequence_number,
            "tags": list(self.tags),
        }


@dataclass(frozen=True, slots=True)
class LedgerValidationReport:
    """Validation result for a run ledger."""

    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        """Return whether the ledger has no validation errors."""

        return not self.errors


@dataclass(frozen=True, slots=True)
class RunLedger:
    """Hash-chained ledger for runtime assurance artifacts."""

    ledger_id: str
    entries: tuple[LedgerEntry, ...] = field(default_factory=tuple)
    created_by: str = "ix-run-ledger"

    def __post_init__(self) -> None:
        object.__setattr__(self, "ledger_id", _require_text(self.ledger_id, "ledger_id"))
        object.__setattr__(self, "created_by", _require_text(self.created_by, "created_by"))

    def latest_entry_hash(self) -> str | None:
        """Return the latest entry hash, computing it when absent."""

        if not self.entries:
            return None
        latest_entry = self.entries[-1]
        return latest_entry.entry_hash or latest_entry.calculate_entry_hash()

    def append_entry(
        self,
        *,
        entry_id: str,
        record_type: LedgerRecordType,
        case_id: str,
        artifact_id: str,
        artifact_hash: str,
        payload: dict[str, JSONValue] | None = None,
        run_id: str | None = None,
        scenario_id: str | None = None,
        tags: tuple[str, ...] = (),
    ) -> RunLedger:
        """Return a new ledger with one hash-chained entry appended."""

        entry = LedgerEntry(
            entry_id=entry_id,
            sequence_number=len(self.entries) + 1,
            record_type=record_type,
            case_id=case_id,
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            payload=payload or {},
            run_id=run_id,
            scenario_id=scenario_id,
            previous_entry_hash=self.latest_entry_hash(),
            created_by=self.created_by,
            tags=tags,
        ).with_computed_hash()

        return RunLedger(
            ledger_id=self.ledger_id,
            entries=(*self.entries, entry),
            created_by=self.created_by,
        )

    def append_evidence_bundle(
        self,
        *,
        entry_id: str,
        bundle: EvidenceBundle,
        run_id: str | None = None,
        record_type: LedgerRecordType = LedgerRecordType.EVIDENCE_BUNDLE,
    ) -> RunLedger:
        """Return a new ledger with an evidence bundle recorded as an entry."""

        hashed_bundle = bundle.with_computed_hashes()
        record_ids: list[JSONValue] = [record.evidence_id for record in hashed_bundle.records]
        payload: dict[str, JSONValue] = {
            "bundle_id": hashed_bundle.bundle_id,
            "case_id": hashed_bundle.case_id,
            "record_count": len(hashed_bundle.records),
            "record_ids": record_ids,
            "scenario_id": hashed_bundle.scenario_id,
        }

        return self.append_entry(
            entry_id=entry_id,
            record_type=record_type,
            case_id=hashed_bundle.case_id,
            artifact_id=hashed_bundle.bundle_id,
            artifact_hash=hashed_bundle.bundle_hash or hashed_bundle.calculate_bundle_hash(),
            payload=payload,
            run_id=run_id,
            scenario_id=hashed_bundle.scenario_id,
            tags=("evidence-bundle",),
        )

    def validate_chain(self, *, require_unique_run_ids: bool = False) -> LedgerValidationReport:
        """Validate hash-chain continuity and entry integrity."""

        errors: list[str] = []
        warnings: list[str] = []

        if not self.entries:
            warnings.append(f"Run ledger {self.ledger_id!r} has no entries.")
            return LedgerValidationReport(errors=(), warnings=tuple(warnings))

        entry_ids = tuple(entry.entry_id for entry in self.entries)
        duplicate_entry_ids = sorted(
            {entry_id for entry_id in entry_ids if entry_ids.count(entry_id) > 1}
        )
        for duplicate_entry_id in duplicate_entry_ids:
            errors.append(f"Ledger entry identifier {duplicate_entry_id!r} is duplicated.")

        if require_unique_run_ids:
            run_ids = tuple(entry.run_id for entry in self.entries if entry.run_id is not None)
            duplicate_run_ids = sorted({run_id for run_id in run_ids if run_ids.count(run_id) > 1})
            for duplicate_run_id in duplicate_run_ids:
                errors.append(f"Ledger run identifier {duplicate_run_id!r} is duplicated.")

        for index, entry in enumerate(self.entries, start=1):
            if entry.sequence_number != index:
                errors.append(
                    f"Ledger entry {entry.entry_id!r} has sequence_number "
                    f"{entry.sequence_number}, expected {index}."
                )

            if entry.entry_hash is None:
                warnings.append(f"Ledger entry {entry.entry_id!r} has no entry hash.")
            elif not entry.has_valid_entry_hash():
                errors.append(f"Ledger entry {entry.entry_id!r} hash does not match entry content.")

            if index == 1:
                if entry.previous_entry_hash is not None:
                    errors.append(
                        f"First ledger entry {entry.entry_id!r} must not have a previous hash."
                    )
                continue

            previous_entry = self.entries[index - 2]
            expected_previous_hash = (
                previous_entry.entry_hash or previous_entry.calculate_entry_hash()
            )

            if entry.previous_entry_hash != expected_previous_hash:
                errors.append(
                    f"Ledger entry {entry.entry_id!r} previous hash does not match "
                    f"entry {previous_entry.entry_id!r}."
                )

        return LedgerValidationReport(
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    def to_dict(self, *, include_computed_hashes: bool = True) -> dict[str, JSONValue]:
        """Return a deterministic JSON-compatible ledger dictionary."""

        return {
            "created_by": self.created_by,
            "entries": [
                entry.to_dict(include_computed_hash=include_computed_hashes)
                for entry in self.entries
            ],
            "ledger_id": self.ledger_id,
        }
