from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import (
    AutonomyDecisionType,
    HazardSeverity,
    RuntimeAuthorityState,
)
from ix_autonomy_assurance_case_runtime.safety_gate import (
    ConditionOperator,
    RuntimeSafetyGate,
    RuntimeTelemetry,
    SafetyGateError,
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


def build_catalog(*, severe: bool = True, restrictive_behavior: bool = True) -> ScenarioCatalog:
    context = OperationalContext(
        context_id="CTX-001",
        name="Route execution",
        environment="degraded navigation range",
        mission_phase="execution",
        description="Autonomy is evaluated while telemetry quality changes.",
    )
    function = AutonomyFunction(
        function_id="AF-001",
        name="Route manager",
        description="Manages autonomous route execution.",
        input_signals=("navigation_confidence", "boundary_distance_ft", "power_margin_pct"),
        output_actions=("continue_route", "clamp_speed", "enter_safe_hold"),
    )
    condition = OperatingCondition(
        condition_id="COND-001",
        name="Navigation confidence",
        description="Navigation confidence telemetry is available.",
        telemetry_key="navigation_confidence",
        expected_range="0.0..1.0",
    )
    stressor = Stressor(
        stressor_id="STR-001",
        name="Navigation confidence degradation",
        description="Navigation confidence drops below nominal operating threshold.",
        severity=HazardSeverity.CRITICAL if severe else HazardSeverity.MINOR,
        affected_capabilities=("route_execution", "boundary_keeping"),
        trigger_condition="navigation_confidence < 0.70",
    )
    behavior = ExpectedSafeBehavior(
        behavior_id="BEH-001",
        description="Expected behavior for navigation confidence loss.",
        required_decision=(
            AutonomyDecisionType.SAFE_HOLD
            if restrictive_behavior
            else AutonomyDecisionType.ALLOW
        ),
        required_authority_state=(
            RuntimeAuthorityState.EMERGENCY_SAFE_HOLD
            if restrictive_behavior
            else RuntimeAuthorityState.AUTONOMOUS_ALLOWED
        ),
        rationale="Critical navigation loss must prevent nominal execution.",
    )
    criterion = AcceptanceCriterion(
        criterion_id="AC-001",
        statement="Runtime decision remains safe under navigation degradation.",
        measurement="runtime_decision",
        expected_result="safe_hold or more restrictive when severe degradation exists",
    )
    mission_thread = MissionThread(
        mission_thread_id="MT-001",
        name="Navigation safety mission thread",
        objective="Keep route autonomy bounded under degraded navigation.",
        operational_context_id="CTX-001",
        autonomy_function_ids=("AF-001",),
        scenario_ids=("SCN-001",),
    )
    scenario = Scenario(
        scenario_id="SCN-001",
        mission_thread_id="MT-001",
        title="Navigation degradation gate",
        description="Evaluate safety-gate behavior under navigation confidence loss.",
        operational_context_id="CTX-001",
        autonomy_function_id="AF-001",
        operating_condition_ids=("COND-001",),
        stressor_ids=("STR-001",),
        expected_behavior_id="BEH-001",
        acceptance_criterion_ids=("AC-001",),
        evidence_ids=("EV-001",),
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


def test_clean_nonsevere_scenario_allows_nominal_execution() -> None:
    catalog = build_catalog(severe=False, restrictive_behavior=False)
    gate = RuntimeSafetyGate()
    telemetry = RuntimeTelemetry(
        values={
            "navigation_confidence": 0.98,
            "boundary_distance_ft": 250.0,
            "power_margin_pct": 80.0,
        },
        source="simulated-run",
    )

    result = gate.evaluate(
        scenario_id="SCN-001",
        catalog=catalog,
        telemetry=telemetry,
        evidence_ids=("EV-001",),
    )

    assert result.decision is AutonomyDecisionType.ALLOW
    assert result.authority_state is RuntimeAuthorityState.AUTONOMOUS_ALLOWED
    assert result.permits_nominal_execution() is True
    assert result.operator_review_required is False
    assert result.degraded_mode is False
    assert result.triggered_rule_ids == ()
    assert result.evidence_ids == ("EV-001",)


def test_severe_scenario_expected_behavior_forces_safe_hold_without_rules() -> None:
    catalog = build_catalog(severe=True, restrictive_behavior=True)
    gate = RuntimeSafetyGate()
    telemetry = RuntimeTelemetry(
        values={
            "navigation_confidence": 0.82,
            "boundary_distance_ft": 250.0,
            "power_margin_pct": 80.0,
        },
    )

    result = gate.evaluate(
        scenario_id="SCN-001",
        catalog=catalog,
        telemetry=telemetry,
    )

    assert result.decision is AutonomyDecisionType.SAFE_HOLD
    assert result.authority_state is RuntimeAuthorityState.EMERGENCY_SAFE_HOLD
    assert result.operator_review_required is True
    assert result.degraded_mode is True
    assert "severe stressor" in result.rationale


def test_triggered_rule_clamps_nominal_behavior() -> None:
    catalog = build_catalog(severe=False, restrictive_behavior=False)
    rule = SafetyRule(
        rule_id="RULE-LOW-POWER",
        name="Low power clamp",
        telemetry_key="power_margin_pct",
        operator=ConditionOperator.LT,
        threshold=25.0,
        decision=AutonomyDecisionType.CLAMP,
        authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
        rationale="Low power margin requires constrained autonomy output.",
    )
    gate = RuntimeSafetyGate(rules=(rule,))
    telemetry = RuntimeTelemetry(
        values={
            "navigation_confidence": 0.95,
            "boundary_distance_ft": 250.0,
            "power_margin_pct": 18.0,
        },
    )

    result = gate.evaluate(
        scenario_id="SCN-001",
        catalog=catalog,
        telemetry=telemetry,
    )

    assert result.decision is AutonomyDecisionType.CLAMP
    assert result.authority_state is RuntimeAuthorityState.AUTONOMOUS_ALLOWED
    assert result.triggered_rule_ids == ("RULE-LOW-POWER",)
    assert result.operator_review_required is True
    assert result.blocks_or_restricts_execution() is True


def test_missing_required_telemetry_defers_to_human_review() -> None:
    catalog = build_catalog(severe=False, restrictive_behavior=False)
    rule = SafetyRule(
        rule_id="RULE-MISSING-NAV",
        name="Missing navigation telemetry",
        telemetry_key="navigation_confidence",
        operator=ConditionOperator.MISSING,
        threshold=None,
        decision=AutonomyDecisionType.DEFER,
        authority_state=RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
        rationale="Navigation confidence is required before autonomy may continue.",
    )
    gate = RuntimeSafetyGate(rules=(rule,))
    telemetry = RuntimeTelemetry(values={"power_margin_pct": 70.0})

    result = gate.evaluate(
        scenario_id="SCN-001",
        catalog=catalog,
        telemetry=telemetry,
    )

    assert result.decision is AutonomyDecisionType.DEFER
    assert result.authority_state is RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED
    assert result.triggered_rule_ids == ("RULE-MISSING-NAV",)
    assert result.operator_review_required is True


def test_most_restrictive_triggered_rule_wins() -> None:
    catalog = build_catalog(severe=False, restrictive_behavior=False)
    clamp_rule = SafetyRule(
        rule_id="RULE-LOW-POWER",
        name="Low power clamp",
        telemetry_key="power_margin_pct",
        operator=ConditionOperator.LT,
        threshold=30.0,
        decision=AutonomyDecisionType.CLAMP,
        authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
        rationale="Low power margin requires clamped execution.",
    )
    safe_hold_rule = SafetyRule(
        rule_id="RULE-LOW-BOUNDARY",
        name="Boundary emergency safe-hold",
        telemetry_key="boundary_distance_ft",
        operator=ConditionOperator.LTE,
        threshold=50.0,
        decision=AutonomyDecisionType.SAFE_HOLD,
        authority_state=RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
        rationale="Boundary distance is too low for continued autonomy.",
    )
    gate = RuntimeSafetyGate(rules=(clamp_rule, safe_hold_rule))
    telemetry = RuntimeTelemetry(
        values={
            "navigation_confidence": 0.91,
            "boundary_distance_ft": 25.0,
            "power_margin_pct": 20.0,
        },
    )

    result = gate.evaluate(
        scenario_id="SCN-001",
        catalog=catalog,
        telemetry=telemetry,
    )

    assert result.decision is AutonomyDecisionType.SAFE_HOLD
    assert result.authority_state is RuntimeAuthorityState.EMERGENCY_SAFE_HOLD
    assert result.triggered_rule_ids == ("RULE-LOW-POWER", "RULE-LOW-BOUNDARY")


def test_between_operator_matches_closed_interval() -> None:
    rule = SafetyRule(
        rule_id="RULE-BETWEEN",
        name="Confidence review band",
        telemetry_key="navigation_confidence",
        operator=ConditionOperator.BETWEEN,
        threshold=0.50,
        upper_threshold=0.70,
        decision=AutonomyDecisionType.DEFER,
        authority_state=RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
        rationale="Intermediate confidence requires review.",
    )
    telemetry = RuntimeTelemetry(values={"navigation_confidence": 0.60})

    evaluation = rule.evaluate(telemetry)

    assert evaluation.matched is True
    assert evaluation.observed_value == 0.60


def test_in_and_not_in_operators_match_expected_values() -> None:
    in_rule = SafetyRule(
        rule_id="RULE-MODE-IN",
        name="Mode allowlist",
        telemetry_key="autonomy_mode",
        operator=ConditionOperator.IN,
        threshold=("degraded", "recovery"),
        decision=AutonomyDecisionType.DEFER,
        authority_state=RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
        rationale="Degraded or recovery modes require review.",
    )
    not_in_rule = SafetyRule(
        rule_id="RULE-MODE-NOT-IN",
        name="Unknown mode veto",
        telemetry_key="autonomy_mode",
        operator=ConditionOperator.NOT_IN,
        threshold=("nominal", "degraded", "recovery"),
        decision=AutonomyDecisionType.VETO,
        authority_state=RuntimeAuthorityState.DENIED,
        rationale="Unknown autonomy modes are denied.",
    )

    assert in_rule.evaluate(RuntimeTelemetry(values={"autonomy_mode": "degraded"})).matched is True
    assert not_in_rule.evaluate(RuntimeTelemetry(values={"autonomy_mode": "unknown"})).matched is True


def test_exists_operator_matches_present_non_null_telemetry() -> None:
    rule = SafetyRule(
        rule_id="RULE-FAULT-FLAG",
        name="Fault flag present",
        telemetry_key="fault_flag",
        operator=ConditionOperator.EXISTS,
        threshold=None,
        decision=AutonomyDecisionType.DEFER,
        authority_state=RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
        rationale="Any explicit fault flag requires review.",
    )

    assert rule.evaluate(RuntimeTelemetry(values={"fault_flag": True})).matched is True
    assert rule.evaluate(RuntimeTelemetry(values={"fault_flag": None})).matched is False


def test_safety_gate_rejects_duplicate_rule_ids() -> None:
    rule = SafetyRule(
        rule_id="RULE-DUP",
        name="Duplicate rule",
        telemetry_key="navigation_confidence",
        operator=ConditionOperator.LT,
        threshold=0.70,
        decision=AutonomyDecisionType.DEFER,
        authority_state=RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
        rationale="Duplicate rule identifiers should be rejected.",
    )

    with pytest.raises(SafetyGateError, match="duplicate rule_id"):
        RuntimeSafetyGate(rules=(rule, rule))


def test_safety_rule_rejects_invalid_between_shape() -> None:
    with pytest.raises(SafetyGateError, match="upper_threshold must not be absent"):
        SafetyRule(
            rule_id="RULE-BAD",
            name="Bad between rule",
            telemetry_key="navigation_confidence",
            operator=ConditionOperator.BETWEEN,
            threshold=0.40,
            decision=AutonomyDecisionType.DEFER,
            authority_state=RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
            rationale="Between rules require an upper threshold.",
        )


def test_numeric_operator_rejects_non_numeric_observed_value() -> None:
    rule = SafetyRule(
        rule_id="RULE-NUMERIC",
        name="Numeric rule",
        telemetry_key="navigation_confidence",
        operator=ConditionOperator.LT,
        threshold=0.70,
        decision=AutonomyDecisionType.DEFER,
        authority_state=RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
        rationale="Numeric comparison requires numeric telemetry.",
    )

    with pytest.raises(SafetyGateError, match="observed telemetry value must be numeric"):
        rule.evaluate(RuntimeTelemetry(values={"navigation_confidence": "low"}))


def test_gate_rejects_unknown_scenario_id() -> None:
    catalog = build_catalog()
    gate = RuntimeSafetyGate()

    with pytest.raises(SafetyGateError, match="Scenario 'SCN-MISSING' is not present"):
        gate.evaluate(
            scenario_id="SCN-MISSING",
            catalog=catalog,
            telemetry=RuntimeTelemetry(values={}),
        )


def test_telemetry_rejects_blank_keys() -> None:
    with pytest.raises(SafetyGateError, match="telemetry key must not be blank"):
        RuntimeTelemetry(values={" ": 1.0})
