"""Traceability graph for mission need, requirements, scenarios, evidence, and claims.

This module gives the assurance runtime a deterministic way to prove that a
runtime scenario is not just a standalone test. It connects mission need,
requirements, mission threads, scenarios, hazards, controls, evidence, and
assurance claims into a reviewable graph that can be validated and queried.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

from ix_autonomy_assurance_case_runtime.assurance_case import AssuranceCase
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.scenarios import ScenarioCatalog


class TraceabilityError(ValueError):
    """Raised when a traceability artifact is malformed."""


class TraceNodeType(StrEnum):
    """Supported node types in the traceability graph."""

    MISSION_NEED = "mission_need"
    REQUIREMENT = "requirement"
    OPERATIONAL_CONTEXT = "operational_context"
    AUTONOMY_FUNCTION = "autonomy_function"
    OPERATING_CONDITION = "operating_condition"
    STRESSOR = "stressor"
    EXPECTED_SAFE_BEHAVIOR = "expected_safe_behavior"
    ACCEPTANCE_CRITERION = "acceptance_criterion"
    MISSION_THREAD = "mission_thread"
    SCENARIO = "scenario"
    HAZARD = "hazard"
    CONTROL = "control"
    MITIGATION = "mitigation"
    ASSUMPTION = "assumption"
    EVIDENCE = "evidence"
    EVIDENCE_BUNDLE = "evidence_bundle"
    VERIFICATION_CRITERION = "verification_criterion"
    ASSURANCE_CLAIM = "assurance_claim"


class TraceEdgeType(StrEnum):
    """Supported edge types in the traceability graph."""

    REFERENCES = "references"
    DERIVES = "derives"
    ALLOCATES = "allocates"
    COVERS = "covers"
    EVALUATES = "evaluates"
    EXPECTS = "expects"
    MITIGATES = "mitigates"
    SUPPORTS = "supports"
    PRODUCES = "produces"
    CONTAINS = "contains"


@dataclass(frozen=True, slots=True)
class MissionNeed:
    """Mission-level need that requirements and evidence must trace back to."""

    need_id: str
    statement: str
    operational_driver: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "need_id", _require_text(self.need_id, "need_id"))
        object.__setattr__(self, "statement", _require_text(self.statement, "statement"))
        object.__setattr__(
            self,
            "operational_driver",
            _require_text(self.operational_driver, "operational_driver"),
        )


@dataclass(frozen=True, slots=True)
class Requirement:
    """System or mission requirement verified by scenarios and evidence."""

    requirement_id: str
    statement: str
    verification_method: str
    source: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "requirement_id",
            _require_text(self.requirement_id, "requirement_id"),
        )
        object.__setattr__(self, "statement", _require_text(self.statement, "statement"))
        object.__setattr__(
            self,
            "verification_method",
            _require_text(self.verification_method, "verification_method"),
        )
        object.__setattr__(self, "source", _require_text(self.source, "source"))


@dataclass(frozen=True, slots=True)
class TraceNode:
    """One traceability graph node."""

    node_id: str
    node_type: TraceNodeType
    title: str
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", _require_text(self.node_id, "node_id"))
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        object.__setattr__(self, "metadata", _normalize_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class TraceEdge:
    """Directed traceability relationship between two nodes."""

    source_id: str
    target_id: str
    edge_type: TraceEdgeType
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _require_text(self.source_id, "source_id"))
        object.__setattr__(self, "target_id", _require_text(self.target_id, "target_id"))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))

        if self.source_id == self.target_id:
            raise TraceabilityError("Trace edge must not point from a node to itself.")


@dataclass(frozen=True, slots=True)
class TraceabilityValidationReport:
    """Validation result for a traceability graph."""

    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        """Return whether the graph has no validation errors."""

        return not self.errors


@dataclass(frozen=True, slots=True)
class TraceabilityGraph:
    """Directed graph with review-friendly directed and undirected queries."""

    nodes: tuple[TraceNode, ...]
    edges: tuple[TraceEdge, ...]

    def node_index(self) -> dict[str, TraceNode]:
        """Return graph nodes keyed by identifier."""

        return {node.node_id: node for node in self.nodes}

    def edge_index(self) -> dict[tuple[str, str, TraceEdgeType], TraceEdge]:
        """Return graph edges keyed by source, target, and edge type."""

        return {(edge.source_id, edge.target_id, edge.edge_type): edge for edge in self.edges}

    def validate(self) -> TraceabilityValidationReport:
        """Validate identifiers, edge endpoints, duplicate edges, and orphan nodes."""

        errors: list[str] = []
        warnings: list[str] = []
        node_ids = tuple(node.node_id for node in self.nodes)
        known_node_ids = set(node_ids)

        for duplicate_node_id in sorted(
            {node_id for node_id in node_ids if node_ids.count(node_id) > 1}
        ):
            errors.append(f"Trace node identifier {duplicate_node_id!r} is duplicated.")

        edge_keys = tuple((edge.source_id, edge.target_id, edge.edge_type) for edge in self.edges)
        for duplicate_edge in sorted(
            {edge_key for edge_key in edge_keys if edge_keys.count(edge_key) > 1}
        ):
            source_id, target_id, edge_type = duplicate_edge
            errors.append(
                f"Trace edge {edge_type.value!r} from {source_id!r} to {target_id!r} is duplicated."
            )

        connected_node_ids: set[str] = set()
        for edge in self.edges:
            connected_node_ids.add(edge.source_id)
            connected_node_ids.add(edge.target_id)

            if edge.source_id not in known_node_ids:
                errors.append(
                    f"Trace edge {edge.edge_type.value!r} references missing source node "
                    f"{edge.source_id!r}."
                )
            if edge.target_id not in known_node_ids:
                errors.append(
                    f"Trace edge {edge.edge_type.value!r} references missing target node "
                    f"{edge.target_id!r}."
                )

        for node_id in sorted(known_node_ids - connected_node_ids):
            warnings.append(f"Trace node {node_id!r} has no traceability edges.")

        return TraceabilityValidationReport(errors=tuple(errors), warnings=tuple(warnings))

    def reachable_from(self, start_node_id: str) -> tuple[str, ...]:
        """Return node IDs reachable from a starting node through directed edges."""

        return self._traverse(start_node_id, undirected=False)

    def connected_component(self, start_node_id: str) -> tuple[str, ...]:
        """Return node IDs connected to a starting node through undirected edges."""

        return self._traverse(start_node_id, undirected=True)

    def has_directed_path(self, source_id: str, target_id: str) -> bool:
        """Return whether a directed path exists from source to target."""

        if source_id == target_id:
            return source_id in self.node_index()
        return target_id in self.reachable_from(source_id)

    def has_connected_path(self, source_id: str, target_id: str) -> bool:
        """Return whether an undirected connection exists between two nodes."""

        if source_id == target_id:
            return source_id in self.node_index()
        return target_id in self.connected_component(source_id)

    def _traverse(self, start_node_id: str, *, undirected: bool) -> tuple[str, ...]:
        node_ids = set(self.node_index())
        if start_node_id not in node_ids:
            return ()

        adjacency = self._undirected_adjacency() if undirected else self._directed_adjacency()
        visited = {start_node_id}
        reachable: list[str] = []
        queue: deque[str] = deque(sorted(adjacency.get(start_node_id, set())))

        while queue:
            node_id = queue.popleft()
            if node_id in visited or node_id not in node_ids:
                continue
            visited.add(node_id)
            reachable.append(node_id)
            queue.extend(sorted(adjacency.get(node_id, set()) - visited))

        return tuple(reachable)

    def _directed_adjacency(self) -> dict[str, set[str]]:
        adjacency: dict[str, set[str]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge.source_id, set()).add(edge.target_id)
        return adjacency

    def _undirected_adjacency(self) -> dict[str, set[str]]:
        adjacency: dict[str, set[str]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge.source_id, set()).add(edge.target_id)
            adjacency.setdefault(edge.target_id, set()).add(edge.source_id)
        return adjacency


def build_traceability_graph(
    *,
    mission_need: MissionNeed,
    requirements: tuple[Requirement, ...],
    assurance_case: AssuranceCase,
    scenario_catalog: ScenarioCatalog,
    evidence_bundles: tuple[EvidenceBundle, ...] = (),
) -> TraceabilityGraph:
    """Build a deterministic traceability graph from runtime assurance artifacts."""

    builder = _TraceabilityGraphBuilder()
    builder.add_node(
        TraceNode(
            node_id=mission_need.need_id,
            node_type=TraceNodeType.MISSION_NEED,
            title=mission_need.statement,
            metadata=(("operational_driver", mission_need.operational_driver),),
        )
    )

    for requirement in requirements:
        builder.add_node(
            TraceNode(
                node_id=requirement.requirement_id,
                node_type=TraceNodeType.REQUIREMENT,
                title=requirement.statement,
                metadata=(
                    ("source", requirement.source),
                    ("verification_method", requirement.verification_method),
                ),
            )
        )
        builder.add_edge(
            mission_need.need_id,
            requirement.requirement_id,
            TraceEdgeType.DERIVES,
            "Mission need derives a verifiable requirement.",
        )

    _add_scenario_nodes(builder, scenario_catalog)
    _add_assurance_case_nodes(builder, assurance_case)
    _add_evidence_bundle_nodes(builder, evidence_bundles)
    _add_requirement_edges(builder, requirements, scenario_catalog)
    _add_scenario_edges(builder, scenario_catalog)
    _add_assurance_case_edges(builder, assurance_case)
    _add_evidence_bundle_edges(builder, evidence_bundles)

    return builder.build()


@dataclass(slots=True)
class _TraceabilityGraphBuilder:
    nodes: dict[str, TraceNode] = field(default_factory=dict)
    edges: dict[tuple[str, str, TraceEdgeType], TraceEdge] = field(default_factory=dict)

    def add_node(self, node: TraceNode) -> None:
        self.nodes.setdefault(node.node_id, node)

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: TraceEdgeType,
        rationale: str,
    ) -> None:
        key = (source_id, target_id, edge_type)
        self.edges.setdefault(
            key,
            TraceEdge(
                source_id=source_id,
                target_id=target_id,
                edge_type=edge_type,
                rationale=rationale,
            ),
        )

    def build(self) -> TraceabilityGraph:
        return TraceabilityGraph(
            nodes=tuple(self.nodes[key] for key in sorted(self.nodes)),
            edges=tuple(
                self.edges[key]
                for key in sorted(
                    self.edges,
                    key=lambda item: (item[0], item[1], item[2].value),
                )
            ),
        )


def _add_scenario_nodes(builder: _TraceabilityGraphBuilder, catalog: ScenarioCatalog) -> None:
    for context in catalog.operational_contexts:
        builder.add_node(
            TraceNode(
                node_id=context.context_id,
                node_type=TraceNodeType.OPERATIONAL_CONTEXT,
                title=context.name,
                metadata=(
                    ("environment", context.environment),
                    ("mission_phase", context.mission_phase),
                ),
            )
        )

    for autonomy_function in catalog.autonomy_functions:
        builder.add_node(
            TraceNode(
                node_id=autonomy_function.function_id,
                node_type=TraceNodeType.AUTONOMY_FUNCTION,
                title=autonomy_function.name,
                metadata=(
                    (
                        "nominal_authority_state",
                        autonomy_function.nominal_authority_state.value,
                    ),
                ),
            )
        )

    for operating_condition in catalog.operating_conditions:
        builder.add_node(
            TraceNode(
                node_id=operating_condition.condition_id,
                node_type=TraceNodeType.OPERATING_CONDITION,
                title=operating_condition.name,
                metadata=(
                    ("telemetry_key", operating_condition.telemetry_key),
                    ("expected_range", operating_condition.expected_range),
                ),
            )
        )

    for stressor in catalog.stressors:
        builder.add_node(
            TraceNode(
                node_id=stressor.stressor_id,
                node_type=TraceNodeType.STRESSOR,
                title=stressor.name,
                metadata=(
                    ("severity", stressor.severity.value),
                    ("trigger_condition", stressor.trigger_condition),
                ),
            )
        )

    for behavior in catalog.expected_behaviors:
        builder.add_node(
            TraceNode(
                node_id=behavior.behavior_id,
                node_type=TraceNodeType.EXPECTED_SAFE_BEHAVIOR,
                title=behavior.description,
                metadata=(
                    ("required_decision", behavior.required_decision.value),
                    ("required_authority_state", behavior.required_authority_state.value),
                ),
            )
        )

    for acceptance_criterion in catalog.acceptance_criteria:
        builder.add_node(
            TraceNode(
                node_id=acceptance_criterion.criterion_id,
                node_type=TraceNodeType.ACCEPTANCE_CRITERION,
                title=acceptance_criterion.statement,
                metadata=(
                    ("measurement", acceptance_criterion.measurement),
                    (
                        "required_verification_result",
                        acceptance_criterion.required_verification_result.value,
                    ),
                ),
            )
        )

    for mission_thread in catalog.mission_threads:
        builder.add_node(
            TraceNode(
                node_id=mission_thread.mission_thread_id,
                node_type=TraceNodeType.MISSION_THREAD,
                title=mission_thread.name,
                metadata=(("objective", mission_thread.objective),),
            )
        )

    for scenario in catalog.scenarios:
        builder.add_node(
            TraceNode(
                node_id=scenario.scenario_id,
                node_type=TraceNodeType.SCENARIO,
                title=scenario.title,
                metadata=(("mission_thread_id", scenario.mission_thread_id),),
            )
        )


def _add_assurance_case_nodes(
    builder: _TraceabilityGraphBuilder, assurance_case: AssuranceCase
) -> None:
    for hazard in assurance_case.hazards:
        builder.add_node(
            TraceNode(
                node_id=hazard.hazard_id,
                node_type=TraceNodeType.HAZARD,
                title=hazard.title,
                metadata=(("severity", hazard.severity.value),),
            )
        )

    for control in assurance_case.controls:
        builder.add_node(
            TraceNode(
                node_id=control.control_id,
                node_type=TraceNodeType.CONTROL,
                title=control.name,
            )
        )

    for mitigation in assurance_case.mitigations:
        builder.add_node(
            TraceNode(
                node_id=mitigation.mitigation_id,
                node_type=TraceNodeType.MITIGATION,
                title=mitigation.description,
            )
        )

    for assumption in assurance_case.assumptions:
        builder.add_node(
            TraceNode(
                node_id=assumption.assumption_id,
                node_type=TraceNodeType.ASSUMPTION,
                title=assumption.statement,
            )
        )

    for evidence in assurance_case.evidence:
        builder.add_node(
            TraceNode(
                node_id=evidence.evidence_id,
                node_type=TraceNodeType.EVIDENCE,
                title=evidence.description,
                metadata=(("status", evidence.status.value), ("source", evidence.source)),
            )
        )

    for verification_criterion in assurance_case.verification_criteria:
        builder.add_node(
            TraceNode(
                node_id=verification_criterion.criterion_id,
                node_type=TraceNodeType.VERIFICATION_CRITERION,
                title=verification_criterion.statement,
                metadata=(
                    ("verification_method", verification_criterion.verification_method),
                    ("result", verification_criterion.result.value),
                ),
            )
        )

    for claim in assurance_case.claims:
        builder.add_node(
            TraceNode(
                node_id=claim.claim_id,
                node_type=TraceNodeType.ASSURANCE_CLAIM,
                title=claim.statement,
                metadata=(("verification_result", claim.verification_result.value),),
            )
        )


def _add_evidence_bundle_nodes(
    builder: _TraceabilityGraphBuilder,
    evidence_bundles: tuple[EvidenceBundle, ...],
) -> None:
    for bundle in evidence_bundles:
        builder.add_node(
            TraceNode(
                node_id=bundle.bundle_id,
                node_type=TraceNodeType.EVIDENCE_BUNDLE,
                title=f"Evidence bundle {bundle.bundle_id}",
                metadata=(("case_id", bundle.case_id),),
            )
        )
        for record in bundle.records:
            builder.add_node(
                TraceNode(
                    node_id=record.evidence_id,
                    node_type=TraceNodeType.EVIDENCE,
                    title=f"{record.kind}: {record.evidence_id}",
                    metadata=(("source", record.source), ("status", str(record.status))),
                )
            )


def _add_requirement_edges(
    builder: _TraceabilityGraphBuilder,
    requirements: tuple[Requirement, ...],
    catalog: ScenarioCatalog,
) -> None:
    requirement_ids = {requirement.requirement_id for requirement in requirements}
    for mission_thread in catalog.mission_threads:
        for requirement_id in mission_thread.requirement_ids:
            if requirement_id in requirement_ids:
                builder.add_edge(
                    requirement_id,
                    mission_thread.mission_thread_id,
                    TraceEdgeType.ALLOCATES,
                    "Requirement is allocated to a mission thread.",
                )
                for scenario_id in mission_thread.scenario_ids:
                    builder.add_edge(
                        requirement_id,
                        scenario_id,
                        TraceEdgeType.EVALUATES,
                        "Requirement is evaluated by a mission-thread scenario.",
                    )


def _add_scenario_edges(builder: _TraceabilityGraphBuilder, catalog: ScenarioCatalog) -> None:
    for mission_thread in catalog.mission_threads:
        builder.add_edge(
            mission_thread.mission_thread_id,
            mission_thread.operational_context_id,
            TraceEdgeType.REFERENCES,
            "Mission thread references an operational context.",
        )
        for function_id in mission_thread.autonomy_function_ids:
            builder.add_edge(
                mission_thread.mission_thread_id,
                function_id,
                TraceEdgeType.REFERENCES,
                "Mission thread references an autonomy function.",
            )
        for scenario_id in mission_thread.scenario_ids:
            builder.add_edge(
                mission_thread.mission_thread_id,
                scenario_id,
                TraceEdgeType.COVERS,
                "Mission thread covers a scenario.",
            )
        for hazard_id in mission_thread.hazard_ids:
            builder.add_edge(
                mission_thread.mission_thread_id,
                hazard_id,
                TraceEdgeType.COVERS,
                "Mission thread covers a hazard.",
            )

    for scenario in catalog.scenarios:
        builder.add_edge(
            scenario.scenario_id,
            scenario.operational_context_id,
            TraceEdgeType.REFERENCES,
            "Scenario references an operational context.",
        )
        builder.add_edge(
            scenario.scenario_id,
            scenario.autonomy_function_id,
            TraceEdgeType.EVALUATES,
            "Scenario evaluates an autonomy function.",
        )
        builder.add_edge(
            scenario.scenario_id,
            scenario.expected_behavior_id,
            TraceEdgeType.EXPECTS,
            "Scenario defines expected safe behavior.",
        )
        for condition_id in scenario.operating_condition_ids:
            builder.add_edge(
                scenario.scenario_id,
                condition_id,
                TraceEdgeType.REFERENCES,
                "Scenario references an operating condition.",
            )
        for stressor_id in scenario.stressor_ids:
            builder.add_edge(
                scenario.scenario_id,
                stressor_id,
                TraceEdgeType.REFERENCES,
                "Scenario injects or covers a stressor.",
            )
        for criterion_id in scenario.acceptance_criterion_ids:
            builder.add_edge(
                scenario.scenario_id,
                criterion_id,
                TraceEdgeType.EVALUATES,
                "Scenario is evaluated by an acceptance criterion.",
            )
        for hazard_id in scenario.hazard_ids:
            builder.add_edge(
                scenario.scenario_id,
                hazard_id,
                TraceEdgeType.COVERS,
                "Scenario covers an assurance hazard.",
            )
        for evidence_id in scenario.evidence_ids:
            builder.add_edge(
                scenario.scenario_id,
                evidence_id,
                TraceEdgeType.PRODUCES,
                "Scenario produces or references evidence.",
            )


def _add_assurance_case_edges(
    builder: _TraceabilityGraphBuilder,
    assurance_case: AssuranceCase,
) -> None:
    for hazard in assurance_case.hazards:
        for control_id in hazard.control_ids:
            builder.add_edge(
                hazard.hazard_id,
                control_id,
                TraceEdgeType.MITIGATES,
                "Hazard is mitigated by a control.",
            )
        for mitigation_id in hazard.mitigation_ids:
            builder.add_edge(
                hazard.hazard_id,
                mitigation_id,
                TraceEdgeType.MITIGATES,
                "Hazard is addressed by a mitigation.",
            )
        for evidence_id in hazard.evidence_ids:
            builder.add_edge(
                hazard.hazard_id,
                evidence_id,
                TraceEdgeType.SUPPORTS,
                "Hazard evidence supports hazard characterization.",
            )

    for control in assurance_case.controls:
        for hazard_id in control.mitigates_hazard_ids:
            builder.add_edge(
                control.control_id,
                hazard_id,
                TraceEdgeType.MITIGATES,
                "Control mitigates a hazard.",
            )
        for evidence_id in control.evidence_ids:
            builder.add_edge(
                evidence_id,
                control.control_id,
                TraceEdgeType.SUPPORTS,
                "Evidence supports a control.",
            )

    for mitigation in assurance_case.mitigations:
        builder.add_edge(
            mitigation.mitigation_id,
            mitigation.hazard_id,
            TraceEdgeType.MITIGATES,
            "Mitigation addresses a hazard.",
        )
        builder.add_edge(
            mitigation.mitigation_id,
            mitigation.control_id,
            TraceEdgeType.REFERENCES,
            "Mitigation references a control.",
        )
        for evidence_id in mitigation.evidence_ids:
            builder.add_edge(
                evidence_id,
                mitigation.mitigation_id,
                TraceEdgeType.SUPPORTS,
                "Evidence supports a mitigation.",
            )

    for assumption in assurance_case.assumptions:
        for evidence_id in assumption.evidence_ids:
            builder.add_edge(
                evidence_id,
                assumption.assumption_id,
                TraceEdgeType.SUPPORTS,
                "Evidence supports an assumption.",
            )

    for criterion in assurance_case.verification_criteria:
        for evidence_id in criterion.evidence_ids:
            builder.add_edge(
                evidence_id,
                criterion.criterion_id,
                TraceEdgeType.SUPPORTS,
                "Evidence supports a verification criterion.",
            )

    for claim in assurance_case.claims:
        for subclaim_id in claim.subclaim_ids:
            builder.add_edge(
                subclaim_id,
                claim.claim_id,
                TraceEdgeType.SUPPORTS,
                "Subclaim supports parent assurance claim.",
            )
        for assumption_id in claim.assumption_ids:
            builder.add_edge(
                assumption_id,
                claim.claim_id,
                TraceEdgeType.SUPPORTS,
                "Assumption supports assurance claim.",
            )
        for criterion_id in claim.verification_criterion_ids:
            builder.add_edge(
                criterion_id,
                claim.claim_id,
                TraceEdgeType.SUPPORTS,
                "Verification criterion supports assurance claim.",
            )
        for evidence_id in claim.evidence_ids:
            builder.add_edge(
                evidence_id,
                claim.claim_id,
                TraceEdgeType.SUPPORTS,
                "Evidence supports assurance claim.",
            )

    for evidence in assurance_case.evidence:
        for supported_id in evidence.supports:
            builder.add_edge(
                evidence.evidence_id,
                supported_id,
                TraceEdgeType.SUPPORTS,
                "Evidence explicitly declares supported artifact.",
            )


def _add_evidence_bundle_edges(
    builder: _TraceabilityGraphBuilder,
    evidence_bundles: tuple[EvidenceBundle, ...],
) -> None:
    for bundle in evidence_bundles:
        if bundle.scenario_id is not None:
            builder.add_edge(
                bundle.scenario_id,
                bundle.bundle_id,
                TraceEdgeType.PRODUCES,
                "Scenario produces an evidence bundle.",
            )
        for record in bundle.records:
            builder.add_edge(
                bundle.bundle_id,
                record.evidence_id,
                TraceEdgeType.CONTAINS,
                "Evidence bundle contains a record.",
            )


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise TraceabilityError(f"{field_name} must not be blank.")
    return normalized


def _normalize_metadata(values: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]:
    normalized: list[tuple[str, str]] = []
    seen_keys: set[str] = set()

    for key, value in values:
        normalized_key = _require_text(key, "metadata key")
        normalized_value = _require_text(value, "metadata value")
        if normalized_key in seen_keys:
            raise TraceabilityError(f"metadata key {normalized_key!r} is duplicated.")
        seen_keys.add(normalized_key)
        normalized.append((normalized_key, normalized_value))

    return tuple(sorted(normalized))


__all__ = [
    "MissionNeed",
    "Requirement",
    "TraceEdge",
    "TraceEdgeType",
    "TraceNode",
    "TraceNodeType",
    "TraceabilityError",
    "TraceabilityGraph",
    "TraceabilityValidationReport",
    "build_traceability_graph",
]
