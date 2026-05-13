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
from ix_autonomy_assurance_case_runtime.monitoring_validation import (
    MonitoringTrailValidator,
    MonitoringValidationFinding,
    MonitoringValidationFindingSeverity,
    MonitoringValidationFindingSource,
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


def _deployment(
    *,
    scenario_ids: tuple[str, ...] = ("scenario-degraded-nav",),
    telemetry_source_ids: tuple[str, ...] = ("telemetry-nav-sim",),
) -> RegisteredDeployment:
    return RegisteredDeployment(
        deployment_id="deploy-nav-001",
        system_id="system-nav-001",
        environment=DeploymentEnvironment.OPERATIONAL_TEST,
        lifecycle_state=RegistryLifecycleState.APPROVED,
        authority_state=RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
        scenario_ids=scenario_ids,
        telemetry_source_ids=telemetry_source_ids,
        evidence_bundle_ids=("ev-registry-deployment",),
    )


def _registry_catalog(
    *,
    deployment: RegisteredDeployment | None = None,
    model: RegisteredModel | None = None,
) -> RegistryCatalog:
    return RegistryCatalog(
        models=(model or _model(),),
        systems=(_system(),),
        use_cases=(_use_case(),),
        deployments=(deployment or _deployment(),),
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
    scenario_ids: tuple[str, ...] = ("scenario-degraded-nav",),
    telemetry_source_ids: tuple[str, ...] = ("telemetry-nav-sim",),
    evidence_bundle_ids: tuple[str, ...] = ("ev-monitoring-snapshot",),
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
        scenario_ids=scenario_ids,
        telemetry_source_ids=telemetry_source_ids,
        evidence_bundle_ids=evidence_bundle_ids,
    )


def _drift(
    *,
    scenario_ids: tuple[str, ...] = ("scenario-degraded-nav",),
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
        status=DriftStatus.DEGRADED,
        scenario_ids=scenario_ids,
        evidence_bundle_ids=("ev-drift-nav",),
    )


def _incident(
    *,
    affected_scenario_ids: tuple[str, ...] = ("scenario-degraded-nav",),
    state: IncidentState = IncidentState.CLOSED,
) -> IncidentRecord:
    return IncidentRecord(
        incident_id="incident-nav-001",
        system_id="system-nav-001",
        deployment_id="deploy-nav-001",
        detected_at_utc="2026-05-12T12:10:00Z",
        severity=IncidentSeverity.HIGH,
        state=state,
        summary="Navigation confidence dropped below the campaign acceptance floor.",
        affected_scenario_ids=affected_scenario_ids,
        hazard_ids=("hazard-nav-drift",),
        evidence_bundle_ids=("ev-incident-nav",),
    )


def _trigger(
    *,
    state: RevalidationTriggerState = RevalidationTriggerState.SATISFIED,
    source_record_id: str = "drift-nav-001",
) -> RevalidationTrigger:
    return RevalidationTrigger(
        trigger_id="trigger-nav-001",
        source=RevalidationTriggerSource.DRIFT_RECORD,
        source_record_id=source_record_id,
        state=state,
        created_at_utc="2026-05-12T12:15:00Z",
        reason="Degraded monitoring drift requires scenario revalidation.",
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
) -> MonitoringTrail:
    return MonitoringTrail(
        snapshots=(snapshot or _snapshot(),),
        drift_records=(drift or _drift(),),
        incidents=(incident or _incident(),),
        revalidation_triggers=(trigger or _trigger(),),
    )


def _bundle(bundle_id: str, *, hashed: bool = True) -> EvidenceBundle:
    bundle = EvidenceBundle(
        bundle_id=bundle_id,
        case_id="case-monitoring-validation-001",
        records=(
            EvidenceRecord(
                evidence_id=f"record-{bundle_id}",
                kind="monitoring-validation",
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


def _validator(
    *,
    registry_catalog: RegistryCatalog | None = None,
    evidence_bundles: tuple[EvidenceBundle, ...] | None = None,
) -> MonitoringTrailValidator:
    return MonitoringTrailValidator(
        registry_catalog or _registry_catalog(),
        _telemetry_catalog(),
        evidence_bundles=_bundles() if evidence_bundles is None else evidence_bundles,
    )


def test_monitoring_validator_accepts_grounded_trail() -> None:
    report = _validator().validate(_trail())

    assert report.is_monitoring_ready()
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "monitoring-validation: 1 snapshot(s), 1 drift record(s), "
        "1 incident(s), 1 trigger(s), 0 blocker(s), 0 warning(s)"
    )


def test_monitoring_validator_blocks_missing_current_snapshot() -> None:
    stale_snapshot = _snapshot(
        status=MonitoringSnapshotStatus.STALE,
        drift_status=DriftStatus.DEGRADED,
    )
    report = _validator().validate(_trail(snapshot=stale_snapshot))

    assert not report.is_monitoring_ready()
    assert any(
        finding.finding_id == "monitoring-trail-no-current-snapshot"
        for finding in report.findings
    )
    assert report.findings_for_snapshot("snapshot-nav-001")


def test_monitoring_validator_blocks_missing_registry_and_telemetry_references() -> None:
    bad_snapshot = _snapshot(
        scenario_ids=("scenario-missing",),
        telemetry_source_ids=("telemetry-missing",),
    )
    report = _validator().validate(_trail(snapshot=bad_snapshot))

    assert not report.is_monitoring_ready()
    assert any(
        finding.source is MonitoringValidationFindingSource.TELEMETRY
        for finding in report.findings_for_telemetry_source("telemetry-missing")
    )
    assert any(
        finding.finding_id
        == "snapshot-snapshot-nav-001-scenario-scenario-missing-not-in-deployment"
        for finding in report.findings_for_snapshot("snapshot-nav-001")
    )


def test_monitoring_validator_blocks_model_not_registered_on_system() -> None:
    alternate_model = RegisteredModel(
        model_id="model-other-001",
        name="Other model",
        version="1.0.0",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.HIGH,
        intended_uses=("bounded navigation assistance",),
        prohibited_uses=("unsupervised live operation",),
        evidence_bundle_ids=("ev-registry-model",),
    )
    snapshot = MonitoringSnapshot(
        snapshot_id="snapshot-nav-001",
        system_id="system-nav-001",
        model_id="model-other-001",
        deployment_id="deploy-nav-001",
        observed_at_utc="2026-05-12T12:00:00Z",
        status=MonitoringSnapshotStatus.CURRENT,
        drift_status=DriftStatus.NONE,
        confidence_score=0.91,
        scenario_ids=("scenario-degraded-nav",),
        telemetry_source_ids=("telemetry-nav-sim",),
        evidence_bundle_ids=("ev-monitoring-snapshot",),
    )

    report = _validator(
        registry_catalog=_registry_catalog(model=alternate_model),
    ).validate(_trail(snapshot=snapshot))

    assert not report.is_monitoring_ready()
    assert any(
        finding.finding_id == "snapshot-snapshot-nav-001-model-not-on-system"
        for finding in report.findings_for_snapshot("snapshot-nav-001")
    )


def test_monitoring_validator_blocks_drift_scenario_not_in_snapshot() -> None:
    report = _validator().validate(_trail(drift=_drift(scenario_ids=("scenario-other",))))

    assert not report.is_monitoring_ready()
    assert report.findings_for_drift("drift-nav-001")[0].scenario_id == "scenario-other"


def test_monitoring_validator_blocks_incident_scenario_not_in_deployment() -> None:
    report = _validator().validate(
        _trail(incident=_incident(affected_scenario_ids=("scenario-other",)))
    )

    assert not report.is_monitoring_ready()
    assert report.findings_for_incident("incident-nav-001")[0].source is (
        MonitoringValidationFindingSource.REGISTRY
    )


def test_monitoring_validator_blocks_open_or_missing_revalidation_trigger_source() -> None:
    report = _validator().validate(
        _trail(trigger=_trigger(state=RevalidationTriggerState.OPEN, source_record_id="missing"))
    )

    assert not report.is_monitoring_ready()
    trigger_findings = report.findings_for_trigger("trigger-nav-001")
    assert {finding.finding_id for finding in trigger_findings} == {
        "trigger-trigger-nav-001-missing-source-record",
        "trigger-trigger-nav-001-blocks-acceptance",
    }


def test_monitoring_validator_blocks_missing_evidence_bundle() -> None:
    report = _validator(evidence_bundles=()).validate(_trail())

    assert not report.is_monitoring_ready()
    assert report.findings_for_evidence_bundle("ev-monitoring-snapshot")[0].source is (
        MonitoringValidationFindingSource.EVIDENCE
    )


def test_monitoring_validator_warns_for_unhashed_evidence() -> None:
    report = _validator(evidence_bundles=_bundles(unhashed="ev-drift-nav")).validate(_trail())

    assert report.is_monitoring_ready()
    assert report.warning_count == 2
    assert report.findings_for_evidence_bundle("ev-drift-nav")


def test_monitoring_validator_warns_when_no_revalidation_history_exists() -> None:
    trail = MonitoringTrail(snapshots=(_snapshot(),))
    report = _validator(evidence_bundles=(_bundle("ev-monitoring-snapshot"),)).validate(trail)

    assert report.is_monitoring_ready()
    assert report.warning_count == 1
    assert report.findings[0].source is MonitoringValidationFindingSource.REVALIDATION


def test_monitoring_validator_rejects_duplicate_evidence_bundles() -> None:
    with pytest.raises(ContractValueError, match="Duplicate monitoring evidence bundle ID"):
        MonitoringTrailValidator(
            _registry_catalog(),
            _telemetry_catalog(),
            evidence_bundles=(
                _bundle("ev-monitoring-snapshot"),
                _bundle("ev-monitoring-snapshot"),
            ),
        )


def test_monitoring_validation_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        MonitoringValidationFinding(
            finding_id="finding-monitoring-001",
            severity=MonitoringValidationFindingSeverity.BLOCKER,
            source=MonitoringValidationFindingSource.MONITORING,
            message="",
        )

    with pytest.raises(ContractValueError, match="snapshot_id must not be blank"):
        MonitoringValidationFinding(
            finding_id="finding-monitoring-001",
            severity=MonitoringValidationFindingSeverity.BLOCKER,
            source=MonitoringValidationFindingSource.MONITORING,
            message="Bad snapshot.",
            snapshot_id="",
        )
