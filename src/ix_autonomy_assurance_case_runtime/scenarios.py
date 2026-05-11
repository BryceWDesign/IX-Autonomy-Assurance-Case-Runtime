"""Mission-thread and scenario model for autonomy T&E.

This module defines the scenario layer used to evaluate AI/autonomous behavior
against operational context, operating conditions, stressors, expected safe
behavior, and acceptance criteria.

The model is intentionally strict. A scenario is not considered review-ready
unless its references resolve and severe stressors are paired with restrictive
safe behavior such as clamp, defer, veto, or safe-hold.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ix_autonomy_assurance_case_runtime.contracts import (
    AutonomyDecisionType,
    HazardSeverity,
    RuntimeAuthorityState,
    VerificationResult,
)


class ScenarioModelError(ValueError):
    """Raised when a scenario artifact is malformed."""


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ScenarioModelError(f"{field_name} must not be blank.")
    return normalized


def _normalize_ids(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ScenarioModelError(f"{field_name} must not contain duplicate identifiers.")
    return normalized


@dataclass(frozen=True, slots=True)
class OperationalContext:
    """Operational setting in which autonomy behavior is evaluated."""

    context_id: str
    name: str
    environment: str
    mission_phase: str
    description: str
    constraints: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "context_id", _require_text(self.context_id, "context_id"))
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(self, "environment", _require_text(self.environment, "environment"))
        object.__setattr__(self, "mission_phase", _require_text(self.mission_phase, "mission_phase"))
        object.__setattr__(self, "description", _require_text(self.description, "description"))
        object.__setattr__(self, "constraints", self._normalize_constraints(self.constraints))

    @staticmethod
    def _normalize_constraints(values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(_require_text(value, "constraints") for value in values)
        if len(normalized) != len(set(normalized)):
            raise ScenarioModelError("constraints must not contain duplicate values.")
        return normalized


@dataclass(frozen=True, slots=True)
class AutonomyFunction:
    """Autonomous function under test."""

    function_id: str
    name: str
    description: str
    input_signals: tuple[str, ...]
    output_actions: tuple[str, ...]
    nominal_authority_state: RuntimeAuthorityState = RuntimeAuthorityState.AUTONOMOUS_ALLOWED

    def __post_init__(self) -> None:
        object.__setattr__(self, "function_id", _require_text(self.function_id, "function_id"))
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(self, "description", _require_text(self.description, "description"))
        object.__setattr__(
            self,
            "input_signals",
            _normalize_ids(self.input_signals, "input_signals"),
        )
        object.__setattr__(
            self,
            "output_actions",
            _normalize_ids(self.output_actions, "output_actions"),
        )

        if not self.input_signals:
            raise ScenarioModelError("input_signals must not be empty.")
        if not self.output_actions:
            raise ScenarioModelError("output_actions must not be empty.")

    def requires_human_authority_by_default(self) -> bool:
        """Return whether the function is not normally allowed to act alone."""

        return not self.nominal_authority_state.permits_autonomous_execution()


@dataclass(frozen=True, slots=True)
class OperatingCondition:
    """Observable operating condition relevant to scenario execution."""

    condition_id: str
    name: str
    description: str
    telemetry_key: str
    expected_range: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition_id", _require_text(self.condition_id, "condition_id"))
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(self, "description", _require_text(self.description, "description"))
        object.__setattr__(self, "telemetry_key", _require_text(self.telemetry_key, "telemetry_key"))
        object.__setattr__(
            self,
            "expected_range",
            _require_text(self.expected_range, "expected_range"),
        )


@dataclass(frozen=True, slots=True)
class Stressor:
    """Fault, degradation, adversarial pressure, or abnormal condition."""

    stressor_id: str
    name: str
    description: str
    severity: HazardSeverity
    affected_capabilities: tuple[str, ...]
    trigger_condition: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "stressor_id", _require_text(self.stressor_id, "stressor_id"))
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(self, "description", _require_text(self.description, "description"))
        object.__setattr__(
            self,
            "affected_capabilities",
            _normalize_ids(self.affected_capabilities, "affected_capabilities"),
        )
        object.__setattr__(
            self,
            "trigger_condition",
            _require_text(self.trigger_condition, "trigger_condition"),
        )

        if not self.affected_capabilities:
            raise ScenarioModelError("affected_capabilities must not be empty.")

    def requires_restrictive_response(self) -> bool:
        """Return whether this stressor is severe enough to require constrained behavior."""

        return self.severity.requires_mitigation()


@dataclass(frozen=True, slots=True)
class ExpectedSafeBehavior:
    """Expected safe response from the runtime assurance layer."""

    behavior_id: str
    description: str
    required_decision: AutonomyDecisionType
    required_authority_state: RuntimeAuthorityState
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "behavior_id", _require_text(self.behavior_id, "behavior_id"))
        object.__setattr__(self, "description", _require_text(self.description, "description"))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))

    def restricts_autonomy(self) -> bool:
        """Return whether the expected behavior restricts nominal autonomy."""

        return (
            self.required_decision.is_restrictive()
            or self.required_authority_state.blocks_autonomous_execution()
        )


@dataclass(frozen=True, slots=True)
class AcceptanceCriterion:
    """Scenario acceptance criterion tied to verification results and evidence."""

    criterion_id: str
    statement: str
    measurement: str
    expected_result: str
    required_verification_result: VerificationResult = VerificationResult.PASS
    requires_evidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "criterion_id", _require_text(self.criterion_id, "criterion_id"))
        object.__setattr__(self, "statement", _require_text(self.statement, "statement"))
        object.__setattr__(self, "measurement", _require_text(self.measurement, "measurement"))
        object.__setattr__(
            self,
            "expected_result",
            _require_text(self.expected_result, "expected_result"),
        )

    def accepts_result(self, result: VerificationResult) -> bool:
        """Return whether a verification result satisfies this criterion."""

        return result is self.required_verification_result


@dataclass(frozen=True, slots=True)
class MissionThread:
    """Mission-thread slice used to organize autonomy evaluation scenarios."""

    mission_thread_id: str
    name: str
    objective: str
    operational_context_id: str
    autonomy_function_ids: tuple[str, ...]
    scenario_ids: tuple[str, ...] = field(default_factory=tuple)
    requirement_ids: tuple[str, ...] = field(default_factory=tuple)
    hazard_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mission_thread_id",
            _require_text(self.mission_thread_id, "mission_thread_id"),
        )
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(self, "objective", _require_text(self.objective, "objective"))
        object.__setattr__(
            self,
            "operational_context_id",
            _require_text(self.operational_context_id, "operational_context_id"),
        )
        object.__setattr__(
            self,
            "autonomy_function_ids",
            _normalize_ids(self.autonomy_function_ids, "autonomy_function_ids"),
        )
        object.__setattr__(self, "scenario_ids", _normalize_ids(self.scenario_ids, "scenario_ids"))
        object.__setattr__(
            self,
            "requirement_ids",
            _normalize_ids(self.requirement_ids, "requirement_ids"),
        )
        object.__setattr__(self, "hazard_ids", _normalize_ids(self.hazard_ids, "hazard_ids"))

        if not self.autonomy_function_ids:
            raise ScenarioModelError("autonomy_function_ids must not be empty.")


@dataclass(frozen=True, slots=True)
class Scenario:
    """Executable scenario definition for autonomy T&E."""

    scenario_id: str
    mission_thread_id: str
    title: str
    description: str
    operational_context_id: str
    autonomy_function_id: str
    operating_condition_ids: tuple[str, ...]
    stressor_ids: tuple[str, ...]
    expected_behavior_id: str
    acceptance_criterion_ids: tuple[str, ...]
    hazard_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", _require_text(self.scenario_id, "scenario_id"))
        object.__setattr__(
            self,
            "mission_thread_id",
            _require_text(self.mission_thread_id, "mission_thread_id"),
        )
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        object.__setattr__(self, "description", _require_text(self.description, "description"))
        object.__setattr__(
            self,
            "operational_context_id",
            _require_text(self.operational_context_id, "operational_context_id"),
        )
        object.__setattr__(
            self,
            "autonomy_function_id",
            _require_text(self.autonomy_function_id, "autonomy_function_id"),
        )
        object.__setattr__(
            self,
            "operating_condition_ids",
            _normalize_ids(self.operating_condition_ids, "operating_condition_ids"),
        )
        object.__setattr__(self, "stressor_ids", _normalize_ids(self.stressor_ids, "stressor_ids"))
        object.__setattr__(
            self,
            "expected_behavior_id",
            _require_text(self.expected_behavior_id, "expected_behavior_id"),
        )
        object.__setattr__(
            self,
            "acceptance_criterion_ids",
            _normalize_ids(self.acceptance_criterion_ids, "acceptance_criterion_ids"),
        )
        object.__setattr__(self, "hazard_ids", _normalize_ids(self.hazard_ids, "hazard_ids"))
        object.__setattr__(self, "evidence_ids", _normalize_ids(self.evidence_ids, "evidence_ids"))

        if not self.operating_condition_ids:
            raise ScenarioModelError("operating_condition_ids must not be empty.")
        if not self.acceptance_criterion_ids:
            raise ScenarioModelError("acceptance_criterion_ids must not be empty.")

    def includes_stressors(self) -> bool:
        """Return whether this scenario contains one or more stressors."""

        return bool(self.stressor_ids)

    def requires_evidence(self, criteria: dict[str, AcceptanceCriterion]) -> bool:
        """Return whether any referenced acceptance criterion requires evidence."""

        return any(criteria[criterion_id].requires_evidence for criterion_id in self.acceptance_criterion_ids)


@dataclass(frozen=True, slots=True)
class ScenarioCatalogValidationReport:
    """Validation result for a scenario catalog."""

    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        """Return whether the scenario catalog has no validation errors."""

        return not self.errors


@dataclass(frozen=True, slots=True)
class ScenarioCatalog:
    """Catalog of mission threads and scenarios for autonomy T&E."""

    operational_contexts: tuple[OperationalContext, ...] = field(default_factory=tuple)
    autonomy_functions: tuple[AutonomyFunction, ...] = field(default_factory=tuple)
    operating_conditions: tuple[OperatingCondition, ...] = field(default_factory=tuple)
    stressors: tuple[Stressor, ...] = field(default_factory=tuple)
    expected_behaviors: tuple[ExpectedSafeBehavior, ...] = field(default_factory=tuple)
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = field(default_factory=tuple)
    mission_threads: tuple[MissionThread, ...] = field(default_factory=tuple)
    scenarios: tuple[Scenario, ...] = field(default_factory=tuple)

    def operational_context_index(self) -> dict[str, OperationalContext]:
        """Return operational contexts keyed by identifier."""

        return {item.context_id: item for item in self.operational_contexts}

    def autonomy_function_index(self) -> dict[str, AutonomyFunction]:
        """Return autonomy functions keyed by identifier."""

        return {item.function_id: item for item in self.autonomy_functions}

    def operating_condition_index(self) -> dict[str, OperatingCondition]:
        """Return operating conditions keyed by identifier."""

        return {item.condition_id: item for item in self.operating_conditions}

    def stressor_index(self) -> dict[str, Stressor]:
        """Return stressors keyed by identifier."""

        return {item.stressor_id: item for item in self.stressors}

    def expected_behavior_index(self) -> dict[str, ExpectedSafeBehavior]:
        """Return expected safe behaviors keyed by identifier."""

        return {item.behavior_id: item for item in self.expected_behaviors}

    def acceptance_criterion_index(self) -> dict[str, AcceptanceCriterion]:
        """Return acceptance criteria keyed by identifier."""

        return {item.criterion_id: item for item in self.acceptance_criteria}

    def mission_thread_index(self) -> dict[str, MissionThread]:
        """Return mission threads keyed by identifier."""

        return {item.mission_thread_id: item for item in self.mission_threads}

    def scenario_index(self) -> dict[str, Scenario]:
        """Return scenarios keyed by identifier."""

        return {item.scenario_id: item for item in self.scenarios}

    def validate_references(self) -> ScenarioCatalogValidationReport:
        """Validate scenario-catalog references and safety expectations."""

        errors: list[str] = []
        warnings: list[str] = []

        self._validate_unique_identifiers(errors)

        contexts = self.operational_context_index()
        functions = self.autonomy_function_index()
        conditions = self.operating_condition_index()
        stressors = self.stressor_index()
        behaviors = self.expected_behavior_index()
        criteria = self.acceptance_criterion_index()
        mission_threads = self.mission_thread_index()
        scenarios = self.scenario_index()

        if not self.mission_threads:
            errors.append("Scenario catalog must contain at least one mission thread.")
        if not self.scenarios:
            errors.append("Scenario catalog must contain at least one scenario.")

        for mission_thread in self.mission_threads:
            self._require_existing(
                (mission_thread.operational_context_id,),
                contexts,
                mission_thread.mission_thread_id,
                "operational context",
                errors,
            )
            self._require_existing(
                mission_thread.autonomy_function_ids,
                functions,
                mission_thread.mission_thread_id,
                "autonomy function",
                errors,
            )
            self._require_existing(
                mission_thread.scenario_ids,
                scenarios,
                mission_thread.mission_thread_id,
                "scenario",
                errors,
            )

        for scenario in self.scenarios:
            self._require_existing(
                (scenario.mission_thread_id,),
                mission_threads,
                scenario.scenario_id,
                "mission thread",
                errors,
            )
            self._require_existing(
                (scenario.operational_context_id,),
                contexts,
                scenario.scenario_id,
                "operational context",
                errors,
            )
            self._require_existing(
                (scenario.autonomy_function_id,),
                functions,
                scenario.scenario_id,
                "autonomy function",
                errors,
            )
            self._require_existing(
                scenario.operating_condition_ids,
                conditions,
                scenario.scenario_id,
                "operating condition",
                errors,
            )
            self._require_existing(
                scenario.stressor_ids,
                stressors,
                scenario.scenario_id,
                "stressor",
                errors,
            )
            self._require_existing(
                (scenario.expected_behavior_id,),
                behaviors,
                scenario.scenario_id,
                "expected safe behavior",
                errors,
            )
            self._require_existing(
                scenario.acceptance_criterion_ids,
                criteria,
                scenario.scenario_id,
                "acceptance criterion",
                errors,
            )

            if scenario.expected_behavior_id in behaviors:
                behavior = behaviors[scenario.expected_behavior_id]
                self._validate_stressor_response(scenario, behavior, stressors, errors)

            if scenario.acceptance_criterion_ids and not scenario.evidence_ids:
                referenced_criteria = [
                    criteria[criterion_id]
                    for criterion_id in scenario.acceptance_criterion_ids
                    if criterion_id in criteria
                ]
                if any(criterion.requires_evidence for criterion in referenced_criteria):
                    warnings.append(
                        f"Scenario {scenario.scenario_id!r} requires evidence but has "
                        "no evidence identifiers yet."
                    )

        return ScenarioCatalogValidationReport(
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    def ready_scenario_ids(self) -> tuple[str, ...]:
        """Return scenario identifiers that pass catalog validation locally."""

        report = self.validate_references()
        if not report.is_valid:
            return ()
        return tuple(scenario.scenario_id for scenario in self.scenarios)

    def scenarios_for_mission_thread(self, mission_thread_id: str) -> tuple[Scenario, ...]:
        """Return scenarios assigned to a mission thread."""

        normalized_id = _require_text(mission_thread_id, "mission_thread_id")
        return tuple(
            scenario
            for scenario in self.scenarios
            if scenario.mission_thread_id == normalized_id
        )

    def _validate_unique_identifiers(self, errors: list[str]) -> None:
        artifact_ids = (
            tuple(item.context_id for item in self.operational_contexts)
            + tuple(item.function_id for item in self.autonomy_functions)
            + tuple(item.condition_id for item in self.operating_conditions)
            + tuple(item.stressor_id for item in self.stressors)
            + tuple(item.behavior_id for item in self.expected_behaviors)
            + tuple(item.criterion_id for item in self.acceptance_criteria)
            + tuple(item.mission_thread_id for item in self.mission_threads)
            + tuple(item.scenario_id for item in self.scenarios)
        )
        duplicates = sorted(
            {artifact_id for artifact_id in artifact_ids if artifact_ids.count(artifact_id) > 1}
        )

        for duplicate in duplicates:
            errors.append(f"Scenario artifact identifier {duplicate!r} is duplicated.")

    @staticmethod
    def _validate_stressor_response(
        scenario: Scenario,
        behavior: ExpectedSafeBehavior,
        stressors: dict[str, Stressor],
        errors: list[str],
    ) -> None:
        severe_stressor_ids = tuple(
            stressor_id
            for stressor_id in scenario.stressor_ids
            if stressor_id in stressors and stressors[stressor_id].requires_restrictive_response()
        )

        if severe_stressor_ids and not behavior.restricts_autonomy():
            joined_ids = ", ".join(repr(stressor_id) for stressor_id in severe_stressor_ids)
            errors.append(
                f"Scenario {scenario.scenario_id!r} includes severe stressor(s) "
                f"{joined_ids} but expected behavior {behavior.behavior_id!r} does not "
                "restrict autonomy."
            )

    @staticmethod
    def _require_existing(
        ids: tuple[str, ...],
        index: dict[str, object],
        owner_id: str,
        reference_name: str,
        errors: list[str],
    ) -> None:
        for reference_id in ids:
            if reference_id not in index:
                errors.append(
                    f"Artifact {owner_id!r} references missing {reference_name} "
                    f"{reference_id!r}."
                )
