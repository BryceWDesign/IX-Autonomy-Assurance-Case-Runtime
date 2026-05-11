from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import (
    AutonomyDecisionType,
    EvidenceStatus,
    RuntimeAuthorityState,
)
from ix_autonomy_assurance_case_runtime.degradation import (
    DegradationAssessment,
    DegradationCategory,
    DegradationEngine,
    DegradationLevel,
    DegradationRule,
    DegradationRuntimeError,
    DegradationSignal,
    TelemetryConflictCheck,
    build_default_degradation_rules,
)
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
from ix_autonomy_assurance_case_runtime.safety_gate import ConditionOperator, RuntimeTelemetry


def test_default_rules_detect_critical_navigation_degradation() -> None:
    engine = DegradationEngine(rules=build_default_degradation_rules())
    telemetry = RuntimeTelemetry(
        values={
            "navigation_confidence": 0.42,
            "comms_link_active": True,
            "power_margin_pct": 70.0,
            "sensor_drift_sigma": 0.5,
            "control_loop_latency_ms": 20.0,
        },
        source="simulated-runtime",
    )

    assessment = engine.assess(
        scenario_id="SCN-001",
        telemetry=telemetry,
    )

    assert assessment.has_category(DegradationCategory.NAVIGATION_UNCERTAINTY) is True
    assert assessment.worst_level() is DegradationLevel.CRITICAL
    assert assessment.recommended_decision() is AutonomyDecisionType.SAFE_HOLD
    assert assessment.recommended_authority_state() is RuntimeAuthorityState.EMERGENCY_SAFE_HOLD
    assert assessment.degraded_mode() is True
    assert assessment.requires_operator_review() is True


def test_clean_telemetry_returns_nominal_assessment() -> None:
    engine = DegradationEngine(rules=build_default_degradation_rules())
    telemetry = RuntimeTelemetry(
        values={
            "navigation_confidence": 0.98,
            "comms_link_active": True,
            "power_margin_pct": 88.0,
            "sensor_drift_sigma": 0.2,
            "control_loop_latency_ms": 18.0,
        }
    )

    assessment = engine.assess(
        scenario_id="SCN-001",
        telemetry=telemetry,
    )

    assert assessment.signals == ()
    assert assessment.worst_level() is DegradationLevel.NOMINAL
    assert assessment.recommended_decision() is AutonomyDecisionType.ALLOW
    assert assessment.recommended_authority_state() is RuntimeAuthorityState.AUTONOMOUS_ALLOWED
    assert assessment.degraded_mode() is False
    assert assessment.requires_operator_review() is False
    assert assessment.summary() == "Scenario SCN-001 is nominal."


def test_missing_comms_telemetry_emits_severe_signal() -> None:
    engine = DegradationEngine(rules=build_default_degradation_rules())
    telemetry = RuntimeTelemetry(
        values={
            "navigation_confidence": 0.92,
            "power_margin_pct": 80.0,
            "sensor_drift_sigma": 0.1,
            "control_loop_latency_ms": 12.0,
        }
    )

    assessment = engine.assess(
        scenario_id="SCN-001",
        telemetry=telemetry,
    )

    assert assessment.has_category(DegradationCategory.COMMS_LOSS) is True
    assert assessment.worst_level() is DegradationLevel.SEVERE
    assert assessment.recommended_decision() is AutonomyDecisionType.VETO
    assert assessment.recommended_authority_state() is RuntimeAuthorityState.DENIED


def test_power_and_sensor_degradation_trigger_degraded_mode() -> None:
    engine = DegradationEngine(rules=build_default_degradation_rules())
    telemetry = RuntimeTelemetry(
        values={
            "navigation_confidence": 0.95,
            "comms_link_active": True,
            "power_margin_pct": 12.0,
            "sensor_drift_sigma": 4.2,
            "control_loop_latency_ms": 20.0,
        }
    )

    assessment = engine.assess(
        scenario_id="SCN-001",
        telemetry=telemetry,
    )

    assert assessment.has_category(DegradationCategory.POWER_DEGRADATION) is True
    assert assessment.has_category(DegradationCategory.SENSOR_DRIFT) is True
    assert assessment.worst_level() is DegradationLevel.DEGRADED
    assert assessment.recommended_decision() is AutonomyDecisionType.DEFER
    assert assessment.recommended_authority_state() is RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED


def test_timing_degradation_overrides_lower_level_signals() -> None:
    engine = DegradationEngine(rules=build_default_degradation_rules())
    telemetry = RuntimeTelemetry(
        values={
            "navigation_confidence": 0.65,
            "comms_link_active": True,
            "power_margin_pct": 10.0,
            "sensor_drift_sigma": 0.1,
            "control_loop_latency_ms": 300.0,
        }
    )

    assessment = engine.assess(
        scenario_id="SCN-001",
        telemetry=telemetry,
    )

    assert assessment.has_category(DegradationCategory.TIMING_DEGRADATION) is True
    assert assessment.worst_level() is DegradationLevel.SEVERE
    assert assessment.recommended_decision() is AutonomyDecisionType.VETO
    assert assessment.recommended_authority_state() is RuntimeAuthorityState.DENIED


