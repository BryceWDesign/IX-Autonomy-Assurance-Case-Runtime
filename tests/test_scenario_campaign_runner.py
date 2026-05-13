from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import (
    AutonomyDecisionType,
    ContractValueError,
    EvidenceStatus,
    HazardSeverity,
    RuntimeAuthorityState,
    VerificationResult,
)
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
from ix_autonomy_assurance_case_runtime.safety_gate import RuntimeTelemetry
from ix_autonomy_assurance_case_runtime.scenario_campaign_runner import (
    ScenarioCampaignRunDecision,
    ScenarioCampaignRunInput,
    ScenarioCampaignRunner,
)
from ix_autonomy_assurance_case_runtime.scenario_campaigns import (
    ScenarioCampaign,
    ScenarioCampaignAcceptanceThreshold,
    ScenarioCampaignObjective,
    ScenarioCampaignScenario,
    ScenarioCampaignScenarioRole,
    ScenarioCampaignStatus,
    ScenarioCampaignTag,
)
from ix_autonomy_assurance_case_runtime.scenarios import (
    AcceptanceCriterion,
    AutonomyFunction,
    ExpectedSafeBehavior,
    MissionThread,
    OperatingCondition,
    OperationalContext,
    Scenario,
    ScenarioCatalog,
    Stressor,
)


def _catalog() -> ScenarioCatalog:
    return ScenarioCatalog(
        operational_contexts=(
            OperationalContext(
                context_id="CTX-001",
                name="Degraded navigation test range",
                environment="controlled autonomy range",
                mission_phase="route execution",
                description="Autonomy is evaluated under degraded navigation telemetry.",
            ),
        ),
        autonomy_functions=(
            AutonomyFunction(
                function_id="AF-001",
                name="Autonomous route manager",
                description="Manages bounded route execution.",
                input_signals=("navigation_confidence",),
                output_actions=("continue_route", "enter_safe_hold"),
            ),
        ),
        operating_conditions=(
            OperatingCondition(
                condition_id="COND-001",
                name="Navigation confidence available",
                description="Navigation confidence telemetry is evaluated.",
                telemetry_key="navigation_confidence",
                expected_range="0.0..1.0",
            ),
        ),
        stressors=(
            Stressor(
                stressor_id="STR-001",
                name="Navigation confidence degradation",
                description="Navigation confidence drops below the safe operating threshold.",
                severity=HazardSeverity.CRITICAL,
                affected_capabilities=("navigation",),
                trigger_condition="navigation_confidence < 0.70",
            ),
        ),
        expected_behaviors=(
            ExpectedSafeBehavior(
                behavior_id="BEH-001",
                description="Critical navigation degradation forces safe-hold.",
                required_decision=AutonomyDecisionType.SAFE_HOLD,
                required_authority_state=RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
                rationale="Critical navigation uncertainty must block nominal autonomy.",
            ),
        ),
        acceptance_criteria=(
            AcceptanceCriterion(
                criterion_id="AC-001",
                statement="Safe-hold is emitted for critical navigation degradation.",
                measurement="runtime_decision",
                expected_result="safe_hold",
            ),
        ),
        mission_threads=(
            MissionThread(
                mission_thread_id="MT-001",
                name="Degraded navigation mission thread",
                objective="Keep autonomy bounded during degraded navigation.",
                operational_context_id="CTX-001",
                autonomy_function_ids=("AF-001",),
                scenario_ids=("SCN-001",),
                requirement_ids=("REQ-NAV-001",),
                hazard_ids=("HZ-NAV-001",),
            ),
        ),
        scenarios=(
            Scenario(
                scenario_id="SCN-001",
                mission_thread_id="MT-001",
                title="Critical navigation drift triggers safe-hold",
                description="Inject navigation degradation and verify constrained behavior.",
                operational_context_id="CTX-001",
                autonomy_function_id="AF-001",
                operating_condition_ids=("COND-001",),
                stressor_ids=("STR-001",),
                expected_behavior_id="BEH-001",
                acceptance_criterion_ids=("AC-001",),
                hazard_ids=("HZ-NAV-001",),
                evidence_ids=("EV-SCN-001",),
            ),
        ),
    )


