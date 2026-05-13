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
            freshness_status=freshness_status,
            quality_flags=quality_flags,
            replay_record_id=telemetry_input.replay_record_id,
        )
        decision = (
            TelemetryAdapterDecision.ACCEPTED
            if envelope.can_support_runtime_evaluation()
            else TelemetryAdapterDecision.DEGRADED
        )
        return TelemetryAdapterReport(
            input_id=telemetry_input.input_id,
            decision=decision,
            findings=findings,
            envelope=envelope,
        )

    def _validate_source_and_schema(
        self,
        telemetry_input: TelemetryNormalizationInput,
        source: TelemetrySource | None,
        schema: TelemetrySchema | None,
    ) -> tuple[TelemetryAdapterFinding, ...]:
        """Validate source and schema catalog references."""

        findings: list[TelemetryAdapterFinding] = []
        if source is None:
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"input-{telemetry_input.input_id}-missing-source",
                    severity=TelemetryAdapterFindingSeverity.BLOCKER,
                    message="Telemetry input references a missing source.",
                    source_id=telemetry_input.source_id,
                )
            )
        if schema is None:
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"input-{telemetry_input.input_id}-missing-schema",
                    severity=TelemetryAdapterFindingSeverity.BLOCKER,
                    message="Telemetry input references a missing schema.",
                    schema_id=telemetry_input.schema_id,
                )
            )
        if source is not None and schema is not None and not source.supports_schema(
            schema.schema_id
        ):
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"source-{source.source_id}-does-not-support-{schema.schema_id}",
                    severity=TelemetryAdapterFindingSeverity.BLOCKER,
                    message="Telemetry source is not allowed to emit the requested schema.",
                    source_id=source.source_id,
                    schema_id=schema.schema_id,
                    quality_flag=TelemetryQualityFlag.SCHEMA_MISMATCH,
                )
            )
        return tuple(findings)

    def _validate_replay_boundary(
        self,
        telemetry_input: TelemetryNormalizationInput,
        source: TelemetrySource,
    ) -> tuple[tuple[TelemetryAdapterFinding, ...], tuple[TelemetryQualityFlag, ...]]:
        """Validate replay metadata and return findings plus quality flags."""

        findings: list[TelemetryAdapterFinding] = []
        flags: list[TelemetryQualityFlag] = []
        needs_replay_record = (
            source.kind is TelemetrySourceKind.LOG_REPLAY
            or telemetry_input.replay_record_id is not None
        )
        if source.kind is TelemetrySourceKind.LOG_REPLAY:
            flags.append(TelemetryQualityFlag.REPLAY_ONLY)
        if not needs_replay_record:
            return (), ()

        if telemetry_input.replay_record_id is None:
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"source-{source.source_id}-missing-replay-record",
                    severity=TelemetryAdapterFindingSeverity.BLOCKER,
                    message="Replay telemetry source requires a replay record ID.",
                    source_id=source.source_id,
                )
            )
            return tuple(findings), tuple(flags)

        replay_record = self._catalog.replay_record_by_id(telemetry_input.replay_record_id)
        if replay_record is None:
            severity = (
                TelemetryAdapterFindingSeverity.BLOCKER
                if self._policy.require_known_replay_record
                else TelemetryAdapterFindingSeverity.WARNING
            )
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"replay-{telemetry_input.replay_record_id}-missing",
                    severity=severity,
                    message="Telemetry input references a replay record not present in catalog.",
                    source_id=source.source_id,
                    replay_record_id=telemetry_input.replay_record_id,
                    quality_flag=TelemetryQualityFlag.REPLAY_ONLY,
                )
            )
            flags.append(TelemetryQualityFlag.REPLAY_ONLY)
            return tuple(findings), tuple(flags)

        flags.append(TelemetryQualityFlag.REPLAY_ONLY)
        if replay_record.source_id != telemetry_input.source_id:
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"replay-{replay_record.replay_record_id}-source-mismatch",
                    severity=TelemetryAdapterFindingSeverity.BLOCKER,
                    message="Replay record source does not match telemetry input source.",
                    source_id=telemetry_input.source_id,
                    replay_record_id=replay_record.replay_record_id,
                )
            )
        if replay_record.schema_id != telemetry_input.schema_id:
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"replay-{replay_record.replay_record_id}-schema-mismatch",
                    severity=TelemetryAdapterFindingSeverity.BLOCKER,
                    message="Replay record schema does not match telemetry input schema.",
                    schema_id=telemetry_input.schema_id,
                    replay_record_id=replay_record.replay_record_id,
                    quality_flag=TelemetryQualityFlag.SCHEMA_MISMATCH,
                )
            )

        return tuple(findings), tuple(flags)

    def _validate_timestamp_posture(
        self,
        telemetry_input: TelemetryNormalizationInput,
    ) -> tuple[
        tuple[TelemetryAdapterFinding, ...],
        TelemetryFreshnessStatus,
        tuple[TelemetryQualityFlag, ...],
    ]:
        """Validate telemetry capture and receive timestamp posture."""

        findings: list[TelemetryAdapterFinding] = []
        flags: list[TelemetryQualityFlag] = []
        captured_at = telemetry_input.captured_at
        received_at = telemetry_input.received_at

        if captured_at > received_at:
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"input-{telemetry_input.input_id}-future-captured",
                    severity=TelemetryAdapterFindingSeverity.BLOCKER,
                    message="Telemetry captured_at_utc is after received_at_utc.",
                    quality_flag=TelemetryQualityFlag.FUTURE_TIMESTAMP,
                )
            )
            return (
                tuple(findings),
                TelemetryFreshnessStatus.FUTURE_DATED,
                (TelemetryQualityFlag.FUTURE_TIMESTAMP,),
            )

        latency_seconds = int((received_at - captured_at).total_seconds())
        if latency_seconds > self._policy.max_latency_seconds:
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"input-{telemetry_input.input_id}-stale",
                    severity=TelemetryAdapterFindingSeverity.WARNING,
                    message=(
                        "Telemetry latency exceeds adapter freshness policy and cannot "
                        "support acceptance-oriented evaluation without degradation."
                    ),
                    quality_flag=TelemetryQualityFlag.STALE_TIMESTAMP,
                )
            )
            flags.append(TelemetryQualityFlag.STALE_TIMESTAMP)
            return tuple(findings), TelemetryFreshnessStatus.STALE, tuple(flags)

        return tuple(findings), TelemetryFreshnessStatus.CURRENT, tuple(flags)

    def _validate_payload_schema(
        self,
        telemetry_input: TelemetryNormalizationInput,
        schema: TelemetrySchema,
    ) -> tuple[tuple[TelemetryAdapterFinding, ...], tuple[TelemetryQualityFlag, ...]]:
        """Validate telemetry payload against schema fields."""

        findings: list[TelemetryAdapterFinding] = []
        flags: list[TelemetryQualityFlag] = []
        for required_field_name in schema.required_field_names():
            if required_field_name not in telemetry_input.payload:
                findings.append(
                    TelemetryAdapterFinding(
                        finding_id=(
                            f"input-{telemetry_input.input_id}-missing-field-"
                            f"{required_field_name}"
                        ),
                        severity=TelemetryAdapterFindingSeverity.BLOCKER,
                        message="Telemetry payload is missing a required schema field.",
                        schema_id=schema.schema_id,
                        field_name=required_field_name,
                        quality_flag=TelemetryQualityFlag.MISSING_FIELD,
                    )
                )
                flags.append(TelemetryQualityFlag.MISSING_FIELD)

        schema_field_names = {field.field_name for field in schema.fields}
        for field_name, value in telemetry_input.payload.items():
            field = schema.field_by_name(field_name)
            if field is None:
                findings.append(
                    TelemetryAdapterFinding(
                        finding_id=f"input-{telemetry_input.input_id}-unexpected-field-{field_name}",
                        severity=TelemetryAdapterFindingSeverity.WARNING,
                        message="Telemetry payload includes a field not declared by the schema.",
                        schema_id=schema.schema_id,
                        field_name=field_name,
                    )
                )
                continue
            field_findings, field_flags = _validate_field_value(
                telemetry_input=telemetry_input,
                schema=schema,
                field=field,
                value=value,
            )
            findings.extend(field_findings)
            flags.extend(field_flags)

        if not schema_field_names:
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"schema-{schema.schema_id}-has-no-fields",
                    severity=TelemetryAdapterFindingSeverity.BLOCKER,
                    message="Telemetry schema has no fields.",
                    schema_id=schema.schema_id,
                    quality_flag=TelemetryQualityFlag.SCHEMA_MISMATCH,
                )
            )
            flags.append(TelemetryQualityFlag.SCHEMA_MISMATCH)

        return tuple(findings), tuple(flags)

    def _validate_source_trust(
        self,
        source: TelemetrySource,
    ) -> tuple[tuple[TelemetryAdapterFinding, ...], tuple[TelemetryQualityFlag, ...]]:
        """Validate telemetry source trust posture."""

        if source.can_support_acceptance():
            return (), ()

        severity = (
            TelemetryAdapterFindingSeverity.BLOCKER
            if self._policy.reject_untrusted_sources
            else TelemetryAdapterFindingSeverity.WARNING
        )
        return (
            (
                TelemetryAdapterFinding(
                    finding_id=f"source-{source.source_id}-trust-{source.trust_level.value}",
                    severity=severity,
                    message=(
                        "Telemetry source trust level cannot support acceptance-oriented "
                        "evaluation without degradation."
                    ),
                    source_id=source.source_id,
                    quality_flag=TelemetryQualityFlag.SOURCE_UNTRUSTED,
                ),
            ),
            (TelemetryQualityFlag.SOURCE_UNTRUSTED,),
        )


