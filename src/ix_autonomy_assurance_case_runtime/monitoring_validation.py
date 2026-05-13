"""Monitoring trail validation against registry, telemetry, and evidence records.

Monitoring domain records describe snapshots, drift, incidents, and revalidation
triggers. This validator checks whether those lifecycle records are grounded in
local registry assets, telemetry sources, scenario links, evidence bundles, and
source-record relationships before later commits count monitoring as a maturity
capability.

The checks are local prototype checks only. They do not claim live monitoring,
operational alerting, deployment readiness, authority to operate, or agency
acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.monitoring import (
    IncidentRecord,
    MonitoringSnapshot,
    MonitoringTrail,
    RevalidationTrigger,
    RevalidationTriggerSource,
)
from ix_autonomy_assurance_case_runtime.registry import RegisteredDeployment
from ix_autonomy_assurance_case_runtime.registry_catalog import RegistryCatalog
from ix_autonomy_assurance_case_runtime.telemetry_adapter import TelemetryAdapterCatalog


class MonitoringValidationFindingSeverity(RuntimeStrEnum):
    """Severity for monitoring validation findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_monitoring_readiness(self) -> bool:
        """Return whether this finding blocks monitoring readiness."""

        return self is MonitoringValidationFindingSeverity.BLOCKER


class MonitoringValidationFindingSource(RuntimeStrEnum):
    """Subsystem that produced a monitoring validation finding."""

    MONITORING = "monitoring"
    REGISTRY = "registry"
    TELEMETRY = "telemetry"
    EVIDENCE = "evidence"
    REVALIDATION = "revalidation"


