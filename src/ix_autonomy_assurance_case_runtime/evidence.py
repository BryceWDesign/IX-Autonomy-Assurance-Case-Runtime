"""Evidence records, deterministic serialization, and evidence bundles.

This module provides the first real evidence layer for the assurance-case
runtime. It intentionally does not claim cryptographic signing yet. It provides
deterministic JSON serialization, SHA-256 content hashes, bundle hashes, and
strict validation so later runtime, reporting, ledger, and CLI commits can rely
on stable evidence artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import TypeAlias

from ix_autonomy_assurance_case_runtime.contracts import EvidenceStatus

JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


class EvidenceRuntimeError(ValueError):
    """Raised when an evidence artifact is malformed or not serializable."""


def _empty_payload() -> dict[str, JSONValue]:
    return {}


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise EvidenceRuntimeError(f"{field_name} must not be blank.")
    return normalized


def _normalize_tags(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(_require_text(value, "tags") for value in values)
    if len(normalized) != len(set(normalized)):
        raise EvidenceRuntimeError("tags must not contain duplicate values.")
    return tuple(sorted(normalized))


def _normalize_json_value(value: JSONValue) -> JSONValue:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvidenceRuntimeError("JSON float values must be finite.")
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, JSONValue] = {}
        for key, item in value.items():
            normalized_key = _require_text(key, "JSON object key")
            normalized[normalized_key] = _normalize_json_value(item)
        return dict(sorted(normalized.items()))
    raise EvidenceRuntimeError(f"Unsupported JSON value type: {type(value).__name__}")


def _normalize_json_object(value: dict[str, JSONValue]) -> dict[str, JSONValue]:
    normalized_value = _normalize_json_value(value)
    if not isinstance(normalized_value, dict):
        raise EvidenceRuntimeError("payload must be a JSON object.")
    return normalized_value


def canonical_json_bytes(value: JSONValue) -> bytes:
    """Return deterministic UTF-8 JSON bytes for a supported JSON value."""

    normalized_value = _normalize_json_value(value)
    encoded = json.dumps(
        normalized_value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return encoded.encode("utf-8")


def sha256_hexdigest(data: bytes) -> str:
    """Return a prefixed SHA-256 digest for raw bytes."""

    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def sha256_canonical_json(value: JSONValue) -> str:
    """Return a prefixed SHA-256 digest for canonical JSON."""

    return sha256_hexdigest(canonical_json_bytes(value))


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """Single evidence record attached to a scenario, claim, hazard, or report."""

    evidence_id: str
    kind: str
    source: str
    payload: dict[str, JSONValue] = field(default_factory=_empty_payload)
    status: EvidenceStatus = EvidenceStatus.PROVIDED
    created_by: str = "ix-assurance-runtime"
    tags: tuple[str, ...] = field(default_factory=tuple)
    content_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _require_text(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "kind", _require_text(self.kind, "kind"))
        object.__setattr__(self, "source", _require_text(self.source, "source"))
        object.__setattr__(self, "payload", _normalize_json_object(self.payload))
        object.__setattr__(self, "created_by", _require_text(self.created_by, "created_by"))
        object.__setattr__(self, "tags", _normalize_tags(self.tags))

        if self.content_hash is not None:
            object.__setattr__(
                self,
                "content_hash",
                _require_text(self.content_hash, "content_hash"),
            )

    def hash_material(self) -> dict[str, JSONValue]:
        """Return deterministic material used to calculate the record content hash."""

        return {
            "created_by": self.created_by,
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "payload": self.payload,
            "source": self.source,
            "status": self.status.value,
            "tags": list(self.tags),
        }

    def calculate_content_hash(self) -> str:
        """Calculate the deterministic SHA-256 content hash for this record."""

        return sha256_canonical_json(self.hash_material())

    def has_valid_content_hash(self) -> bool:
        """Return whether the stored content hash matches the record content."""

        return self.content_hash == self.calculate_content_hash()

    def with_computed_hash(self) -> EvidenceRecord:
        """Return a copy of this record with its deterministic content hash set."""

        return EvidenceRecord(
            evidence_id=self.evidence_id,
            kind=self.kind,
            source=self.source,
            payload=self.payload,
            status=self.status,
            created_by=self.created_by,
            tags=self.tags,
            content_hash=self.calculate_content_hash(),
        )

    def to_dict(self, *, include_computed_hash: bool = True) -> dict[str, JSONValue]:
        """Return a deterministic JSON-compatible representation."""

        hash_value = self.content_hash
        if hash_value is None and include_computed_hash:
            hash_value = self.calculate_content_hash()

        return {
            "content_hash": hash_value,
            "created_by": self.created_by,
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "payload": self.payload,
            "source": self.source,
            "status": self.status.value,
            "tags": list(self.tags),
        }


@dataclass(frozen=True, slots=True)
class EvidenceBundleValidationReport:
    """Validation result for an evidence bundle."""

    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        """Return whether the evidence bundle has no validation errors."""

        return not self.errors


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Deterministic collection of evidence records for a case or scenario."""

    bundle_id: str
    case_id: str
    records: tuple[EvidenceRecord, ...]
    scenario_id: str | None = None
    created_by: str = "ix-assurance-runtime"
    bundle_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "bundle_id", _require_text(self.bundle_id, "bundle_id"))
        object.__setattr__(self, "case_id", _require_text(self.case_id, "case_id"))
        object.__setattr__(self, "created_by", _require_text(self.created_by, "created_by"))

        if self.scenario_id is not None:
            object.__setattr__(
                self,
                "scenario_id",
                _require_text(self.scenario_id, "scenario_id"),
            )

        if self.bundle_hash is not None:
            object.__setattr__(
                self,
                "bundle_hash",
                _require_text(self.bundle_hash, "bundle_hash"),
            )

        if not self.records:
            raise EvidenceRuntimeError("records must not be empty.")

        record_ids = tuple(record.evidence_id for record in self.records)
        if len(record_ids) != len(set(record_ids)):
            raise EvidenceRuntimeError("records must not contain duplicate evidence_id values.")

    def record_index(self) -> dict[str, EvidenceRecord]:
        """Return evidence records keyed by evidence identifier."""

        return {record.evidence_id: record for record in self.records}

    def bundle_material(self) -> dict[str, JSONValue]:
        """Return deterministic material used to calculate the bundle hash."""

        return {
            "bundle_id": self.bundle_id,
            "case_id": self.case_id,
            "created_by": self.created_by,
            "records": [
                record.with_computed_hash().to_dict(include_computed_hash=True)
                for record in self.records
            ],
            "scenario_id": self.scenario_id,
        }

    def calculate_bundle_hash(self) -> str:
        """Calculate the deterministic SHA-256 bundle hash."""

        return sha256_canonical_json(self.bundle_material())

    def has_valid_bundle_hash(self) -> bool:
        """Return whether the stored bundle hash matches the bundle content."""

        return self.bundle_hash == self.calculate_bundle_hash()

    def with_computed_hashes(self) -> EvidenceBundle:
        """Return a copy with all record hashes and the bundle hash computed."""

        hashed_records = tuple(record.with_computed_hash() for record in self.records)
        unsigned_bundle = EvidenceBundle(
            bundle_id=self.bundle_id,
            case_id=self.case_id,
            records=hashed_records,
            scenario_id=self.scenario_id,
            created_by=self.created_by,
        )

        return EvidenceBundle(
            bundle_id=unsigned_bundle.bundle_id,
            case_id=unsigned_bundle.case_id,
            records=unsigned_bundle.records,
            scenario_id=unsigned_bundle.scenario_id,
            created_by=unsigned_bundle.created_by,
            bundle_hash=unsigned_bundle.calculate_bundle_hash(),
        )

    def validate_integrity(self) -> EvidenceBundleValidationReport:
        """Validate record hashes, bundle hash, and evidence status."""

        errors: list[str] = []
        warnings: list[str] = []

        for record in self.records:
            if record.content_hash is None:
                warnings.append(f"Evidence record {record.evidence_id!r} has no content hash.")
            elif not record.has_valid_content_hash():
                errors.append(
                    f"Evidence record {record.evidence_id!r} content hash does not match "
                    "record content."
                )

            if record.status is EvidenceStatus.INVALID:
                errors.append(f"Evidence record {record.evidence_id!r} is marked invalid.")
            elif not record.status.is_usable():
                warnings.append(
                    f"Evidence record {record.evidence_id!r} has non-usable status "
                    f"{record.status.value!r}."
                )

        if self.bundle_hash is None:
            warnings.append(f"Evidence bundle {self.bundle_id!r} has no bundle hash.")
        elif not self.has_valid_bundle_hash():
            errors.append(
                f"Evidence bundle {self.bundle_id!r} hash does not match bundle content."
            )

        return EvidenceBundleValidationReport(
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    def to_dict(self, *, include_computed_hash: bool = True) -> dict[str, JSONValue]:
        """Return a deterministic JSON-compatible representation."""

        hash_value = self.bundle_hash
        if hash_value is None and include_computed_hash:
            hash_value = self.calculate_bundle_hash()

        return {
            "bundle_hash": hash_value,
            "bundle_id": self.bundle_id,
            "case_id": self.case_id,
            "created_by": self.created_by,
            "records": [
                record.to_dict(include_computed_hash=include_computed_hash)
                for record in self.records
            ],
            "scenario_id": self.scenario_id,
        }
