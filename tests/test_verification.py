from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.assurance_case import (
    AssuranceCase,
    AssuranceClaim,
    Control,
    EvidenceLink,
    Hazard,
    Mitigation,
    VerificationCriterion,
)
from ix_autonomy_assurance_case_runtime.contracts import (
    AssuranceCaseStatus,
    AutonomyDecisionType,
    EvidenceStatus,
    HazardSeverity,
    RuntimeAuthorityState,
    VerificationResult,
)
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
from ix_autonomy_assurance_case_runtime.runner import ScenarioRunInput, ScenarioRunner
from ix_autonomy_assurance_case_runtime.safety_gate import RuntimeTelemetry
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
from ix_autonomy_assurance_case_runtime.traceability import (
    MissionNeed,
    Requirement,
    TraceabilityGraph,
    build_traceability_graph,
)
from ix_autonomy_assurance_case_runtime.verification import (
    RuntimeVerificationSummary,
    VerificationCheckResult,
    VerificationEngine,
    VerificationEngineError,
    VerificationIssueSeverity,
)


def build_assurance_case() -> AssuranceCase:
    evidence = EvidenceLink(
        evidence_id="EV-001",
        description="Scenario evidence showing safe-hold under degraded navigation.",
        source="run-bundles/scn-001.json",
        status=EvidenceStatus.ACCEPTED,
        supports=("CLM-001", "VC-001", "CTRL-001"),
        content_hash="sha256:0123456789abcdef",
    )
    criterion = VerificationCriterion(
        criterion_id="VC-001",
        statement="Safe-hold occurs before mission boundary violation.",
        verification_method="fault-injection scenario",
        expected_result="safe_hold emitted while boundary distance remains positive",
        result=VerificationResult.PASS,
        evidence_ids=("EV-001",),
    )
    hazard = Hazard(
        hazard_id="HZ-001",
        title="Navigation confidence loss",
        description="Autonomy may continue nominal routing after navigation confidence degrades.",
        severity=HazardSeverity.CRITICAL,
        control_ids=("CTRL-001",),
        mitigation_ids=("MIT-001",),
        evidence_ids=("EV-001",),
    )
    control = Control(
        control_id="CTRL-001",
        name="Navigation confidence gate",
        description="Blocks nominal route execution when navigation confidence is degraded.",
        mitigates_hazard_ids=("HZ-001",),
        evidence_ids=("EV-001",),
    )
    mitigation = Mitigation(
        mitigation_id="MIT-001",
        hazard_id="HZ-001",
        control_id="CTRL-001",
        description="Force safe-hold and require review under degraded navigation.",
        evidence_ids=("EV-001",),
    )
    claim = AssuranceClaim(
        claim_id="CLM-001",
        statement="Autonomy remains bounded during degraded navigation.",
        argument="Runtime gating prevents nominal operation without trusted navigation.",
        evidence_ids=("EV-001",),
        verification_criterion_ids=("VC-001",),
        verification_result=VerificationResult.PASS,
    )

    return AssuranceCase(
        case_id="CASE-001",
        title="Navigation Degradation Assurance Case",
        system_name="Reference Autonomy Stack",
        mission_context="Autonomous route execution under degraded navigation.",
        status=AssuranceCaseStatus.READY_FOR_REVIEW,
        claims=(claim,),
        hazards=(hazard,),
        controls=(control,),
        mitigations=(mitigation,),
        evidence=(evidence,),
        verification_criteria=(criterion,),
    )