@dataclass(frozen=True, slots=True)
class MonitoringValidationFinding:
    """One monitoring validation finding."""

    finding_id: str
    severity: MonitoringValidationFindingSeverity
    source: MonitoringValidationFindingSource
    message: str
    snapshot_id: str | None = None
    drift_id: str | None = None
    incident_id: str | None = None
    trigger_id: str | None = None
    system_id: str | None = None
    model_id: str | None = None
    deployment_id: str | None = None
    scenario_id: str | None = None
    telemetry_source_id: str | None = None
    evidence_bundle_id: str | None = None

    def __post_init__(self) -> None:
        """Validate monitoring validation finding fields."""

        _require_identifier(self.finding_id, "monitoring validation finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Monitoring validation finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("snapshot_id", self.snapshot_id),
            ("drift_id", self.drift_id),
            ("incident_id", self.incident_id),
            ("trigger_id", self.trigger_id),
            ("system_id", self.system_id),
            ("model_id", self.model_id),
            ("deployment_id", self.deployment_id),
            ("scenario_id", self.scenario_id),
            ("telemetry_source_id", self.telemetry_source_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class MonitoringValidationReport:
    """Validation report for a monitoring trail."""

    snapshot_count: int
    drift_count: int
    incident_count: int
    trigger_count: int
    findings: tuple[MonitoringValidationFinding, ...]

    def __post_init__(self) -> None:
        """Validate monitoring validation report counters."""

        for field_name, value in (
            ("snapshot_count", self.snapshot_count),
            ("drift_count", self.drift_count),
            ("incident_count", self.incident_count),
            ("trigger_count", self.trigger_count),
        ):
            if value < 0:
                raise ContractValueError(f"{field_name} must not be negative.")

    @property
    def blocker_count(self) -> int:
        """Return blocker finding count."""

        return sum(
            finding.severity.blocks_monitoring_readiness() for finding in self.findings
        )

    @property
    def warning_count(self) -> int:
        """Return warning finding count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is MonitoringValidationFindingSeverity.WARNING
        )

    def is_monitoring_ready(self) -> bool:
        """Return whether monitoring validation has no blockers."""

        return self.blocker_count == 0

    def findings_for_snapshot(
        self,
        snapshot_id: str,
    ) -> tuple[MonitoringValidationFinding, ...]:
        """Return findings for a monitoring snapshot."""

        return tuple(finding for finding in self.findings if finding.snapshot_id == snapshot_id)

    def findings_for_drift(self, drift_id: str) -> tuple[MonitoringValidationFinding, ...]:
        """Return findings for a drift record."""

        return tuple(finding for finding in self.findings if finding.drift_id == drift_id)

    def findings_for_incident(
        self,
        incident_id: str,
    ) -> tuple[MonitoringValidationFinding, ...]:
        """Return findings for an incident record."""

        return tuple(finding for finding in self.findings if finding.incident_id == incident_id)

    def findings_for_trigger(
        self,
        trigger_id: str,
    ) -> tuple[MonitoringValidationFinding, ...]:
        """Return findings for a revalidation trigger."""

        return tuple(finding for finding in self.findings if finding.trigger_id == trigger_id)

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[MonitoringValidationFinding, ...]:
        """Return findings for an evidence bundle."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def findings_for_telemetry_source(
        self,
        telemetry_source_id: str,
    ) -> tuple[MonitoringValidationFinding, ...]:
        """Return findings for a telemetry source."""

        return tuple(
            finding
            for finding in self.findings
            if finding.telemetry_source_id == telemetry_source_id
        )

    def summary(self) -> str:
        """Return a deterministic monitoring validation summary."""

        return (
            "monitoring-validation: "
            f"{self.snapshot_count} snapshot(s), {self.drift_count} drift record(s), "
            f"{self.incident_count} incident(s), {self.trigger_count} trigger(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s)"
        )


class MonitoringTrailValidator:
    """Validate a monitoring trail against local catalogs and evidence."""

    def __init__(
        self,
        registry_catalog: RegistryCatalog,
        telemetry_catalog: TelemetryAdapterCatalog,
        evidence_bundles: Iterable[EvidenceBundle] = (),
    ) -> None:
        """Create a monitoring trail validator."""

        self._registry_catalog = registry_catalog
        self._telemetry_catalog = telemetry_catalog
        self._bundle_by_id = self._index_evidence_bundles(evidence_bundles)

    def validate(self, trail: MonitoringTrail) -> MonitoringValidationReport:
        """Validate a monitoring trail."""

        findings = (
            self._validate_minimum_monitoring_posture(trail)
            + self._validate_snapshots(trail.snapshots)
            + self._validate_drift_records(trail)
            + self._validate_incidents(trail.incidents)
            + self._validate_revalidation_triggers(trail)
            + self._validate_evidence(trail)
        )
        return MonitoringValidationReport(
            snapshot_count=len(trail.snapshots),
            drift_count=len(trail.drift_records),
            incident_count=len(trail.incidents),
            trigger_count=len(trail.revalidation_triggers),
            findings=findings,
        )

    @staticmethod
    def _index_evidence_bundles(
        bundles: Iterable[EvidenceBundle],
    ) -> dict[str, EvidenceBundle]:
        """Index evidence bundles and reject duplicate bundle IDs."""

        indexed: dict[str, EvidenceBundle] = {}
        for bundle in bundles:
            if bundle.bundle_id in indexed:
                raise ContractValueError(
                    f"Duplicate monitoring evidence bundle ID {bundle.bundle_id!r}."
                )
            indexed[bundle.bundle_id] = bundle
        return indexed

    @staticmethod
    def _validate_minimum_monitoring_posture(
        trail: MonitoringTrail,
    ) -> tuple[MonitoringValidationFinding, ...]:
        """Validate the minimum useful monitoring posture."""

        findings: list[MonitoringValidationFinding] = []
        if not trail.snapshots:
            findings.append(
                MonitoringValidationFinding(
                    finding_id="monitoring-trail-no-snapshots",
                    severity=MonitoringValidationFindingSeverity.BLOCKER,
                    source=MonitoringValidationFindingSource.MONITORING,
                    message="Monitoring validation requires at least one snapshot.",
                )
            )
        if trail.snapshots and not trail.current_snapshot_ids():
            findings.append(
                MonitoringValidationFinding(
                    finding_id="monitoring-trail-no-current-snapshot",
                    severity=MonitoringValidationFindingSeverity.BLOCKER,
                    source=MonitoringValidationFindingSource.MONITORING,
                    message="Monitoring validation requires at least one current snapshot.",
                )
            )
        if not trail.revalidation_triggers:
            findings.append(
                MonitoringValidationFinding(
                    finding_id="monitoring-trail-no-revalidation-trigger-history",
                    severity=MonitoringValidationFindingSeverity.WARNING,
                    source=MonitoringValidationFindingSource.REVALIDATION,
                    message=(
                        "Monitoring trail has no revalidation-trigger history; this limits "
                        "lifecycle oversight evidence."
                    ),
                )
            )
        return tuple(findings)

    def _validate_snapshots(
        self,
        snapshots: tuple[MonitoringSnapshot, ...],
    ) -> tuple[MonitoringValidationFinding, ...]:
        """Validate monitoring snapshots against registry and telemetry catalogs."""

        findings: list[MonitoringValidationFinding] = []
        telemetry_source_ids = {source.source_id for source in self._telemetry_catalog.sources}
        for snapshot in snapshots:
            findings.extend(self._validate_registry_links_for_snapshot(snapshot))
            for telemetry_source_id in snapshot.telemetry_source_ids:
                if telemetry_source_id not in telemetry_source_ids:
                    findings.append(
                        MonitoringValidationFinding(
                            finding_id=(
                                f"snapshot-{snapshot.snapshot_id}-missing-telemetry-"
                                f"{telemetry_source_id}"
                            ),
                            severity=MonitoringValidationFindingSeverity.BLOCKER,
                            source=MonitoringValidationFindingSource.TELEMETRY,
                            message="Monitoring snapshot references a missing telemetry source.",
                            snapshot_id=snapshot.snapshot_id,
                            telemetry_source_id=telemetry_source_id,
                        )
                    )
            if snapshot.requires_revalidation():
                findings.append(
                    MonitoringValidationFinding(
                        finding_id=f"snapshot-{snapshot.snapshot_id}-requires-revalidation",
                        severity=MonitoringValidationFindingSeverity.BLOCKER,
                        source=MonitoringValidationFindingSource.MONITORING,
                        message="Monitoring snapshot requires revalidation before acceptance.",
                        snapshot_id=snapshot.snapshot_id,
                    )
                )
        return tuple(findings)

    def _validate_registry_links_for_snapshot(
        self,
        snapshot: MonitoringSnapshot,
    ) -> tuple[MonitoringValidationFinding, ...]:
        """Validate registry links for one snapshot."""

        findings: list[MonitoringValidationFinding] = []
        system = self._registry_catalog.system_by_id(snapshot.system_id)
        model = self._registry_catalog.model_by_id(snapshot.model_id)
        deployment = self._registry_catalog.deployment_by_id(snapshot.deployment_id)
        if system is None:
            findings.append(
                MonitoringValidationFinding(
                    finding_id=f"snapshot-{snapshot.snapshot_id}-missing-system",
                    severity=MonitoringValidationFindingSeverity.BLOCKER,
                    source=MonitoringValidationFindingSource.REGISTRY,
                    message="Monitoring snapshot references a missing registered system.",
                    snapshot_id=snapshot.snapshot_id,
                    system_id=snapshot.system_id,
                )
            )
        elif snapshot.model_id not in system.model_ids:
            findings.append(
                MonitoringValidationFinding(
                    finding_id=f"snapshot-{snapshot.snapshot_id}-model-not-on-system",
                    severity=MonitoringValidationFindingSeverity.BLOCKER,
                    source=MonitoringValidationFindingSource.REGISTRY,
                    message="Monitoring snapshot model is not registered on the system.",
                    snapshot_id=snapshot.snapshot_id,
                    system_id=snapshot.system_id,
                    model_id=snapshot.model_id,
                )
            )
        if model is None:
            findings.append(
                MonitoringValidationFinding(
                    finding_id=f"snapshot-{snapshot.snapshot_id}-missing-model",
                    severity=MonitoringValidationFindingSeverity.BLOCKER,
                    source=MonitoringValidationFindingSource.REGISTRY,
                    message="Monitoring snapshot references a missing registered model.",
                    snapshot_id=snapshot.snapshot_id,
                    model_id=snapshot.model_id,
                )
            )
        if deployment is None:
            findings.append(
                MonitoringValidationFinding(
                    finding_id=f"snapshot-{snapshot.snapshot_id}-missing-deployment",
                    severity=MonitoringValidationFindingSeverity.BLOCKER,
                    source=MonitoringValidationFindingSource.REGISTRY,
                    message="Monitoring snapshot references a missing registered deployment.",
                    snapshot_id=snapshot.snapshot_id,
                    deployment_id=snapshot.deployment_id,
                )
            )
            return tuple(findings)
        if deployment.system_id != snapshot.system_id:
            findings.append(
                MonitoringValidationFinding(
                    finding_id=f"snapshot-{snapshot.snapshot_id}-deployment-system-mismatch",
                    severity=MonitoringValidationFindingSeverity.BLOCKER,
                    source=MonitoringValidationFindingSource.REGISTRY,
                    message="Monitoring snapshot deployment belongs to a different system.",
                    snapshot_id=snapshot.snapshot_id,
                    system_id=snapshot.system_id,
                    deployment_id=snapshot.deployment_id,
                )
            )
        findings.extend(_missing_membership_findings_for_snapshot(snapshot, deployment))
        return tuple(findings)

    def _validate_drift_records(
        self,
        trail: MonitoringTrail,
    ) -> tuple[MonitoringValidationFinding, ...]:
        """Validate drift records against snapshots and registry links."""

        findings: list[MonitoringValidationFinding] = []
        snapshot_by_id = {snapshot.snapshot_id: snapshot for snapshot in trail.snapshots}
        for drift_record in trail.drift_records:
            snapshot = snapshot_by_id.get(drift_record.snapshot_id)
            if snapshot is None:
                findings.append(
                    MonitoringValidationFinding(
                        finding_id=f"drift-{drift_record.drift_id}-missing-snapshot",
                        severity=MonitoringValidationFindingSeverity.BLOCKER,
                        source=MonitoringValidationFindingSource.MONITORING,
                        message="Drift record references a missing monitoring snapshot.",
                        drift_id=drift_record.drift_id,
                        snapshot_id=drift_record.snapshot_id,
                    )
                )
                continue
            if (
                drift_record.system_id != snapshot.system_id
                or drift_record.model_id != snapshot.model_id
                or drift_record.deployment_id != snapshot.deployment_id
            ):
                findings.append(
                    MonitoringValidationFinding(
                        finding_id=f"drift-{drift_record.drift_id}-asset-mismatch",
                        severity=MonitoringValidationFindingSeverity.BLOCKER,
                        source=MonitoringValidationFindingSource.MONITORING,
                        message="Drift record asset links do not match its monitoring snapshot.",
                        snapshot_id=snapshot.snapshot_id,
                        drift_id=drift_record.drift_id,
                        system_id=drift_record.system_id,
                        model_id=drift_record.model_id,
                        deployment_id=drift_record.deployment_id,
                    )
                )
            for scenario_id in drift_record.scenario_ids:
                if scenario_id not in snapshot.scenario_ids:
                    findings.append(
                        MonitoringValidationFinding(
                            finding_id=(
                                f"drift-{drift_record.drift_id}-scenario-{scenario_id}-"
                                "not-in-snapshot"
                            ),
                            severity=MonitoringValidationFindingSeverity.BLOCKER,
                            source=MonitoringValidationFindingSource.MONITORING,
                            message="Drift scenario is not represented by its snapshot.",
                            snapshot_id=snapshot.snapshot_id,
                            drift_id=drift_record.drift_id,
                            scenario_id=scenario_id,
                        )
                    )
        return tuple(findings)

    def _validate_incidents(
        self,
        incidents: tuple[IncidentRecord, ...],
    ) -> tuple[MonitoringValidationFinding, ...]:
        """Validate incident registry links."""

        findings: list[MonitoringValidationFinding] = []
        for incident in incidents:
            system = self._registry_catalog.system_by_id(incident.system_id)
            deployment = self._registry_catalog.deployment_by_id(incident.deployment_id)
            if system is None:
                findings.append(
                    MonitoringValidationFinding(
                        finding_id=f"incident-{incident.incident_id}-missing-system",
                        severity=MonitoringValidationFindingSeverity.BLOCKER,
                        source=MonitoringValidationFindingSource.REGISTRY,
                        message="Incident references a missing registered system.",
                        incident_id=incident.incident_id,
                        system_id=incident.system_id,
                    )
                )
            if deployment is None:
                findings.append(
                    MonitoringValidationFinding(
                        finding_id=f"incident-{incident.incident_id}-missing-deployment",
                        severity=MonitoringValidationFindingSeverity.BLOCKER,
                        source=MonitoringValidationFindingSource.REGISTRY,
                        message="Incident references a missing registered deployment.",
                        incident_id=incident.incident_id,
                        deployment_id=incident.deployment_id,
                    )
                )
                continue
            if deployment.system_id != incident.system_id:
                findings.append(
                    MonitoringValidationFinding(
                        finding_id=f"incident-{incident.incident_id}-deployment-system-mismatch",
                        severity=MonitoringValidationFindingSeverity.BLOCKER,
                        source=MonitoringValidationFindingSource.REGISTRY,
                        message="Incident deployment belongs to a different registered system.",
                        incident_id=incident.incident_id,
                        system_id=incident.system_id,
                        deployment_id=incident.deployment_id,
                    )
                )
            for scenario_id in incident.affected_scenario_ids:
                if scenario_id not in deployment.scenario_ids:
                    findings.append(
                        MonitoringValidationFinding(
                            finding_id=(
                                f"incident-{incident.incident_id}-scenario-{scenario_id}-"
                                "not-in-deployment"
                            ),
                            severity=MonitoringValidationFindingSeverity.BLOCKER,
                            source=MonitoringValidationFindingSource.REGISTRY,
                            message="Incident scenario is not registered on the deployment.",
                            incident_id=incident.incident_id,
                            deployment_id=incident.deployment_id,
                            scenario_id=scenario_id,
                        )
                    )
        return tuple(findings)

    @staticmethod
    def _validate_revalidation_triggers(
        trail: MonitoringTrail,
    ) -> tuple[MonitoringValidationFinding, ...]:
        """Validate trigger source references and blocking posture."""

        findings: list[MonitoringValidationFinding] = []
        snapshot_ids = {snapshot.snapshot_id for snapshot in trail.snapshots}
        drift_ids = {drift_record.drift_id for drift_record in trail.drift_records}
        incident_ids = {incident.incident_id for incident in trail.incidents}
        for trigger in trail.revalidation_triggers:
            if not _trigger_source_exists(
                trigger=trigger,
                snapshot_ids=snapshot_ids,
                drift_ids=drift_ids,
                incident_ids=incident_ids,
            ):
                findings.append(
                    MonitoringValidationFinding(
                        finding_id=f"trigger-{trigger.trigger_id}-missing-source-record",
                        severity=MonitoringValidationFindingSeverity.BLOCKER,
                        source=MonitoringValidationFindingSource.REVALIDATION,
                        message="Revalidation trigger references a missing source record.",
                        trigger_id=trigger.trigger_id,
                    )
                )
            if trigger.blocks_acceptance():
                findings.append(
                    MonitoringValidationFinding(
                        finding_id=f"trigger-{trigger.trigger_id}-blocks-acceptance",
                        severity=MonitoringValidationFindingSeverity.BLOCKER,
                        source=MonitoringValidationFindingSource.REVALIDATION,
                        message="Open or in-progress revalidation trigger blocks acceptance.",
                        trigger_id=trigger.trigger_id,
                    )
                )
        return tuple(findings)

    def _validate_evidence(
        self,
        trail: MonitoringTrail,
    ) -> tuple[MonitoringValidationFinding, ...]:
        """Validate all monitoring evidence bundle references."""

        findings: list[MonitoringValidationFinding] = []
        for bundle_id in _required_evidence_bundle_ids(trail):
            bundle = self._bundle_by_id.get(bundle_id)
            if bundle is None:
                findings.append(
                    MonitoringValidationFinding(
                        finding_id=f"evidence-{bundle_id}-missing",
                        severity=MonitoringValidationFindingSeverity.BLOCKER,
                        source=MonitoringValidationFindingSource.EVIDENCE,
                        message="Monitoring trail references a missing evidence bundle.",
                        evidence_bundle_id=bundle_id,
                    )
                )
                continue
            validation = bundle.validate_integrity()
            if validation.errors:
                findings.append(
                    MonitoringValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-error",
                        severity=MonitoringValidationFindingSeverity.BLOCKER,
                        source=MonitoringValidationFindingSource.EVIDENCE,
                        message="; ".join(validation.errors),
                        evidence_bundle_id=bundle_id,
                    )
                )
            for warning_index, warning in enumerate(validation.warnings, start=1):
                findings.append(
                    MonitoringValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-warning-{warning_index}",
                        severity=MonitoringValidationFindingSeverity.WARNING,
                        source=MonitoringValidationFindingSource.EVIDENCE,
                        message=warning,
                        evidence_bundle_id=bundle_id,
                    )
                )
        return tuple(findings)