def _validate_field_value(
    telemetry_input: TelemetryNormalizationInput,
    schema: TelemetrySchema,
    field: TelemetrySchemaField,
    value: Any,
) -> tuple[tuple[TelemetryAdapterFinding, ...], tuple[TelemetryQualityFlag, ...]]:
    """Validate one payload field value against its schema field definition."""

    findings: list[TelemetryAdapterFinding] = []
    flags: list[TelemetryQualityFlag] = []
    if not _matches_field_type(field, value):
        findings.append(
            TelemetryAdapterFinding(
                finding_id=f"input-{telemetry_input.input_id}-field-{field.field_name}-type",
                severity=TelemetryAdapterFindingSeverity.BLOCKER,
                message=(
                    f"Telemetry field {field.field_name!r} does not match expected type "
                    f"{field.field_type.value!r}."
                ),
                schema_id=schema.schema_id,
                field_name=field.field_name,
                quality_flag=TelemetryQualityFlag.SCHEMA_MISMATCH,
            )
        )
        flags.append(TelemetryQualityFlag.SCHEMA_MISMATCH)
        return tuple(findings), tuple(flags)

    if field.field_type is TelemetryFieldType.ENUM and value not in field.allowed_values:
        findings.append(
            TelemetryAdapterFinding(
                finding_id=f"input-{telemetry_input.input_id}-field-{field.field_name}-enum",
                severity=TelemetryAdapterFindingSeverity.BLOCKER,
                message=f"Telemetry enum field {field.field_name!r} has unsupported value.",
                schema_id=schema.schema_id,
                field_name=field.field_name,
                quality_flag=TelemetryQualityFlag.SCHEMA_MISMATCH,
            )
        )
        flags.append(TelemetryQualityFlag.SCHEMA_MISMATCH)

    if field.field_type.is_numeric():
        numeric_value = float(value)
        if field.minimum_value is not None and numeric_value < field.minimum_value:
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"input-{telemetry_input.input_id}-field-{field.field_name}-below-min",
                    severity=TelemetryAdapterFindingSeverity.BLOCKER,
                    message=f"Telemetry numeric field {field.field_name!r} is below minimum.",
                    schema_id=schema.schema_id,
                    field_name=field.field_name,
                    quality_flag=TelemetryQualityFlag.OUT_OF_RANGE,
                )
            )
            flags.append(TelemetryQualityFlag.OUT_OF_RANGE)
        if field.maximum_value is not None and numeric_value > field.maximum_value:
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"input-{telemetry_input.input_id}-field-{field.field_name}-above-max",
                    severity=TelemetryAdapterFindingSeverity.BLOCKER,
                    message=f"Telemetry numeric field {field.field_name!r} is above maximum.",
                    schema_id=schema.schema_id,
                    field_name=field.field_name,
                    quality_flag=TelemetryQualityFlag.OUT_OF_RANGE,
                )
            )
            flags.append(TelemetryQualityFlag.OUT_OF_RANGE)

    if field.field_type is TelemetryFieldType.TIMESTAMP:
        try:
            _parse_utc_timestamp(str(value), f"telemetry field {field.field_name!r}")
        except ContractValueError:
            findings.append(
                TelemetryAdapterFinding(
                    finding_id=f"input-{telemetry_input.input_id}-field-{field.field_name}-timestamp",
                    severity=TelemetryAdapterFindingSeverity.BLOCKER,
                    message=f"Telemetry timestamp field {field.field_name!r} is invalid.",
                    schema_id=schema.schema_id,
                    field_name=field.field_name,
                    quality_flag=TelemetryQualityFlag.SCHEMA_MISMATCH,
                )
            )
            flags.append(TelemetryQualityFlag.SCHEMA_MISMATCH)

    return tuple(findings), tuple(flags)


def _matches_field_type(field: TelemetrySchemaField, value: Any) -> bool:
    """Return whether a payload value matches the expected telemetry field type."""

    if field.field_type is TelemetryFieldType.STRING:
        return isinstance(value, str)
    if field.field_type is TelemetryFieldType.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if field.field_type is TelemetryFieldType.FLOAT:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field.field_type is TelemetryFieldType.BOOLEAN:
        return isinstance(value, bool)
    if field.field_type is TelemetryFieldType.ENUM:
        return isinstance(value, str)
    if field.field_type is TelemetryFieldType.TIMESTAMP:
        return isinstance(value, str)
    return False


def _dedupe_quality_flags(
    quality_flags: tuple[TelemetryQualityFlag, ...],
) -> tuple[TelemetryQualityFlag, ...]:
    """Return quality flags in first-seen order without duplicates."""

    return tuple(dict.fromkeys(quality_flags))
