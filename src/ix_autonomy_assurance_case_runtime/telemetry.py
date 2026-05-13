"""Telemetry source, schema, envelope, and replay records.

The serious prototype needs a telemetry adapter layer before it can claim
source-trust-aware runtime evaluation. This module adds strict local records for
telemetry sources, schemas, normalized envelopes, quality flags, timestamp
posture, and replay fixtures. Adapter execution and readiness evaluation are
left for later commits so this foundation stays narrow and reviewable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable telemetry identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")


def _require_text(value: str, field_name: str) -> None:
    """Validate nonblank telemetry text."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")


def _require_nonblank_unique_tuple(values: tuple[str, ...], field_name: str) -> None:
    """Validate a nonempty tuple of nonblank unique strings."""

    if not values:
        raise ContractValueError(f"{field_name} must not be empty.")
    for value in values:
        if not value.strip():
            raise ContractValueError(f"{field_name} must not contain blank values.")
    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")


def _require_optional_nonblank_unique_tuple(values: tuple[str, ...], field_name: str) -> None:
    """Validate an optional tuple of nonblank unique strings."""

    for value in values:
        if not value.strip():
            raise ContractValueError(f"{field_name} must not contain blank values.")
    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")


def _parse_utc_timestamp(value: str, field_name: str) -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC."""

    _require_text(value, field_name)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractValueError(f"{field_name} must be an ISO-8601 UTC timestamp.") from exc
    if parsed.tzinfo is None:
        raise ContractValueError(f"{field_name} must include a timezone.")
    return parsed.astimezone(UTC)


class TelemetrySourceKind(RuntimeStrEnum):
    """Kind of telemetry source feeding runtime evaluation."""

    SENSOR = "sensor"
    SIMULATOR = "simulator"
    OPERATOR_REPORT = "operator_report"
    MODEL_OUTPUT = "model_output"
    LOG_REPLAY = "log_replay"
    EXTERNAL_FEED = "external_feed"

    def is_replay_source(self) -> bool:
        """Return whether this source is replay-only."""

        return self is TelemetrySourceKind.LOG_REPLAY

    def is_machine_generated(self) -> bool:
        """Return whether this source is machine-generated."""

        return self in {
            TelemetrySourceKind.SENSOR,
            TelemetrySourceKind.SIMULATOR,
            TelemetrySourceKind.MODEL_OUTPUT,
            TelemetrySourceKind.LOG_REPLAY,
            TelemetrySourceKind.EXTERNAL_FEED,
        }


class TelemetryTrustLevel(RuntimeStrEnum):
    """Trust level assigned to a telemetry source."""

    UNTRUSTED = "untrusted"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERIFIED_SOURCE = "verified_source"

    @property
    def rank(self) -> int:
        """Return ordinal trust rank."""

        ranks = {
            TelemetryTrustLevel.UNTRUSTED: 0,
            TelemetryTrustLevel.LOW: 1,
            TelemetryTrustLevel.MODERATE: 2,
            TelemetryTrustLevel.HIGH: 3,
            TelemetryTrustLevel.VERIFIED_SOURCE: 4,
        }
        return ranks[self]

    def supports_acceptance(self) -> bool:
        """Return whether this trust level can support acceptance-oriented evaluation."""

        return self.rank >= TelemetryTrustLevel.HIGH.rank

    def requires_evidence(self) -> bool:
        """Return whether this trust level should be backed by evidence records."""

        return self.rank >= TelemetryTrustLevel.HIGH.rank


class TelemetryTimestampAuthority(RuntimeStrEnum):
    """Timestamp authority for telemetry capture time."""

    LOCAL_CLOCK = "local_clock"
    SOURCE_PROVIDED = "source_provided"
    SIGNED_SOURCE = "signed_source"
    REPLAY_FILE = "replay_file"
    UNKNOWN = "unknown"

    def supports_strong_ordering(self) -> bool:
        """Return whether this timestamp authority can support stronger ordering claims."""

        return self in {
            TelemetryTimestampAuthority.SOURCE_PROVIDED,
            TelemetryTimestampAuthority.SIGNED_SOURCE,
        }


class TelemetryFieldType(RuntimeStrEnum):
    """Supported telemetry schema field types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ENUM = "enum"
    TIMESTAMP = "timestamp"

    def is_numeric(self) -> bool:
        """Return whether this field type is numeric."""

        return self in {TelemetryFieldType.INTEGER, TelemetryFieldType.FLOAT}