def test_conflicting_telemetry_check_emits_signal_when_delta_exceeds_limit() -> None:
    check = TelemetryConflictCheck(
        check_id="GPS-INS-DIVERGENCE",
        primary_key="gps_position_error_ft",
        comparison_key="ins_position_error_ft",
        max_allowed_delta=10.0,
        level=DegradationLevel.SEVERE,
        rationale="GPS and INS position-error estimates diverge beyond allowed tolerance.",
        affected_capabilities=("navigation", "state_estimation"),
    )
    engine = DegradationEngine(conflict_checks=(check,))
    telemetry = RuntimeTelemetry(
        values={
            "gps_position_error_ft": 12.0,
            "ins_position_error_ft": 31.0,
        }
    )

    assessment = engine.assess(
        scenario_id="SCN-001",
        telemetry=telemetry,
    )

    assert assessment.has_category(DegradationCategory.CONFLICTING_TELEMETRY) is True
    assert assessment.signals[0].observed_value == 19.0
    assert assessment.worst_level() is DegradationLevel.SEVERE


def test_conflicting_telemetry_check_ignores_missing_values() -> None:
    check = TelemetryConflictCheck(
        check_id="GPS-INS-DIVERGENCE",
        primary_key="gps_position_error_ft",
        comparison_key="ins_position_error_ft",
        max_allowed_delta=10.0,
        level=DegradationLevel.SEVERE,
        rationale="GPS and INS position-error estimates diverge beyond allowed tolerance.",
        affected_capabilities=("navigation",),
    )
    engine = DegradationEngine(conflict_checks=(check,))

    assessment = engine.assess(
        scenario_id="SCN-001",
        telemetry=RuntimeTelemetry(values={"gps_position_error_ft": 12.0}),
    )

    assert assessment.signals == ()
    assert assessment.worst_level() is DegradationLevel.NOMINAL


def test_stale_evidence_bundle_creates_degraded_evidence_signal() -> None:
    record = EvidenceRecord(
        evidence_id="EV-STALE",
        kind="scenario-run",
        source="run-bundles/old.json",
        payload={"decision": "defer"},
        status=EvidenceStatus.STALE,
    ).with_computed_hash()
    bundle = EvidenceBundle(
        bundle_id="BND-STALE",
        case_id="CASE-001",
        records=(record,),
    ).with_computed_hashes()
    engine = DegradationEngine()

    assessment = engine.assess(
        scenario_id="SCN-001",
        telemetry=RuntimeTelemetry(values={}),
        evidence_bundles=(bundle,),
    )

    assert assessment.has_category(DegradationCategory.STALE_EVIDENCE) is True
    assert assessment.worst_level() is DegradationLevel.DEGRADED
    assert assessment.recommended_decision() is AutonomyDecisionType.DEFER
    assert assessment.evidence_bundle_ids == ("BND-STALE",)


def test_invalid_evidence_bundle_creates_critical_evidence_signal() -> None:
    record = EvidenceRecord(
        evidence_id="EV-INVALID",
        kind="scenario-run",
        source="run-bundles/invalid.json",
        payload={"decision": "allow"},
        status=EvidenceStatus.INVALID,
    ).with_computed_hash()
    bundle = EvidenceBundle(
        bundle_id="BND-INVALID",
        case_id="CASE-001",
        records=(record,),
    ).with_computed_hashes()
    engine = DegradationEngine()

    assessment = engine.assess(
        scenario_id="SCN-001",
        telemetry=RuntimeTelemetry(values={}),
        evidence_bundles=(bundle,),
    )

    assert assessment.has_category(DegradationCategory.STALE_EVIDENCE) is True
    assert assessment.worst_level() is DegradationLevel.CRITICAL
    assert assessment.recommended_decision() is AutonomyDecisionType.SAFE_HOLD


def test_unhashed_evidence_bundle_creates_watch_signal() -> None:
    record = EvidenceRecord(
        evidence_id="EV-UNHASHED",
        kind="scenario-run",
        source="run-bundles/unhashed.json",
        payload={"decision": "allow"},
        status=EvidenceStatus.ACCEPTED,
    )
    bundle = EvidenceBundle(
        bundle_id="BND-UNHASHED",
        case_id="CASE-001",
        records=(record,),
    )
    engine = DegradationEngine()

    assessment = engine.assess(
        scenario_id="SCN-001",
        telemetry=RuntimeTelemetry(values={}),
        evidence_bundles=(bundle,),
    )

    assert assessment.has_category(DegradationCategory.STALE_EVIDENCE) is True
    assert assessment.worst_level() is DegradationLevel.WATCH
    assert assessment.recommended_decision() is AutonomyDecisionType.ALLOW


