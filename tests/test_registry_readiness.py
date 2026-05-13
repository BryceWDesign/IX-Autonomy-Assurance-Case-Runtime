from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime import (
    DeploymentEnvironment,
    EvidenceBundle,
    EvidenceRecord,
    EvidenceStatus,
    PrototypeClaimLevel,
    PrototypeReadinessDecision,
    RegisteredDeployment,
    RegisteredModel,
    RegisteredSystem,
    RegisteredUseCase,
    RegisteredUseCategory,
    RegistryCatalog,
    RegistryLayerReadinessEvaluator,
    RegistryLifecycleState,
    RegistryReadinessDecision,
    RegistryReadinessFinding,
    RegistryReadinessFindingSeverity,
    RegistryReadinessFindingSource,
    RegistryRiskTier,
    RuntimeAuthorityState,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError


def _bundle(
    bundle_id: str,
    *,
    scenario_id: str | None = None,
    status: EvidenceStatus = EvidenceStatus.ACCEPTED,
) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=bundle_id,
        case_id="case-nav-001",
        scenario_id=scenario_id,
        records=(
            EvidenceRecord(
                evidence_id=f"record-{bundle_id}",
                kind="registry-readiness",
                source="unit-test",
                payload={"supports": bundle_id},
                status=status,
            ),
        ),
    ).with_computed_hashes()


def _approved_model() -> RegisteredModel:
    return RegisteredModel(
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


def _approved_system() -> RegisteredSystem:
    return RegisteredSystem(
        system_id="system-nav-001",
        name="Navigation assurance system",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.HIGH,
        mission_thread_ids=("mission-thread-nav",),
        model_ids=("model-nav-001",),
        assurance_case_id="case-nav-001",
    )


def _approved_use_case() -> RegisteredUseCase:
    return RegisteredUseCase(
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


def _approved_deployment() -> RegisteredDeployment:
    return RegisteredDeployment(
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


def _complete_catalog() -> RegistryCatalog:
    return RegistryCatalog(
        models=(_approved_model(),),
        systems=(_approved_system(),),
        use_cases=(_approved_use_case(),),
        deployments=(_approved_deployment(),),
    )


def _complete_bundles() -> tuple[EvidenceBundle, ...]:
    return (
        _bundle("ev-model-nav-001"),
        _bundle("ev-use-case-nav-001"),
        _bundle("ev-deploy-nav-001", scenario_id="scenario-degraded-nav"),
    )


def test_registry_readiness_is_complete_when_catalog_and_evidence_are_clean() -> None:
    report = RegistryLayerReadinessEvaluator(_complete_bundles()).evaluate(_complete_catalog())

    assert report.decision is RegistryReadinessDecision.COMPLETE
    assert report.is_complete()
    assert report.completed_capability_ids() == ("registry-layer",)
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "registry-readiness: complete "
        "(0 blocker(s), 0 warning(s), capability=registry-layer)"
    )


def test_registry_readiness_feeds_prototype_claim_gate_without_overclaiming() -> None:
    report = RegistryLayerReadinessEvaluator(_complete_bundles()).evaluate(_complete_catalog())

    prototype_report = report.prototype_readiness_report(
        PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE
    )

    assert prototype_report.decision is PrototypeReadinessDecision.BLOCK
    assert prototype_report.achieved_percent == 44
    assert prototype_report.completed_capability_ids == ("registry-layer",)
    assert "policy-pack-engine" in prototype_report.remaining_capability_ids


def test_registry_readiness_blocks_when_required_evidence_is_missing() -> None:
    report = RegistryLayerReadinessEvaluator(evidence_bundles=()).evaluate(_complete_catalog())

    assert report.decision is RegistryReadinessDecision.BLOCKED
    assert not report.is_complete()
    assert report.completed_capability_ids() == ()
    assert report.blocker_count == 3
    assert {
        finding.source for finding in report.findings_for_subject("model-nav-001")
    } == {RegistryReadinessFindingSource.EVIDENCE}


def test_registry_readiness_blocks_catalog_reference_failures() -> None:
    system = RegisteredSystem(
        system_id="system-nav-001",
        name="Navigation assurance system",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.UNDER_REVIEW,
        risk_tier=RegistryRiskTier.HIGH,
        mission_thread_ids=("mission-thread-nav",),
        model_ids=("missing-model",),
    )
    catalog = RegistryCatalog(systems=(system,))
    report = RegistryLayerReadinessEvaluator(evidence_bundles=()).evaluate(catalog)

    assert report.decision is RegistryReadinessDecision.BLOCKED
    assert report.blocker_count == 1
    assert report.findings[0].source is RegistryReadinessFindingSource.CATALOG
    assert report.findings[0].source_finding_id == (
        "system-system-nav-001-missing-model-missing-model"
    )


def test_registry_readiness_is_limited_when_catalog_has_only_warnings() -> None:
    system = RegisteredSystem(
        system_id="system-nav-001",
        name="Navigation assurance system",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.UNDER_REVIEW,
        risk_tier=RegistryRiskTier.LOW,
        mission_thread_ids=("mission-thread-nav",),
    )
    report = RegistryLayerReadinessEvaluator(evidence_bundles=()).evaluate(
        RegistryCatalog(systems=(system,))
    )

    assert report.decision is RegistryReadinessDecision.LIMITED
    assert not report.is_complete()
    assert report.blocker_count == 0
    assert report.warning_count == 1
    assert report.findings[0].severity is RegistryReadinessFindingSeverity.WARNING


def test_registry_readiness_is_limited_when_evidence_has_hash_warnings() -> None:
    unhashed_bundle = EvidenceBundle(
        bundle_id="ev-model-nav-001",
        case_id="case-nav-001",
        records=(
            EvidenceRecord(
                evidence_id="record-ev-model-nav-001",
                kind="registry-readiness",
                source="unit-test",
                payload={"supports": "ev-model-nav-001"},
                status=EvidenceStatus.ACCEPTED,
            ),
        ),
    )
    catalog = RegistryCatalog(models=(_approved_model(),))
    report = RegistryLayerReadinessEvaluator(evidence_bundles=(unhashed_bundle,)).evaluate(catalog)

    assert report.decision is RegistryReadinessDecision.LIMITED
    assert report.blocker_count == 0
    assert report.warning_count == 2
    assert {finding.source for finding in report.findings} == {
        RegistryReadinessFindingSource.EVIDENCE
    }


def test_registry_readiness_finding_validates_required_fields() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        RegistryReadinessFinding(
            finding_id="bad-finding",
            severity=RegistryReadinessFindingSeverity.BLOCKER,
            source=RegistryReadinessFindingSource.READINESS,
            message="",
            subject_id="registry-layer",
            subject_type="capability",
        )

    with pytest.raises(ContractValueError, match="blank source finding ID"):
        RegistryReadinessFinding(
            finding_id="bad-finding",
            severity=RegistryReadinessFindingSeverity.BLOCKER,
            source=RegistryReadinessFindingSource.READINESS,
            message="Bad finding.",
            subject_id="registry-layer",
            subject_type="capability",
            source_finding_id="",
        )