def build_scenario_catalog(
    *,
    expected_decision: AutonomyDecisionType = AutonomyDecisionType.SAFE_HOLD,
    expected_authority: RuntimeAuthorityState = RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
    criterion_result: VerificationResult = VerificationResult.PASS,
    scenario_hazard_ids: tuple[str, ...] = ("HZ-001",),
    include_scenario_evidence_id: bool = True,
) -> ScenarioCatalog:
    context = OperationalContext(
        context_id="CTX-001",
        name="Degraded navigation route execution",
        environment="controlled autonomy test range",
        mission_phase="route execution",
        description="Autonomy is evaluated under degraded navigation telemetry.",
    )
    function = AutonomyFunction(
        function_id="AF-001",
        name="Autonomous route manager",
        description="Manages bounded route execution.",
        input_signals=("navigation_confidence", "power_margin_pct", "comms_link_active"),
        output_actions=("continue_route", "defer_to_operator", "enter_safe_hold"),
    )
    condition = OperatingCondition(
        condition_id="COND-001",
        name="Navigation confidence available",
        description="Navigation confidence telemetry is evaluated.",
        telemetry_key="navigation_confidence",
        expected_range="0.0..1.0",
    )
    stressor = Stressor(
        stressor_id="STR-001",
        name="Navigation confidence degradation",
        description="Navigation confidence drops below normal operating expectations.",
        severity=HazardSeverity.CRITICAL,
        affected_capabilities=("navigation", "route_execution"),
        trigger_condition="navigation_confidence < 0.70",
    )
    behavior = ExpectedSafeBehavior(
        behavior_id="BEH-001",
        description="Expected safe behavior under degraded navigation.",
        required_decision=expected_decision,
        required_authority_state=expected_authority,
        rationale="Unsafe navigation confidence requires bounded autonomy behavior.",
    )
    criterion = AcceptanceCriterion(
        criterion_id="AC-001",
        statement="Runtime decision satisfies expected safe behavior.",
        measurement="runtime_decision",
        expected_result=expected_decision.value,
        required_verification_result=criterion_result,
    )
    mission_thread = MissionThread(
        mission_thread_id="MT-001",
        name="Navigation assurance mission thread",
        objective="Keep autonomy bounded during degraded navigation.",
        operational_context_id="CTX-001",
        autonomy_function_ids=("AF-001",),
        scenario_ids=("SCN-001",),
        requirement_ids=("REQ-001",),
        hazard_ids=scenario_hazard_ids,
    )
    evidence_ids = ("EV-001",) if include_scenario_evidence_id else ()
    scenario = Scenario(
        scenario_id="SCN-001",
        mission_thread_id="MT-001",
        title="Navigation degradation scenario",
        description="Evaluate runtime response to degraded navigation confidence.",
        operational_context_id="CTX-001",
        autonomy_function_id="AF-001",
        operating_condition_ids=("COND-001",),
        stressor_ids=("STR-001",),
        expected_behavior_id="BEH-001",
        acceptance_criterion_ids=("AC-001",),
        hazard_ids=scenario_hazard_ids,
        evidence_ids=evidence_ids,
    )

    return ScenarioCatalog(
        operational_contexts=(context,),
        autonomy_functions=(function,),
        operating_conditions=(condition,),
        stressors=(stressor,),
        expected_behaviors=(behavior,),
        acceptance_criteria=(criterion,),
        mission_threads=(mission_thread,),
        scenarios=(scenario,),
    )


def build_run_result(
    *,
    catalog: ScenarioCatalog | None = None,
    telemetry_confidence: float = 0.92,
):
    scenario_catalog = catalog or build_scenario_catalog()
    runner = ScenarioRunner()
    return runner.run(
        catalog=scenario_catalog,
        run_input=ScenarioRunInput(
            run_id="RUN-001",
            case_id="CASE-001",
            scenario_id="SCN-001",
            telemetry=RuntimeTelemetry(
                values={
                    "navigation_confidence": telemetry_confidence,
                    "power_margin_pct": 80.0,
                    "comms_link_active": True,
                },
                source="simulated-runtime",
            ),
        ),
    )