class TelemetryFreshnessStatus(RuntimeStrEnum):
    """Freshness posture for a telemetry envelope."""

    CURRENT = "current"
    STALE = "stale"
    EXPIRED = "expired"
    FUTURE_DATED = "future_dated"
    UNKNOWN = "unknown"

    def supports_runtime_evaluation(self) -> bool:
        """Return whether this freshness status can support runtime evaluation."""

        return self is TelemetryFreshnessStatus.CURRENT


class TelemetryQualityFlag(RuntimeStrEnum):
    """Quality flags attached to normalized telemetry envelopes."""

    MISSING_FIELD = "missing_field"
    SCHEMA_MISMATCH = "schema_mismatch"
    STALE_TIMESTAMP = "stale_timestamp"
    FUTURE_TIMESTAMP = "future_timestamp"
    OUT_OF_RANGE = "out_of_range"
    SOURCE_UNTRUSTED = "source_untrusted"
    REPLAY_ONLY = "replay_only"

    def blocks_acceptance(self) -> bool:
        """Return whether this flag blocks acceptance-oriented evaluation."""

        return self in {
            TelemetryQualityFlag.MISSING_FIELD,
            TelemetryQualityFlag.SCHEMA_MISMATCH,
            TelemetryQualityFlag.STALE_TIMESTAMP,
            TelemetryQualityFlag.FUTURE_TIMESTAMP,
            TelemetryQualityFlag.OUT_OF_RANGE,
            TelemetryQualityFlag.SOURCE_UNTRUSTED,
        }


@dataclass(frozen=True, slots=True)
class TelemetrySource:
    """Registered telemetry source with trust and schema boundaries."""

    source_id: str
    name: str
    kind: TelemetrySourceKind
    trust_level: TelemetryTrustLevel
    timestamp_authority: TelemetryTimestampAuthority
    owner: str
    allowed_schema_ids: tuple[str, ...]
    evidence_bundle_ids: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        """Validate telemetry source records."""

        _require_identifier(self.source_id, "telemetry source_id")
        _require_text(self.name, "telemetry source name")
        _require_text(self.owner, "telemetry source owner")
        _require_nonblank_unique_tuple(
            self.allowed_schema_ids,
            f"telemetry source {self.source_id!r} allowed_schema_ids",
        )
        _require_optional_nonblank_unique_tuple(
            self.evidence_bundle_ids,
            f"telemetry source {self.source_id!r} evidence_bundle_ids",
        )
        if self.description and not self.description.strip():
            raise ContractValueError(f"Telemetry source {self.source_id!r} description is blank.")
        if self.trust_level.requires_evidence() and not self.evidence_bundle_ids:
            raise ContractValueError(
                f"Telemetry source {self.source_id!r} trust level requires evidence bundles."
            )
        if (
            self.kind.is_replay_source()
            and self.timestamp_authority is not TelemetryTimestampAuthority.REPLAY_FILE
        ):
            raise ContractValueError(
                f"Telemetry replay source {self.source_id!r} must use replay-file timestamp "
                "authority."
            )

    def supports_schema(self, schema_id: str) -> bool:
        """Return whether this source is allowed to emit a schema."""

        return schema_id in self.allowed_schema_ids

    def can_support_acceptance(self) -> bool:
        """Return whether this source can support acceptance-oriented evaluation."""

        return self.trust_level.supports_acceptance()


