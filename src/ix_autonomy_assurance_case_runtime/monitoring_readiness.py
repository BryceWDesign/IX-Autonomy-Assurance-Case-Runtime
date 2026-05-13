"""Monitoring, drift, incident, and revalidation readiness surface.

Monitoring domain records and validation reports only support prototype maturity
when they prove current monitoring, clean evidence, closed incident posture, and
resolved revalidation triggers. This module turns that into the capability gate
for the ``monitoring-incidents`` target.

The checks are local prototype checks only. They do not claim live monitoring
integration, operational alerting, deployment readiness, authority to operate,
certification, or agency acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.monitoring import MonitoringTrail
from ix_autonomy_assurance_case_runtime.monitoring_validation import (
    MonitoringTrailValidator,
    MonitoringValidationFinding,
    MonitoringValidationFindingSeverity,
    MonitoringValidationReport,
)
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)
from ix_autonomy_assurance_case_runtime.registry_catalog import RegistryCatalog
from ix_autonomy_assurance_case_runtime.telemetry_adapter import TelemetryAdapterCatalog

MONITORING_CAPABILITY_ID = "monitoring-incidents"


class MonitoringReadinessDecision(RuntimeStrEnum):
    """Decision for whether monitoring can support prototype maturity."""

    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"

    def supports_capability_completion(self) -> bool:
        """Return whether this decision completes the monitoring capability."""

        return self is MonitoringReadinessDecision.COMPLETE

    def blocks_claim_progress(self) -> bool:
        """Return whether this decision blocks monitoring-based maturity progress."""

        return self is MonitoringReadinessDecision.BLOCKED


class MonitoringReadinessFindingSeverity(RuntimeStrEnum):
    """Severity for normalized monitoring readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_completion(self) -> bool:
        """Return whether this finding blocks monitoring capability completion."""

        return self is MonitoringReadinessFindingSeverity.BLOCKER


