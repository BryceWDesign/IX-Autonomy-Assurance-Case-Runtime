from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, VerificationResult
from ix_autonomy_assurance_case_runtime.scenario_campaigns import (
    ScenarioCampaign,
    ScenarioCampaignAcceptanceThreshold,
    ScenarioCampaignCatalog,
    ScenarioCampaignObjective,
    ScenarioCampaignScenario,
    ScenarioCampaignScenarioRole,
    ScenarioCampaignStatus,
    ScenarioCampaignStopRule,
    ScenarioCampaignTag,
)


def _objective() -> ScenarioCampaignObjective:
    return ScenarioCampaignObjective(
        objective_id="objective-trace-runtime-decision",
        statement="Prove runtime decisions remain bounded under degraded navigation.",
        success_criteria=(
            "Every scenario produces deterministic evidence.",
            "Restrictive behavior is preserved under degraded inputs.",
        ),
        requirement_ids=("REQ-AUTO-001",),
        hazard_ids=("HAZ-NAV-001",),
    )


def _threshold() -> ScenarioCampaignAcceptanceThreshold:
    return ScenarioCampaignAcceptanceThreshold(
        threshold_id="threshold-zero-false-acceptance",
        minimum_pass_rate=1.0,
        maximum_failed_runs=0,
        maximum_inconclusive_runs=0,
    )


def _baseline_scenario() -> ScenarioCampaignScenario:
    return ScenarioCampaignScenario(
        campaign_scenario_id="campaign-scenario-baseline-nav",
        scenario_id="scenario-baseline-nav",
        role=ScenarioCampaignScenarioRole.BASELINE,
        expected_result=VerificationResult.PASS,
        tags=(ScenarioCampaignTag.BASELINE, ScenarioCampaignTag.REGRESSION),
        requirement_ids=("REQ-AUTO-001",),
        evidence_bundle_ids=("ev-baseline-nav",),
    )


def _adversarial_scenario() -> ScenarioCampaignScenario:
    return ScenarioCampaignScenario(
        campaign_scenario_id="campaign-scenario-spoofed-nav",
        scenario_id="scenario-spoofed-nav",
        role=ScenarioCampaignScenarioRole.ADVERSARIAL_PROBE,
        expected_result=VerificationResult.PASS,
        minimum_runs=2,
        tags=(
            ScenarioCampaignTag.ADVERSARIAL,
            ScenarioCampaignTag.SOURCE_TRUST,
            ScenarioCampaignTag.TELEMETRY_REPLAY,
        ),
        requirement_ids=("REQ-AUTO-001",),
        hazard_ids=("HAZ-NAV-001",),
        evidence_bundle_ids=("ev-spoofed-nav",),
        replay_record_ids=("replay-spoofed-nav-001",),
    )


def _campaign() -> ScenarioCampaign:
    return ScenarioCampaign(
        campaign_id="campaign-degraded-nav-adversarial",
        name="Degraded navigation adversarial campaign",
        purpose="Exercise traceable runtime decisions across baseline and spoofed telemetry.",
        status=ScenarioCampaignStatus.READY_FOR_RUN,
        mission_thread_id="mission-thread-nav",
        objectives=(_objective(),),
        scenarios=(_baseline_scenario(), _adversarial_scenario()),
        acceptance_threshold=_threshold(),
        tags=(
            ScenarioCampaignTag.BASELINE,
            ScenarioCampaignTag.ADVERSARIAL,
            ScenarioCampaignTag.REGRESSION,
        ),
        stop_rules=(
            ScenarioCampaignStopRule(
                stop_rule_id="stop-on-safe-hold-miss",
                description="Stop if expected safe hold behavior is not observed.",
                trigger_condition="expected safe hold is missed",
                evidence_bundle_ids=("ev-stop-rule",),
            ),
        ),
        evidence_bundle_ids=("ev-campaign-plan",),
        owner="assurance-lab",
        version="2026.05",
        notes=("Local prototype campaign only; no certification claim.",),
    )


def test_campaign_records_trace_objectives_scenarios_evidence_and_replay() -> None:
    campaign = _campaign()

    assert campaign.can_execute_locally()
    assert campaign.has_adversarial_coverage()
    assert campaign.has_non_nominal_coverage()
    assert campaign.scenario_ids() == ("scenario-baseline-nav", "scenario-spoofed-nav")
    assert campaign.adversarial_scenario_ids() == ("scenario-spoofed-nav",)
    assert campaign.required_requirement_ids() == ("REQ-AUTO-001",)
    assert campaign.required_hazard_ids() == ("HAZ-NAV-001",)
    assert campaign.required_replay_record_ids() == ("replay-spoofed-nav-001",)
    assert campaign.required_evidence_bundle_ids() == (
        "ev-campaign-plan",
        "ev-baseline-nav",
        "ev-spoofed-nav",
        "ev-stop-rule",
    )


