from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import (
    AutonomyDecisionType,
    HazardSeverity,
    RuntimeAuthorityState,
    VerificationResult,
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
    ScenarioModelError,
    Stressor,
)


def build_valid_catalog() -> ScenarioCatalog:
    context = OperationalContext(
        context_id="CTX-001",
        name="Contested route execution",
        environment="degraded navigation test range",
        mission_phase="route execution",
        description="Autonomy must remain bounded while navigation confidence degrades.",
        constraints=("maintain mission boundary", "preserve operator authority"),
    )
    autonomy_function = AutonomyFunction(
        function_id="AF-001",
        name="Autonomous route manager",
        description="Plans and executes route updates under bounded autonomy.",
        input_signals=("navigation_confidence", "mission_boundary_distance"),
        output_actions=("continue_route", "enter_safe_hold"),
    )
    condition = OperatingCondition(
        condition_id="COND-001",
        name="Navigation confidence degraded",
        description="Navigation confidence is below the nominal execution threshold.",
        telemetry_key="navigation.confidence",
        expected_range="< 0.70",
    )
    stressor = Stressor(
        stressor_id="STR-001",
        name="Navigation drift",
        description="Position estimate diverges from trusted reference telemetry.",
        severity=HazardSeverity.CRITICAL,
        affected_capabilities=("route_execution", "boundary_keeping"),
        trigger_condition="navigation.confidence < 0.70",
    )
    behavior = ExpectedSafeBehavior(
        behavior_id="BEH-001",
        description="Runtime gate forces safe-hold and requires operator review.",
        required_decision=AutonomyDecisionType.SAFE_HOLD,
        required_authority_state=RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
        rationale="Critical navigation uncertainty must block nominal autonomy.",
    )
    criterion = AcceptanceCriterion(
        criterion_id="AC-001",
        statement="Safe-hold is emitted before boundary violation.",
        measurement="runtime_decision",
        expected_result="safe_hold emitted while boundary distance remains positive",
    )
    mission_thread = MissionThread(
        mission_thread_id="MT-001",
        name="Degraded navigation route safety",
        objective="Keep autonomy bounded under degraded navigation.",
        operational_context_id="CTX-001",
        autonomy_function_ids=("AF-001",),
        scenario_ids=("SCN-001",),
        requirement_ids=("REQ-NAV-BOUNDARY-001",),
        hazard_ids=("HZ-NAV-001",),
    )
    scenario = Scenario(
        scenario_id="SCN-001",
        mission_thread_id="MT-001",
        title="Critical navigation drift triggers safe-hold",
        description="Inject navigation drift and verify autonomy leaves nominal execution.",
        operational_context_id="CTX-001",
        autonomy_function_id="AF-001",
        operating_condition_ids=("COND-001",),
        stressor_ids=("STR-001",),
        expected_behavior_id="BEH-001",
        acceptance_criterion_ids=("AC-001",),
        hazard_ids=("HZ-NAV-001",),
        evidence_ids=("EV-SCN-001",),
    )

    return ScenarioCatalog(
        operational_contexts=(context,),
        autonomy_functions=(autonomy_function,),
        operating_conditions=(condition,),
        stressors=(stressor,),
        expected_behaviors=(behavior,),
        acceptance_criteria=(criterion,),
        mission_threads=(mission_thread,),
        scenarios=(scenario,),
    )


def test_valid_catalog_passes_reference_validation() -> None:
    catalog = build_valid_catalog()

    report = catalog.validate_references()

    assert report.is_valid is True
    assert report.errors == ()
    assert report.warnings == ()
    assert catalog.ready_scenario_ids() == ("SCN-001",)


def test_catalog_builds_indexes_by_identifier() -> None:
    catalog = build_valid_catalog()

    assert set(catalog.operational_context_index()) == {"CTX-001"}
    assert set(catalog.autonomy_function_index()) == {"AF-001"}
    assert set(catalog.operating_condition_index()) == {"COND-001"}
    assert set(catalog.stressor_index()) == {"STR-001"}
    assert set(catalog.expected_behavior_index()) == {"BEH-001"}
    assert set(catalog.acceptance_criterion_index()) == {"AC-001"}
    assert set(catalog.mission_thread_index()) == {"MT-001"}
    assert set(catalog.scenario_index()) == {"SCN-001"}


def test_scenarios_can_be_selected_by_mission_thread() -> None:
    catalog = build_valid_catalog()

    scenarios = catalog.scenarios_for_mission_thread("MT-001")

    assert len(scenarios) == 1
    assert scenarios[0].scenario_id == "SCN-001"


