from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError
from ix_autonomy_assurance_case_runtime.monitoring import (
    DriftRecord,
    DriftStatus,
    IncidentRecord,
    IncidentSeverity,
    IncidentState,
    MonitoringSnapshot,
    MonitoringSnapshotStatus,
    MonitoringTrail,
    RevalidationTrigger,
    RevalidationTriggerSource,
    RevalidationTriggerState,
)


def _snapshot(
    *,
    snapshot_id: str = "snapshot-nav-001",
    status: MonitoringSnapshotStatus = MonitoringSnapshotStatus.CURRENT,
    drift_status: DriftStatus = DriftStatus.NONE,
) -> MonitoringSnapshot:
    return MonitoringSnapshot(
        snapshot_id=snapshot_id,
        system_id="system-nav-001",
        model_id="model-nav-001",
        deployment_id="deploy-nav-001",
        observed_at_utc="2026-05-12T12:00:00Z",
        status=status,
        drift_status=drift_status,
        confidence_score=0.91,
        scenario_ids=("scenario-degraded-nav",),
        telemetry_source_ids=("telemetry-nav-sim",),
        evidence_bundle_ids=("ev-monitoring-snapshot-001",),
    )


def _drift(
    *,
    status: DriftStatus = DriftStatus.DEGRADED,
) -> DriftRecord:
    return DriftRecord(
        drift_id="drift-nav-001",
        snapshot_id="snapshot-nav-001",
        system_id="system-nav-001",
        model_id="model-nav-001",
        deployment_id="deploy-nav-001",
        detected_at_utc="2026-05-12T12:05:00Z",
        metric_name="navigation_confidence",
        baseline_value=0.93,
        observed_value=0.64,
        status=status,
        scenario_ids=("scenario-degraded-nav",),
        evidence_bundle_ids=("ev-drift-nav-001",),
    )


def _incident(
    *,
    state: IncidentState = IncidentState.OPEN,
    severity: IncidentSeverity = IncidentSeverity.HIGH,
) -> IncidentRecord:
    return IncidentRecord(
        incident_id="incident-nav-001",
        system_id="system-nav-001",
        deployment_id="deploy-nav-001",
        detected_at_utc="2026-05-12T12:10:00Z",
        severity=severity,
        state=state,
        summary="Navigation confidence dropped below the campaign acceptance floor.",
        affected_scenario_ids=("scenario-degraded-nav",),
        evidence_bundle_ids=("ev-incident-nav-001",),
        hazard_ids=("hazard-nav-drift",),
    )


def _trigger(
    *,
    state: RevalidationTriggerState = RevalidationTriggerState.OPEN,
) -> RevalidationTrigger:
    return RevalidationTrigger(
        trigger_id="trigger-nav-001",
        source=RevalidationTriggerSource.DRIFT_RECORD,
        source_record_id="drift-nav-001",
        state=state,
        created_at_utc="2026-05-12T12:15:00Z",
        reason="Degraded monitoring drift requires scenario revalidation.",
        requirement_ids=("req-nav-boundary",),
        hazard_ids=("hazard-nav-drift",),
        evidence_bundle_ids=("ev-trigger-nav-001",),
    )


def test_monitoring_snapshot_preserves_runtime_links_and_acceptance_posture() -> None:
    snapshot = _snapshot()

    assert snapshot.status.supports_current_acceptance()
    assert not snapshot.requires_revalidation()
    assert snapshot.scenario_ids == ("scenario-degraded-nav",)
    assert snapshot.telemetry_source_ids == ("telemetry-nav-sim",)


def test_monitoring_snapshot_blocks_current_status_with_degraded_drift() -> None:
    with pytest.raises(ContractValueError, match="current monitoring snapshots"):
        _snapshot(drift_status=DriftStatus.DEGRADED)

    stale = _snapshot(
        status=MonitoringSnapshotStatus.STALE,
        drift_status=DriftStatus.DEGRADED,
    )

    assert stale.requires_revalidation()
    assert stale.status.blocks_current_acceptance()