def _missing_membership_findings_for_snapshot(
    snapshot: MonitoringSnapshot,
    deployment: RegisteredDeployment,
) -> tuple[MonitoringValidationFinding, ...]:
    """Return findings for snapshot scenario/telemetry not registered on deployment."""

    findings: list[MonitoringValidationFinding] = []
    for scenario_id in snapshot.scenario_ids:
        if scenario_id not in deployment.scenario_ids:
            findings.append(
                MonitoringValidationFinding(
                    finding_id=(
                        f"snapshot-{snapshot.snapshot_id}-scenario-{scenario_id}-"
                        "not-in-deployment"
                    ),
                    severity=MonitoringValidationFindingSeverity.BLOCKER,
                    source=MonitoringValidationFindingSource.REGISTRY,
                    message="Snapshot scenario is not registered on its deployment.",
                    snapshot_id=snapshot.snapshot_id,
                    deployment_id=snapshot.deployment_id,
                    scenario_id=scenario_id,
                )
            )
    for telemetry_source_id in snapshot.telemetry_source_ids:
        if telemetry_source_id not in deployment.telemetry_source_ids:
            findings.append(
                MonitoringValidationFinding(
                    finding_id=(
                        f"snapshot-{snapshot.snapshot_id}-telemetry-{telemetry_source_id}-"
                        "not-in-deployment"
                    ),
                    severity=MonitoringValidationFindingSeverity.WARNING,
                    source=MonitoringValidationFindingSource.REGISTRY,
                    message="Snapshot telemetry source is not registered on its deployment.",
                    snapshot_id=snapshot.snapshot_id,
                    deployment_id=snapshot.deployment_id,
                    telemetry_source_id=telemetry_source_id,
                )
            )
    return tuple(findings)


