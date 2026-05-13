"""Telemetry adapter normalization and validation engine.

Telemetry records define sources, schemas, envelopes, and replay metadata. This
module turns raw telemetry input into normalized telemetry envelopes while
preserving source trust, schema validation, timestamp posture, quality flags, and
replay boundaries.

The adapter is deterministic and local. It does not claim live sensor
integration, classified feed handling, external time authority, or operational
deployment readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.telemetry import (
    TelemetryEnvelope,
    TelemetryFieldType,
    TelemetryFreshnessStatus,
    TelemetryQualityFlag,
    TelemetryReplayRecord,
    TelemetrySchema,
    TelemetrySchemaField,
    TelemetrySource,
    TelemetrySourceKind,
    TelemetryTrustLevel,
)


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable telemetry adapter identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")


def _require_text(value: str, field_name: str) -> None:
    """Validate nonblank telemetry adapter text."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")


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


class TelemetryAdapterDecision(RuntimeStrEnum):
    """Decision emitted by the telemetry adapter."""

    ACCEPTED = "accepted"
    DEGRADED = "degraded"
    REJECTED = "rejected"

    def produced_envelope(self) -> bool:
        """Return whether this decision should include a normalized envelope."""

        return self in {
            TelemetryAdapterDecision.ACCEPTED,
            TelemetryAdapterDecision.DEGRADED,
        }

    def blocks_runtime_evaluation(self) -> bool:
        """Return whether this decision blocks runtime evaluation."""

        return self is TelemetryAdapterDecision.REJECTED


class TelemetryAdapterFindingSeverity(RuntimeStrEnum):
    """Severity for telemetry adapter findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_normalization(self) -> bool:
        """Return whether this finding blocks envelope normalization."""

        return self is TelemetryAdapterFindingSeverity.BLOCKER


@dataclass(frozen=True, slots=True)
class TelemetryAdapterPolicy:
    """Local normalization policy for telemetry adapter decisions."""

    max_latency_seconds: int = 300
    require_known_replay_record: bool = True
    reject_untrusted_sources: bool = False

    def __post_init__(self) -> None:
        """Validate adapter policy settings."""

        if self.max_latency_seconds <= 0:
            raise ContractValueError("Telemetry adapter max_latency_seconds must be positive.")


@dataclass(frozen=True, slots=True)
class TelemetryNormalizationInput:
    """Raw telemetry input supplied to the adapter."""

    input_id: str
    source_id: str
    schema_id: str
    captured_at_utc: str
    received_at_utc: str
    payload: dict[str, Any]
    replay_record_id: str | None = None

    def __post_init__(self) -> None:
        """Validate raw telemetry normalization input."""

        _require_identifier(self.input_id, "telemetry input_id")
        _require_identifier(self.source_id, "telemetry input source_id")
        _require_identifier(self.schema_id, "telemetry input schema_id")
        _parse_utc_timestamp(self.captured_at_utc, "telemetry input captured_at_utc")
        _parse_utc_timestamp(self.received_at_utc, "telemetry input received_at_utc")
        for field_name in self.payload:
            if not isinstance(field_name, str) or not field_name.strip():
                raise ContractValueError(
                    f"Telemetry input {self.input_id!r} payload field names must be nonblank "
                    "strings."
                )
        if self.replay_record_id is not None:
            _require_identifier(self.replay_record_id, "telemetry input replay_record_id")

    @property
    def captured_at(self) -> datetime:
        """Return parsed UTC capture time."""

        return _parse_utc_timestamp(self.captured_at_utc, "telemetry input captured_at_utc")

    @property
    def received_at(self) -> datetime:
        """Return parsed UTC receive time."""

        return _parse_utc_timestamp(self.received_at_utc, "telemetry input received_at_utc")


@dataclass(frozen=True, slots=True)
class TelemetryAdapterFinding:
    """One normalization, trust, schema, timestamp, or replay finding."""

    finding_id: str
    severity: TelemetryAdapterFindingSeverity
    message: str
    source_id: str | None = None
    schema_id: str | None = None
    field_name: str | None = None
    replay_record_id: str | None = None
    quality_flag: TelemetryQualityFlag | None = None

    def __post_init__(self) -> None:
        """Validate telemetry adapter finding records."""

        if not self.finding_id.strip():
            raise ContractValueError("Telemetry adapter finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Telemetry adapter finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Telemetry adapter finding {self.finding_id!r} needs a message."
            )
        if self.source_id is not None and not self.source_id.strip():
            raise ContractValueError(
                f"Telemetry adapter finding {self.finding_id!r} has a blank source ID."
            )
        if self.schema_id is not None and not self.schema_id.strip():
            raise ContractValueError(
                f"Telemetry adapter finding {self.finding_id!r} has a blank schema ID."
            )
        if self.field_name is not None and not self.field_name.strip():
            raise ContractValueError(
                f"Telemetry adapter finding {self.finding_id!r} has a blank field name."
            )
        if self.replay_record_id is not None and not self.replay_record_id.strip():
            raise ContractValueError(
                f"Telemetry adapter finding {self.finding_id!r} has a blank replay record ID."
            )


@dataclass(frozen=True, slots=True)
class TelemetryAdapterReport:
    """Telemetry adapter decision report."""

    input_id: str
    decision: TelemetryAdapterDecision
    findings: tuple[TelemetryAdapterFinding, ...]
    envelope: TelemetryEnvelope | None = None

    @property
    def blocker_count(self) -> int:
        """Return blocker finding count."""

        return sum(1 for finding in self.findings if finding.severity.blocks_normalization())

    @property
    def warning_count(self) -> int:
        """Return warning finding count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is TelemetryAdapterFindingSeverity.WARNING
        )

    def has_envelope(self) -> bool:
        """Return whether normalization produced an envelope."""

        return self.envelope is not None

    def can_support_runtime_evaluation(self) -> bool:
        """Return whether the report can support runtime evaluation."""

        return (
            self.decision is TelemetryAdapterDecision.ACCEPTED
            and self.envelope is not None
            and self.envelope.can_support_runtime_evaluation()
        )

    def findings_for_field(self, field_name: str) -> tuple[TelemetryAdapterFinding, ...]:
        """Return adapter findings for one payload field."""

        return tuple(finding for finding in self.findings if finding.field_name == field_name)

    def summary(self) -> str:
        """Return a deterministic adapter summary."""

        envelope_state = "envelope" if self.envelope is not None else "no-envelope"
        return (
            f"telemetry-adapter: {self.decision.value} "
            f"({envelope_state}, {self.blocker_count} blocker(s), "
            f"{self.warning_count} warning(s))"
        )


