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
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.safety_gate import RuntimeTelemetry
from ix_autonomy_assurance_case_runtime.scenario_campaign_readiness import (
    ScenarioCampaignLayerReadinessEvaluator,
    ScenarioCampaignReadinessDecision,
    ScenarioCampaignReadinessFinding,
    ScenarioCampaignReadinessFindingSeverity,
    ScenarioCampaignReadinessFindingSource,
)
from ix_autonomy_assurance_case_runtime.scenario_campaign_runner import (
    ScenarioCampaignRunner,
    ScenarioCampaignRunInput,
    ScenarioCampaignRunReport,
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
    role: ScenarioCampaignScenarioRole = ScenarioCampaignScenarioRole.ADVERSARIAL_PROBE,
    tags: tuple[ScenarioCampaignTag, ...] = (ScenarioCampaignTag.ADVERSARIAL,),
    campaign_tags: tuple[ScenarioCampaignTag, ...] = (ScenarioCampaignTag.ADVERSARIAL,),
) -> ScenarioCampaign:
    return ScenarioCampaign(
        campaign_id="campaign-degraded-nav",
        name="Degraded navigation campaign",
        purpose="Validate bounded autonomy under critical navigation degradation.",
        status=ScenarioCampaignStatus.READY_FOR_RUN,
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
                role=role,
                expected_result=VerificationResult.PASS,
                tags=tags,
                requirement_ids=("REQ-NAV-001",),
                hazard_ids=("HZ-NAV-001",),
                evidence_bundle_ids=("ev-campaign-scenario-001",),
            ),
        ),
        acceptance_threshold=ScenarioCampaignAcceptanceThreshold(
            threshold_id="threshold-campaign",
            minimum_pass_rate=1.0,
        ),
        tags=campaign_tags,
        evidence_bundle_ids=("ev-campaign-plan-001",),
    )


def _bundle(bundle_id: str, *, hashed: bool = True) -> EvidenceBundle:
    bundle = EvidenceBundle(
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
    )
    if hashed:
        return bundle.with_computed_hashes()
    return bundle


def _bundles() -> tuple[EvidenceBundle, ...]:
    return (_bundle("ev-campaign-plan-001"), _bundle("ev-campaign-scenario-001"))


def _accepted_report(campaign: ScenarioCampaign | None = None) -> ScenarioCampaignRunReport:
    target_campaign = campaign or _campaign()
    return ScenarioCampaignRunner().run(
        campaign=target_campaign,
        scenario_catalog=_catalog(),
        run_input=ScenarioCampaignRunInput(
            campaign_run_id="CAMPAIGN-RUN-001",
            case_id="CASE-001",
            campaign_id=target_campaign.campaign_id,
            telemetry_by_scenario_id={
                "SCN-001": RuntimeTelemetry(values={"navigation_confidence": 0.62})
            },
            operator_id="operator-001",
        ),
        evidence_bundles=_bundles(),
    )


def _failed_report() -> ScenarioCampaignRunReport:
    campaign = _campaign()
    return ScenarioCampaignRunner().run(
        campaign=campaign,
        scenario_catalog=_catalog(),
        run_input=ScenarioCampaignRunInput(
            campaign_run_id="CAMPAIGN-RUN-001",
            case_id="CASE-001",
            campaign_id=campaign.campaign_id,
            telemetry_by_scenario_id={
                "SCN-001": RuntimeTelemetry(values={"navigation_confidence": 0.98})
            },
        ),
        evidence_bundles=_bundles(),
    )


def test_scenario_campaign_readiness_completes_accepted_adversarial_campaign() -> None:
    campaign = _campaign()
    report = ScenarioCampaignLayerReadinessEvaluator().evaluate(
        campaigns=(campaign,),
        run_reports=(_accepted_report(campaign),),
    )

    assert report.decision is ScenarioCampaignReadinessDecision.COMPLETE
    assert report.is_complete()
    assert report.completed_capability_ids() == ("scenario-campaign-runner",)
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "scenario-campaign-readiness: complete "
        "(1 campaign(s), 1 run report(s), 0 blocker(s), 0 warning(s), "
        "capability=scenario-campaign-runner)"
    )


def test_scenario_campaign_readiness_feeds_prototype_claim_gate() -> None:
    campaign = _campaign()
    report = ScenarioCampaignLayerReadinessEvaluator().evaluate(
        campaigns=(campaign,),
        run_reports=(_accepted_report(campaign),),
    )

    prototype_report = report.prototype_readiness_report(
        PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE,
        existing_completed_capability_ids=(
            "registry-layer",
            "policy-pack-engine",
            "framework-crosswalks",
            "signed-provenance",
            "telemetry-adapters",
        ),
    )

    assert prototype_report.decision is PrototypeReadinessDecision.BLOCK
    assert prototype_report.achieved_percent == 66
    assert prototype_report.completed_capability_ids == (
        "registry-layer",
        "policy-pack-engine",
        "framework-crosswalks",
        "signed-provenance",
        "telemetry-adapters",
        "scenario-campaign-runner",
    )
    assert "monitoring-incidents" in prototype_report.remaining_capability_ids


