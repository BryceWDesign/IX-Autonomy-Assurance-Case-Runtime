from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import (
    ContractValueError,
    EvidenceStatus,
    RuntimeAuthorityState,
)
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
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
from ix_autonomy_assurance_case_runtime.monitoring_readiness import (
    MONITORING_CAPABILITY_ID,
    MonitoringLayerReadinessEvaluator,
    MonitoringReadinessDecision,
    MonitoringReadinessFinding,
    MonitoringReadinessFindingSeverity,
    MonitoringReadinessFindingSource,
)
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.registry import (
    DeploymentEnvironment,
    RegisteredDeployment,
    RegisteredModel,
    RegisteredSystem,
    RegisteredUseCase,
    RegisteredUseCategory,
    RegistryLifecycleState,
    RegistryRiskTier,
)
from ix_autonomy_assurance_case_runtime.registry_catalog import RegistryCatalog
from ix_autonomy_assurance_case_runtime.telemetry import (
    TelemetryFieldType,
    TelemetrySchema,
    TelemetrySchemaField,
    TelemetrySource,
    TelemetrySourceKind,
    TelemetryTimestampAuthority,
    TelemetryTrustLevel,
)
from ix_autonomy_assurance_case_runtime.telemetry_adapter import TelemetryAdapterCatalog


def _model() -> RegisteredModel:
    return RegisteredModel(
        model_id="model-nav-001",
        name="Navigation model",
        version="1.0.0",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.HIGH,
        intended_uses=("bounded navigation assistance",),
        prohibited_uses=("unsupervised live operation",),
        evidence_bundle_ids=("ev-registry-model",),
    )


def _system() -> RegisteredSystem:
    return RegisteredSystem(
        system_id="system-nav-001",
        name="Navigation autonomy system",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.HIGH,
        mission_thread_ids=("mission-thread-nav",),
        model_ids=("model-nav-001",),
        assurance_case_id="case-nav-001",
    )


def _use_case() -> RegisteredUseCase:
    return RegisteredUseCase(
        use_case_id="use-case-nav-001",
        name="Degraded navigation support",
        system_id="system-nav-001",
        category=RegisteredUseCategory.AUTONOMY_CONTROL,
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.HIGH,
        mission_need_ids=("mission-need-nav",),
        requirement_ids=("req-nav-boundary",),
        prohibited_conditions=("operator override unavailable",),
        evidence_bundle_ids=("ev-registry-use-case",),
    )


def _deployment() -> RegisteredDeployment:
    return RegisteredDeployment(
        deployment_id="deploy-nav-001",
        system_id="system-nav-001",
        environment=DeploymentEnvironment.OPERATIONAL_TEST,
        lifecycle_state=RegistryLifecycleState.APPROVED,
        authority_state=RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
        scenario_ids=("scenario-degraded-nav",),
        evidence_bundle_ids=("ev-registry-deployment",),
        telemetry_source_ids=("telemetry-nav-sim",),
    )


def _registry_catalog() -> RegistryCatalog:
    return RegistryCatalog(
        models=(_model(),),
        systems=(_system(),),
        use_cases=(_use_case(),),
        deployments=(_deployment(),),
    )


def _telemetry_catalog() -> TelemetryAdapterCatalog:
    return TelemetryAdapterCatalog(
        sources=(
            TelemetrySource(
                source_id="telemetry-nav-sim",
                name="Navigation simulator",
                kind=TelemetrySourceKind.SIMULATOR,
                trust_level=TelemetryTrustLevel.HIGH,
                timestamp_authority=TelemetryTimestampAuthority.SOURCE_PROVIDED,
                owner="Assurance Lab",
                allowed_schema_ids=("schema-nav-v1",),
                evidence_bundle_ids=("ev-telemetry-source",),
            ),
        ),
        schemas=(
            TelemetrySchema(
                schema_id="schema-nav-v1",
                name="Navigation telemetry schema",
                version="1.0.0",
                fields=(
                    TelemetrySchemaField(
                        field_name="navigation_confidence",
                        field_type=TelemetryFieldType.FLOAT,
                        minimum_value=0.0,
                        maximum_value=1.0,
                    ),
                ),
            ),
        ),
    )


