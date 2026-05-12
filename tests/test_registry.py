from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime import (
    DeploymentEnvironment,
    RegisteredDeployment,
    RegisteredModel,
    RegisteredSystem,
    RegisteredUseCase,
    RegisteredUseCategory,
    RegistryLifecycleState,
    RegistryRiskTier,
    RuntimeAuthorityState,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError


def test_registered_model_preserves_lifecycle_owner_risk_and_use_limits() -> None:
    model = RegisteredModel(
        model_id="model-nav-001",
        name="Navigation Decision Support Model",
        version="2026.05",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.UNDER_REVIEW,
        risk_tier=RegistryRiskTier.HIGH,
        intended_uses=("navigation anomaly triage",),
        prohibited_uses=("unreviewed lethal targeting", "unsupervised public release"),
    )

    assert model.model_id == "model-nav-001"
    assert model.requires_human_review()
    assert model.lifecycle_state.blocks_runtime_use()
    assert RegistryRiskTier.HIGH.requires_evidence_for_approval()


def test_approved_registered_model_requires_evidence_bundle_reference() -> None:
    with pytest.raises(ContractValueError, match="approved registered models"):
        RegisteredModel(
            model_id="model-nav-001",
            name="Navigation Decision Support Model",
            version="2026.05",
            owner="Assurance Lab",
            lifecycle_state=RegistryLifecycleState.APPROVED,
            risk_tier=RegistryRiskTier.MODERATE,
            intended_uses=("navigation anomaly triage",),
            prohibited_uses=("unsupervised public release",),
        )

    model = RegisteredModel(
        model_id="model-nav-001",
        name="Navigation Decision Support Model",
        version="2026.05",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.MODERATE,
        intended_uses=("navigation anomaly triage",),
        prohibited_uses=("unsupervised public release",),
        evidence_bundle_ids=("ev-nav-model-001",),
    )

    assert model.lifecycle_state.can_support_acceptance()


def test_registered_system_requires_assurance_case_before_approval() -> None:
    with pytest.raises(ContractValueError, match="approved registered systems"):
        RegisteredSystem(
            system_id="system-nav-001",
            name="Navigation Assurance System",
            owner="Assurance Lab",
            lifecycle_state=RegistryLifecycleState.APPROVED,
            risk_tier=RegistryRiskTier.HIGH,
            mission_thread_ids=("mission-thread-nav",),
            model_ids=("model-nav-001",),
        )

    system = RegisteredSystem(
        system_id="system-nav-001",
        name="Navigation Assurance System",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.HIGH,
        mission_thread_ids=("mission-thread-nav",),
        model_ids=("model-nav-001",),
        assurance_case_id="case-nav-001",
    )

    assert system.can_reference_models()
    assert system.assurance_case_id == "case-nav-001"


def test_registered_use_case_links_mission_need_requirements_and_prohibited_conditions() -> None:
    use_case = RegisteredUseCase(
        use_case_id="use-case-nav-001",
        name="Autonomy navigation confidence monitor",
        system_id="system-nav-001",
        category=RegisteredUseCategory.SAFETY_MONITORING,
        lifecycle_state=RegistryLifecycleState.UNDER_REVIEW,
        risk_tier=RegistryRiskTier.HIGH,
        mission_need_ids=("mn-nav-survivability",),
        requirement_ids=("req-nav-boundary", "req-human-authority"),
        prohibited_conditions=("unbounded autonomous maneuver",),
    )

    assert use_case.requires_authority_review()
    assert RegisteredUseCategory.TEST_AND_EVALUATION.is_consequential() is False
    assert RegisteredUseCategory.INTELLIGENCE_ANALYSIS.is_consequential()


def test_approved_registered_use_case_requires_evidence_bundle_reference() -> None:
    with pytest.raises(ContractValueError, match="approved registered use cases"):
        RegisteredUseCase(
            use_case_id="use-case-nav-001",
            name="Autonomy navigation confidence monitor",
            system_id="system-nav-001",
            category=RegisteredUseCategory.AUTONOMY_CONTROL,
            lifecycle_state=RegistryLifecycleState.APPROVED,
            risk_tier=RegistryRiskTier.CRITICAL,
            mission_need_ids=("mn-nav-survivability",),
            requirement_ids=("req-nav-boundary",),
            prohibited_conditions=("unbounded autonomous maneuver",),
        )


def test_registered_deployment_blocks_live_operation_without_strict_approval_state() -> None:
    with pytest.raises(ContractValueError, match="approved deployment lifecycle"):
        RegisteredDeployment(
            deployment_id="deploy-nav-001",
            system_id="system-nav-001",
            environment=DeploymentEnvironment.OPERATIONAL_TEST,
            lifecycle_state=RegistryLifecycleState.UNDER_REVIEW,
            authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
            scenario_ids=("scenario-degraded-nav",),
            evidence_bundle_ids=("ev-deploy-nav-001",),
            telemetry_source_ids=("telemetry-nav-sim",),
            approved_for_live_operation=True,
        )

    with pytest.raises(ContractValueError, match="blocking authority state"):
        RegisteredDeployment(
            deployment_id="deploy-nav-001",
            system_id="system-nav-001",
            environment=DeploymentEnvironment.OPERATIONAL_TEST,
            lifecycle_state=RegistryLifecycleState.APPROVED,
            authority_state=RuntimeAuthorityState.DENIED,
            scenario_ids=("scenario-degraded-nav",),
            evidence_bundle_ids=("ev-deploy-nav-001",),
            telemetry_source_ids=("telemetry-nav-sim",),
            approved_for_live_operation=True,
        )


def test_registered_deployment_requires_telemetry_sources_for_operational_live_use() -> None:
    with pytest.raises(ContractValueError, match="requires telemetry sources"):
        RegisteredDeployment(
            deployment_id="deploy-nav-001",
            system_id="system-nav-001",
            environment=DeploymentEnvironment.CONTROLLED_FIELD,
            lifecycle_state=RegistryLifecycleState.APPROVED,
            authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
            scenario_ids=("scenario-degraded-nav",),
            evidence_bundle_ids=("ev-deploy-nav-001",),
            approved_for_live_operation=True,
        )

    deployment = RegisteredDeployment(
        deployment_id="deploy-nav-001",
        system_id="system-nav-001",
        environment=DeploymentEnvironment.CONTROLLED_FIELD,
        lifecycle_state=RegistryLifecycleState.APPROVED,
        authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
        scenario_ids=("scenario-degraded-nav",),
        evidence_bundle_ids=("ev-deploy-nav-001",),
        telemetry_source_ids=("telemetry-nav-sim",),
        approved_for_live_operation=True,
    )

    assert not deployment.needs_revalidation_before_use()
    assert DeploymentEnvironment.SIMULATION.needs_operational_evidence() is False


def test_registry_records_reject_blank_and_duplicate_identity_data() -> None:
    with pytest.raises(ContractValueError, match="must not contain spaces"):
        RegisteredModel(
            model_id="model nav 001",
            name="Navigation Decision Support Model",
            version="2026.05",
            owner="Assurance Lab",
            lifecycle_state=RegistryLifecycleState.DRAFT,
            risk_tier=RegistryRiskTier.LOW,
            intended_uses=("navigation anomaly triage",),
            prohibited_uses=("unsupervised public release",),
        )

    with pytest.raises(ContractValueError, match="duplicate values"):
        RegisteredSystem(
            system_id="system-nav-001",
            name="Navigation Assurance System",
            owner="Assurance Lab",
            lifecycle_state=RegistryLifecycleState.DRAFT,
            risk_tier=RegistryRiskTier.LOW,
            mission_thread_ids=("mission-thread-nav", "mission-thread-nav"),
        )
