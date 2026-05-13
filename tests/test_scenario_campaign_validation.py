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
from ix_autonomy_assurance_case_runtime.scenario_campaign_validation import (
    ScenarioCampaignFindingSeverity,
    ScenarioCampaignFindingSource,
    ScenarioCampaignValidationFinding,
    ScenarioCampaignValidator,
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
from ix_autonomy_assurance_case_runtime.telemetry import TelemetryReplayRecord


def _catalog() -> ScenarioCatalog:
    return ScenarioCatalog(
        operational_contexts=(
            OperationalContext(
                context_id="CTX-001",
                name="Contested route execution",
                environment="degraded navigation test range",
                mission_phase="route execution",
                description="Autonomy remains bounded while navigation confidence degrades.",
            ),
        ),
        autonomy_functions=(
            AutonomyFunction(
                function_id="AF-001",
                name="Autonomous route manager",
                description="Plans route updates under bounded autonomy.",
                input_signals=("navigation_confidence",),
                output_actions=("continue_route", "enter_safe_hold"),
            ),
        ),
        operating_conditions=(
            OperatingCondition(
                condition_id="COND-001",
                name="Navigation confidence degraded",
                description="Navigation confidence is below the nominal threshold.",
                telemetry_key="navigation.confidence",
                expected_range="< 0.70",
            ),
        ),
        stressors=(
            Stressor(
                stressor_id="STR-001",
                name="Navigation drift",
                description="Position estimate diverges from reference telemetry.",
                severity=HazardSeverity.CRITICAL,
                affected_capabilities=("route_execution",),
                trigger_condition="navigation.confidence < 0.70",
            ),
        ),
        expected_behaviors=(
            ExpectedSafeBehavior(
                behavior_id="BEH-001",
                description="Runtime gate forces safe-hold and operator review.",
                required_decision=AutonomyDecisionType.SAFE_HOLD,
                required_authority_state=RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
                rationale="Critical navigation uncertainty must block nominal autonomy.",
            ),
        ),
        acceptance_criteria=(
            AcceptanceCriterion(
                criterion_id="AC-001",
                statement="Safe-hold is emitted before boundary violation.",
                measurement="runtime_decision",
                expected_result="safe_hold emitted",
            ),
        ),
        mission_threads=(
            MissionThread(
                mission_thread_id="MT-001",
                name="Degraded navigation route safety",
                objective="Keep autonomy bounded under degraded navigation.",
                operational_context_id="CTX-001",
                autonomy_function_ids=("AF-001",),
                scenario_ids=("SCN-001",),
                requirement_ids=("REQ-NAV-BOUNDARY-001",),
                hazard_ids=("HZ-NAV-001",),
            ),
        ),
        scenarios=(
            Scenario(
                scenario_id="SCN-001",
                mission_thread_id="MT-001",
                title="Critical navigation drift triggers safe-hold",
                description="Inject navigation drift and verify constrained behavior.",
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
    scenario_id: str = "SCN-001",
    status: ScenarioCampaignStatus = ScenarioCampaignStatus.READY_FOR_RUN,
    requirement_ids: tuple[str, ...] = ("REQ-NAV-BOUNDARY-001",),
    hazard_ids: tuple[str, ...] = ("HZ-NAV-001",),
    evidence_bundle_ids: tuple[str, ...] = ("ev-campaign-scenario-001",),
    replay_record_ids: tuple[str, ...] = ("replay-nav-001",),
    expected_result: VerificationResult = VerificationResult.PASS,
) -> ScenarioCampaign:
    return ScenarioCampaign(
        campaign_id="campaign-degraded-nav",
        name="Degraded navigation campaign",
        purpose="Validate bounded autonomy under degraded navigation telemetry.",
        status=status,
        mission_thread_id="MT-001",
        objectives=(
            ScenarioCampaignObjective(
                objective_id="objective-safe-hold",
                statement="Prove critical navigation drift causes safe-hold.",
                success_criteria=("Safe-hold evidence exists for every run.",),
                requirement_ids=("REQ-NAV-BOUNDARY-001",),
                hazard_ids=("HZ-NAV-001",),
            ),
        ),
        scenarios=(
            ScenarioCampaignScenario(
                campaign_scenario_id="campaign-scenario-degraded-nav",
                scenario_id=scenario_id,
                role=ScenarioCampaignScenarioRole.ADVERSARIAL_PROBE,
                expected_result=expected_result,
                tags=(ScenarioCampaignTag.ADVERSARIAL, ScenarioCampaignTag.TELEMETRY_REPLAY),
                requirement_ids=requirement_ids,
                hazard_ids=hazard_ids,
                evidence_bundle_ids=evidence_bundle_ids,
                replay_record_ids=replay_record_ids,
            ),
        ),
        acceptance_threshold=ScenarioCampaignAcceptanceThreshold(
            threshold_id="threshold-all-pass",
            minimum_pass_rate=1.0,
        ),
        tags=(ScenarioCampaignTag.ADVERSARIAL, ScenarioCampaignTag.TELEMETRY_REPLAY),
        evidence_bundle_ids=("ev-campaign-plan-001",),
    )


def _bundle(bundle_id: str, *, hashed: bool = True) -> EvidenceBundle:
    bundle = EvidenceBundle(
        bundle_id=bundle_id,
        case_id="case-campaign-validation-001",
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


def _replay_record(
    *,
    replay_record_id: str = "replay-nav-001",
    scenario_ids: tuple[str, ...] = ("SCN-001",),
    evidence_bundle_ids: tuple[str, ...] = ("ev-replay-001",),
) -> TelemetryReplayRecord:
    return TelemetryReplayRecord(
        replay_record_id=replay_record_id,
        source_id="telemetry-nav-replay",
        schema_id="schema-nav-v1",
        replay_file_uri="local://replay/nav.jsonl",
        recorded_at_utc="2026-05-12T12:00:00Z",
        scenario_ids=scenario_ids,
        evidence_bundle_ids=evidence_bundle_ids,
    )


def test_scenario_campaign_validator_accepts_grounded_campaign() -> None:
    report = ScenarioCampaignValidator(
        _catalog(),
        evidence_bundles=_bundles(),
        replay_records=(_replay_record(),),
    ).validate(_campaign())

    assert report.is_execution_ready()
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.scenario_count == 1
    assert report.evidence_bundle_count == 2
    assert report.replay_record_count == 1
    assert report.summary() == (
        "scenario-campaign-validation: campaign-degraded-nav "
        "(1 scenario(s), 2 evidence bundle(s), 1 replay record(s), "
        "0 blocker(s), 0 warning(s))"
    )


def test_scenario_campaign_validator_blocks_non_executable_status() -> None:
    report = ScenarioCampaignValidator(
        _catalog(),
        evidence_bundles=_bundles(),
        replay_records=(_replay_record(),),
    ).validate(_campaign(status=ScenarioCampaignStatus.DRAFT))

    assert not report.is_execution_ready()
    assert report.blocker_count == 1
    assert report.findings[0].source is ScenarioCampaignFindingSource.CAMPAIGN


def test_scenario_campaign_validator_blocks_missing_scenario_reference() -> None:
    report = ScenarioCampaignValidator(
        _catalog(),
        evidence_bundles=_bundles(),
        replay_records=(_replay_record(),),
    ).validate(_campaign(scenario_id="SCN-MISSING"))

    assert not report.is_execution_ready()
    assert any(
        finding.finding_id == "scenario-SCN-MISSING-missing"
        for finding in report.findings_for_scenario("SCN-MISSING")
    )


def test_scenario_campaign_validator_blocks_requirement_not_on_mission_thread() -> None:
    report = ScenarioCampaignValidator(
        _catalog(),
        evidence_bundles=_bundles(),
        replay_records=(_replay_record(),),
    ).validate(_campaign(requirement_ids=("REQ-UNKNOWN",)))

    assert not report.is_execution_ready()
    assert report.findings_for_requirement("REQ-UNKNOWN")[0].severity is (
        ScenarioCampaignFindingSeverity.BLOCKER
    )


def test_scenario_campaign_validator_blocks_hazard_not_in_catalog_trace() -> None:
    report = ScenarioCampaignValidator(
        _catalog(),
        evidence_bundles=_bundles(),
        replay_records=(_replay_record(),),
    ).validate(_campaign(hazard_ids=("HZ-UNKNOWN",)))

    assert not report.is_execution_ready()
    assert report.findings_for_hazard("HZ-UNKNOWN")[0].source is (
        ScenarioCampaignFindingSource.SCENARIO_CATALOG
    )


def test_scenario_campaign_validator_blocks_missing_evidence_bundle() -> None:
    report = ScenarioCampaignValidator(
        _catalog(),
        evidence_bundles=(_bundle("ev-campaign-plan-001"),),
        replay_records=(_replay_record(),),
    ).validate(_campaign())

    assert not report.is_execution_ready()
    assert report.findings_for_evidence_bundle("ev-campaign-scenario-001")[0].source is (
        ScenarioCampaignFindingSource.EVIDENCE
    )


def test_scenario_campaign_validator_warns_for_unhashed_evidence() -> None:
    report = ScenarioCampaignValidator(
        _catalog(),
        evidence_bundles=(
            _bundle("ev-campaign-plan-001"),
            _bundle("ev-campaign-scenario-001", hashed=False),
        ),
        replay_records=(_replay_record(),),
    ).validate(_campaign())

    assert report.is_execution_ready()
    assert report.warning_count == 2
    assert report.findings_for_evidence_bundle("ev-campaign-scenario-001")


def test_scenario_campaign_validator_blocks_missing_replay_record() -> None:
    report = ScenarioCampaignValidator(_catalog(), evidence_bundles=_bundles()).validate(
        _campaign()
    )

    assert not report.is_execution_ready()
    assert report.findings_for_replay_record("replay-nav-001")[0].source is (
        ScenarioCampaignFindingSource.REPLAY
    )


def test_scenario_campaign_validator_blocks_replay_without_scenario_coverage() -> None:
    report = ScenarioCampaignValidator(
        _catalog(),
        evidence_bundles=_bundles(),
        replay_records=(_replay_record(scenario_ids=("SCN-OTHER",)),),
    ).validate(_campaign())

    assert not report.is_execution_ready()
    assert any(
        finding.finding_id == "replay-replay-nav-001-missing-scenario-SCN-001"
        for finding in report.findings_for_replay_record("replay-nav-001")
    )


def test_scenario_campaign_validator_warns_replay_without_evidence_reference() -> None:
    report = ScenarioCampaignValidator(
        _catalog(),
        evidence_bundles=_bundles(),
        replay_records=(_replay_record(evidence_bundle_ids=()),),
    ).validate(_campaign())

    assert report.is_execution_ready()
    assert report.warning_count == 1
    assert report.findings_for_replay_record("replay-nav-001")[0].severity is (
        ScenarioCampaignFindingSeverity.WARNING
    )


def test_scenario_campaign_validator_rejects_duplicate_indexes() -> None:
    with pytest.raises(ContractValueError, match="Duplicate scenario campaign evidence"):
        ScenarioCampaignValidator(
            _catalog(),
            evidence_bundles=(
                _bundle("ev-campaign-plan-001"),
                _bundle("ev-campaign-plan-001"),
            ),
        )

    with pytest.raises(ContractValueError, match="Duplicate scenario campaign replay"):
        ScenarioCampaignValidator(
            _catalog(),
            replay_records=(_replay_record(), _replay_record()),
        )


def test_scenario_campaign_validation_finding_validates_optional_ids() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        ScenarioCampaignValidationFinding(
            finding_id="finding-001",
            severity=ScenarioCampaignFindingSeverity.BLOCKER,
            source=ScenarioCampaignFindingSource.CAMPAIGN,
            message="",
        )

    with pytest.raises(ContractValueError, match="scenario_id must not be blank"):
        ScenarioCampaignValidationFinding(
            finding_id="finding-001",
            severity=ScenarioCampaignFindingSeverity.BLOCKER,
            source=ScenarioCampaignFindingSource.CAMPAIGN,
            message="Bad scenario.",
            scenario_id="",
        )
