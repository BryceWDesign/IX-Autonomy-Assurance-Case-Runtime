"""Fault and degradation reasoning for autonomy assurance.

The degradation engine detects operational degradation signals from telemetry,
conflicting telemetry checks, and evidence-bundle integrity posture. It turns
those signals into an assessment with a worst level, recommended autonomy
decision, and recommended authority state.

This module is intentionally conservative. Critical degradation recommends
safe-hold, severe degradation recommends veto/deny, degraded posture recommends
defer to human approval, and nominal/no-signal posture allows autonomy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ix_autonomy_assurance_case_runtime.contracts import (
    AutonomyDecisionType,
    EvidenceStatus,
    RuntimeAuthorityState,
)
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.safety_gate import (
    ConditionOperator,
    RuntimeTelemetry,
    TelemetryThreshold,
    TelemetryValue,
)


class DegradationRuntimeError(ValueError):
    """Raised when degradation detection inputs are malformed."""


class DegradationCategory(StrEnum):
    """Categories of runtime degradation relevant to autonomy assurance."""

    SENSOR_DRIFT = "sensor_drift"
    COMMS_LOSS = "comms_loss"
    NAVIGATION_UNCERTAINTY = "navigation_uncertainty"
    POWER_DEGRADATION = "power_degradation"
    CONFLICTING_TELEMETRY = "conflicting_telemetry"
    TIMING_DEGRADATION = "timing_degradation"
    STALE_EVIDENCE = "stale_evidence"


class DegradationLevel(StrEnum):
    """Severity level for detected degradation."""

    NOMINAL = "nominal"
    WATCH = "watch"
    DEGRADED = "degraded"
    SEVERE = "severe"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """Return ordinal rank where larger values are more severe."""

        ranks = {
            DegradationLevel.NOMINAL: 0,
            DegradationLevel.WATCH: 1,
            DegradationLevel.DEGRADED: 2,
            DegradationLevel.SEVERE: 3,
            DegradationLevel.CRITICAL: 4,
        }
        return ranks[self]

    def is_degraded(self) -> bool:
        """Return whether the level is worse than nominal/watch posture."""

        return self.rank >= DegradationLevel.DEGRADED.rank

    def requires_operator_review(self) -> bool:
        """Return whether this level requires human authority review."""

        return self.rank >= DegradationLevel.DEGRADED.rank

    def recommended_decision(self) -> AutonomyDecisionType:
        """Return the recommended autonomy decision for this degradation level."""

        if self is DegradationLevel.CRITICAL:
            return AutonomyDecisionType.SAFE_HOLD
        if self is DegradationLevel.SEVERE:
            return AutonomyDecisionType.VETO
        if self is DegradationLevel.DEGRADED:
            return AutonomyDecisionType.DEFER
        return AutonomyDecisionType.ALLOW

    def recommended_authority_state(self) -> RuntimeAuthorityState:
        """Return the recommended authority state for this degradation level."""

        if self is DegradationLevel.CRITICAL:
            return RuntimeAuthorityState.EMERGENCY_SAFE_HOLD
        if self is DegradationLevel.SEVERE:
            return RuntimeAuthorityState.DENIED
        if self is DegradationLevel.DEGRADED:
            return RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED
        return RuntimeAuthorityState.AUTONOMOUS_ALLOWED


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise DegradationRuntimeError(f"{field_name} must not be blank.")
    return normalized


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise DegradationRuntimeError(f"{field_name} must not contain duplicate values.")
    return normalized


def _as_number(value: TelemetryValue, *, field_name: str) -> float:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        raise DegradationRuntimeError(f"{field_name} must be numeric.")
    return float(value)


def _threshold_as_scalar(
    threshold: TelemetryThreshold | None, *, field_name: str
) -> TelemetryValue:
    if threshold is None:
        raise DegradationRuntimeError(f"{field_name} must not be absent.")
    if isinstance(threshold, tuple):
        raise DegradationRuntimeError(f"{field_name} must be a scalar value.")
    return threshold


def _threshold_as_tuple(
    threshold: TelemetryThreshold | None,
    *,
    field_name: str,
) -> tuple[TelemetryValue, ...]:
    if not isinstance(threshold, tuple):
        raise DegradationRuntimeError(f"{field_name} must be a tuple of values.")
    if not threshold:
        raise DegradationRuntimeError(f"{field_name} must not be empty.")
    return threshold


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


def _more_severe_level(current: DegradationLevel, candidate: DegradationLevel) -> DegradationLevel:
    if candidate.rank > current.rank:
        return candidate
    return current


@dataclass(frozen=True, slots=True)
class DegradationSignal:
    """Single detected degradation signal."""

    signal_id: str
    category: DegradationCategory
    level: DegradationLevel
    source: str
    rationale: str
    observed_value: TelemetryValue = None
    affected_capabilities: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_id", _require_text(self.signal_id, "signal_id"))
        object.__setattr__(self, "source", _require_text(self.source, "source"))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        object.__setattr__(
            self,
            "affected_capabilities",
            _normalize_text_tuple(self.affected_capabilities, "affected_capabilities"),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _normalize_text_tuple(self.evidence_ids, "evidence_ids"),
        )

    def requires_operator_review(self) -> bool:
        """Return whether this signal requires human review."""

        return self.level.requires_operator_review()

    def recommended_decision(self) -> AutonomyDecisionType:
        """Return the recommended decision for this signal."""

        return self.level.recommended_decision()

    def recommended_authority_state(self) -> RuntimeAuthorityState:
        """Return the recommended authority state for this signal."""

        return self.level.recommended_authority_state()


@dataclass(frozen=True, slots=True)
class DegradationRule:
    """Telemetry rule that emits a degradation signal when matched."""

    rule_id: str
    category: DegradationCategory
    telemetry_key: str
    operator: ConditionOperator
    threshold: TelemetryThreshold | None
    level: DegradationLevel
    rationale: str
    affected_capabilities: tuple[str, ...]
    upper_threshold: TelemetryValue = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", _require_text(self.rule_id, "rule_id"))
        object.__setattr__(
            self, "telemetry_key", _require_text(self.telemetry_key, "telemetry_key")
        )
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        object.__setattr__(
            self,
            "affected_capabilities",
            _normalize_text_tuple(self.affected_capabilities, "affected_capabilities"),
        )

        if not self.affected_capabilities:
            raise DegradationRuntimeError("affected_capabilities must not be empty.")

        self._validate_operator_shape()

    def evaluate(self, telemetry: RuntimeTelemetry) -> DegradationSignal | None:
        """Evaluate telemetry and return a degradation signal when matched."""

        observed_value = telemetry.get(self.telemetry_key)
        if not self._matches(observed_value, telemetry.has(self.telemetry_key)):
            return None

        return DegradationSignal(
            signal_id=f"DEG-{self.rule_id}",
            category=self.category,
            level=self.level,
            source=f"telemetry:{telemetry.source}",
            rationale=self.rationale,
            observed_value=observed_value,
            affected_capabilities=self.affected_capabilities,
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
                raise DegradationRuntimeError(
                    "upper_threshold must not be absent for between degradation rules."
                )

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

        raise DegradationRuntimeError(f"Unsupported condition operator {self.operator.value!r}.")


@dataclass(frozen=True, slots=True)
class TelemetryConflictCheck:
    """Detect conflicting numeric telemetry values."""

    check_id: str
    primary_key: str
    comparison_key: str
    max_allowed_delta: float
    level: DegradationLevel
    rationale: str
    affected_capabilities: tuple[str, ...]
    category: DegradationCategory = DegradationCategory.CONFLICTING_TELEMETRY

    def __post_init__(self) -> None:
        object.__setattr__(self, "check_id", _require_text(self.check_id, "check_id"))
        object.__setattr__(self, "primary_key", _require_text(self.primary_key, "primary_key"))
        object.__setattr__(
            self,
            "comparison_key",
            _require_text(self.comparison_key, "comparison_key"),
        )
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        object.__setattr__(
            self,
            "affected_capabilities",
            _normalize_text_tuple(self.affected_capabilities, "affected_capabilities"),
        )

        if self.max_allowed_delta < 0:
            raise DegradationRuntimeError("max_allowed_delta must be non-negative.")
        if not self.affected_capabilities:
            raise DegradationRuntimeError("affected_capabilities must not be empty.")

    def evaluate(self, telemetry: RuntimeTelemetry) -> DegradationSignal | None:
        """Return a signal when the two telemetry values conflict."""

        if not telemetry.has(self.primary_key) or not telemetry.has(self.comparison_key):
            return None

        primary_value = telemetry.get(self.primary_key)
        comparison_value = telemetry.get(self.comparison_key)
        primary_number = _as_number(primary_value, field_name="primary telemetry value")
        comparison_number = _as_number(comparison_value, field_name="comparison telemetry value")
        delta = abs(primary_number - comparison_number)

        if delta <= self.max_allowed_delta:
            return None

        return DegradationSignal(
            signal_id=f"DEG-{self.check_id}",
            category=self.category,
            level=self.level,
            source=f"telemetry:{telemetry.source}",
            rationale=f"{self.rationale} Observed delta {delta:.6g}.",
            observed_value=delta,
            affected_capabilities=self.affected_capabilities,
        )


@dataclass(frozen=True, slots=True)
class DegradationAssessment:
    """Aggregated degradation assessment for a scenario or runtime snapshot."""

    scenario_id: str
    signals: tuple[DegradationSignal, ...]
    telemetry_source: str
    evidence_bundle_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", _require_text(self.scenario_id, "scenario_id"))
        object.__setattr__(
            self,
            "telemetry_source",
            _require_text(self.telemetry_source, "telemetry_source"),
        )
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_text_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )

        signal_ids = tuple(signal.signal_id for signal in self.signals)
        if len(signal_ids) != len(set(signal_ids)):
            raise DegradationRuntimeError("signals must not contain duplicate signal_id values.")

    def worst_level(self) -> DegradationLevel:
        """Return the worst degradation level in the assessment."""

        worst = DegradationLevel.NOMINAL
        for signal in self.signals:
            worst = _more_severe_level(worst, signal.level)
        return worst

    def degraded_mode(self) -> bool:
        """Return whether the assessment indicates degraded mode."""

        return self.worst_level().is_degraded()

    def requires_operator_review(self) -> bool:
        """Return whether any signal requires human review."""

        return any(signal.requires_operator_review() for signal in self.signals)

    def recommended_decision(self) -> AutonomyDecisionType:
        """Return the most restrictive recommended autonomy decision."""

        decision = AutonomyDecisionType.ALLOW
        for signal in self.signals:
            decision = _more_restrictive_decision(decision, signal.recommended_decision())
        return decision

    def recommended_authority_state(self) -> RuntimeAuthorityState:
        """Return the most restrictive recommended authority state."""

        authority_state = RuntimeAuthorityState.AUTONOMOUS_ALLOWED
        for signal in self.signals:
            authority_state = _more_restrictive_authority(
                authority_state,
                signal.recommended_authority_state(),
            )
        return authority_state

    def has_category(self, category: DegradationCategory) -> bool:
        """Return whether the assessment contains at least one signal category."""

        return any(signal.category is category for signal in self.signals)

    def signal_ids_by_level(self, level: DegradationLevel) -> tuple[str, ...]:
        """Return signal identifiers matching a degradation level."""

        return tuple(signal.signal_id for signal in self.signals if signal.level is level)

    def summary(self) -> str:
        """Return a compact human-readable assessment summary."""

        if not self.signals:
            return f"Scenario {self.scenario_id} is nominal."

        return (
            f"Scenario {self.scenario_id} worst degradation level: "
            f"{self.worst_level().value}; signals: "
            f"{', '.join(signal.signal_id for signal in self.signals)}."
        )


@dataclass(frozen=True, slots=True)
class DegradationEngine:
    """Evaluates telemetry, conflicts, and evidence integrity for degradation."""

    rules: tuple[DegradationRule, ...] = field(default_factory=tuple)
    conflict_checks: tuple[TelemetryConflictCheck, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        identifiers = tuple(rule.rule_id for rule in self.rules) + tuple(
            check.check_id for check in self.conflict_checks
        )
        if len(identifiers) != len(set(identifiers)):
            raise DegradationRuntimeError(
                "rules and conflict_checks must not contain duplicate identifiers."
            )

    def assess(
        self,
        *,
        scenario_id: str,
        telemetry: RuntimeTelemetry,
        evidence_bundles: tuple[EvidenceBundle, ...] = (),
    ) -> DegradationAssessment:
        """Assess degradation from telemetry, conflict checks, and evidence bundles."""

        normalized_scenario_id = _require_text(scenario_id, "scenario_id")
        signals: list[DegradationSignal] = []

        for rule in self.rules:
            signal = rule.evaluate(telemetry)
            if signal is not None:
                signals.append(signal)

        for check in self.conflict_checks:
            signal = check.evaluate(telemetry)
            if signal is not None:
                signals.append(signal)

        signals.extend(self._signals_from_evidence_bundles(evidence_bundles))

        return DegradationAssessment(
            scenario_id=normalized_scenario_id,
            signals=tuple(signals),
            telemetry_source=telemetry.source,
            evidence_bundle_ids=tuple(bundle.bundle_id for bundle in evidence_bundles),
        )

    @staticmethod
    def _signals_from_evidence_bundles(
        evidence_bundles: tuple[EvidenceBundle, ...],
    ) -> tuple[DegradationSignal, ...]:
        signals: list[DegradationSignal] = []

        for bundle in evidence_bundles:
            report = bundle.validate_integrity()

            for index, error in enumerate(report.errors, start=1):
                signals.append(
                    DegradationSignal(
                        signal_id=f"DEG-EVIDENCE-ERROR-{bundle.bundle_id}-{index}",
                        category=DegradationCategory.STALE_EVIDENCE,
                        level=DegradationLevel.CRITICAL,
                        source=f"evidence-bundle:{bundle.bundle_id}",
                        rationale=error,
                        affected_capabilities=("assurance-evidence",),
                    )
                )

            for index, warning in enumerate(report.warnings, start=1):
                level = DegradationLevel.DEGRADED
                if "has no content hash" in warning or "has no bundle hash" in warning:
                    level = DegradationLevel.WATCH

                signals.append(
                    DegradationSignal(
                        signal_id=f"DEG-EVIDENCE-WARNING-{bundle.bundle_id}-{index}",
                        category=DegradationCategory.STALE_EVIDENCE,
                        level=level,
                        source=f"evidence-bundle:{bundle.bundle_id}",
                        rationale=warning,
                        affected_capabilities=("assurance-evidence",),
                    )
                )

            for record in bundle.records:
                if record.status is EvidenceStatus.STALE:
                    signals.append(
                        DegradationSignal(
                            signal_id=f"DEG-EVIDENCE-STALE-{record.evidence_id}",
                            category=DegradationCategory.STALE_EVIDENCE,
                            level=DegradationLevel.DEGRADED,
                            source=f"evidence-record:{record.evidence_id}",
                            rationale="Evidence record is stale.",
                            affected_capabilities=("assurance-evidence",),
                            evidence_ids=(record.evidence_id,),
                        )
                    )
                if record.status is EvidenceStatus.INVALID:
                    signals.append(
                        DegradationSignal(
                            signal_id=f"DEG-EVIDENCE-INVALID-{record.evidence_id}",
                            category=DegradationCategory.STALE_EVIDENCE,
                            level=DegradationLevel.CRITICAL,
                            source=f"evidence-record:{record.evidence_id}",
                            rationale="Evidence record is invalid.",
                            affected_capabilities=("assurance-evidence",),
                            evidence_ids=(record.evidence_id,),
                        )
                    )

        return tuple(signals)


def build_default_degradation_rules() -> tuple[DegradationRule, ...]:
    """Build default degradation rules for common autonomy T&E telemetry."""

    return (
        DegradationRule(
            rule_id="NAV-CONFIDENCE-CRITICAL",
            category=DegradationCategory.NAVIGATION_UNCERTAINTY,
            telemetry_key="navigation_confidence",
            operator=ConditionOperator.LT,
            threshold=0.50,
            level=DegradationLevel.CRITICAL,
            rationale="Navigation confidence is critically low.",
            affected_capabilities=("navigation", "route_execution", "boundary_keeping"),
        ),
        DegradationRule(
            rule_id="NAV-CONFIDENCE-DEGRADED",
            category=DegradationCategory.NAVIGATION_UNCERTAINTY,
            telemetry_key="navigation_confidence",
            operator=ConditionOperator.LT,
            threshold=0.70,
            level=DegradationLevel.DEGRADED,
            rationale="Navigation confidence is below nominal operating threshold.",
            affected_capabilities=("navigation", "route_execution"),
        ),
        DegradationRule(
            rule_id="COMMS-LINK-MISSING",
            category=DegradationCategory.COMMS_LOSS,
            telemetry_key="comms_link_active",
            operator=ConditionOperator.MISSING,
            threshold=None,
            level=DegradationLevel.SEVERE,
            rationale="Required communications-link telemetry is missing.",
            affected_capabilities=("operator_link", "remote_supervision"),
        ),
        DegradationRule(
            rule_id="POWER-MARGIN-LOW",
            category=DegradationCategory.POWER_DEGRADATION,
            telemetry_key="power_margin_pct",
            operator=ConditionOperator.LT,
            threshold=20.0,
            level=DegradationLevel.DEGRADED,
            rationale="Power margin is below the degraded-mode threshold.",
            affected_capabilities=("power", "mission_duration"),
        ),
        DegradationRule(
            rule_id="SENSOR-DRIFT-HIGH",
            category=DegradationCategory.SENSOR_DRIFT,
            telemetry_key="sensor_drift_sigma",
            operator=ConditionOperator.GT,
            threshold=3.0,
            level=DegradationLevel.DEGRADED,
            rationale="Sensor drift exceeds the accepted sigma threshold.",
            affected_capabilities=("sensing", "state_estimation"),
        ),
        DegradationRule(
            rule_id="CONTROL-LOOP-LATENCY-HIGH",
            category=DegradationCategory.TIMING_DEGRADATION,
            telemetry_key="control_loop_latency_ms",
            operator=ConditionOperator.GT,
            threshold=250.0,
            level=DegradationLevel.SEVERE,
            rationale="Control-loop latency exceeds safe runtime budget.",
            affected_capabilities=("control_loop", "runtime_assurance"),
        ),
    )