@dataclass(frozen=True, slots=True)
class TelemetrySchemaField:
    """One field definition inside a telemetry schema."""

    field_name: str
    field_type: TelemetryFieldType
    required: bool = True
    unit: str = ""
    allowed_values: tuple[str, ...] = ()
    minimum_value: float | None = None
    maximum_value: float | None = None
    description: str = ""

    def __post_init__(self) -> None:
        """Validate telemetry schema field records."""

        _require_identifier(self.field_name, "telemetry field_name")
        if self.unit and not self.unit.strip():
            raise ContractValueError(
                f"Telemetry field {self.field_name!r} unit must not be whitespace only."
            )
        if self.description and not self.description.strip():
            raise ContractValueError(
                f"Telemetry field {self.field_name!r} description must not be whitespace only."
            )
        _require_optional_nonblank_unique_tuple(
            self.allowed_values,
            f"telemetry field {self.field_name!r} allowed_values",
        )
        self._validate_enum_boundary()
        self._validate_numeric_boundary()

    def _validate_enum_boundary(self) -> None:
        """Validate enum allowed-value requirements."""

        if self.field_type is TelemetryFieldType.ENUM and not self.allowed_values:
            raise ContractValueError(
                f"Telemetry enum field {self.field_name!r} requires allowed values."
            )
        if self.field_type is not TelemetryFieldType.ENUM and self.allowed_values:
            raise ContractValueError(
                f"Telemetry non-enum field {self.field_name!r} must not define allowed values."
            )

    def _validate_numeric_boundary(self) -> None:
        """Validate numeric range requirements."""

        if not self.field_type.is_numeric() and (
            self.minimum_value is not None or self.maximum_value is not None
        ):
            raise ContractValueError(
                f"Telemetry non-numeric field {self.field_name!r} must not define numeric range."
            )
        if (
            self.minimum_value is not None
            and self.maximum_value is not None
            and self.maximum_value < self.minimum_value
        ):
            raise ContractValueError(
                f"Telemetry field {self.field_name!r} maximum_value must be >= minimum_value."
            )


@dataclass(frozen=True, slots=True)
class TelemetrySchema:
    """Schema describing normalized telemetry payload fields."""

    schema_id: str
    name: str
    version: str
    fields: tuple[TelemetrySchemaField, ...]
    description: str = ""

    def __post_init__(self) -> None:
        """Validate telemetry schema records."""

        _require_identifier(self.schema_id, "telemetry schema_id")
        _require_text(self.name, "telemetry schema name")
        _require_text(self.version, "telemetry schema version")
        if not self.fields:
            raise ContractValueError(f"Telemetry schema {self.schema_id!r} requires fields.")
        field_names = tuple(field.field_name for field in self.fields)
        if len(field_names) != len(set(field_names)):
            raise ContractValueError(
                f"Telemetry schema {self.schema_id!r} must not contain duplicate fields."
            )
        if self.description and not self.description.strip():
            raise ContractValueError(
                f"Telemetry schema {self.schema_id!r} description must not be whitespace only."
            )

    def field_by_name(self, field_name: str) -> TelemetrySchemaField | None:
        """Return a schema field by name."""

        return {field.field_name: field for field in self.fields}.get(field_name)

    def required_field_names(self) -> tuple[str, ...]:
        """Return required field names in schema order."""

        return tuple(field.field_name for field in self.fields if field.required)