class MonitoringReadinessFindingSource(RuntimeStrEnum):
    """Source subsystem that produced a monitoring readiness finding."""

    VALIDATION = "validation"
    MONITORING = "monitoring"
    INCIDENT = "incident"
    REVALIDATION = "revalidation"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class MonitoringReadinessFinding:
    """One normalized monitoring readiness finding."""

    finding_id: str
    severity: MonitoringReadinessFindingSeverity
    source: MonitoringReadinessFindingSource
    message: str
    snapshot_id: str | None = None
    drift_id: str | None = None
    incident_id: str | None = None
    trigger_id: str | None = None
    deployment_id: str | None = None
    scenario_id: str | None = None
    telemetry_source_id: str | None = None
    evidence_bundle_id: str | None = None
    source_finding_id: str | None = None

    def __post_init__(self) -> None:
        """Validate monitoring readiness finding fields."""

        _require_identifier(self.finding_id, "monitoring readiness finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Monitoring readiness finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("snapshot_id", self.snapshot_id),
            ("drift_id", self.drift_id),
            ("incident_id", self.incident_id),
            ("trigger_id", self.trigger_id),
            ("deployment_id", self.deployment_id),
            ("scenario_id", self.scenario_id),
            ("telemetry_source_id", self.telemetry_source_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
            ("source_finding_id", self.source_finding_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class MonitoringLayerReadinessReport:
    """Combined readiness report for the monitoring-incidents capability layer."""

    decision: MonitoringReadinessDecision
    validation_report: MonitoringValidationReport
    findings: tuple[MonitoringReadinessFinding, ...]
    capability_id: str = MONITORING_CAPABILITY_ID

    @property
    def blocker_count(self) -> int:
        """Return normalized blocker count."""

        return sum(finding.severity.blocks_completion() for finding in self.findings)

    @property
    def warning_count(self) -> int:
        """Return normalized warning count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is MonitoringReadinessFindingSeverity.WARNING
        )

    def is_complete(self) -> bool:
        """Return whether monitoring can count as complete."""

        return self.decision.supports_capability_completion()

    def completed_capability_ids(self) -> tuple[str, ...]:
        """Return capability IDs this readiness report can honestly mark complete."""

        if not self.is_complete():
            return ()
        return (self.capability_id,)

    def prototype_readiness_report(
        self,
        requested_claim_level: PrototypeClaimLevel,
        existing_completed_capability_ids: Iterable[str] = (),
    ) -> PrototypeReadinessReport:
        """Evaluate prototype claim readiness with monitoring completion state."""

        completed = tuple(existing_completed_capability_ids) + self.completed_capability_ids()
        return PrototypeReadinessGate().evaluate(
            completed_capability_ids=completed,
            requested_claim_level=requested_claim_level,
        )

    def findings_for_snapshot(
        self,
        snapshot_id: str,
    ) -> tuple[MonitoringReadinessFinding, ...]:
        """Return findings for a monitoring snapshot."""

        return tuple(finding for finding in self.findings if finding.snapshot_id == snapshot_id)

    def findings_for_drift(self, drift_id: str) -> tuple[MonitoringReadinessFinding, ...]:
        """Return findings for a drift record."""

        return tuple(finding for finding in self.findings if finding.drift_id == drift_id)

    def findings_for_incident(
        self,
        incident_id: str,
    ) -> tuple[MonitoringReadinessFinding, ...]:
        """Return findings for an incident record."""

        return tuple(finding for finding in self.findings if finding.incident_id == incident_id)

    def findings_for_trigger(
        self,
        trigger_id: str,
    ) -> tuple[MonitoringReadinessFinding, ...]:
        """Return findings for a revalidation trigger."""

        return tuple(finding for finding in self.findings if finding.trigger_id == trigger_id)

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[MonitoringReadinessFinding, ...]:
        """Return findings for an evidence bundle."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def summary(self) -> str:
        """Return a deterministic monitoring readiness summary."""

        return (
            f"monitoring-readiness: {self.decision.value} "
            f"({self.validation_report.snapshot_count} snapshot(s), "
            f"{self.validation_report.drift_count} drift record(s), "
            f"{self.validation_report.incident_count} incident(s), "
            f"{self.validation_report.trigger_count} trigger(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"capability={self.capability_id})"
        )


class MonitoringLayerReadinessEvaluator:
    """Evaluate whether monitoring can count toward prototype maturity."""

    def __init__(
        self,
        registry_catalog: RegistryCatalog,
        telemetry_catalog: TelemetryAdapterCatalog,
        evidence_bundles: Iterable[EvidenceBundle] = (),
    ) -> None:
        """Create a monitoring readiness evaluator."""

        self._validator = MonitoringTrailValidator(
            registry_catalog=registry_catalog,
            telemetry_catalog=telemetry_catalog,
            evidence_bundles=evidence_bundles,
        )

    def evaluate(self, trail: MonitoringTrail) -> MonitoringLayerReadinessReport:
        """Evaluate monitoring validation and lifecycle readiness as one surface."""

        validation_report = self._validator.validate(trail)
        findings = (
            self._build_readiness_findings(trail)
            + self._normalize_validation_findings(validation_report.findings)
        )
        return MonitoringLayerReadinessReport(
            decision=self._decide(findings),
            validation_report=validation_report,
            findings=findings,
        )

    @staticmethod
    def _build_readiness_findings(
        trail: MonitoringTrail,
    ) -> tuple[MonitoringReadinessFinding, ...]:
        """Build readiness findings not emitted directly by validation."""

        findings: list[MonitoringReadinessFinding] = []
        if not trail.current_snapshot_ids():
            findings.append(
                MonitoringReadinessFinding(
                    finding_id="monitoring-readiness-no-current-snapshot",
                    severity=MonitoringReadinessFindingSeverity.BLOCKER,
                    source=MonitoringReadinessFindingSource.READINESS,
                    message="Monitoring readiness requires at least one current snapshot.",
                )
            )

        for snapshot in trail.snapshots:
            if snapshot.requires_revalidation():
                findings.append(
                    MonitoringReadinessFinding(
                        finding_id=f"snapshot-{snapshot.snapshot_id}-requires-revalidation",
                        severity=MonitoringReadinessFindingSeverity.BLOCKER,
                        source=MonitoringReadinessFindingSource.MONITORING,
                        message=(
                            "Monitoring snapshot requires revalidation before the monitoring "
                            "capability can be counted complete."
                        ),
                        snapshot_id=snapshot.snapshot_id,
                    )
                )

        for incident in trail.incidents:
            if incident.state.is_open():
                findings.append(
                    MonitoringReadinessFinding(
                        finding_id=f"incident-{incident.incident_id}-open",
                        severity=MonitoringReadinessFindingSeverity.BLOCKER,
                        source=MonitoringReadinessFindingSource.INCIDENT,
                        message="Open or triaged monitoring incidents block capability completion.",
                        incident_id=incident.incident_id,
                        deployment_id=incident.deployment_id,
                    )
                )

        for trigger in trail.revalidation_triggers:
            if trigger.blocks_acceptance():
                findings.append(
                    MonitoringReadinessFinding(
                        finding_id=f"trigger-{trigger.trigger_id}-blocks-acceptance",
                        severity=MonitoringReadinessFindingSeverity.BLOCKER,
                        source=MonitoringReadinessFindingSource.REVALIDATION,
                        message=(
                            "Open or in-progress revalidation triggers block monitoring "
                            "capability completion."
                        ),
                        trigger_id=trigger.trigger_id,
                    )
                )

        if not trail.drift_records:
            findings.append(
                MonitoringReadinessFinding(
                    finding_id="monitoring-readiness-no-drift-record-history",
                    severity=MonitoringReadinessFindingSeverity.WARNING,
                    source=MonitoringReadinessFindingSource.READINESS,
                    message=(
                        "Monitoring readiness is stronger when the trail includes drift-record "
                        "history, even if no drift was observed."
                    ),
                )
            )

        return tuple(findings)

    @staticmethod
    def _normalize_validation_findings(
        findings: tuple[MonitoringValidationFinding, ...],
    ) -> tuple[MonitoringReadinessFinding, ...]:
        """Normalize monitoring validation findings into readiness findings."""

        return tuple(
            MonitoringReadinessFinding(
                finding_id=f"validation-{finding.finding_id}",
                severity=_map_validation_severity(finding.severity),
                source=MonitoringReadinessFindingSource.VALIDATION,
                message=finding.message,
                snapshot_id=finding.snapshot_id,
                drift_id=finding.drift_id,
                incident_id=finding.incident_id,
                trigger_id=finding.trigger_id,
                deployment_id=finding.deployment_id,
                scenario_id=finding.scenario_id,
                telemetry_source_id=finding.telemetry_source_id,
                evidence_bundle_id=finding.evidence_bundle_id,
                source_finding_id=finding.finding_id,
            )
            for finding in findings
        )

    @staticmethod
    def _decide(
        findings: tuple[MonitoringReadinessFinding, ...],
    ) -> MonitoringReadinessDecision:
        """Return the combined monitoring readiness decision."""

        if any(finding.severity.blocks_completion() for finding in findings):
            return MonitoringReadinessDecision.BLOCKED
        if any(
            finding.severity is MonitoringReadinessFindingSeverity.WARNING
            for finding in findings
        ):
            return MonitoringReadinessDecision.LIMITED
        return MonitoringReadinessDecision.COMPLETE


def _map_validation_severity(
    severity: MonitoringValidationFindingSeverity,
) -> MonitoringReadinessFindingSeverity:
    """Map monitoring validation severity to readiness severity."""

    if severity is MonitoringValidationFindingSeverity.BLOCKER:
        return MonitoringReadinessFindingSeverity.BLOCKER
    if severity is MonitoringValidationFindingSeverity.WARNING:
        return MonitoringReadinessFindingSeverity.WARNING
    return MonitoringReadinessFindingSeverity.INFO


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable monitoring readiness identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")