def build_traceability_graph_instance() -> TraceabilityGraph:
    return build_traceability_graph(
        mission_need=MissionNeed(
            need_id="MN-001",
            statement="Autonomous behavior remains bounded under degraded navigation.",
            operational_driver="trusted autonomy T&E",
        ),
        requirements=(
            Requirement(
                requirement_id="REQ-001",
                statement="The autonomy function shall enter safe-hold under degraded navigation.",
                verification_method="fault-injection scenario",
                source="system safety requirement",
            ),
        ),
        assurance_case=build_assurance_case(),
        scenario_catalog=build_scenario_catalog(),
    )


def test_verification_engine_accepts_valid_run_with_traceability() -> None:
    assurance_case = build_assurance_case()
    scenario_catalog = build_scenario_catalog()
    run_result = build_run_result(catalog=scenario_catalog)
    traceability_graph = build_traceability_graph_instance()

    summary = VerificationEngine(require_traceability=True).verify_run(
        assurance_case=assurance_case,
        scenario_catalog=scenario_catalog,
        run_result=run_result,
        traceability_graph=traceability_graph,
    )

    assert summary.overall_result is VerificationResult.PASS
    assert summary.accepted() is True
    assert summary.failed_check_ids() == ()
    assert summary.follow_up_check_ids() == ()
    assert summary.error_messages() == ()
    assert summary.warning_messages() == ()


def test_verification_engine_fails_when_expected_behavior_is_not_satisfied() -> None:
    scenario_catalog = build_scenario_catalog(
        expected_decision=AutonomyDecisionType.SAFE_HOLD,
        expected_authority=RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
    )
    run_result = build_run_result(
        catalog=scenario_catalog,
        telemetry_confidence=0.99,
    )

    assert run_result.verification_result is VerificationResult.PASS

    summary = VerificationEngine(require_traceability=False).verify_run(
        assurance_case=build_assurance_case(),
        scenario_catalog=scenario_catalog,
        run_result=run_result,
    )

    assert summary.overall_result is VerificationResult.FAIL
    assert "traceability-graph-present" in summary.follow_up_check_ids()
    assert "expected-safe-behavior" not in summary.failed_check_ids()


def test_verification_engine_fails_when_acceptance_criterion_result_mismatches() -> None:
    scenario_catalog = build_scenario_catalog(
        expected_decision=AutonomyDecisionType.SAFE_HOLD,
        expected_authority=RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
        criterion_result=VerificationResult.FAIL,
    )
    run_result = build_run_result(catalog=scenario_catalog)

    summary = VerificationEngine().verify_run(
        assurance_case=build_assurance_case(),
        scenario_catalog=scenario_catalog,
        run_result=run_result,
    )

    assert summary.overall_result is VerificationResult.FAIL
    assert "acceptance-criterion:AC-001" in summary.failed_check_ids()
    assert any("requires 'fail'" in message for message in summary.error_messages())


def test_verification_engine_fails_when_assurance_case_has_missing_hazard_reference() -> None:
    scenario_catalog = build_scenario_catalog(scenario_hazard_ids=("HZ-MISSING",))
    run_result = build_run_result(catalog=scenario_catalog)

    summary = VerificationEngine().verify_run(
        assurance_case=build_assurance_case(),
        scenario_catalog=scenario_catalog,
        run_result=run_result,
    )

    assert summary.overall_result is VerificationResult.FAIL
    assert "scenario-hazard-coverage" in summary.failed_check_ids()
    assert any("HZ-MISSING" in message for message in summary.error_messages())


def test_verification_engine_reports_required_traceability_missing_as_failure() -> None:
    scenario_catalog = build_scenario_catalog()
    run_result = build_run_result(catalog=scenario_catalog)

    summary = VerificationEngine(require_traceability=True).verify_run(
        assurance_case=build_assurance_case(),
        scenario_catalog=scenario_catalog,
        run_result=run_result,
    )

    assert summary.overall_result is VerificationResult.FAIL
    assert "traceability-graph-present" in summary.failed_check_ids()