def test_drift_record_requires_scenario_trace_when_revalidation_is_needed() -> None:
    drift = _drift()

    assert drift.requires_revalidation()
    assert drift.absolute_delta == pytest.approx(0.29)

    with pytest.raises(ContractValueError, match="degraded or critical drift"):
        DriftRecord(
            drift_id="drift-nav-002",
            snapshot_id="snapshot-nav-001",
            system_id="system-nav-001",
            model_id="model-nav-001",
            deployment_id="deploy-nav-001",
            detected_at_utc="2026-05-12T12:05:00Z",
            metric_name="navigation_confidence",
            baseline_value=0.93,
            observed_value=0.64,
            status=DriftStatus.CRITICAL,
            evidence_bundle_ids=("ev-drift-nav-002",),
        )


def test_incident_record_enforces_hazard_links_for_authority_review_severity() -> None:
    incident = _incident()

    assert incident.requires_authority_review()
    assert incident.state.is_open()
    assert IncidentSeverity.HIGH.requires_authority_review()

    with pytest.raises(ContractValueError, match="high or critical incidents"):
        IncidentRecord(
            incident_id="incident-nav-002",
            system_id="system-nav-001",
            deployment_id="deploy-nav-001",
            detected_at_utc="2026-05-12T12:10:00Z",
            severity=IncidentSeverity.CRITICAL,
            state=IncidentState.OPEN,
            summary="Critical incident without hazard trace.",
            affected_scenario_ids=("scenario-degraded-nav",),
            evidence_bundle_ids=("ev-incident-nav-002",),
        )


def test_revalidation_trigger_blocks_acceptance_until_satisfied_or_waived() -> None:
    trigger = _trigger()
    satisfied = _trigger(state=RevalidationTriggerState.SATISFIED)

    assert trigger.blocks_acceptance()
    assert not satisfied.blocks_acceptance()


def test_monitoring_trail_summarizes_current_open_and_blocking_records() -> None:
    trail = MonitoringTrail(
        snapshots=(_snapshot(),),
        drift_records=(_drift(),),
        incidents=(_incident(),),
        revalidation_triggers=(_trigger(),),
    )

    assert trail.current_snapshot_ids() == ("snapshot-nav-001",)
    assert trail.open_incident_ids() == ("incident-nav-001",)
    assert trail.blocking_revalidation_trigger_ids() == ("trigger-nav-001",)
    assert trail.requires_authority_review()


def test_monitoring_trail_rejects_duplicate_record_ids() -> None:
    with pytest.raises(ContractValueError, match="monitoring snapshot IDs"):
        MonitoringTrail(snapshots=(_snapshot(), _snapshot()))


def test_monitoring_records_reject_blank_duplicate_and_invalid_values() -> None:
    with pytest.raises(ContractValueError, match="snapshot_id must not contain spaces"):
        _snapshot(snapshot_id="snapshot nav 001")

    with pytest.raises(ContractValueError, match="confidence_score"):
        MonitoringSnapshot(
            snapshot_id="snapshot-nav-002",
            system_id="system-nav-001",
            model_id="model-nav-001",
            deployment_id="deploy-nav-001",
            observed_at_utc="2026-05-12T12:00:00Z",
            status=MonitoringSnapshotStatus.CURRENT,
            drift_status=DriftStatus.NONE,
            confidence_score=1.1,
            scenario_ids=("scenario-degraded-nav",),
            telemetry_source_ids=("telemetry-nav-sim",),
            evidence_bundle_ids=("ev-monitoring-snapshot-002",),
        )

    with pytest.raises(ContractValueError, match="duplicate identifiers"):
        _snapshot().__class__(
            snapshot_id="snapshot-nav-003",
            system_id="system-nav-001",
            model_id="model-nav-001",
            deployment_id="deploy-nav-001",
            observed_at_utc="2026-05-12T12:00:00Z",
            status=MonitoringSnapshotStatus.CURRENT,
            drift_status=DriftStatus.NONE,
            confidence_score=0.91,
            scenario_ids=("scenario-degraded-nav", "scenario-degraded-nav"),
            telemetry_source_ids=("telemetry-nav-sim",),
            evidence_bundle_ids=("ev-monitoring-snapshot-003",),
        )
