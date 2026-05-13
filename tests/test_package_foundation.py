from __future__ import annotations

import ix_autonomy_assurance_case_runtime as ix
from ix_autonomy_assurance_case_runtime import (
    PROJECT_NAME,
    ProjectIdentity,
    __version__,
    get_project_identity,
)


def test_project_identity_is_canonical() -> None:
    identity = get_project_identity()

    assert isinstance(identity, ProjectIdentity)
    assert identity.repository_name == "IX-Autonomy-Assurance-Case-Runtime"
    assert identity.repository_name == PROJECT_NAME
    assert identity.package_name == "ix-autonomy-assurance-case-runtime"
    assert identity.license_spdx == "Apache-2.0"
    assert identity.python_package == "ix_autonomy_assurance_case_runtime"


def test_project_identity_mission_states_runtime_scope() -> None:
    identity = get_project_identity()

    assert "Trusted Autonomy T&E" in identity.mission
    assert "assurance-case runtime" in identity.mission
    assert "evidence-backed" in identity.mission


def test_package_version_is_initial_alpha_version() -> None:
    assert __version__ == "0.1.0"


def test_scenario_campaign_public_exports_are_available() -> None:
    expected_exports = (
        "SCENARIO_CAMPAIGN_CAPABILITY_ID",
        "ScenarioCampaign",
        "ScenarioCampaignAcceptanceThreshold",
        "ScenarioCampaignCatalog",
        "ScenarioCampaignFindingSeverity",
        "ScenarioCampaignFindingSource",
        "ScenarioCampaignLayerReadinessEvaluator",
        "ScenarioCampaignLayerReadinessReport",
        "ScenarioCampaignObjective",
        "ScenarioCampaignReadinessDecision",
        "ScenarioCampaignReadinessFinding",
        "ScenarioCampaignReadinessFindingSeverity",
        "ScenarioCampaignReadinessFindingSource",
        "ScenarioCampaignRunDecision",
        "ScenarioCampaignRunInput",
        "ScenarioCampaignRunReport",
        "ScenarioCampaignRunner",
        "ScenarioCampaignScenario",
        "ScenarioCampaignScenarioRole",
        "ScenarioCampaignStatus",
        "ScenarioCampaignStopRule",
        "ScenarioCampaignTag",
        "ScenarioCampaignValidationFinding",
        "ScenarioCampaignValidationReport",
        "ScenarioCampaignValidator",
    )

    for export_name in expected_exports:
        assert export_name in ix.__all__
        assert hasattr(ix, export_name)
