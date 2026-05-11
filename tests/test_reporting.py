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
from ix_autonomy_assurance_case_runtime.reporting import (
    AssuranceReport,
    AssuranceReportGenerator,
    ReportGenerationError,
    ReportSection,
    ReportSeverity,
)
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
from ix_autonomy_assurance_case_runtime.verification import VerificationEngine


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
    )
    mission_thread = MissionThread(
        mission_thread_id="MT-001",
        name="Navigation assurance mission thread",
        objective="Keep autonomy bounded during degraded navigation.",
        operational_context_id="CTX-001",
        autonomy_function_ids=("AF-001",),
        scenario_ids=("SCN-001",),
        requirement_ids=("REQ-001",),
        hazard_ids=("HZ-001",),
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
        hazard_ids=("HZ-001",),
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


def build_report() -> AssuranceReport:
    assurance_case = build_assurance_case()
    scenario_catalog = build_scenario_catalog()
    run_result = ScenarioRunner().run(
        catalog=scenario_catalog,
        run_input=ScenarioRunInput(
            run_id="RUN-001",
            case_id="CASE-001",
            scenario_id="SCN-001",
            telemetry=RuntimeTelemetry(
                values={
                    "navigation_confidence": 0.62,
                    "power_margin_pct": 80.0,
                    "comms_link_active": True,
                },
                source="simulated-runtime",
            ),
        ),
    )
    traceability_graph = build_traceability_graph_instance()
    verification_summary = VerificationEngine(require_traceability=True).verify_run(
        assurance_case=assurance_case,
        scenario_catalog=scenario_catalog,
        run_result=run_result,
        traceability_graph=traceability_graph,
    )

    return AssuranceReportGenerator().generate(
        report_id="RPT-001",
        assurance_case=assurance_case,
        scenario_catalog=scenario_catalog,
        run_result=run_result,
        verification_summary=verification_summary,
        traceability_graph=traceability_graph,
    )


def test_report_generator_creates_accepted_report_for_verified_run() -> None:
    report = build_report()

    assert report.report_id == "RPT-001"
    assert report.case_id == "CASE-001"
    assert report.scenario_id == "SCN-001"
    assert report.run_id == "RUN-001"
    assert report.overall_result is VerificationResult.PASS
    assert report.accepted() is True
    assert report.error_section_titles() == ()
    assert report.warning_section_titles() == ("Runtime Outcome",)


def test_report_contains_expected_sections_in_order() -> None:
    report = build_report()

    assert report.section_titles() == (
        "Executive Summary",
        "Runtime Outcome",
        "Verification Checks",
        "Assurance Gaps",
        "Claim Posture",
        "Acceptance Criteria",
        "Evidence Integrity",
        "Traceability",
    )


def test_report_dictionary_is_machine_readable() -> None:
    report = build_report()
    payload = report.to_dict()

    assert payload["accepted"] is True
    assert payload["overall_result"] == "pass"
    assert payload["report_id"] == "RPT-001"
    assert payload["case_id"] == "CASE-001"
    assert payload["scenario_id"] == "SCN-001"
    assert payload["run_id"] == "RUN-001"

    sections = payload["sections"]
    assert isinstance(sections, list)
    assert len(sections) == 8
    assert sections[0]["title"] == "Executive Summary"


def test_report_markdown_is_human_readable() -> None:
    report = build_report()
    markdown = report.to_markdown()

    assert "# Assurance Report: RPT-001" in markdown
    assert "- Case ID: `CASE-001`" in markdown
    assert "- Overall Result: `pass`" in markdown
    assert "## Executive Summary" in markdown
    assert "## Evidence Integrity" in markdown
    assert "Evidence bundle: `BND-RUN-001`." in markdown


def test_report_generator_marks_failed_acceptance_criteria() -> None:
    assurance_case = build_assurance_case()
    scenario_catalog = build_scenario_catalog(
        expected_decision=AutonomyDecisionType.SAFE_HOLD,
        expected_authority=RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
    )
    run_result = ScenarioRunner().run(
        catalog=scenario_catalog,
        run_input=ScenarioRunInput(
            run_id="RUN-FAIL",
            case_id="CASE-001",
            scenario_id="SCN-001",
            telemetry=RuntimeTelemetry(
                values={
                    "navigation_confidence": 0.99,
                    "power_margin_pct": 80.0,
                    "comms_link_active": True,
                },
            ),
        ),
    )
    verification_summary = VerificationEngine(require_traceability=True).verify_run(
        assurance_case=assurance_case,
        scenario_catalog=scenario_catalog,
        run_result=run_result,
    )

    report = AssuranceReportGenerator().generate(
        report_id="RPT-FAIL",
        assurance_case=assurance_case,
        scenario_catalog=scenario_catalog,
        run_result=run_result,
        verification_summary=verification_summary,
    )

    assert report.accepted() is False
    assert "Executive Summary" in report.error_section_titles()
    assert "Traceability" in report.error_section_titles()
    assert report.overall_result is VerificationResult.FAIL


def test_report_generator_identifies_assurance_gaps() -> None:
    broken_case = AssuranceCase(
        case_id="CASE-001",
        title="Broken Assurance Case",
        system_name="Reference Autonomy Stack",
        mission_context="Mission context exists.",
        claims=(
            AssuranceClaim(
                claim_id="CLM-BLOCKED",
                statement="Unsupported claim.",
                argument="This claim has no support path.",
            ),
        ),
        hazards=(
            Hazard(
                hazard_id="HZ-CRITICAL",
                title="Unresolved critical hazard",
                description="Critical hazard lacks control or mitigation path.",
                severity=HazardSeverity.CRITICAL,
                evidence_ids=("EV-MISSING",),
            ),
        ),
    )
    scenario_catalog = build_scenario_catalog()
    run_result = ScenarioRunner().run(
        catalog=scenario_catalog,
        run_input=ScenarioRunInput(
            run_id="RUN-GAPS",
            case_id="CASE-001",
            scenario_id="SCN-001",
            telemetry=RuntimeTelemetry(
                values={
                    "navigation_confidence": 0.62,
                    "power_margin_pct": 80.0,
                    "comms_link_active": True,
                },
            ),
        ),
    )
    verification_summary = VerificationEngine().verify_run(
        assurance_case=broken_case,
        scenario_catalog=scenario_catalog,
        run_result=run_result,
    )

    report = AssuranceReportGenerator().generate(
        report_id="RPT-GAPS",
        assurance_case=broken_case,
        scenario_catalog=scenario_catalog,
        run_result=run_result,
        verification_summary=verification_summary,
    )

    assert "Assurance Gaps" in report.error_section_titles()

    markdown = report.to_markdown()
    assert "HZ-CRITICAL" in markdown
    assert "CLM-BLOCKED" in markdown
    assert "EV-MISSING" in markdown


def test_report_generator_rejects_case_id_mismatch() -> None:
    assurance_case = build_assurance_case()
    scenario_catalog = build_scenario_catalog()
    run_result = ScenarioRunner().run(
        catalog=scenario_catalog,
        run_input=ScenarioRunInput(
            run_id="RUN-001",
            case_id="CASE-001",
            scenario_id="SCN-001",
            telemetry=RuntimeTelemetry(
                values={
                    "navigation_confidence": 0.62,
                    "power_margin_pct": 80.0,
                    "comms_link_active": True,
                },
            ),
        ),
    )
    verification_summary = VerificationEngine().verify_run(
        assurance_case=assurance_case,
        scenario_catalog=scenario_catalog,
        run_result=run_result,
    )
    mismatched_case = AssuranceCase(
        case_id="CASE-OTHER",
        title=assurance_case.title,
        system_name=assurance_case.system_name,
        mission_context=assurance_case.mission_context,
        claims=assurance_case.claims,
        hazards=assurance_case.hazards,
        controls=assurance_case.controls,
        mitigations=assurance_case.mitigations,
        evidence=assurance_case.evidence,
        verification_criteria=assurance_case.verification_criteria,
    )

    with pytest.raises(ReportGenerationError, match="does not match run case"):
        AssuranceReportGenerator().generate(
            report_id="RPT-BAD",
            assurance_case=mismatched_case,
            scenario_catalog=scenario_catalog,
            run_result=run_result,
            verification_summary=verification_summary,
        )


def test_report_section_requires_lines() -> None:
    with pytest.raises(ReportGenerationError, match="section lines must not be empty"):
        ReportSection(
            title="Empty Section",
            severity=ReportSeverity.INFO,
            lines=(),
        )


def test_report_requires_sections() -> None:
    with pytest.raises(ReportGenerationError, match="sections must not be empty"):
        AssuranceReport(
            report_id="RPT-EMPTY",
            case_id="CASE-001",
            scenario_id="SCN-001",
            run_id="RUN-001",
            overall_result=VerificationResult.PASS,
            generated_by="test",
            sections=(),
        )