@dataclass(frozen=True, slots=True)
class TelemetryEnvelope:
    """Normalized telemetry payload with source, schema, timestamp, and quality posture."""

    envelope_id: str
    source_id: str
    schema_id: str
    captured_at_utc: str
    received_at_utc: str
    payload: dict[str, Any]
    freshness_status: TelemetryFreshnessStatus
    quality_flags: tuple[TelemetryQualityFlag, ...] = ()
    replay_record_id: str | None = None

    def __post_init__(self) -> None:
        """Validate telemetry envelope records."""

        _require_identifier(self.envelope_id, "telemetry envelope_id")
        _require_identifier(self.source_id, "telemetry envelope source_id")
        _require_identifier(self.schema_id, "telemetry envelope schema_id")
        captured_at = _parse_utc_timestamp(
            self.captured_at_utc,
            "telemetry envelope captured_at_utc",
        )
        received_at = _parse_utc_timestamp(
            self.received_at_utc,
            "telemetry envelope received_at_utc",
        )
        if captured_at > received_at:
            raise ContractValueError(
                f"Telemetry envelope {self.envelope_id!r} captured_at_utc must not be after "
                "received_at_utc."
            )
        for field_name in self.payload:
            if not field_name.strip():
                raise ContractValueError(
                    f"Telemetry envelope {self.envelope_id!r} payload has a blank field name."
                )
        if len(self.quality_flags) != len(set(self.quality_flags)):
            raise ContractValueError(
                f"Telemetry envelope {self.envelope_id!r} quality_flags must be unique."
            )
        if self.replay_record_id is not None:
            _require_identifier(self.replay_record_id, "telemetry envelope replay_record_id")
        self._validate_freshness_consistency()

    @property
    def captured_at(self) -> datetime:
        """Return parsed UTC capture time."""

        return _parse_utc_timestamp(self.captured_at_utc, "telemetry envelope captured_at_utc")

    @property
    def received_at(self) -> datetime:
        """Return parsed UTC receive time."""

        return _parse_utc_timestamp(self.received_at_utc, "telemetry envelope received_at_utc")

    def has_blocking_quality_flags(self) -> bool:
        """Return whether any quality flag blocks acceptance-oriented evaluation."""

        return any(flag.blocks_acceptance() for flag in self.quality_flags)

    def can_support_runtime_evaluation(self) -> bool:
        """Return whether this envelope can support runtime evaluation."""

        return (
            self.freshness_status.supports_runtime_evaluation()
            and not self.has_blocking_quality_flags()
        )

    def _validate_freshness_consistency(self) -> None:
        """Validate consistency between freshness status and quality flags."""

        if (
            self.freshness_status is TelemetryFreshnessStatus.CURRENT
            and TelemetryQualityFlag.STALE_TIMESTAMP in self.quality_flags
        ):
            raise ContractValueError(
                f"Telemetry envelope {self.envelope_id!r} cannot be current and stale."
            )
        if (
            self.freshness_status is TelemetryFreshnessStatus.CURRENT
            and TelemetryQualityFlag.FUTURE_TIMESTAMP in self.quality_flags
        ):
            raise ContractValueError(
                f"Telemetry envelope {self.envelope_id!r} cannot be current and future-dated."
            )
        if (
            self.freshness_status is TelemetryFreshnessStatus.STALE
            and TelemetryQualityFlag.STALE_TIMESTAMP not in self.quality_flags
        ):
            raise ContractValueError(
                f"Telemetry envelope {self.envelope_id!r} stale status requires stale flag."
            )
        if (
            self.freshness_status is TelemetryFreshnessStatus.FUTURE_DATED
            and TelemetryQualityFlag.FUTURE_TIMESTAMP not in self.quality_flags
        ):
            raise ContractValueError(
                f"Telemetry envelope {self.envelope_id!r} future-dated status requires "
                "future-timestamp flag."
            )


@dataclass(frozen=True, slots=True)
class TelemetryReplayRecord:
    """Replay fixture metadata for deterministic telemetry re-evaluation."""

    replay_record_id: str
    source_id: str
    schema_id: str
    replay_file_uri: str
    recorded_at_utc: str
    scenario_ids: tuple[str, ...]
    envelope_ids: tuple[str, ...] = ()
    evidence_bundle_ids: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        """Validate telemetry replay records."""

        _require_identifier(self.replay_record_id, "telemetry replay_record_id")
        _require_identifier(self.source_id, "telemetry replay source_id")
        _require_identifier(self.schema_id, "telemetry replay schema_id")
        _require_text(self.replay_file_uri, "telemetry replay_file_uri")
        _parse_utc_timestamp(self.recorded_at_utc, "telemetry replay recorded_at_utc")
        _require_nonblank_unique_tuple(
            self.scenario_ids,
            f"telemetry replay {self.replay_record_id!r} scenario_ids",
        )
        _require_optional_nonblank_unique_tuple(
            self.envelope_ids,
            f"telemetry replay {self.replay_record_id!r} envelope_ids",
        )
        _require_optional_nonblank_unique_tuple(
            self.evidence_bundle_ids,
            f"telemetry replay {self.replay_record_id!r} evidence_bundle_ids",
        )
        if self.notes and not self.notes.strip():
            raise ContractValueError(
                f"Telemetry replay {self.replay_record_id!r} notes must not be whitespace only."
            )

    @property
    def recorded_at(self) -> datetime:
        """Return parsed UTC replay recording time."""

        return _parse_utc_timestamp(self.recorded_at_utc, "telemetry replay recorded_at_utc")
