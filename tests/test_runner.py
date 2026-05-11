from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import (
    AutonomyDecisionType,
    HazardSeverity,
    RuntimeAuthorityState,
    VerificationResult,
)
from ix_autonomy_assurance_case_runtime.degradation import (
    DegradationCategory,
    DegradationEngine,
    build_default_degradation_rules,
)
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
from ix_autonomy_assurance_case_runtime.runner import (
    ScenarioRunInput,
    ScenarioRunner,
    ScenarioRunnerError,
)
from ix_autonomy_assurance_case_runtime.safety_gate import (
    ConditionOperator,
    RuntimeSafetyGate,
    RuntimeTelemetry,
    SafetyRule,
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


def build_catalog(
    *,
    severe: bool = True,
    expected_decision: AutonomyDecisionType = AutonomyDecisionType.SAFE_HOLD,
    expected_authority: RuntimeAuthorityState = RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
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
        severity=HazardSeverity.CRITICAL if severe else HazardSeverity.MINOR,
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
    )
    mission_thread = MissionThread(
        mission_thread_id="MT-001",
        name="Navigation assurance mission thread",
        objective="Keep autonomy bounded during degraded navigation.",
        operational_context_id="CTX-001",
        autonomy_function_ids=("AF-001",),
        scenario_ids=("SCN-001",),
    )
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
        evidence_ids=("EV-SCN-001",),
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


def build_run_input(
    *,
    telemetry: RuntimeTelemetry,
    run_id: str = "RUN-001",
) -> ScenarioRunInput:
    return ScenarioRunInput(
        run_id=run_id,
        case_id="CASE-001",
        scenario_id="SCN-001",
        telemetry=telemetry,
        operator_id="operator-001",
        notes=("controlled test execution",),
    )


def test_runner_executes_severe_scenario_and_produces_hashed_evidence_bundle() -> None:
    catalog = build_catalog()
    runner = ScenarioRunner()
    run_input = build_run_input(
        telemetry=RuntimeTelemetry(
            values={
                "navigation_confidence": 0.62,
                "power_margin_pct": 80.0,
                "comms_link_active": True,
            },
            source="simulated-runtime",
        )
    )

    result = runner.run(catalog=catalog, run_input=run_input)

    assert result.final_decision is AutonomyDecisionType.SAFE_HOLD
    assert result.final_authority_state is RuntimeAuthorityState.EMERGENCY_SAFE_HOLD
    assert result.verification_result is VerificationResult.PASS
    assert result.expected_behavior_satisfied is True
    assert result.operator_review_required is True
    assert result.degraded_mode is True
    assert result.blocks_or_restricts_execution() is True
    assert result.evidence_bundle.bundle_hash is not None
    assert result.evidence_bundle.validate_integrity().is_valid is True
    assert result.evidence_bundle.records[0].content_hash is not None


def test_runner_allows_nominal_execution_when_expectation_is_allow_and_no_degradation() -> None:
    catalog = build_catalog(
        severe=False,
        expected_decision=AutonomyDecisionType.ALLOW,
        expected_authority=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
    )
    runner = ScenarioRunner(
        degradation_engine=DegradationEngine(rules=build_default_degradation_rules())
    )
    run_input = build_run_input(
        telemetry=RuntimeTelemetry(
            values={
                "navigation_confidence": 0.98,
                "power_margin_pct": 90.0,
                "comms_link_active": True,
                "sensor_drift_sigma": 0.2,
                "control_loop_latency_ms": 20.0,
            }
        )
    )

    result = runner.run(catalog=catalog, run_input=run_input)

    assert result.final_decision is AutonomyDecisionType.ALLOW
    assert result.final_authority_state is RuntimeAuthorityState.AUTONOMOUS_ALLOWED
    assert result.permits_nominal_execution() is True
    assert result.operator_review_required is False
    assert result.degraded_mode is False
    assert result.verification_result is VerificationResult.PASS


def test_runner_combines_degradation_engine_with_safety_gate_conservatively() -> None:
    catalog = build_catalog(
        severe=False,
        expected_decision=AutonomyDecisionType.DEFER,
        expected_authority=RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
    )
    runner = ScenarioRunner(
        degradation_engine=DegradationEngine(rules=build_default_degradation_rules())
    )
    run_input = build_run_input(
        telemetry=RuntimeTelemetry(
            values={
                "navigation_confidence": 0.65,
                "power_margin_pct": 80.0,
                "comms_link_active": True,
                "sensor_drift_sigma": 0.2,
                "control_loop_latency_ms": 20.0,
            }
        )
    )

    result = runner.run(catalog=catalog, run_input=run_input)

    assert result.degradation_assessment.worst_level().value == "degraded"
    assert result.final_decision is AutonomyDecisionType.DEFER
    assert result.final_authority_state is RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED
    assert result.verification_result is VerificationResult.PASS


def test_runner_uses_more_restrictive_safety_gate_rule_when_it_exceeds_degradation() -> None:
    catalog = build_catalog(
        severe=False,
        expected_decision=AutonomyDecisionType.VETO,
        expected_authority=RuntimeAuthorityState.DENIED,
    )
    rule = SafetyRule(
        rule_id="RULE-BOUNDARY",
        name="Boundary distance veto",
        telemetry_key="boundary_distance_ft",
        operator=ConditionOperator.LT,
        threshold=50.0,
        decision=AutonomyDecisionType.VETO,
        authority_state=RuntimeAuthorityState.DENIED,
        rationale="Boundary distance is too low for continued autonomy.",
    )
    runner = ScenarioRunner(
        safety_gate=RuntimeSafetyGate(rules=(rule,)),
        degradation_engine=DegradationEngine(rules=build_default_degradation_rules()),
    )
    run_input = build_run_input(
        telemetry=RuntimeTelemetry(
            values={
                "navigation_confidence": 0.98,
                "power_margin_pct": 80.0,
                "comms_link_active": True,
                "sensor_drift_sigma": 0.2,
                "control_loop_latency_ms": 20.0,
                "boundary_distance_ft": 25.0,
            }
        )
    )

    result = runner.run(catalog=catalog, run_input=run_input)

    assert result.safety_gate_result.triggered_rule_ids == ("RULE-BOUNDARY",)
    assert result.final_decision is AutonomyDecisionType.VETO
    assert result.final_authority_state is RuntimeAuthorityState.DENIED
    assert result.verification_result is VerificationResult.PASS


def test_runner_fails_verification_when_expected_behavior_is_not_satisfied() -> None:
    catalog = build_catalog(
        severe=False,
        expected_decision=AutonomyDecisionType.SAFE_HOLD,
        expected_authority=RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
    )
    runner = ScenarioRunner()
    run_input = build_run_input(
        telemetry=RuntimeTelemetry(
            values={
                "navigation_confidence": 0.98,
                "power_margin_pct": 80.0,
                "comms_link_active": True,
            }
        )
    )

    result = runner.run(catalog=catalog, run_input=run_input)

    assert result.final_decision is AutonomyDecisionType.ALLOW
    assert result.final_authority_state is RuntimeAuthorityState.AUTONOMOUS_ALLOWED
    assert result.expected_behavior_satisfied is False
    assert result.verification_result is VerificationResult.FAIL


def test_runner_preserves_prior_evidence_integrity_as_degradation_input() -> None:
    catalog = build_catalog(
        severe=False,
        expected_decision=AutonomyDecisionType.SAFE_HOLD,
        expected_authority=RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
    )
    stale_record = EvidenceRecord(
        evidence_id="EV-STALE",
        kind="old-run",
        source="run-bundles/old.json",
        payload={"decision": "defer"},
    )
    stale_bundle = EvidenceBundle(
        bundle_id="BND-UNHASHED",
        case_id="CASE-001",
        scenario_id="SCN-001",
        records=(stale_record,),
    )
    runner = ScenarioRunner(
        degradation_engine=DegradationEngine(rules=build_default_degradation_rules())
    )
    run_input = ScenarioRunInput(
        run_id="RUN-002",
        case_id="CASE-001",
        scenario_id="SCN-001",
        telemetry=RuntimeTelemetry(
            values={
                "navigation_confidence": 0.98,
                "power_margin_pct": 80.0,
                "comms_link_active": True,
                "sensor_drift_sigma": 0.2,
                "control_loop_latency_ms": 20.0,
            }
        ),
        prior_evidence_bundles=(stale_bundle,),
    )

    result = runner.run(catalog=catalog, run_input=run_input)

    assert result.degradation_assessment.has_category(DegradationCategory.STALE_EVIDENCE) is True
    assert result.degradation_assessment.worst_level().value == "watch"
    assert result.verification_result is VerificationResult.FAIL
    assert result.evidence_bundle.bundle_id == "BND-RUN-002"


def test_run_result_evidence_payload_is_json_compatible_and_complete() -> None:
    catalog = build_catalog()
    runner = ScenarioRunner()
    run_input = build_run_input(
        telemetry=RuntimeTelemetry(
            values={
                "navigation_confidence": 0.62,
                "power_margin_pct": 80.0,
                "comms_link_active": True,
            }
        )
    )

    result = runner.run(catalog=catalog, run_input=run_input)
    payload = result.to_evidence_payload()

    assert payload["run_id"] == "RUN-001"
    assert payload["case_id"] == "CASE-001"
    assert payload["scenario_id"] == "SCN-001"
    assert payload["final_decision"] == "safe_hold"
    assert payload["final_authority_state"] == "emergency_safe_hold"
    assert payload["verification_result"] == "pass"
    assert payload["expected_behavior_satisfied"] is True


def test_runner_rejects_invalid_catalog_before_execution() -> None:
    catalog = ScenarioCatalog()
    runner = ScenarioRunner()
    run_input = build_run_input(telemetry=RuntimeTelemetry(values={}))

    with pytest.raises(ScenarioRunnerError, match="Scenario catalog is invalid"):
        runner.run(catalog=catalog, run_input=run_input)


def test_runner_rejects_unknown_scenario_id() -> None:
    catalog = build_catalog()
    runner = ScenarioRunner()
    run_input = ScenarioRunInput(
        run_id="RUN-404",
        case_id="CASE-001",
        scenario_id="SCN-MISSING",
        telemetry=RuntimeTelemetry(values={}),
    )

    with pytest.raises(ScenarioRunnerError, match="Scenario 'SCN-MISSING'"):
        runner.run(catalog=catalog, run_input=run_input)


def test_run_input_rejects_duplicate_notes() -> None:
    with pytest.raises(ScenarioRunnerError, match="notes must not contain duplicate"):
        ScenarioRunInput(
            run_id="RUN-DUP",
            case_id="CASE-001",
            scenario_id="SCN-001",
            telemetry=RuntimeTelemetry(values={}),
            notes=("same", "same"),
        )


def test_runner_rejects_blank_evidence_creator() -> None:
    with pytest.raises(ScenarioRunnerError, match="evidence_created_by must not be blank"):
        ScenarioRunner(evidence_created_by=" ")