def _snapshot(
    *,
    status: MonitoringSnapshotStatus = MonitoringSnapshotStatus.CURRENT,
    drift_status: DriftStatus = DriftStatus.NONE,
) -> MonitoringSnapshot:
    return MonitoringSnapshot(
        snapshot_id="snapshot-nav-001",
        system_id="system-nav-001",
        model_id="model-nav-001",
        deployment_id="deploy-nav-001",
        observed_at_utc="2026-05-12T12:00:00Z",
        status=status,
        drift_status=drift_status,
        confidence_score=0.91,
        scenario_ids=("scenario-degraded-nav",),
        telemetry_source_ids=("telemetry-nav-sim",),
        evidence_bundle_ids=("ev-monitoring-snapshot",),
    )


def _drift() -> DriftRecord:
    return DriftRecord(
        drift_id="drift-nav-001",
        snapshot_id="snapshot-nav-001",
        system_id="system-nav-001",
        model_id="model-nav-001",
        deployment_id="deploy-nav-001",
        detected_at_utc="2026-05-12T12:05:00Z",
        metric_name="navigation_confidence",
        baseline_value=0.93,
        observed_value=0.91,
        status=DriftStatus.WATCH,
        scenario_ids=("scenario-degraded-nav",),
        evidence_bundle_ids=("ev-drift-nav",),
    )


def _incident(
    *,
    state: IncidentState = IncidentState.CLOSED,
) -> IncidentRecord:
    return IncidentRecord(
        incident_id="incident-nav-001",
        system_id="system-nav-001",
        deployment_id="deploy-nav-001",
        detected_at_utc="2026-05-12T12:10:00Z",
        severity=IncidentSeverity.HIGH,
        state=state,
        summary="Navigation confidence event was reviewed and closed.",
        affected_scenario_ids=("scenario-degraded-nav",),
        evidence_bundle_ids=("ev-incident-nav",),
        hazard_ids=("hazard-nav-drift",),
    )


def _trigger(
    *,
    state: RevalidationTriggerState = RevalidationTriggerState.SATISFIED,
) -> RevalidationTrigger:
    return RevalidationTrigger(
        trigger_id="trigger-nav-001",
        source=RevalidationTriggerSource.DRIFT_RECORD,
        source_record_id="drift-nav-001",
        state=state,
        created_at_utc="2026-05-12T12:15:00Z",
        reason="Drift watch record was reviewed against the campaign evidence.",
        requirement_ids=("req-nav-boundary",),
        hazard_ids=("hazard-nav-drift",),
        evidence_bundle_ids=("ev-trigger-nav",),
    )


def _trail(
    *,
    snapshot: MonitoringSnapshot | None = None,
    drift: DriftRecord | None = None,
    incident: IncidentRecord | None = None,
    trigger: RevalidationTrigger | None = None,
    include_drift: bool = True,
    include_incident: bool = True,
    include_trigger: bool = True,
) -> MonitoringTrail:
    return MonitoringTrail(
        snapshots=(snapshot or _snapshot(),),
        drift_records=(drift or _drift(),) if include_drift else (),
        incidents=(incident or _incident(),) if include_incident else (),
        revalidation_triggers=(trigger or _trigger(),) if include_trigger else (),
    )


def _bundle(bundle_id: str, *, hashed: bool = True) -> EvidenceBundle:
    bundle = EvidenceBundle(
        bundle_id=bundle_id,
        case_id="case-monitoring-readiness-001",
        records=(
            EvidenceRecord(
                evidence_id=f"record-{bundle_id}",
                kind="monitoring-readiness",
                source="unit-test",
                payload={"bundle_id": bundle_id},
                status=EvidenceStatus.ACCEPTED,
            ),
        ),
    )
    if hashed:
        return bundle.with_computed_hashes()
    return bundle


def _bundles(*, unhashed: str | None = None) -> tuple[EvidenceBundle, ...]:
    bundle_ids = (
        "ev-monitoring-snapshot",
        "ev-drift-nav",
        "ev-incident-nav",
        "ev-trigger-nav",
    )
    return tuple(_bundle(bundle_id, hashed=bundle_id != unhashed) for bundle_id in bundle_ids)


def _evaluator(
    *,
    evidence_bundles: tuple[EvidenceBundle, ...] | None = None,
) -> MonitoringLayerReadinessEvaluator:
    return MonitoringLayerReadinessEvaluator(
        registry_catalog=_registry_catalog(),
        telemetry_catalog=_telemetry_catalog(),
        evidence_bundles=_bundles() if evidence_bundles is None else evidence_bundles,
    )


