"""Executable scenario runner for the autonomy assurance-case runtime.

The scenario runner is the first end-to-end execution layer in the repository.
It validates a scenario catalog, evaluates runtime telemetry through the
degradation engine, evaluates the runtime safety gate, combines both outcomes
conservatively, and emits a deterministic evidence bundle for the run.

This is not the final verification engine. The verification engine arrives in
the next commit. This module produces the structured runtime evidence that later
verification, reports, ledgers, and CLI commands can inspect.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ix_autonomy_assurance_case_runtime.contracts import (
    AutonomyDecisionType,
    EvidenceStatus,
    RuntimeAuthorityState,
    VerificationResult,
)
from ix_autonomy_assurance_case_runtime.degradation import (
    DegradationAssessment,
    DegradationEngine,
)
from ix_autonomy_assurance_case_runtime.evidence import (
    EvidenceBundle,
    EvidenceRecord,
    JSONValue,
)
from ix_autonomy_assurance_case_runtime.safety_gate import (
    RuntimeSafetyGate,
    RuntimeTelemetry,
    SafetyGateResult,
)
from ix_autonomy_assurance_case_runtime.scenarios import (
    ExpectedSafeBehavior,
    Scenario,
    ScenarioCatalog,
)


class ScenarioRunnerError(ValueError):
    """Raised when a scenario cannot be executed safely or deterministically."""


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ScenarioRunnerError(f"{field_name} must not be blank.")
    return normalized


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ScenarioRunnerError(f"{field_name} must not contain duplicate values.")
    return normalized


def _decision_rank(decision: AutonomyDecisionType) -> int:
    ranks = {
        AutonomyDecisionType.ALLOW: 1,
        AutonomyDecisionType.CLAMP: 2,
        AutonomyDecisionType.DEFER: 3,
        AutonomyDecisionType.VETO: 4,
        AutonomyDecisionType.SAFE_HOLD: 5,
    }
    return ranks[decision]


def _authority_rank(authority_state: RuntimeAuthorityState) -> int:
    ranks = {
        RuntimeAuthorityState.AUTONOMOUS_ALLOWED: 1,
        RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED: 2,
        RuntimeAuthorityState.HUMAN_OVERRIDE_ACTIVE: 3,
        RuntimeAuthorityState.DENIED: 4,
        RuntimeAuthorityState.EMERGENCY_SAFE_HOLD: 5,
    }
    return ranks[authority_state]


def _more_restrictive_decision(
    current: AutonomyDecisionType,
    candidate: AutonomyDecisionType,
) -> AutonomyDecisionType:
    if _decision_rank(candidate) > _decision_rank(current):
        return candidate
    return current


def _more_restrictive_authority(
    current: RuntimeAuthorityState,
    candidate: RuntimeAuthorityState,
) -> RuntimeAuthorityState:
    if _authority_rank(candidate) > _authority_rank(current):
        return candidate
    return current


@dataclass(frozen=True, slots=True)
class ScenarioRunInput:
    """Input required to execute one scenario through the assurance runtime."""

    run_id: str
    case_id: str
    scenario_id: str
    telemetry: RuntimeTelemetry
    prior_evidence_bundles: tuple[EvidenceBundle, ...] = field(default_factory=tuple)
    operator_id: str = "unassigned-operator"
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text(self.run_id, "run_id"))
        object.__setattr__(self, "case_id", _require_text(self.case_id, "case_id"))
        object.__setattr__(self, "scenario_id", _require_text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "operator_id", _require_text(self.operator_id, "operator_id"))
        object.__setattr__(self, "notes", _normalize_text_tuple(self.notes, "notes"))


@dataclass(frozen=True, slots=True)
class ScenarioRunResult:
    """Structured output of executing one scenario through the runtime."""

    run_id: str
    case_id: str
    scenario_id: str
    final_decision: AutonomyDecisionType
    final_authority_state: RuntimeAuthorityState
    verification_result: VerificationResult
    expected_behavior_satisfied: bool
    operator_review_required: bool
    degraded_mode: bool
    safety_gate_result: SafetyGateResult
    degradation_assessment: DegradationAssessment
    evidence_bundle: EvidenceBundle
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text(self.run_id, "run_id"))
        object.__setattr__(self, "case_id", _require_text(self.case_id, "case_id"))
        object.__setattr__(self, "scenario_id", _require_text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))

    def permits_nominal_execution(self) -> bool:
        """Return whether the final run result permits nominal autonomy."""

        return (
            self.final_decision.permits_nominal_execution()
            and self.final_authority_state.permits_autonomous_execution()
        )

    def blocks_or_restricts_execution(self) -> bool:
        """Return whether the run result restricts or blocks autonomy."""

        return not self.permits_nominal_execution()

    def to_evidence_payload(self) -> dict[str, JSONValue]:
        """Return a JSON-compatible summary of the scenario run."""

        return {
            "case_id": self.case_id,
            "degraded_mode": self.degraded_mode,
            "degradation": {
                "requires_operator_review": (
                    self.degradation_assessment.requires_operator_review()
                ),
                "recommended_authority_state": (
                    self.degradation_assessment.recommended_authority_state().value
                ),
                "recommended_decision": (
                    self.degradation_assessment.recommended_decision().value
                ),
                "signal_ids": [
                    signal.signal_id for signal in self.degradation_assessment.signals
                ],
                "worst_level": self.degradation_assessment.worst_level().value,
            },
            "expected_behavior_satisfied": self.expected_behavior_satisfied,
            "final_authority_state": self.final_authority_state.value,
            "final_decision": self.final_decision.value,
            "operator_review_required": self.operator_review_required,
            "rationale": self.rationale,
            "run_id": self.run_id,
            "safety_gate": {
                "authority_state": self.safety_gate_result.authority_state.value,
                "decision": self.safety_gate_result.decision.value,
                "expected_behavior_id": self.safety_gate_result.expected_behavior_id,
                "triggered_rule_ids": list(self.safety_gate_result.triggered_rule_ids),
            },
            "scenario_id": self.scenario_id,
            "verification_result": self.verification_result.value,
        }


@dataclass(frozen=True, slots=True)
class ScenarioRunner:
    """Runs autonomy T&E scenarios through safety and degradation evaluation."""

    safety_gate: RuntimeSafetyGate = field(default_factory=RuntimeSafetyGate)
    degradation_engine: DegradationEngine = field(default_factory=DegradationEngine)
    evidence_created_by: str = "ix-scenario-runner"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_created_by",
            _require_text(self.evidence_created_by, "evidence_created_by"),
        )

    def run(
        self,
        *,
        catalog: ScenarioCatalog,
        run_input: ScenarioRunInput,
    ) -> ScenarioRunResult:
        """Execute one scenario through the runtime pipeline."""

        catalog_report = catalog.validate_references()
        if not catalog_report.is_valid:
            errors = "; ".join(catalog_report.errors)
            raise ScenarioRunnerError(f"Scenario catalog is invalid: {errors}")

        scenario = self._get_scenario(catalog=catalog, scenario_id=run_input.scenario_id)
        expected_behavior = self._get_expected_behavior(catalog=catalog, scenario=scenario)

        degradation_assessment = self.degradation_engine.assess(
            scenario_id=scenario.scenario_id,
            telemetry=run_input.telemetry,
            evidence_bundles=run_input.prior_evidence_bundles,
        )
        safety_gate_result = self.safety_gate.evaluate(
            scenario_id=scenario.scenario_id,
            catalog=catalog,
            telemetry=run_input.telemetry,
            evidence_ids=scenario.evidence_ids,
        )

        final_decision = _more_restrictive_decision(
            safety_gate_result.decision,
            degradation_assessment.recommended_decision(),
        )
        final_authority_state = _more_restrictive_authority(
            safety_gate_result.authority_state,
            degradation_assessment.recommended_authority_state(),
        )
        expected_behavior_satisfied = self._satisfies_expected_behavior(
            final_decision=final_decision,
            final_authority_state=final_authority_state,
            expected_behavior=expected_behavior,
        )
        verification_result = (
            VerificationResult.PASS
            if expected_behavior_satisfied
            else VerificationResult.FAIL
        )
        operator_review_required = (
            safety_gate_result.operator_review_required
            or degradation_assessment.requires_operator_review()
            or not final_authority_state.permits_autonomous_execution()
            or final_decision.is_restrictive()
        )
        degraded_mode = safety_gate_result.degraded_mode or degradation_assessment.degraded_mode()
        rationale = self._build_rationale(
            safety_gate_result=safety_gate_result,
            degradation_assessment=degradation_assessment,
            expected_behavior_satisfied=expected_behavior_satisfied,
        )

        provisional_result = ScenarioRunResult(
            run_id=run_input.run_id,
            case_id=run_input.case_id,
            scenario_id=scenario.scenario_id,
            final_decision=final_decision,
            final_authority_state=final_authority_state,
            verification_result=verification_result,
            expected_behavior_satisfied=expected_behavior_satisfied,
            operator_review_required=operator_review_required,
            degraded_mode=degraded_mode,
            safety_gate_result=safety_gate_result,
            degradation_assessment=degradation_assessment,
            evidence_bundle=EvidenceBundle(
                bundle_id=f"BND-{run_input.run_id}",
                case_id=run_input.case_id,
                scenario_id=scenario.scenario_id,
                records=(
                    self._build_run_record(
                        run_input=run_input,
                        scenario=scenario,
                        payload={},
                    ),
                ),
                created_by=self.evidence_created_by,
            ),
            rationale=rationale,
        )
        evidence_payload = provisional_result.to_evidence_payload()
        evidence_bundle = EvidenceBundle(
            bundle_id=f"BND-{run_input.run_id}",
            case_id=run_input.case_id,
            scenario_id=scenario.scenario_id,
            records=(
                self._build_run_record(
                    run_input=run_input,
                    scenario=scenario,
                    payload=evidence_payload,
                ),
            ),
            created_by=self.evidence_created_by,
        ).with_computed_hashes()

        return ScenarioRunResult(
            run_id=provisional_result.run_id,
            case_id=provisional_result.case_id,
            scenario_id=provisional_result.scenario_id,
            final_decision=provisional_result.final_decision,
            final_authority_state=provisional_result.final_authority_state,
            verification_result=provisional_result.verification_result,
            expected_behavior_satisfied=provisional_result.expected_behavior_satisfied,
            operator_review_required=provisional_result.operator_review_required,
            degraded_mode=provisional_result.degraded_mode,
            safety_gate_result=provisional_result.safety_gate_result,
            degradation_assessment=provisional_result.degradation_assessment,
            evidence_bundle=evidence_bundle,
            rationale=provisional_result.rationale,
        )

    @staticmethod
    def _get_scenario(*, catalog: ScenarioCatalog, scenario_id: str) -> Scenario:
        scenarios = catalog.scenario_index()
        normalized_scenario_id = _require_text(scenario_id, "scenario_id")
        if normalized_scenario_id not in scenarios:
            raise ScenarioRunnerError(
                f"Scenario {normalized_scenario_id!r} is not present in the catalog."
            )
        return scenarios[normalized_scenario_id]

    @staticmethod
    def _get_expected_behavior(
        *,
        catalog: ScenarioCatalog,
        scenario: Scenario,
    ) -> ExpectedSafeBehavior:
        expected_behaviors = catalog.expected_behavior_index()
        if scenario.expected_behavior_id not in expected_behaviors:
            raise ScenarioRunnerError(
                f"Scenario {scenario.scenario_id!r} references missing expected behavior "
                f"{scenario.expected_behavior_id!r}."
            )
        return expected_behaviors[scenario.expected_behavior_id]

    @staticmethod
    def _satisfies_expected_behavior(
        *,
        final_decision: AutonomyDecisionType,
        final_authority_state: RuntimeAuthorityState,
        expected_behavior: ExpectedSafeBehavior,
    ) -> bool:
        decision_satisfies = (
            _decision_rank(final_decision)
            >= _decision_rank(expected_behavior.required_decision)
        )
        authority_satisfies = (
            _authority_rank(final_authority_state)
            >= _authority_rank(expected_behavior.required_authority_state)
        )
        return decision_satisfies and authority_satisfies

    @staticmethod
    def _build_rationale(
        *,
        safety_gate_result: SafetyGateResult,
        degradation_assessment: DegradationAssessment,
        expected_behavior_satisfied: bool,
    ) -> str:
        expected_result_text = (
            "expected safe behavior was satisfied"
            if expected_behavior_satisfied
            else "expected safe behavior was not satisfied"
        )
        return (
            f"{safety_gate_result.rationale} "
            f"{degradation_assessment.summary()} "
            f"Runtime comparison result: {expected_result_text}."
        )

    def _build_run_record(
        self,
        *,
        run_input: ScenarioRunInput,
        scenario: Scenario,
        payload: dict[str, JSONValue],
    ) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id=f"EV-RUN-{run_input.run_id}",
            kind="scenario-run",
            source=f"scenario:{scenario.scenario_id}",
            payload=payload,
            status=EvidenceStatus.ACCEPTED,
            created_by=self.evidence_created_by,
            tags=("scenario-run", scenario.scenario_id),
        )
