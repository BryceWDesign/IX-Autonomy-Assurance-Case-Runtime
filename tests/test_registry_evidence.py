from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime import (
    DeploymentEnvironment,
    EvidenceBundle,
    EvidenceRecord,
    EvidenceStatus,
    RegisteredDeployment,
    RegisteredModel,
    RegisteredSystem,
    RegisteredUseCase,
    RegisteredUseCategory,
    RegistryCatalog,
    RegistryEvidenceFinding,
    RegistryEvidenceFindingSeverity,
    RegistryEvidenceReference,
    RegistryEvidenceValidator,
    RegistryLifecycleState,
    RegistryReferenceType,
    RegistryRiskTier,
    RuntimeAuthorityState,
    collect_registry_evidence_references,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError


def _bundle(
    bundle_id: str,
    *,
    case_id: str = "case-nav-001",
    scenario_id: str | None = None,
    status: EvidenceStatus = EvidenceStatus.ACCEPTED,
) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=bundle_id,
        case_id=case_id,
        scenario_id=scenario_id,
        records=(
            EvidenceRecord(
                evidence_id=f"record-{bundle_id}",
                kind="registry-evidence",
                source="unit-test",
                payload={"supports": bundle_id},
                status=status,
            ),
        ),
    ).with_computed_hashes()


def _catalog() -> RegistryCatalog:
    model = RegisteredModel(
        model_id="model-nav-001",
        name="Navigation decision model",
        version="2026.05",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.HIGH,
        intended_uses=("navigation anomaly triage",),
        prohibited_uses=("unbounded autonomous maneuver",),
        evidence_bundle_ids=("ev-model-nav-001",),
    )
    system = RegisteredSystem(
        system_id="system-nav-001",
        name="Navigation assurance system",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.HIGH,
        mission_thread_ids=("mission-thread-nav",),
        model_ids=("model-nav-001",),
        assurance_case_id="case-nav-001",
    )
    use_case = RegisteredUseCase(
        use_case_id="use-case-nav-001",
        name="Navigation confidence monitor",
        system_id="system-nav-001",
        category=RegisteredUseCategory.SAFETY_MONITORING,
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.HIGH,
        mission_need_ids=("mn-nav-survivability",),
        requirement_ids=("req-nav-boundary",),
        prohibited_conditions=("unbounded autonomous maneuver",),
        evidence_bundle_ids=("ev-use-case-nav-001",),
    )
    deployment = RegisteredDeployment(
        deployment_id="deploy-nav-001",
        system_id="system-nav-001",
        environment=DeploymentEnvironment.OPERATIONAL_TEST,
        lifecycle_state=RegistryLifecycleState.APPROVED,
        authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
        scenario_ids=("scenario-degraded-nav",),
        evidence_bundle_ids=("ev-deploy-nav-001",),
        telemetry_source_ids=("telemetry-nav-sim",),
        approved_for_live_operation=True,
    )
    return RegistryCatalog(
        models=(model,),
        systems=(system,),
        use_cases=(use_case,),
        deployments=(deployment,),
    )


def test_collect_registry_evidence_references_preserves_subjects_and_bundle_ids() -> None:
    references = collect_registry_evidence_references(_catalog())

    assert references == (
        RegistryEvidenceReference(
            subject_id="model-nav-001",
            subject_type=RegistryReferenceType.MODEL,
            bundle_id="ev-model-nav-001",
        ),
        RegistryEvidenceReference(
            subject_id="use-case-nav-001",
            subject_type=RegistryReferenceType.USE_CASE,
            bundle_id="ev-use-case-nav-001",
        ),
        RegistryEvidenceReference(
            subject_id="deploy-nav-001",
            subject_type=RegistryReferenceType.DEPLOYMENT,
            bundle_id="ev-deploy-nav-001",
            expected_scenario_ids=("scenario-degraded-nav",),
        ),
    )