def test_campaign_threshold_accepts_only_when_counts_meet_policy() -> None:
    threshold = _threshold()

    assert threshold.accepts_counts(
        pass_count=3,
        fail_count=0,
        inconclusive_count=0,
        total_count=3,
    )
    assert not threshold.accepts_counts(
        pass_count=2,
        fail_count=1,
        inconclusive_count=0,
        total_count=3,
    )

    with pytest.raises(ContractValueError, match="counts must add up"):
        threshold.accepts_counts(
            pass_count=2,
            fail_count=0,
            inconclusive_count=0,
            total_count=3,
        )


def test_non_nominal_scenario_requires_hazard_traceability() -> None:
    with pytest.raises(ContractValueError, match="Non-nominal campaign scenarios"):
        ScenarioCampaignScenario(
            campaign_scenario_id="campaign-scenario-bad-adversarial",
            scenario_id="scenario-bad-adversarial",
            role=ScenarioCampaignScenarioRole.ADVERSARIAL_PROBE,
            expected_result=VerificationResult.PASS,
            tags=(ScenarioCampaignTag.ADVERSARIAL,),
            requirement_ids=("REQ-AUTO-001",),
        )


def test_scenario_role_requires_matching_campaign_tag() -> None:
    with pytest.raises(ContractValueError, match="requires tag"):
        ScenarioCampaignScenario(
            campaign_scenario_id="campaign-scenario-bad-role-tag",
            scenario_id="scenario-bad-role-tag",
            role=ScenarioCampaignScenarioRole.STRESS,
            expected_result=VerificationResult.PASS,
            tags=(ScenarioCampaignTag.ADVERSARIAL,),
            requirement_ids=("REQ-AUTO-001",),
            hazard_ids=("HAZ-NAV-001",),
        )


def test_campaign_rejects_duplicate_scenario_ids() -> None:
    duplicate = ScenarioCampaignScenario(
        campaign_scenario_id="campaign-scenario-duplicate-entry",
        scenario_id="scenario-baseline-nav",
        role=ScenarioCampaignScenarioRole.BASELINE,
        expected_result=VerificationResult.PASS,
        tags=(ScenarioCampaignTag.BASELINE,),
        requirement_ids=("REQ-AUTO-001",),
    )

    with pytest.raises(ContractValueError, match="scenario IDs must not duplicate"):
        ScenarioCampaign(
            campaign_id="campaign-duplicate-scenario",
            name="Duplicate scenario campaign",
            purpose="Prove duplicate scenario IDs are rejected.",
            status=ScenarioCampaignStatus.READY_FOR_RUN,
            mission_thread_id="mission-thread-nav",
            objectives=(_objective(),),
            scenarios=(_baseline_scenario(), duplicate),
            acceptance_threshold=_threshold(),
            tags=(ScenarioCampaignTag.BASELINE,),
        )


def test_campaign_rejects_missing_campaign_level_role_tags() -> None:
    with pytest.raises(ContractValueError, match="tags missing required role coverage"):
        ScenarioCampaign(
            campaign_id="campaign-missing-adversarial-tag",
            name="Missing adversarial campaign tag",
            purpose="Prove campaign-level tags cover scenario roles.",
            status=ScenarioCampaignStatus.READY_FOR_RUN,
            mission_thread_id="mission-thread-nav",
            objectives=(_objective(),),
            scenarios=(_baseline_scenario(), _adversarial_scenario()),
            acceptance_threshold=_threshold(),
            tags=(ScenarioCampaignTag.BASELINE,),
        )


def test_campaign_catalog_indexes_executable_and_adversarial_campaigns() -> None:
    campaign = _campaign()
    catalog = ScenarioCampaignCatalog(campaigns=(campaign,))

    assert catalog.campaign_by_id("campaign-degraded-nav-adversarial") == campaign
    assert catalog.campaign_by_id("missing-campaign") is None
    assert catalog.executable_campaign_ids() == ("campaign-degraded-nav-adversarial",)
    assert catalog.adversarial_campaign_ids() == ("campaign-degraded-nav-adversarial",)

    with pytest.raises(ContractValueError, match="must not duplicate campaign IDs"):
        ScenarioCampaignCatalog(campaigns=(campaign, campaign))


def test_campaign_status_helpers_are_strict() -> None:
    assert ScenarioCampaignStatus.READY_FOR_RUN.can_execute()
    assert ScenarioCampaignStatus.RUNNING.can_execute()
    assert not ScenarioCampaignStatus.DRAFT.can_execute()
    assert ScenarioCampaignStatus.COMPLETED.is_terminal()
    assert ScenarioCampaignTag.ADVERSARIAL.is_non_nominal()
    assert not ScenarioCampaignTag.BASELINE.is_non_nominal()