def test_degradation_rule_supports_in_operator() -> None:
    rule = DegradationRule(
        rule_id="MODE-DEGRADED",
        category=DegradationCategory.TIMING_DEGRADATION,
        telemetry_key="autonomy_mode",
        operator=ConditionOperator.IN,
        threshold=("degraded", "recovery"),
        level=DegradationLevel.DEGRADED,
        rationale="Degraded or recovery modes require review.",
        affected_capabilities=("runtime_assurance",),
    )

    signal = rule.evaluate(RuntimeTelemetry(values={"autonomy_mode": "recovery"}))

    assert signal is not None
    assert signal.level is DegradationLevel.DEGRADED
    assert signal.category is DegradationCategory.TIMING_DEGRADATION


def test_degradation_rule_rejects_invalid_between_shape() -> None:
    with pytest.raises(DegradationRuntimeError, match="upper_threshold must not be absent"):
        DegradationRule(
            rule_id="BAD-BETWEEN",
            category=DegradationCategory.NAVIGATION_UNCERTAINTY,
            telemetry_key="navigation_confidence",
            operator=ConditionOperator.BETWEEN,
            threshold=0.40,
            level=DegradationLevel.DEGRADED,
            rationale="Invalid between rule.",
            affected_capabilities=("navigation",),
        )


def test_numeric_degradation_rule_rejects_non_numeric_observed_value() -> None:
    rule = DegradationRule(
        rule_id="NAV-NUMERIC",
        category=DegradationCategory.NAVIGATION_UNCERTAINTY,
        telemetry_key="navigation_confidence",
        operator=ConditionOperator.LT,
        threshold=0.70,
        level=DegradationLevel.DEGRADED,
        rationale="Navigation confidence requires numeric telemetry.",
        affected_capabilities=("navigation",),
    )

    with pytest.raises(DegradationRuntimeError, match="observed telemetry value must be numeric"):
        rule.evaluate(RuntimeTelemetry(values={"navigation_confidence": "low"}))


def test_degradation_engine_rejects_duplicate_rule_and_check_identifiers() -> None:
    rule = DegradationRule(
        rule_id="DUP",
        category=DegradationCategory.POWER_DEGRADATION,
        telemetry_key="power_margin_pct",
        operator=ConditionOperator.LT,
        threshold=20.0,
        level=DegradationLevel.DEGRADED,
        rationale="Low power margin.",
        affected_capabilities=("power",),
    )
    check = TelemetryConflictCheck(
        check_id="DUP",
        primary_key="a",
        comparison_key="b",
        max_allowed_delta=1.0,
        level=DegradationLevel.DEGRADED,
        rationale="Duplicate identifier across rule and check.",
        affected_capabilities=("navigation",),
    )

    with pytest.raises(DegradationRuntimeError, match="duplicate identifiers"):
        DegradationEngine(rules=(rule,), conflict_checks=(check,))


def test_degradation_signal_rejects_duplicate_evidence_ids() -> None:
    with pytest.raises(DegradationRuntimeError, match="evidence_ids must not contain duplicate"):
        DegradationSignal(
            signal_id="SIG-001",
            category=DegradationCategory.STALE_EVIDENCE,
            level=DegradationLevel.DEGRADED,
            source="evidence-record:EV-001",
            rationale="Duplicate evidence identifiers should be rejected.",
            evidence_ids=("EV-001", "EV-001"),
        )


def test_assessment_rejects_duplicate_signal_ids() -> None:
    signal = DegradationSignal(
        signal_id="SIG-001",
        category=DegradationCategory.NAVIGATION_UNCERTAINTY,
        level=DegradationLevel.DEGRADED,
        source="telemetry:test",
        rationale="A degradation signal.",
        affected_capabilities=("navigation",),
    )

    with pytest.raises(DegradationRuntimeError, match="duplicate signal_id"):
        DegradationAssessment(
            scenario_id="SCN-001",
            signals=(signal, signal),
            telemetry_source="simulated-runtime",
        )


def test_conflict_check_rejects_negative_allowed_delta() -> None:
    with pytest.raises(DegradationRuntimeError, match="non-negative"):
        TelemetryConflictCheck(
            check_id="NEGATIVE-DELTA",
            primary_key="a",
            comparison_key="b",
            max_allowed_delta=-1.0,
            level=DegradationLevel.DEGRADED,
            rationale="Negative deltas are invalid.",
            affected_capabilities=("navigation",),
        )


def test_degradation_artifacts_reject_blank_fields() -> None:
    with pytest.raises(DegradationRuntimeError, match="rule_id must not be blank"):
        DegradationRule(
            rule_id=" ",
            category=DegradationCategory.POWER_DEGRADATION,
            telemetry_key="power_margin_pct",
            operator=ConditionOperator.LT,
            threshold=20.0,
            level=DegradationLevel.DEGRADED,
            rationale="Low power margin.",
            affected_capabilities=("power",),
        )