def test_verification_engine_reports_optional_missing_traceability_as_inconclusive() -> None:
    scenario_catalog = build_scenario_catalog()
    run_result = build_run_result(catalog=scenario_catalog)

    summary = VerificationEngine(require_traceability=False).verify_run(
        assurance_case=build_assurance_case(),
        scenario_catalog=scenario_catalog,
        run_result=run_result,
    )

    assert summary.overall_result is VerificationResult.INCONCLUSIVE
    assert "traceability-graph-present" in summary.follow_up_check_ids()
    assert summary.warning_messages() == ("Traceability graph was not provided.",)


def test_verification_engine_fails_on_tampered_evidence_bundle() -> None:
    scenario_catalog = build_scenario_catalog()
    run_result = build_run_result(catalog=scenario_catalog)
    original_record = run_result.evidence_bundle.records[0]
    tampered_record = EvidenceRecord(
        evidence_id=original_record.evidence_id,
        kind=original_record.kind,
        source=original_record.source,
        payload={"tampered": True},
        status=EvidenceStatus.ACCEPTED,
        created_by=original_record.created_by,
        tags=original_record.tags,
        content_hash=original_record.content_hash,
    )
    tampered_bundle = EvidenceBundle(
        bundle_id=run_result.evidence_bundle.bundle_id,
        case_id=run_result.evidence_bundle.case_id,
        scenario_id=run_result.evidence_bundle.scenario_id,
        records=(tampered_record,),
        created_by=run_result.evidence_bundle.created_by,
        bundle_hash=run_result.evidence_bundle.bundle_hash,
    )
    tampered_result = type(run_result)(
        run_id=run_result.run_id,
        case_id=run_result.case_id,
        scenario_id=run_result.scenario_id,
        final_decision=run_result.final_decision,
        final_authority_state=run_result.final_authority_state,
        verification_result=run_result.verification_result,
        expected_behavior_satisfied=run_result.expected_behavior_satisfied,
        operator_review_required=run_result.operator_review_required,
        degraded_mode=run_result.degraded_mode,
        safety_gate_result=run_result.safety_gate_result,
        degradation_assessment=run_result.degradation_assessment,
        evidence_bundle=tampered_bundle,
        rationale=run_result.rationale,
    )

    summary = VerificationEngine().verify_run(
        assurance_case=build_assurance_case(),
        scenario_catalog=scenario_catalog,
        run_result=tampered_result,
    )

    assert summary.overall_result is VerificationResult.FAIL
    assert "evidence-bundle-integrity" in summary.failed_check_ids()
    assert any("integrity failed" in message for message in summary.error_messages())


def test_verification_engine_marks_unconnected_traceability_as_inconclusive() -> None:
    scenario_catalog = build_scenario_catalog()
    run_result = build_run_result(catalog=scenario_catalog)
    graph = TraceabilityGraph(
        nodes=(
            build_traceability_graph_instance().node_index()["SCN-001"],
            build_traceability_graph_instance().node_index()["CLM-001"],
        ),
        edges=(),
    )

    summary = VerificationEngine().verify_run(
        assurance_case=build_assurance_case(),
        scenario_catalog=scenario_catalog,
        run_result=run_result,
        traceability_graph=graph,
    )

    assert summary.overall_result is VerificationResult.INCONCLUSIVE
    assert "scenario-to-claim-trace" in summary.follow_up_check_ids()


def test_verification_check_result_rejects_duplicate_evidence_ids() -> None:
    with pytest.raises(VerificationEngineError, match="evidence_ids must not contain duplicate"):
        VerificationCheckResult(
            check_id="duplicate-evidence",
            result=VerificationResult.PASS,
            severity=VerificationIssueSeverity.INFO,
            message="Duplicate evidence identifiers should be rejected.",
            evidence_ids=("EV-001", "EV-001"),
        )


def test_runtime_verification_summary_requires_checks() -> None:
    with pytest.raises(VerificationEngineError, match="checks must not be empty"):
        RuntimeVerificationSummary(
            run_id="RUN-001",
            case_id="CASE-001",
            scenario_id="SCN-001",
            overall_result=VerificationResult.PASS,
            checks=(),
        )
