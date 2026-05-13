"""Monitoring, drift, incident, and revalidation domain records.

The serious prototype target needs lifecycle monitoring before it can make
credible claims about post-run oversight. These records capture monitoring
snapshots, drift findings, incident reports, and revalidation triggers while
preserving system/model/deployment links, scenario references, telemetry source
references, and evidence bundle references.

This module is local prototype infrastructure only. It does not claim live
monitoring integration, operational alerting, deployment readiness, authority to
operate, or agency acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable monitoring identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if normalized != value:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    """Validate and return nonblank monitoring text."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    return normalized


def _normalize_identifier_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    """Validate identifier tuples and reject duplicate identifiers."""

    normalized = tuple(_require_identifier(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicate identifiers.")
    return normalized


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    """Validate text tuples and reject duplicates."""

    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")
    return normalized


def _parse_utc_timestamp(value: str, field_name: str) -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC."""

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractValueError(f"{field_name} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise ContractValueError(f"{field_name} must include a timezone.")
    return parsed.astimezone(UTC)


class MonitoringSnapshotStatus(RuntimeStrEnum):
    """Lifecycle status for one monitoring snapshot."""

    CURRENT = "current"
    STALE = "stale"
    DEGRADED = "degraded"
    INVALID = "invalid"

    def supports_current_acceptance(self) -> bool:
        """Return whether the snapshot can support current acceptance claims."""

        return self is MonitoringSnapshotStatus.CURRENT

    def blocks_current_acceptance(self) -> bool:
        """Return whether the snapshot blocks current acceptance claims."""

        return self in {
            MonitoringSnapshotStatus.STALE,
            MonitoringSnapshotStatus.DEGRADED,
            MonitoringSnapshotStatus.INVALID,
        }


class DriftStatus(RuntimeStrEnum):
    """Observed drift posture for monitored autonomy behavior."""

    NONE = "none"
    WATCH = "watch"
    DEGRADED = "degraded"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """Return an ordinal drift rank where larger values are worse."""

        ranks = {
            DriftStatus.NONE: 0,
            DriftStatus.WATCH: 1,
            DriftStatus.DEGRADED: 2,
            DriftStatus.CRITICAL: 3,
        }
        return ranks[self]

    def requires_revalidation(self) -> bool:
        """Return whether drift requires revalidation before acceptance."""

        return self.rank >= DriftStatus.DEGRADED.rank


class IncidentSeverity(RuntimeStrEnum):
    """Severity for monitoring incident records."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """Return an ordinal incident severity rank."""

        ranks = {
            IncidentSeverity.LOW: 1,
            IncidentSeverity.MEDIUM: 2,
            IncidentSeverity.HIGH: 3,
            IncidentSeverity.CRITICAL: 4,
        }
        return ranks[self]

    def requires_authority_review(self) -> bool:
        """Return whether this incident severity requires authority review."""

        return self.rank >= IncidentSeverity.HIGH.rank


class IncidentState(RuntimeStrEnum):
    """Lifecycle state for monitoring incidents."""

    OPEN = "open"
    TRIAGED = "triaged"
    MITIGATED = "mitigated"
    CLOSED = "closed"

    def is_open(self) -> bool:
        """Return whether the incident is still open for review."""

        return self in {IncidentState.OPEN, IncidentState.TRIAGED}


class RevalidationTriggerSource(RuntimeStrEnum):
    """Source record type that opened a revalidation trigger."""

    MONITORING_SNAPSHOT = "monitoring_snapshot"
    DRIFT_RECORD = "drift_record"
    INCIDENT_RECORD = "incident_record"
    REVIEW_FINDING = "review_finding"


class RevalidationTriggerState(RuntimeStrEnum):
    """Lifecycle state for a revalidation trigger."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    SATISFIED = "satisfied"
    WAIVED = "waived"

    def blocks_acceptance(self) -> bool:
        """Return whether the trigger blocks current acceptance."""

        return self in {RevalidationTriggerState.OPEN, RevalidationTriggerState.IN_PROGRESS}


@dataclass(frozen=True, slots=True)
class MonitoringSnapshot:
    """Point-in-time lifecycle monitoring snapshot for a registered deployment."""

    snapshot_id: str
    system_id: str
    model_id: str
    deployment_id: str
    observed_at_utc: str
    status: MonitoringSnapshotStatus
    drift_status: DriftStatus
    confidence_score: float
    scenario_ids: tuple[str, ...]
    telemetry_source_ids: tuple[str, ...]
    evidence_bundle_ids: tuple[str, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate monitoring snapshot fields."""

        object.__setattr__(
            self,
            "snapshot_id",
            _require_identifier(self.snapshot_id, "snapshot_id"),
        )
        object.__setattr__(self, "system_id", _require_identifier(self.system_id, "system_id"))
        object.__setattr__(self, "model_id", _require_identifier(self.model_id, "model_id"))
        object.__setattr__(
            self,
            "deployment_id",
            _require_identifier(self.deployment_id, "deployment_id"),
        )
        _parse_utc_timestamp(self.observed_at_utc, "observed_at_utc")
        object.__setattr__(
            self,
            "scenario_ids",
            _normalize_identifier_tuple(self.scenario_ids, "scenario_ids"),
        )
        object.__setattr__(
            self,
            "telemetry_source_ids",
            _normalize_identifier_tuple(self.telemetry_source_ids, "telemetry_source_ids"),
        )
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        object.__setattr__(self, "notes", _normalize_text_tuple(self.notes, "notes"))
        if self.confidence_score < 0.0 or self.confidence_score > 1.0:
            raise ContractValueError("confidence_score must be between 0.0 and 1.0.")
        if not self.scenario_ids:
            raise ContractValueError("monitoring snapshots require scenario_ids.")
        if not self.telemetry_source_ids:
            raise ContractValueError("monitoring snapshots require telemetry_source_ids.")
        if not self.evidence_bundle_ids:
            raise ContractValueError("monitoring snapshots require evidence_bundle_ids.")
        if self.status.supports_current_acceptance() and self.drift_status.requires_revalidation():
            raise ContractValueError(
                "current monitoring snapshots cannot carry degraded or critical drift."
            )

    def requires_revalidation(self) -> bool:
        """Return whether the snapshot requires revalidation."""

        return self.status.blocks_current_acceptance() or self.drift_status.requires_revalidation()


@dataclass(frozen=True, slots=True)
class DriftRecord:
    """Measured drift finding tied to a monitored system/model/deployment."""

    drift_id: str
    snapshot_id: str
    system_id: str
    model_id: str
    deployment_id: str
    detected_at_utc: str
    metric_name: str
    baseline_value: float
    observed_value: float
    status: DriftStatus
    evidence_bundle_ids: tuple[str, ...]
    scenario_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate drift record fields."""

        object.__setattr__(self, "drift_id", _require_identifier(self.drift_id, "drift_id"))
        object.__setattr__(
            self,
            "snapshot_id",
            _require_identifier(self.snapshot_id, "snapshot_id"),
        )
        object.__setattr__(self, "system_id", _require_identifier(self.system_id, "system_id"))
        object.__setattr__(self, "model_id", _require_identifier(self.model_id, "model_id"))
        object.__setattr__(
            self,
            "deployment_id",
            _require_identifier(self.deployment_id, "deployment_id"),
        )
        _parse_utc_timestamp(self.detected_at_utc, "detected_at_utc")
        object.__setattr__(self, "metric_name", _require_text(self.metric_name, "metric_name"))
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        object.__setattr__(
            self,
            "scenario_ids",
            _normalize_identifier_tuple(self.scenario_ids, "scenario_ids"),
        )
        if not self.evidence_bundle_ids:
            raise ContractValueError("drift records require evidence_bundle_ids.")
        if self.status.requires_revalidation() and not self.scenario_ids:
            raise ContractValueError("degraded or critical drift records require scenario_ids.")

    @property
    def absolute_delta(self) -> float:
        """Return the absolute metric delta from baseline to observed value."""

        return abs(self.observed_value - self.baseline_value)

    def requires_revalidation(self) -> bool:
        """Return whether this drift record requires revalidation."""

        return self.status.requires_revalidation()


@dataclass(frozen=True, slots=True)
class IncidentRecord:
    """Monitoring incident tied to runtime behavior, evidence, and review scope."""

    incident_id: str
    system_id: str
    deployment_id: str
    detected_at_utc: str
    severity: IncidentSeverity
    state: IncidentState
    summary: str
    affected_scenario_ids: tuple[str, ...]
    evidence_bundle_ids: tuple[str, ...]
    hazard_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate incident record fields."""

        object.__setattr__(
            self,
            "incident_id",
            _require_identifier(self.incident_id, "incident_id"),
        )
        object.__setattr__(self, "system_id", _require_identifier(self.system_id, "system_id"))
        object.__setattr__(
            self,
            "deployment_id",
            _require_identifier(self.deployment_id, "deployment_id"),
        )
        _parse_utc_timestamp(self.detected_at_utc, "detected_at_utc")
        object.__setattr__(self, "summary", _require_text(self.summary, "summary"))
        object.__setattr__(
            self,
            "affected_scenario_ids",
            _normalize_identifier_tuple(self.affected_scenario_ids, "affected_scenario_ids"),
        )
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        object.__setattr__(
            self,
            "hazard_ids",
            _normalize_identifier_tuple(self.hazard_ids, "hazard_ids"),
        )
        if not self.affected_scenario_ids:
            raise ContractValueError("incident records require affected_scenario_ids.")
        if not self.evidence_bundle_ids:
            raise ContractValueError("incident records require evidence_bundle_ids.")
        if self.severity.requires_authority_review() and not self.hazard_ids:
            raise ContractValueError("high or critical incidents require hazard_ids.")

    def requires_authority_review(self) -> bool:
        """Return whether this incident requires authority review."""

        return self.severity.requires_authority_review() or self.state.is_open()


@dataclass(frozen=True, slots=True)
class RevalidationTrigger:
    """Trigger requiring a bounded revalidation or explicit waiver."""

    trigger_id: str
    source: RevalidationTriggerSource
    source_record_id: str
    state: RevalidationTriggerState
    created_at_utc: str
    reason: str
    requirement_ids: tuple[str, ...]
    evidence_bundle_ids: tuple[str, ...]
    hazard_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate revalidation trigger fields."""

        object.__setattr__(
            self,
            "trigger_id",
            _require_identifier(self.trigger_id, "trigger_id"),
        )
        object.__setattr__(
            self,
            "source_record_id",
            _require_identifier(self.source_record_id, "source_record_id"),
        )
        _parse_utc_timestamp(self.created_at_utc, "created_at_utc")
        object.__setattr__(self, "reason", _require_text(self.reason, "reason"))
        object.__setattr__(
            self,
            "requirement_ids",
            _normalize_identifier_tuple(self.requirement_ids, "requirement_ids"),
        )
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        object.__setattr__(
            self,
            "hazard_ids",
            _normalize_identifier_tuple(self.hazard_ids, "hazard_ids"),
        )
        if not self.requirement_ids:
            raise ContractValueError("revalidation triggers require requirement_ids.")
        if not self.evidence_bundle_ids:
            raise ContractValueError("revalidation triggers require evidence_bundle_ids.")

    def blocks_acceptance(self) -> bool:
        """Return whether this trigger blocks current acceptance."""

        return self.state.blocks_acceptance()


@dataclass(frozen=True, slots=True)
class MonitoringTrail:
    """Collection of lifecycle monitoring records for readiness validation."""

    snapshots: tuple[MonitoringSnapshot, ...] = field(default_factory=tuple)
    drift_records: tuple[DriftRecord, ...] = field(default_factory=tuple)
    incidents: tuple[IncidentRecord, ...] = field(default_factory=tuple)
    revalidation_triggers: tuple[RevalidationTrigger, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate monitoring trail record identifiers."""

        _reject_duplicate_ids(
            tuple(snapshot.snapshot_id for snapshot in self.snapshots),
            "monitoring snapshot IDs",
        )
        _reject_duplicate_ids(
            tuple(drift_record.drift_id for drift_record in self.drift_records),
            "drift record IDs",
        )
        _reject_duplicate_ids(
            tuple(incident.incident_id for incident in self.incidents),
            "incident IDs",
        )
        _reject_duplicate_ids(
            tuple(trigger.trigger_id for trigger in self.revalidation_triggers),
            "revalidation trigger IDs",
        )

    def current_snapshot_ids(self) -> tuple[str, ...]:
        """Return IDs for snapshots that support current acceptance."""

        return tuple(
            snapshot.snapshot_id
            for snapshot in self.snapshots
            if snapshot.status.supports_current_acceptance()
        )

    def open_incident_ids(self) -> tuple[str, ...]:
        """Return IDs for incidents that are still open for review."""

        return tuple(
            incident.incident_id for incident in self.incidents if incident.state.is_open()
        )

    def blocking_revalidation_trigger_ids(self) -> tuple[str, ...]:
        """Return IDs for revalidation triggers that block acceptance."""

        return tuple(
            trigger.trigger_id
            for trigger in self.revalidation_triggers
            if trigger.blocks_acceptance()
        )

    def requires_authority_review(self) -> bool:
        """Return whether any monitoring record requires authority review."""

        return any(incident.requires_authority_review() for incident in self.incidents) or any(
            trigger.blocks_acceptance() for trigger in self.revalidation_triggers
        )


def _reject_duplicate_ids(values: tuple[str, ...], field_name: str) -> None:
    """Reject duplicate identifier sequences."""

    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicates.")