def _campaign(
    *,
    status: ScenarioCampaignStatus = ScenarioCampaignStatus.READY_FOR_RUN,
    minimum_runs: int = 1,
    maximum_failed_runs: int = 0,
) -> ScenarioCampaign:
    return ScenarioCampaign(
        campaign_id="campaign-degraded-nav",
        name="Degraded navigation campaign",
        purpose="Validate bounded autonomy under critical navigation degradation.",
        status=status,
        mission_thread_id="MT-001",
        objectives=(
            ScenarioCampaignObjective(
                objective_id="objective-safe-hold",
                statement="Prove critical navigation degradation causes safe-hold.",
                success_criteria=("Every run emits safe-hold evidence.",),
                requirement_ids=("REQ-NAV-001",),
                hazard_ids=("HZ-NAV-001",),
            ),
        ),
        scenarios=(
            ScenarioCampaignScenario(
                campaign_scenario_id="campaign-scenario-degraded-nav",
                scenario_id="SCN-001",
                role=ScenarioCampaignScenarioRole.ADVERSARIAL_PROBE,
                expected_result=VerificationResult.PASS,
                minimum_runs=minimum_runs,
                tags=(ScenarioCampaignTag.ADVERSARIAL,),
                requirement_ids=("REQ-NAV-001",),
                hazard_ids=("HZ-NAV-001",),
                evidence_bundle_ids=("ev-campaign-scenario-001",),
            ),
        ),
        acceptance_threshold=ScenarioCampaignAcceptanceThreshold(
            threshold_id="threshold-campaign",
            minimum_pass_rate=1.0,
            maximum_failed_runs=maximum_failed_runs,
        ),
        tags=(ScenarioCampaignTag.ADVERSARIAL,),
        evidence_bundle_ids=("ev-campaign-plan-001",),
    )


def _bundle(bundle_id: str) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=bundle_id,
        case_id="CASE-001",
        records=(
            EvidenceRecord(
                evidence_id=f"record-{bundle_id}",
                kind="scenario-campaign",
                source="unit-test",
                payload={"bundle_id": bundle_id},
                status=EvidenceStatus.ACCEPTED,
            ),
        ),
    ).with_computed_hashes()


def _bundles() -> tuple[EvidenceBundle, ...]:
    return (_bundle("ev-campaign-plan-001"), _bundle("ev-campaign-scenario-001"))


def _run_input(
    *,
    telemetry: RuntimeTelemetry | None = None,
) -> ScenarioCampaignRunInput:
    return ScenarioCampaignRunInput(
        campaign_run_id="CAMPAIGN-RUN-001",
        case_id="CASE-001",
        campaign_id="campaign-degraded-nav",
        telemetry_by_scenario_id={
            "SCN-001": telemetry
            or RuntimeTelemetry(values={"navigation_confidence": 0.62}),
        },
        operator_id="operator-001",
        notes=("local deterministic campaign execution",),
    )


def test_campaign_runner_accepts_valid_campaign_and_hashes_evidence() -> None:
    report = ScenarioCampaignRunner().run(
        campaign=_campaign(minimum_runs=2),
        scenario_catalog=_catalog(),
        run_input=_run_input(),
        evidence_bundles=_bundles(),
    )

    assert report.decision is ScenarioCampaignRunDecision.ACCEPTED
    assert report.is_accepted()
    assert report.total_count == 2
    assert report.pass_count == 2
    assert report.fail_count == 0
    assert report.inconclusive_count == 0
    assert report.scenario_result_for_run_id("CAMPAIGN-RUN-001-SCN-001-1") is not None
    assert report.evidence_bundle.bundle_hash is not None
    assert report.evidence_bundle.validate_integrity().is_valid
    assert report.summary() == (
        "scenario-campaign-run: accepted (2 pass, 0 fail, 0 inconclusive, total=2)"
    )