def test_catalog_reports_missing_scenario_references() -> None:
    catalog = ScenarioCatalog(
        operational_contexts=(
            OperationalContext(
                context_id="CTX-001",
                name="Known context",
                environment="test range",
                mission_phase="execution",
                description="Known operational context.",
            ),
        ),
        autonomy_functions=(
            AutonomyFunction(
                function_id="AF-001",
                name="Known function",
                description="Known autonomy function.",
                input_signals=("signal",),
                output_actions=("action",),
            ),
        ),
        mission_threads=(
            MissionThread(
                mission_thread_id="MT-001",
                name="Broken mission thread",
                objective="Expose missing scenario reference.",
                operational_context_id="CTX-001",
                autonomy_function_ids=("AF-001",),
                scenario_ids=("SCN-MISSING",),
            ),
        ),
        scenarios=(
            Scenario(
                scenario_id="SCN-001",
                mission_thread_id="MT-MISSING",
                title="Broken scenario",
                description="Scenario intentionally references missing artifacts.",
                operational_context_id="CTX-MISSING",
                autonomy_function_id="AF-MISSING",
                operating_condition_ids=("COND-MISSING",),
                stressor_ids=("STR-MISSING",),
                expected_behavior_id="BEH-MISSING",
                acceptance_criterion_ids=("AC-MISSING",),
            ),
        ),
    )

    report = catalog.validate_references()

    assert report.is_valid is False
    assert "Artifact 'MT-001' references missing scenario 'SCN-MISSING'." in report.errors
    assert "Artifact 'SCN-001' references missing mission thread 'MT-MISSING'." in report.errors
    assert (
        "Artifact 'SCN-001' references missing operational context 'CTX-MISSING'."
        in report.errors
    )
    assert "Artifact 'SCN-001' references missing autonomy function 'AF-MISSING'." in report.errors
    assert (
        "Artifact 'SCN-001' references missing operating condition 'COND-MISSING'."
        in report.errors
    )
    assert "Artifact 'SCN-001' references missing stressor 'STR-MISSING'." in report.errors
    assert (
        "Artifact 'SCN-001' references missing expected safe behavior 'BEH-MISSING'."
        in report.errors
    )
    assert (
        "Artifact 'SCN-001' references missing acceptance criterion 'AC-MISSING'."
        in report.errors
    )


def test_severe_stressor_requires_restrictive_expected_behavior() -> None:
    catalog = build_valid_catalog()
    permissive_behavior = ExpectedSafeBehavior(
        behavior_id="BEH-ALLOW",
        description="Permissive behavior that should be rejected for severe stressors.",
        required_decision=AutonomyDecisionType.ALLOW,
        required_authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
        rationale="This is intentionally unsafe for the test.",
    )
    broken_catalog = ScenarioCatalog(
        operational_contexts=catalog.operational_contexts,
        autonomy_functions=catalog.autonomy_functions,
        operating_conditions=catalog.operating_conditions,
        stressors=catalog.stressors,
        expected_behaviors=(permissive_behavior,),
        acceptance_criteria=catalog.acceptance_criteria,
        mission_threads=catalog.mission_threads,
        scenarios=(
            Scenario(
                scenario_id="SCN-001",
                mission_thread_id="MT-001",
                title="Severe stressor with permissive behavior",
                description="This scenario should fail validation.",
                operational_context_id="CTX-001",
                autonomy_function_id="AF-001",
                operating_condition_ids=("COND-001",),
                stressor_ids=("STR-001",),
                expected_behavior_id="BEH-ALLOW",
                acceptance_criterion_ids=("AC-001",),
                evidence_ids=("EV-SCN-001",),
            ),
        ),
    )

    report = broken_catalog.validate_references()

    assert report.is_valid is False
    assert (
        "Scenario 'SCN-001' includes severe stressor(s) 'STR-001' but expected behavior "
        "'BEH-ALLOW' does not restrict autonomy."
    ) in report.errors


def test_scenario_with_evidence_required_but_no_evidence_gets_warning() -> None:
    catalog = build_valid_catalog()
    scenario_without_evidence = Scenario(
        scenario_id="SCN-001",
        mission_thread_id="MT-001",
        title="Scenario missing evidence identifiers",
        description="The scenario is structurally valid but has not received evidence yet.",
        operational_context_id="CTX-001",
        autonomy_function_id="AF-001",
        operating_condition_ids=("COND-001",),
        stressor_ids=("STR-001",),
        expected_behavior_id="BEH-001",
        acceptance_criterion_ids=("AC-001",),
    )
    warning_catalog = ScenarioCatalog(
        operational_contexts=catalog.operational_contexts,
        autonomy_functions=catalog.autonomy_functions,
        operating_conditions=catalog.operating_conditions,
        stressors=catalog.stressors,
        expected_behaviors=catalog.expected_behaviors,
        acceptance_criteria=catalog.acceptance_criteria,
        mission_threads=catalog.mission_threads,
        scenarios=(scenario_without_evidence,),
    )

    report = warning_catalog.validate_references()

    assert report.is_valid is True
    assert report.warnings == (
        "Scenario 'SCN-001' requires evidence but has no evidence identifiers yet.",
    )


