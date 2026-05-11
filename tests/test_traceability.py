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
    TraceEdge,
    TraceEdgeType,
    TraceNode,
    TraceNodeType,
    TraceabilityError,
    TraceabilityGraph,
    build_traceability_graph,
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


def build_scenario_catalog() -> ScenarioCatalog:
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
        requirement_ids=("REQ-001",),
        hazard_ids=("HZ-001",),
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
        hazard_ids=("HZ-001",),
        evidence_ids=("EV-001",),
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


def build_evidence_bundle() -> EvidenceBundle:
    record = EvidenceRecord(
        evidence_id="EV-RUNTIME-001",
        kind="runtime-decision",
        source="run-bundles/scn-001-runtime.json",
        payload={
            "decision": "safe_hold",
            "navigation_confidence": 0.42,
            "boundary_distance_ft": 125.0,
        },
        status=EvidenceStatus.ACCEPTED,
        tags=("navigation", "safe-hold"),
    ).with_computed_hash()

    return EvidenceBundle(
        bundle_id="BND-001",
        case_id="CASE-001",
        scenario_id="SCN-001",
        records=(record,),
    ).with_computed_hashes()


def build_graph() -> TraceabilityGraph:
    return build_traceability_graph(
        mission_need=MissionNeed(
            need_id="MN-001",
            statement="Autonomous mission behavior remains bounded under degraded conditions.",
            operational_driver="trusted autonomy T&E",
        ),
        requirements=(
            Requirement(
                requirement_id="REQ-001",
                statement="The autonomy function shall enter safe-hold when navigation is degraded.",
                verification_method="fault-injection scenario with runtime evidence",
                source="system safety requirement",
            ),
        ),
        assurance_case=build_assurance_case(),
        scenario_catalog=build_scenario_catalog(),
        evidence_bundles=(build_evidence_bundle(),),
    )


def test_traceability_graph_builds_expected_nodes() -> None:
    graph = build_graph()
    node_index = graph.node_index()

    assert node_index["MN-001"].node_type is TraceNodeType.MISSION_NEED
    assert node_index["REQ-001"].node_type is TraceNodeType.REQUIREMENT
    assert node_index["HZ-001"].node_type is TraceNodeType.HAZARD
    assert node_index["CTRL-001"].node_type is TraceNodeType.CONTROL
    assert node_index["SCN-001"].node_type is TraceNodeType.SCENARIO
    assert node_index["EV-001"].node_type is TraceNodeType.EVIDENCE
    assert node_index["EV-RUNTIME-001"].node_type is TraceNodeType.EVIDENCE
    assert node_index["CLM-001"].node_type is TraceNodeType.ASSURANCE_CLAIM


def test_traceability_graph_validates_without_errors_or_warnings() -> None:
    graph = build_graph()

    report = graph.validate()

    assert report.is_valid is True
    assert report.errors == ()
    assert report.warnings == ()


def test_traceability_graph_provides_directed_path_from_mission_need_to_claim() -> None:
    graph = build_graph()

    assert graph.has_directed_path("MN-001", "REQ-001") is True
    assert graph.has_directed_path("REQ-001", "SCN-001") is True
    assert graph.has_directed_path("SCN-001", "EV-001") is True
    assert graph.has_directed_path("EV-001", "CLM-001") is True
    assert graph.has_directed_path("MN-001", "CLM-001") is True


def test_traceability_graph_exposes_undirected_connections_for_assurance_review() -> None:
    graph = build_graph()

    assert graph.has_connected_path("CLM-001", "HZ-001") is True
    assert graph.has_connected_path("CLM-001", "CTRL-001") is True
    assert graph.has_connected_path("CLM-001", "STR-001") is True


def test_traceability_graph_returns_reachable_nodes() -> None:
    graph = build_graph()

    reachable = graph.reachable_from("MN-001")

    assert "REQ-001" in reachable
    assert "SCN-001" in reachable
    assert "EV-001" in reachable
    assert "CLM-001" in reachable


def test_traceability_graph_detects_missing_edge_endpoints() -> None:
    graph = TraceabilityGraph(
        nodes=(
            TraceNode(
                node_id="NODE-001",
                node_type=TraceNodeType.MISSION_NEED,
                title="A valid node",
            ),
        ),
        edges=(
            TraceEdge(
                source_id="NODE-001",
                target_id="NODE-MISSING",
                edge_type=TraceEdgeType.REFERENCES,
                rationale="This edge intentionally points to a missing node.",
            ),
        ),
    )

    report = graph.validate()

    assert report.is_valid is False
    assert report.errors == (
        "Trace edge 'references' references missing target node 'NODE-MISSING'.",
    )


def test_traceability_graph_detects_duplicate_node_ids() -> None:
    graph = TraceabilityGraph(
        nodes=(
            TraceNode(
                node_id="DUP-001",
                node_type=TraceNodeType.MISSION_NEED,
                title="First node",
            ),
            TraceNode(
                node_id="DUP-001",
                node_type=TraceNodeType.REQUIREMENT,
                title="Second node",
            ),
        ),
        edges=(),
    )

    report = graph.validate()

    assert report.is_valid is False
    assert "Trace node identifier 'DUP-001' is duplicated." in report.errors


def test_traceability_graph_warns_on_orphan_nodes() -> None:
    graph = TraceabilityGraph(
        nodes=(
            TraceNode(
                node_id="NODE-001",
                node_type=TraceNodeType.MISSION_NEED,
                title="Connected node",
            ),
            TraceNode(
                node_id="NODE-002",
                node_type=TraceNodeType.REQUIREMENT,
                title="Orphan node",
            ),
        ),
        edges=(
            TraceEdge(
                source_id="NODE-001",
                target_id="NODE-MISSING",
                edge_type=TraceEdgeType.REFERENCES,
                rationale="This keeps NODE-001 connected while leaving NODE-002 orphaned.",
            ),
        ),
    )

    report = graph.validate()

    assert "Trace node 'NODE-002' has no traceability edges." in report.warnings


def test_traceability_artifacts_reject_blank_fields() -> None:
    with pytest.raises(TraceabilityError, match="need_id must not be blank"):
        MissionNeed(
            need_id=" ",
            statement="Valid mission need.",
            operational_driver="trusted autonomy T&E",
        )

    with pytest.raises(TraceabilityError, match="requirement_id must not be blank"):
        Requirement(
            requirement_id=" ",
            statement="Valid requirement.",
            verification_method="scenario test",
            source="system safety requirement",
        )


def test_trace_node_rejects_duplicate_metadata_keys() -> None:
    with pytest.raises(TraceabilityError, match="metadata key 'source' is duplicated"):
        TraceNode(
            node_id="NODE-001",
            node_type=TraceNodeType.REQUIREMENT,
            title="Requirement node",
            metadata=(("source", "one"), ("source", "two")),
        )


def test_trace_edge_rejects_self_reference() -> None:
    with pytest.raises(TraceabilityError, match="must not point from a node to itself"):
        TraceEdge(
            source_id="NODE-001",
            target_id="NODE-001",
            edge_type=TraceEdgeType.REFERENCES,
            rationale="Self references are not useful traceability.",
        )


def test_missing_start_node_returns_no_reachable_nodes() -> None:
    graph = build_graph()

    assert graph.reachable_from("MISSING") == ()
    assert graph.connected_component("MISSING") == ()
