from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime import (
    DeploymentEnvironment,
    RegisteredDeployment,
    RegisteredModel,
    RegisteredSystem,
    RegisteredUseCase,
    RegisteredUseCategory,
    RegistryCatalog,
    RegistryFindingSeverity,
    RegistryLifecycleState,
    RegistryReferenceType,
    RegistryRiskTier,
    RegistryValidationFinding,
    RuntimeAuthorityState,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError


def _approved_model(model_id: str = "model-nav-001") -> RegisteredModel:
    return RegisteredModel(
        model_id=model_id,
        name="Navigation decision model",
        version="2026.05",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.HIGH,
        intended_uses=("navigation anomaly triage",),
        prohibited_uses=("unbounded autonomous maneuver",),
        evidence_bundle_ids=("ev-model-nav-001",),
    )


def _approved_system(system_id: str = "system-nav-001") -> RegisteredSystem:
    return RegisteredSystem(
        system_id=system_id,
        name="Navigation assurance system",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.HIGH,
        mission_thread_ids=("mission-thread-nav",),
        model_ids=("model-nav-001",),
        assurance_case_id="case-nav-001",
    )


def _approved_use_case(system_id: str = "system-nav-001") -> RegisteredUseCase:
    return RegisteredUseCase(
        use_case_id="use-case-nav-001",
        name="Navigation confidence monitor",
        system_id=system_id,
        category=RegisteredUseCategory.SAFETY_MONITORING,
        lifecycle_state=RegistryLifecycleState.APPROVED,
        risk_tier=RegistryRiskTier.HIGH,
        mission_need_ids=("mn-nav-survivability",),
        requirement_ids=("req-nav-boundary",),
        prohibited_conditions=("unbounded autonomous maneuver",),
        evidence_bundle_ids=("ev-use-case-nav-001",),
    )


def _approved_deployment(system_id: str = "system-nav-001") -> RegisteredDeployment:
    return RegisteredDeployment(
        deployment_id="deploy-nav-001",
        system_id=system_id,
        environment=DeploymentEnvironment.OPERATIONAL_TEST,
        lifecycle_state=RegistryLifecycleState.APPROVED,
        authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
        scenario_ids=("scenario-degraded-nav",),
        evidence_bundle_ids=("ev-deploy-nav-001",),
        telemetry_source_ids=("telemetry-nav-sim",),
        approved_for_live_operation=True,
    )


def test_registry_catalog_accepts_valid_cross_referenced_records() -> None:
    catalog = RegistryCatalog(
        models=(_approved_model(),),
        systems=(_approved_system(),),
        use_cases=(_approved_use_case(),),
        deployments=(_approved_deployment(),),
    )

    report = catalog.validate()

    assert report.is_acceptance_ready()
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "registry: 1 model(s), 1 system(s), 1 use case(s), 1 deployment(s), "
        "0 blocker(s), 0 warning(s)"
    )
    assert catalog.model_by_id("model-nav-001") == _approved_model()
    assert catalog.system_by_id("system-nav-001") == _approved_system()
    assert catalog.use_case_by_id("use-case-nav-001") == _approved_use_case()
    assert catalog.deployment_by_id("deploy-nav-001") == _approved_deployment()
    assert catalog.approved_use_cases_for_system("system-nav-001") == (_approved_use_case(),)


def test_registry_catalog_rejects_duplicate_record_ids() -> None:
    with pytest.raises(ContractValueError, match="Duplicate registry ID"):
        RegistryCatalog(models=(_approved_model(), _approved_model()))


def test_registry_catalog_reports_missing_system_model_reference_as_blocker() -> None:
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

    report = catalog.validate()

    assert not report.is_acceptance_ready()
    assert report.blocker_count == 1
    finding = report.findings_for_subject("system-nav-001")[0]
    assert finding.finding_id == "system-system-nav-001-missing-model-missing-model"
    assert finding.reference_id == "missing-model"
    assert finding.reference_type is RegistryReferenceType.MODEL


def test_registry_catalog_blocks_approved_system_using_unapproved_model() -> None:
    model = RegisteredModel(
        model_id="model-nav-001",
        name="Navigation decision model",
        version="2026.05",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.UNDER_REVIEW,
        risk_tier=RegistryRiskTier.HIGH,
        intended_uses=("navigation anomaly triage",),
        prohibited_uses=("unbounded autonomous maneuver",),
    )
    catalog = RegistryCatalog(models=(model,), systems=(_approved_system(),))

    report = catalog.validate()

    assert report.blocker_count == 1
    assert report.findings[0].finding_id == (
        "approved-system-system-nav-001-uses-unapproved-model-model-nav-001"
    )
    assert report.findings[0].severity is RegistryFindingSeverity.BLOCKER


def test_registry_catalog_reports_missing_use_case_system_reference() -> None:
    catalog = RegistryCatalog(use_cases=(_approved_use_case(system_id="missing-system"),))

    report = catalog.validate()

    assert report.blocker_count == 1
    assert report.findings[0].finding_id == "use-case-use-case-nav-001-missing-system"
    assert report.findings[0].reference_type is RegistryReferenceType.SYSTEM


def test_registry_catalog_blocks_approved_use_case_for_unapproved_system() -> None:
    system = RegisteredSystem(
        system_id="system-nav-001",
        name="Navigation assurance system",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.UNDER_REVIEW,
        risk_tier=RegistryRiskTier.HIGH,
        mission_thread_ids=("mission-thread-nav",),
    )
    catalog = RegistryCatalog(systems=(system,), use_cases=(_approved_use_case(),))

    report = catalog.validate()

    assert report.blocker_count == 1
    finding_ids = {finding.finding_id for finding in report.findings}
    assert "approved-use-case-use-case-nav-001-uses-unapproved-system" in finding_ids


def test_registry_catalog_blocks_live_deployment_without_approved_use_case() -> None:
    catalog = RegistryCatalog(
        models=(_approved_model(),),
        systems=(_approved_system(),),
        deployments=(_approved_deployment(),),
    )

    report = catalog.validate()

    assert report.blocker_count == 1
    assert report.findings[0].finding_id == (
        "live-deployment-deploy-nav-001-has-no-approved-use-case"
    )


def test_registry_catalog_warns_on_empty_catalog_and_system_without_models() -> None:
    empty_report = RegistryCatalog().validate()

    assert empty_report.is_acceptance_ready()
    assert empty_report.warning_count == 1
    assert empty_report.findings[0].finding_id == "registry-catalog-empty"

    system = RegisteredSystem(
        system_id="system-nav-001",
        name="Navigation assurance system",
        owner="Assurance Lab",
        lifecycle_state=RegistryLifecycleState.UNDER_REVIEW,
        risk_tier=RegistryRiskTier.LOW,
        mission_thread_ids=("mission-thread-nav",),
    )
    system_report = RegistryCatalog(systems=(system,)).validate()

    assert system_report.warning_count == 1
    assert system_report.findings[0].finding_id == "system-system-nav-001-has-no-models"


def test_registry_validation_finding_requires_reference_id_and_type_pair() -> None:
    with pytest.raises(ContractValueError, match="must pair reference ID and reference type"):
        RegistryValidationFinding(
            finding_id="bad-reference",
            severity=RegistryFindingSeverity.BLOCKER,
            message="Bad reference.",
            subject_id="system-nav-001",
            subject_type=RegistryReferenceType.SYSTEM,
            reference_id="model-nav-001",
        )