def test_acceptance_criterion_accepts_only_required_verification_result() -> None:
    criterion = AcceptanceCriterion(
        criterion_id="AC-001",
        statement="Scenario must pass.",
        measurement="verification_result",
        expected_result="pass",
        required_verification_result=VerificationResult.PASS,
    )

    assert criterion.accepts_result(VerificationResult.PASS) is True
    assert criterion.accepts_result(VerificationResult.FAIL) is False
    assert criterion.accepts_result(VerificationResult.INCONCLUSIVE) is False


def test_autonomy_function_reports_default_human_authority_requirement() -> None:
    function = AutonomyFunction(
        function_id="AF-HUMAN",
        name="Human-gated function",
        description="Function normally requires human approval.",
        input_signals=("operator_command",),
        output_actions=("execute_command",),
        nominal_authority_state=RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
    )

    assert function.requires_human_authority_by_default() is True


def test_stressor_severity_marks_restrictive_response_requirement() -> None:
    minor = Stressor(
        stressor_id="STR-MINOR",
        name="Minor nuisance",
        description="Minor issue that does not require restrictive behavior by itself.",
        severity=HazardSeverity.MINOR,
        affected_capabilities=("telemetry_quality",),
        trigger_condition="telemetry jitter detected",
    )
    critical = Stressor(
        stressor_id="STR-CRITICAL",
        name="Critical degradation",
        description="Critical issue requiring constrained behavior.",
        severity=HazardSeverity.CRITICAL,
        affected_capabilities=("navigation",),
        trigger_condition="navigation confidence lost",
    )

    assert minor.requires_restrictive_response() is False
    assert critical.requires_restrictive_response() is True


def test_model_rejects_blank_required_fields() -> None:
    with pytest.raises(ScenarioModelError, match="scenario_id must not be blank"):
        Scenario(
            scenario_id=" ",
            mission_thread_id="MT-001",
            title="Title",
            description="Description",
            operational_context_id="CTX-001",
            autonomy_function_id="AF-001",
            operating_condition_ids=("COND-001",),
            stressor_ids=(),
            expected_behavior_id="BEH-001",
            acceptance_criterion_ids=("AC-001",),
        )


def test_model_rejects_empty_autonomy_function_io() -> None:
    with pytest.raises(ScenarioModelError, match="input_signals must not be empty"):
        AutonomyFunction(
            function_id="AF-BAD",
            name="Bad function",
            description="Function has no inputs.",
            input_signals=(),
            output_actions=("action",),
        )

    with pytest.raises(ScenarioModelError, match="output_actions must not be empty"):
        AutonomyFunction(
            function_id="AF-BAD",
            name="Bad function",
            description="Function has no outputs.",
            input_signals=("signal",),
            output_actions=(),
        )


def test_model_rejects_duplicate_identifier_lists() -> None:
    with pytest.raises(ScenarioModelError, match="scenario_ids must not contain duplicate"):
        MissionThread(
            mission_thread_id="MT-DUP",
            name="Duplicate scenario references",
            objective="Reject duplicate scenario identifiers.",
            operational_context_id="CTX-001",
            autonomy_function_ids=("AF-001",),
            scenario_ids=("SCN-001", "SCN-001"),
        )


def test_catalog_reports_global_duplicate_artifact_identifiers() -> None:
    catalog = ScenarioCatalog(
        operational_contexts=(
            OperationalContext(
                context_id="DUP-001",
                name="Context",
                environment="test range",
                mission_phase="execution",
                description="Context with duplicate global identifier.",
            ),
        ),
        autonomy_functions=(
            AutonomyFunction(
                function_id="DUP-001",
                name="Function",
                description="Function with duplicate global identifier.",
                input_signals=("signal",),
                output_actions=("action",),
            ),
        ),
        mission_threads=(
            MissionThread(
                mission_thread_id="MT-001",
                name="Mission thread",
                objective="Expose duplicate global identifiers.",
                operational_context_id="DUP-001",
                autonomy_function_ids=("DUP-001",),
            ),
        ),
        scenarios=(
            Scenario(
                scenario_id="SCN-001",
                mission_thread_id="MT-001",
                title="Scenario",
                description="Scenario exists so catalog has a scenario.",
                operational_context_id="DUP-001",
                autonomy_function_id="DUP-001",
                operating_condition_ids=("COND-MISSING",),
                stressor_ids=(),
                expected_behavior_id="BEH-MISSING",
                acceptance_criterion_ids=("AC-MISSING",),
            ),
        ),
    )

    report = catalog.validate_references()

    assert "Scenario artifact identifier 'DUP-001' is duplicated." in report.errors