@dataclass(frozen=True, slots=True)
class TelemetryAdapterCatalog:
    """Local catalog of telemetry sources, schemas, and replay records."""

    sources: tuple[TelemetrySource, ...]
    schemas: tuple[TelemetrySchema, ...]
    replay_records: tuple[TelemetryReplayRecord, ...] = ()

    def __post_init__(self) -> None:
        """Validate duplicate catalog records."""

        self._index_sources()
        self._index_schemas()
        self._index_replay_records()

    def source_by_id(self, source_id: str) -> TelemetrySource | None:
        """Return a telemetry source by ID."""

        return self._index_sources().get(source_id)

    def schema_by_id(self, schema_id: str) -> TelemetrySchema | None:
        """Return a telemetry schema by ID."""

        return self._index_schemas().get(schema_id)

    def replay_record_by_id(self, replay_record_id: str) -> TelemetryReplayRecord | None:
        """Return a replay record by ID."""

        return self._index_replay_records().get(replay_record_id)

    def _index_sources(self) -> dict[str, TelemetrySource]:
        """Index telemetry sources by source ID."""

        indexed: dict[str, TelemetrySource] = {}
        for source in self.sources:
            if source.source_id in indexed:
                raise ContractValueError(
                    f"Duplicate telemetry source ID {source.source_id!r}."
                )
            indexed[source.source_id] = source
        return indexed

    def _index_schemas(self) -> dict[str, TelemetrySchema]:
        """Index telemetry schemas by schema ID."""

        indexed: dict[str, TelemetrySchema] = {}
        for schema in self.schemas:
            if schema.schema_id in indexed:
                raise ContractValueError(
                    f"Duplicate telemetry schema ID {schema.schema_id!r}."
                )
            indexed[schema.schema_id] = schema
        return indexed

    def _index_replay_records(self) -> dict[str, TelemetryReplayRecord]:
        """Index telemetry replay records by replay record ID."""

        indexed: dict[str, TelemetryReplayRecord] = {}
        for replay_record in self.replay_records:
            if replay_record.replay_record_id in indexed:
                raise ContractValueError(
                    f"Duplicate telemetry replay record ID {replay_record.replay_record_id!r}."
                )
            indexed[replay_record.replay_record_id] = replay_record
        return indexed


class TelemetryAdapter:
    """Normalize raw telemetry inputs into bounded telemetry envelopes."""

    def __init__(
        self,
        catalog: TelemetryAdapterCatalog,
        policy: TelemetryAdapterPolicy | None = None,
    ) -> None:
        """Create a telemetry adapter."""

        self._catalog = catalog
        self._policy = policy or TelemetryAdapterPolicy()

    def normalize(self, telemetry_input: TelemetryNormalizationInput) -> TelemetryAdapterReport:
        """Normalize raw telemetry input into an envelope or rejected report."""

        source = self._catalog.source_by_id(telemetry_input.source_id)
        schema = self._catalog.schema_by_id(telemetry_input.schema_id)
        preflight_findings = self._validate_source_and_schema(telemetry_input, source, schema)

        if source is None or schema is None:
            return TelemetryAdapterReport(
                input_id=telemetry_input.input_id,
                decision=TelemetryAdapterDecision.REJECTED,
                findings=preflight_findings,
            )

        replay_findings, replay_flags = self._validate_replay_boundary(
            telemetry_input=telemetry_input,
            source=source,
        )
        timestamp_findings, freshness_status, timestamp_flags = self._validate_timestamp_posture(
            telemetry_input
        )
        schema_findings, schema_flags = self._validate_payload_schema(
            telemetry_input=telemetry_input,
            schema=schema,
        )
        trust_findings, trust_flags = self._validate_source_trust(source)

        findings = (
            preflight_findings
            + replay_findings
            + timestamp_findings
            + schema_findings
            + trust_findings
        )
        if any(finding.severity.blocks_normalization() for finding in findings):
            return TelemetryAdapterReport(
                input_id=telemetry_input.input_id,
                decision=TelemetryAdapterDecision.REJECTED,
                findings=findings,
            )

        quality_flags = _dedupe_quality_flags(
            replay_flags + timestamp_flags + schema_flags + trust_flags
        )
        envelope = TelemetryEnvelope(
            envelope_id=f"envelope-{telemetry_input.input_id}",
            source_id=telemetry_input.source_id,
            schema_id=telemetry_input.schema_id,
            captured_at_utc=telemetry_input.captured_at_utc,
            received_at_utc=telemetry_input.received_at_utc,
            payload=telemetry_input.payload,