def test_scenario_campaign_readiness_blocks_missing_inputs() -> None:
    report = ScenarioCampaignLayerReadinessEvaluator().evaluate(campaigns=(), run_reports=())

    assert report.decision is ScenarioCampaignReadinessDecision.BLOCKED
    assert report.blocker_count == 2
    assert not report.is_complete()


def test_scenario_campaign_readiness_blocks_failed_run_report() -> None:
    campaign = _campaign()
    report = ScenarioCampaignLayerReadinessEvaluator().evaluate(
        campaigns=(campaign,),
        run_reports=(_failed_report(),),
    )

    assert report.decision is ScenarioCampaignReadinessDecision.BLOCKED
    assert any(
        finding.finding_id == "campaign-campaign-degraded-nav-no-accepted-run"
        for finding in report.findings_for_campaign("campaign-degraded-nav")
    )
    assert any(
        finding.finding_id == "run-CAMPAIGN-RUN-001-decision-failed"
        for finding in report.findings_for_run("CAMPAIGN-RUN-001")
    )


def test_scenario_campaign_readiness_blocks_unrun_campaign_scenario() -> None:
    campaign = _campaign()
    report = ScenarioCampaignLayerReadinessEvaluator().evaluate(
        campaigns=(campaign,),
        run_reports=(),
    )

    assert report.decision is ScenarioCampaignReadinessDecision.BLOCKED
    assert any(
        finding.finding_id == "campaign-campaign-degraded-nav-missing-run-report"
        for finding in report.findings_for_campaign("campaign-degraded-nav")
    )


def test_scenario_campaign_readiness_warns_without_explicit_adversarial_probe() -> None:
    campaign = _campaign(
        role=ScenarioCampaignScenarioRole.DEGRADED_MODE,
        tags=(ScenarioCampaignTag.DEGRADED_MODE,),
        campaign_tags=(ScenarioCampaignTag.DEGRADED_MODE,),
    )
    report = ScenarioCampaignLayerReadinessEvaluator().evaluate(
        campaigns=(campaign,),
        run_reports=(_accepted_report(campaign),),
    )

    assert report.decision is ScenarioCampaignReadinessDecision.LIMITED
    assert report.warning_count == 1
    assert report.findings[0].source is ScenarioCampaignReadinessFindingSource.READINESS


def test_scenario_campaign_readiness_warns_for_evidence_integrity_warnings() -> None:
    campaign = _campaign()
    accepted = _accepted_report(campaign)
    report_with_unhashed_evidence = ScenarioCampaignRunReport(
        campaign_run_id=accepted.campaign_run_id,
        case_id=accepted.case_id,
        campaign_id=accepted.campaign_id,
        decision=accepted.decision,
        validation_report=accepted.validation_report,
        scenario_results=accepted.scenario_results,
        evidence_bundle=_bundle("BND-CAMPAIGN-RUN-001", hashed=False),
        rationale=accepted.rationale,
    )

    readiness = ScenarioCampaignLayerReadinessEvaluator().evaluate(
        campaigns=(campaign,),
        run_reports=(report_with_unhashed_evidence,),
    )

    assert readiness.decision is ScenarioCampaignReadinessDecision.LIMITED
    assert readiness.warning_count == 2
    assert readiness.findings_for_evidence_bundle("BND-CAMPAIGN-RUN-001")


def test_scenario_campaign_readiness_rejects_duplicate_campaign_ids() -> None:
    campaign = _campaign()

    with pytest.raises(ContractValueError, match="Duplicate scenario campaign readiness"):
        ScenarioCampaignLayerReadinessEvaluator().evaluate(
            campaigns=(campaign, campaign),
            run_reports=(_accepted_report(campaign),),
        )


def test_scenario_campaign_readiness_finding_validates_optional_ids() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        ScenarioCampaignReadinessFinding(
            finding_id="finding-001",
            severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
            source=ScenarioCampaignReadinessFindingSource.READINESS,
            message="",
        )

    with pytest.raises(ContractValueError, match="scenario_id must not be blank"):
        ScenarioCampaignReadinessFinding(
            finding_id="finding-001",
            severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
            source=ScenarioCampaignReadinessFindingSource.READINESS,
            message="Bad scenario.",
            scenario_id="",
        )