def test_monitoring_readiness_completes_clean_monitoring_trail() -> None:
    report = _evaluator().evaluate(_trail())

    assert report.decision is MonitoringReadinessDecision.COMPLETE
    assert report.is_complete()
    assert report.completed_capability_ids() == (MONITORING_CAPABILITY_ID,)
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "monitoring-readiness: complete "
        "(1 snapshot(s), 1 drift record(s), 1 incident(s), 1 trigger(s), "
        "0 blocker(s), 0 warning(s), capability=monitoring-incidents)"
    )


def test_monitoring_readiness_feeds_prototype_claim_gate() -> None:
    report = _evaluator().evaluate(_trail())

    prototype_report = report.prototype_readiness_report(
        PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE,
        existing_completed_capability_ids=(
            "registry-layer",
            "policy-pack-engine",
            "framework-crosswalks",
            "signed-provenance",
            "telemetry-adapters",
            "scenario-campaign-runner",
        ),
    )

    assert prototype_report.decision is PrototypeReadinessDecision.BLOCK
    assert prototype_report.achieved_percent == 72
    assert prototype_report.completed_capability_ids == (
        "registry-layer",
        "policy-pack-engine",
        "framework-crosswalks",
        "signed-provenance",
        "telemetry-adapters",
        "scenario-campaign-runner",
        "monitoring-incidents",
    )
    assert "review-workflow" in prototype_report.remaining_capability_ids


def test_monitoring_readiness_blocks_missing_current_snapshot() -> None:
    report = _evaluator().evaluate(
        _trail(
            snapshot=_snapshot(
                status=MonitoringSnapshotStatus.STALE,
                drift_status=DriftStatus.DEGRADED,
            )
        )
    )

    assert report.decision is MonitoringReadinessDecision.BLOCKED
    assert not report.is_complete()
    assert any(
        finding.finding_id == "monitoring-readiness-no-current-snapshot"
        for finding in report.findings
    )
    assert report.findings_for_snapshot("snapshot-nav-001")


def test_monitoring_readiness_blocks_open_incidents() -> None:
    report = _evaluator().evaluate(_trail(incident=_incident(state=IncidentState.OPEN)))

    assert report.decision is MonitoringReadinessDecision.BLOCKED
    assert any(
        finding.finding_id == "incident-incident-nav-001-open"
        for finding in report.findings_for_incident("incident-nav-001")
    )


def test_monitoring_readiness_blocks_active_revalidation_trigger() -> None:
    report = _evaluator().evaluate(
        _trail(trigger=_trigger(state=RevalidationTriggerState.IN_PROGRESS))
    )

    assert report.decision is MonitoringReadinessDecision.BLOCKED
    assert any(
        finding.finding_id == "trigger-trigger-nav-001-blocks-acceptance"
        for finding in report.findings_for_trigger("trigger-nav-001")
    )


def test_monitoring_readiness_limited_for_validation_warnings() -> None:
    report = _evaluator(
        evidence_bundles=_bundles(unhashed="ev-drift-nav"),
    ).evaluate(_trail())

    assert report.decision is MonitoringReadinessDecision.LIMITED
    assert not report.is_complete()
    assert report.warning_count == 2
    assert report.findings_for_evidence_bundle("ev-drift-nav")


def test_monitoring_readiness_warns_when_drift_history_is_missing() -> None:
    report = _evaluator(
        evidence_bundles=(
            _bundle("ev-monitoring-snapshot"),
            _bundle("ev-incident-nav"),
            _bundle("ev-trigger-nav"),
        )
    ).evaluate(_trail(include_drift=False, trigger=_trigger(source_record_id="snapshot-nav-001")))

    assert report.decision is MonitoringReadinessDecision.LIMITED
    assert any(
        finding.finding_id == "monitoring-readiness-no-drift-record-history"
        for finding in report.findings
    )


def test_monitoring_readiness_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        MonitoringReadinessFinding(
            finding_id="finding-monitoring-001",
            severity=MonitoringReadinessFindingSeverity.BLOCKER,
            source=MonitoringReadinessFindingSource.READINESS,
            message="",
        )

    with pytest.raises(ContractValueError, match="incident_id must not be blank"):
        MonitoringReadinessFinding(
            finding_id="finding-monitoring-001",
            severity=MonitoringReadinessFindingSeverity.BLOCKER,
            source=MonitoringReadinessFindingSource.INCIDENT,
            message="Bad incident.",
            incident_id="",
        )