def test_registry_evidence_validator_accepts_complete_valid_coverage() -> None:
    report = RegistryEvidenceValidator(
        bundles=(
            _bundle("ev-model-nav-001"),
            _bundle("ev-use-case-nav-001"),
            _bundle("ev-deploy-nav-001", scenario_id="scenario-degraded-nav"),
        )
    ).validate(_catalog())

    assert report.is_coverage_ready()
    assert report.referenced_bundle_count == 3
    assert report.provided_bundle_count == 3
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "registry-evidence: 3 referenced bundle(s), 3 provided bundle(s), "
        "0 blocker(s), 0 warning(s)"
    )


def test_registry_evidence_validator_blocks_missing_referenced_bundles() -> None:
    report = RegistryEvidenceValidator(bundles=()).validate(_catalog())

    assert not report.is_coverage_ready()
    assert report.blocker_count == 3
    assert {
        finding.finding_id for finding in report.findings_for_subject("model-nav-001")
    } == {"model-model-nav-001-missing-evidence-ev-model-nav-001"}


def test_registry_evidence_validator_blocks_deployment_scenario_mismatch() -> None:
    report = RegistryEvidenceValidator(
        bundles=(
            _bundle("ev-model-nav-001"),
            _bundle("ev-use-case-nav-001"),
            _bundle("ev-deploy-nav-001", scenario_id="wrong-scenario"),
        )
    ).validate(_catalog())

    assert report.blocker_count == 1
    assert report.findings[0].finding_id == (
        "deployment-deploy-nav-001-scenario-mismatch-ev-deploy-nav-001"
    )


def test_registry_evidence_validator_reports_bundle_integrity_warnings() -> None:
    unhashed_bundle = EvidenceBundle(
        bundle_id="ev-model-nav-001",
        case_id="case-nav-001",
        records=(
            EvidenceRecord(
                evidence_id="record-ev-model-nav-001",
                kind="registry-evidence",
                source="unit-test",
                payload={"supports": "ev-model-nav-001"},
                status=EvidenceStatus.ACCEPTED,
            ),
        ),
    )
    report = RegistryEvidenceValidator(
        bundles=(
            unhashed_bundle,
            _bundle("ev-use-case-nav-001"),
            _bundle("ev-deploy-nav-001", scenario_id="scenario-degraded-nav"),
        )
    ).validate(_catalog())

    assert report.is_coverage_ready()
    assert report.warning_count == 2
    assert {finding.severity for finding in report.findings} == {
        RegistryEvidenceFindingSeverity.WARNING
    }


def test_registry_evidence_validator_blocks_invalid_evidence_status() -> None:
    report = RegistryEvidenceValidator(
        bundles=(
            _bundle("ev-model-nav-001", status=EvidenceStatus.INVALID),
            _bundle("ev-use-case-nav-001"),
            _bundle("ev-deploy-nav-001", scenario_id="scenario-degraded-nav"),
        )
    ).validate(_catalog())

    assert report.blocker_count == 1
    assert "is marked invalid" in report.findings[0].message


def test_registry_evidence_validator_rejects_duplicate_provided_bundle_ids() -> None:
    with pytest.raises(ContractValueError, match="Duplicate evidence bundle ID"):
        RegistryEvidenceValidator(
            bundles=(
                _bundle("ev-model-nav-001"),
                _bundle("ev-model-nav-001"),
            )
        )


def test_registry_evidence_reference_rejects_blank_and_duplicate_scenario_expectations() -> None:
    with pytest.raises(ContractValueError, match="bundle_id must not be blank"):
        RegistryEvidenceReference(
            subject_id="deploy-nav-001",
            subject_type=RegistryReferenceType.DEPLOYMENT,
            bundle_id="",
        )

    with pytest.raises(ContractValueError, match="must not contain duplicates"):
        RegistryEvidenceReference(
            subject_id="deploy-nav-001",
            subject_type=RegistryReferenceType.DEPLOYMENT,
            bundle_id="ev-deploy-nav-001",
            expected_scenario_ids=("scenario-a", "scenario-a"),
        )


def test_registry_evidence_finding_rejects_blank_bundle_id() -> None:
    with pytest.raises(ContractValueError, match="blank bundle ID"):
        RegistryEvidenceFinding(
            finding_id="bad-finding",
            severity=RegistryEvidenceFindingSeverity.BLOCKER,
            message="Bad finding.",
            subject_id="model-nav-001",
            subject_type=RegistryReferenceType.MODEL,
            bundle_id="",
        )