def test_campaign_runner_fails_threshold_when_scenario_result_fails() -> None:
    report = ScenarioCampaignRunner().run(
        campaign=_campaign(),
        scenario_catalog=_catalog(),
        run_input=_run_input(telemetry=RuntimeTelemetry(values={"navigation_confidence": 0.98})),
        evidence_bundles=_bundles(),
    )

    assert report.decision is ScenarioCampaignRunDecision.FAILED
    assert report.requires_follow_up()
    assert report.failed_scenario_ids() == ("SCN-001",)
    assert report.pass_count == 0
    assert report.fail_count == 1
    assert report.is_accepted() is False


def test_campaign_runner_blocks_validation_failures_before_execution() -> None:
    report = ScenarioCampaignRunner().run(
        campaign=_campaign(status=ScenarioCampaignStatus.DRAFT),
        scenario_catalog=_catalog(),
        run_input=_run_input(),
        evidence_bundles=_bundles(),
    )

    assert report.decision is ScenarioCampaignRunDecision.BLOCKED
    assert report.validation_report.blocker_count == 1
    assert report.total_count == 0
    assert report.evidence_bundle.validate_integrity().is_valid


def test_campaign_runner_blocks_missing_telemetry_before_execution() -> None:
    run_input = ScenarioCampaignRunInput(
        campaign_run_id="CAMPAIGN-RUN-001",
        case_id="CASE-001",
        campaign_id="campaign-degraded-nav",
        telemetry_by_scenario_id={"SCN-OTHER": RuntimeTelemetry(values={})},
    )

    report = ScenarioCampaignRunner().run(
        campaign=_campaign(),
        scenario_catalog=_catalog(),
        run_input=run_input,
        evidence_bundles=_bundles(),
    )

    assert report.decision is ScenarioCampaignRunDecision.BLOCKED
    assert "missing telemetry" in report.rationale
    assert report.total_count == 0


def test_campaign_runner_evidence_payload_is_json_compatible_and_complete() -> None:
    report = ScenarioCampaignRunner().run(
        campaign=_campaign(),
        scenario_catalog=_catalog(),
        run_input=_run_input(),
        evidence_bundles=_bundles(),
    )
    payload = report.to_evidence_payload()

    assert payload["campaign_run_id"] == "CAMPAIGN-RUN-001"
    assert payload["campaign_id"] == "campaign-degraded-nav"
    assert payload["decision"] == "accepted"
    assert payload["pass_count"] == 1
    assert payload["validation_blocker_count"] == 0
    assert payload["scenario_results"] == [
        {
            "authority_state": "emergency_safe_hold",
            "decision": "safe_hold",
            "evidence_bundle_id": "BND-CAMPAIGN-RUN-001-SCN-001-1",
            "operator_review_required": True,
            "run_id": "CAMPAIGN-RUN-001-SCN-001-1",
            "scenario_id": "SCN-001",
            "verification_result": "pass",
        }
    ]


def test_campaign_runner_rejects_mismatched_campaign_id() -> None:
    run_input = ScenarioCampaignRunInput(
        campaign_run_id="CAMPAIGN-RUN-001",
        case_id="CASE-001",
        campaign_id="campaign-other",
        telemetry_by_scenario_id={"SCN-001": RuntimeTelemetry(values={})},
    )

    with pytest.raises(ContractValueError, match="campaign_id must match"):
        ScenarioCampaignRunner().run(
            campaign=_campaign(),
            scenario_catalog=_catalog(),
            run_input=run_input,
            evidence_bundles=_bundles(),
        )


def test_campaign_run_input_requires_telemetry_and_unique_notes() -> None:
    with pytest.raises(ContractValueError, match="telemetry_by_scenario_id must not be empty"):
        ScenarioCampaignRunInput(
            campaign_run_id="CAMPAIGN-RUN-001",
            case_id="CASE-001",
            campaign_id="campaign-degraded-nav",
            telemetry_by_scenario_id={},
        )

    with pytest.raises(ContractValueError, match="notes must not contain duplicate"):
        ScenarioCampaignRunInput(
            campaign_run_id="CAMPAIGN-RUN-001",
            case_id="CASE-001",
            campaign_id="campaign-degraded-nav",
            telemetry_by_scenario_id={"SCN-001": RuntimeTelemetry(values={})},
            notes=("same", "same"),
        )
