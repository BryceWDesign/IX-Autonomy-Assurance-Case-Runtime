"""Runtime safety gate for autonomy assurance evaluation.

The runtime safety gate converts telemetry, scenario expectations, and explicit
safety rules into an autonomy decision:

allow, clamp, defer, veto, or safe-hold.

The gate is deliberately conservative. Severe scenario stressors can force the
scenario's expected safe behavior even before telemetry rules fire, and triggered
rules are ranked by restrictiveness. The result is a structured record that can
later be attached to evidence bundles, traceability graphs, verification reports,
and human review workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias

from ix_autonomy_assurance_case_runtime.contracts import (
    AutonomyDecisionType,
    RuntimeAuthorityState,
)
from ix_autonomy_assurance_case_runtime.scenarios import (
    ExpectedSafeBehavior,
    Scenario,
    ScenarioCatalog,
    Stressor,
)

TelemetryValue: TypeAlias = str | int | float | bool | None
TelemetryThreshold: TypeAlias = TelemetryValue | tuple[TelemetryValue, ...]


class SafetyGateError(ValueError):
    """Raised when runtime safety-gate inputs are malformed."""


class ConditionOperator(StrEnum):
    """Supported condition operators for telemetry safety rules."""

    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    GTE = "gte"
    GT = "gt"
    BETWEEN = "between"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"
    MISSING = "missing"


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise SafetyGateError(f"{field_name} must not be blank.")
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


def _as_number(value: TelemetryValue, *, field_name: str) -> float:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        raise SafetyGateError(f"{field_name} must be numeric.")
    return float(value)


def _threshold_as_scalar(
    threshold: TelemetryThreshold | None, *, field_name: str
) -> TelemetryValue:
    if threshold is None:
        raise SafetyGateError(f"{field_name} must not be absent.")
    if isinstance(threshold, tuple):
        raise SafetyGateError(f"{field_name} must be a scalar value.")
    return threshold


def _threshold_as_tuple(
    threshold: TelemetryThreshold | None,
    *,
    field_name: str,
) -> tuple[TelemetryValue, ...]:
    if not isinstance(threshold, tuple):
        raise SafetyGateError(f"{field_name} must be a tuple of values.")
    if not threshold:
        raise SafetyGateError(f"{field_name} must not be empty.")
    return threshold


@dataclass(frozen=True, slots=True)
class RuntimeTelemetry:
    """Telemetry snapshot evaluated by the runtime safety gate."""

    values: dict[str, TelemetryValue]
    source: str = "runtime-telemetry"

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", _require_text(self.source, "source"))

        normalized: dict[str, TelemetryValue] = {}
        for key, value in self.values.items():
            normalized[_require_text(key, "telemetry key")] = value

        object.__setattr__(self, "values", dict(sorted(normalized.items())))

    def has(self, key: str) -> bool:
        """Return whether a telemetry key exists and is not None."""

        normalized_key = _require_text(key, "telemetry key")
        return normalized_key in self.values and self.values[normalized_key] is not None

    def get(self, key: str) -> TelemetryValue:
        """Return a telemetry value or None when absent."""

        normalized_key = _require_text(key, "telemetry key")
        return self.values.get(normalized_key)


@dataclass(frozen=True, slots=True)
class SafetyRuleEvaluation:
    """Result of evaluating one safety rule against telemetry."""

    rule_id: str
    matched: bool
    observed_value: TelemetryValue
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", _require_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "message", _require_text(self.message, "message"))


@dataclass(frozen=True, slots=True)
class SafetyRule:
    """Telemetry rule that can restrict runtime autonomy when matched."""

    rule_id: str
    name: str
    telemetry_key: str
    operator: ConditionOperator
    threshold: TelemetryThreshold | None
    decision: AutonomyDecisionType
    authority_state: RuntimeAuthorityState
    rationale: str
    upper_threshold: TelemetryValue = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", _require_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(
            self, "telemetry_key", _require_text(self.telemetry_key, "telemetry_key")
        )
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        self._validate_operator_shape()

    def evaluate(self, telemetry: RuntimeTelemetry) -> SafetyRuleEvaluation:
        """Evaluate this rule against runtime telemetry."""

        observed_value = telemetry.get(self.telemetry_key)
        matched = self._matches(observed_value, telemetry.has(self.telemetry_key))
        comparison = "matched" if matched else "did not match"
        return SafetyRuleEvaluation(
            rule_id=self.rule_id,
            matched=matched,
            observed_value=observed_value,
            message=(
                f"Rule {self.rule_id!r} {comparison}: telemetry "
                f"{self.telemetry_key!r} observed {observed_value!r}."
            ),
        )

    def _validate_operator_shape(self) -> None:
        if self.operator in {
            ConditionOperator.LT,
            ConditionOperator.LTE,
            ConditionOperator.EQ,
            ConditionOperator.GTE,
            ConditionOperator.GT,
        }:
            _threshold_as_scalar(self.threshold, field_name="threshold")

        if self.operator is ConditionOperator.BETWEEN:
            _threshold_as_scalar(self.threshold, field_name="threshold")
            if self.upper_threshold is None:
                raise SafetyGateError("upper_threshold must not be absent for between rules.")

        if self.operator in {ConditionOperator.IN, ConditionOperator.NOT_IN}:
            _threshold_as_tuple(self.threshold, field_name="threshold")

    def _matches(self, observed_value: TelemetryValue, exists: bool) -> bool:
        if self.operator is ConditionOperator.EXISTS:
            return exists
        if self.operator is ConditionOperator.MISSING:
            return not exists

        if not exists:
            return False

        if self.operator is ConditionOperator.EQ:
            return observed_value == _threshold_as_scalar(self.threshold, field_name="threshold")

        if self.operator is ConditionOperator.IN:
            return observed_value in _threshold_as_tuple(self.threshold, field_name="threshold")

        if self.operator is ConditionOperator.NOT_IN:
            return observed_value not in _threshold_as_tuple(self.threshold, field_name="threshold")

        observed_number = _as_number(observed_value, field_name="observed telemetry value")
        threshold_number = _as_number(
            _threshold_as_scalar(self.threshold, field_name="threshold"),
            field_name="threshold",
        )

        if self.operator is ConditionOperator.LT:
            return observed_number < threshold_number
        if self.operator is ConditionOperator.LTE:
            return observed_number <= threshold_number
        if self.operator is ConditionOperator.GTE:
            return observed_number >= threshold_number
        if self.operator is ConditionOperator.GT:
            return observed_number > threshold_number

        if self.operator is ConditionOperator.BETWEEN:
            upper_number = _as_number(self.upper_threshold, field_name="upper_threshold")
            return threshold_number <= observed_number <= upper_number

        raise SafetyGateError(f"Unsupported condition operator {self.operator.value!r}.")


@dataclass(frozen=True, slots=True)
class SafetyGateResult:
    """Structured runtime safety-gate result."""

    scenario_id: str
    decision: AutonomyDecisionType
    authority_state: RuntimeAuthorityState
    operator_review_required: bool
    degraded_mode: bool
    triggered_rule_ids: tuple[str, ...]
    expected_behavior_id: str
    rule_evaluations: tuple[SafetyRuleEvaluation, ...]
    rationale: str
    telemetry_source: str
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", _require_text(self.scenario_id, "scenario_id"))
        object.__setattr__(
            self,
            "expected_behavior_id",
            _require_text(self.expected_behavior_id, "expected_behavior_id"),
        )
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        object.__setattr__(
            self, "telemetry_source", _require_text(self.telemetry_source, "telemetry_source")
        )

    def permits_nominal_execution(self) -> bool:
        """Return whether the result allows unrestricted nominal autonomy."""

        return (
            self.decision.permits_nominal_execution()
            and self.authority_state.permits_autonomous_execution()
        )

    def blocks_or_restricts_execution(self) -> bool:
        """Return whether the result restricts or blocks nominal autonomy."""

        return not self.permits_nominal_execution()


@dataclass(frozen=True, slots=True)
class RuntimeSafetyGate:
    """Rule-based runtime safety gate for autonomy scenarios."""

    rules: tuple[SafetyRule, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        rule_ids = tuple(rule.rule_id for rule in self.rules)
        if len(rule_ids) != len(set(rule_ids)):
            raise SafetyGateError("rules must not contain duplicate rule_id values.")

    def evaluate(
        self,
        *,
        scenario_id: str,
        catalog: ScenarioCatalog,
        telemetry: RuntimeTelemetry,
        evidence_ids: tuple[str, ...] = (),
    ) -> SafetyGateResult:
        """Evaluate runtime telemetry against scenario expectations and safety rules."""

        scenario = self._get_scenario(scenario_id=scenario_id, catalog=catalog)
        expected_behavior = self._get_expected_behavior(scenario=scenario, catalog=catalog)
        severe_stressor_ids = self._active_severe_stressor_ids(
            scenario=scenario, catalog=catalog, telemetry=telemetry
        )

        decision = AutonomyDecisionType.ALLOW
        authority_state = RuntimeAuthorityState.AUTONOMOUS_ALLOWED
        rationale_parts: list[str] = []

        if severe_stressor_ids and expected_behavior.restricts_autonomy():
            decision = _more_restrictive_decision(decision, expected_behavior.required_decision)
            authority_state = _more_restrictive_authority(
                authority_state,
                expected_behavior.required_authority_state,
            )
            rationale_parts.append(
                "Scenario contains active severe stressor(s) "
                f"{', '.join(severe_stressor_ids)} and expected safe behavior "
                f"{expected_behavior.behavior_id!r} restricts autonomy."
            )

        evaluations = tuple(rule.evaluate(telemetry) for rule in self.rules)
        triggered_rule_ids: list[str] = []

        for rule, evaluation in zip(self.rules, evaluations, strict=True):
            if evaluation.matched:
                triggered_rule_ids.append(rule.rule_id)
                decision = _more_restrictive_decision(decision, rule.decision)
                authority_state = _more_restrictive_authority(authority_state, rule.authority_state)
                rationale_parts.append(f"Safety rule {rule.rule_id!r} triggered: {rule.rationale}")

        if not rationale_parts:
            rationale_parts.append(
                "No severe scenario expectation or safety rule restricted autonomy."
            )

        operator_review_required = (
            decision.is_restrictive() or not authority_state.permits_autonomous_execution()
        )
        degraded_mode = operator_review_required or bool(triggered_rule_ids)

        return SafetyGateResult(
            scenario_id=scenario.scenario_id,
            decision=decision,
            authority_state=authority_state,
            operator_review_required=operator_review_required,
            degraded_mode=degraded_mode,
            triggered_rule_ids=tuple(triggered_rule_ids),
            expected_behavior_id=expected_behavior.behavior_id,
            rule_evaluations=evaluations,
            rationale=" ".join(rationale_parts),
            telemetry_source=telemetry.source,
            evidence_ids=evidence_ids,
        )

    @staticmethod
    def _get_scenario(*, scenario_id: str, catalog: ScenarioCatalog) -> Scenario:
        normalized_id = _require_text(scenario_id, "scenario_id")
        scenarios = catalog.scenario_index()
        if normalized_id not in scenarios:
            raise SafetyGateError(f"Scenario {normalized_id!r} is not present in the catalog.")
        return scenarios[normalized_id]

    @staticmethod
    def _get_expected_behavior(
        *,
        scenario: Scenario,
        catalog: ScenarioCatalog,
    ) -> ExpectedSafeBehavior:
        behaviors = catalog.expected_behavior_index()
        if scenario.expected_behavior_id not in behaviors:
            raise SafetyGateError(
                f"Scenario {scenario.scenario_id!r} references missing expected behavior "
                f"{scenario.expected_behavior_id!r}."
            )
        return behaviors[scenario.expected_behavior_id]

    @staticmethod
    def _active_severe_stressor_ids(
        *,
        scenario: Scenario,
        catalog: ScenarioCatalog,
        telemetry: RuntimeTelemetry,
    ) -> tuple[str, ...]:
        stressors = catalog.stressor_index()
        severe_ids: list[str] = []
        for stressor_id in scenario.stressor_ids:
            if stressor_id not in stressors:
                raise SafetyGateError(
                    f"Scenario {scenario.scenario_id!r} references missing stressor "
                    f"{stressor_id!r}."
                )
            stressor = stressors[stressor_id]
            if stressor.requires_restrictive_response() and _stressor_trigger_matches(
                stressor, telemetry
            ):
                severe_ids.append(stressor_id)
        return tuple(severe_ids)


def _stressor_trigger_matches(stressor: Stressor, telemetry: RuntimeTelemetry) -> bool:
    """Return whether a stressor's simple trigger condition matches telemetry.

    Unsupported trigger strings are treated as active. That keeps the runtime
    fail-closed instead of silently allowing autonomy when trigger parsing cannot
    prove the stressor is inactive.
    """

    parts = stressor.trigger_condition.split()
    if len(parts) != 3:
        return True

    telemetry_key, operator, raw_threshold = parts
    observed_value = telemetry.get(telemetry_key)
    if observed_value is None:
        return False

    if operator in {"<", "<=", ">", ">="}:
        observed_number = _as_number(observed_value, field_name="observed telemetry value")
        threshold_number = _as_number(
            _parse_trigger_literal(raw_threshold), field_name="trigger threshold"
        )
        if operator == "<":
            return observed_number < threshold_number
        if operator == "<=":
            return observed_number <= threshold_number
        if operator == ">":
            return observed_number > threshold_number
        return observed_number >= threshold_number

    threshold = _parse_trigger_literal(raw_threshold)
    if operator in {"==", "="}:
        return observed_value == threshold
    if operator == "!=":
        return observed_value != threshold

    return True


def _parse_trigger_literal(value: str) -> TelemetryValue:
    normalized = value.strip()
    if normalized in {"true", "True"}:
        return True
    if normalized in {"false", "False"}:
        return False
    if normalized in {"null", "None"}:
        return None
    try:
        if "." not in normalized and "e" not in normalized.lower():
            return int(normalized)
        return float(normalized)
    except ValueError:
        return normalized.strip("\"'")