def _trigger_source_exists(
    *,
    trigger: RevalidationTrigger,
    snapshot_ids: set[str],
    drift_ids: set[str],
    incident_ids: set[str],
) -> bool:
    """Return whether a trigger source record exists in the monitoring trail."""

    if trigger.source is RevalidationTriggerSource.MONITORING_SNAPSHOT:
        return trigger.source_record_id in snapshot_ids
    if trigger.source is RevalidationTriggerSource.DRIFT_RECORD:
        return trigger.source_record_id in drift_ids
    if trigger.source is RevalidationTriggerSource.INCIDENT_RECORD:
        return trigger.source_record_id in incident_ids
    return True


def _required_evidence_bundle_ids(trail: MonitoringTrail) -> tuple[str, ...]:
    """Return unique evidence bundle IDs referenced by the monitoring trail."""

    bundle_ids: list[str] = []
    for snapshot in trail.snapshots:
        bundle_ids.extend(snapshot.evidence_bundle_ids)
    for drift_record in trail.drift_records:
        bundle_ids.extend(drift_record.evidence_bundle_ids)
    for incident in trail.incidents:
        bundle_ids.extend(incident.evidence_bundle_ids)
    for trigger in trail.revalidation_triggers:
        bundle_ids.extend(trigger.evidence_bundle_ids)
    return tuple(dict.fromkeys(bundle_ids))


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable monitoring validation identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")
