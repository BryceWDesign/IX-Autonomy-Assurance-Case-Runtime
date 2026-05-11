"""Human authority and review model for runtime autonomy decisions.

The authority layer converts safety-gate output into reviewable authority
requests and final authority outcomes. It does not allow a human-review record to
silently bypass severe runtime restrictions. If the runtime is in emergency
safe-hold, denied, veto, or clamp, approval cannot relax the decision unless the
request is a defer-to-human case where human approval is the explicit gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ix_autonomy_assurance_case_runtime.contracts import (
    AutonomyDecisionType,
    ReviewDisposition,
    RuntimeAuthorityState,
)
from ix_autonomy_assurance_case_runtime.safety_gate import SafetyGateResult


class AuthorityReviewError(ValueError):
    """Raised when an authority review artifact is malformed or unsafe."""


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise AuthorityReviewError(f"{field_name} must not be blank.")
    return normalized


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise AuthorityReviewError(f"{field_name} must not contain duplicate values.")
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
    left: AutonomyDecisionType,
    right: AutonomyDecisionType,
) -> AutonomyDecisionType:
    if _decision_rank(right) > _decision_rank(left):
        return right
    return left


def _more_restrictive_authority(
    left: RuntimeAuthorityState,
    right: RuntimeAuthorityState,
) -> RuntimeAuthorityState:
    if _authority_rank(right) > _authority_rank(left):
        return right
    return left


@dataclass(frozen=True, slots=True)
class ReviewActor:
    """Human or accountable authority participating in a review workflow."""

    actor_id: str
    role: str
    display_name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor_id", _require_text(self.actor_id, "actor_id"))
        object.__setattr__(self, "role", _require_text(self.role, "role"))
        object.__setattr__(self, "display_name", _require_text(self.display_name, "display_name"))


@dataclass(frozen=True, slots=True)
class AuthorityReviewRequest:
    """Review request created from a runtime safety-gate result."""

    request_id: str
    scenario_id: str
    requested_by: ReviewActor
    required_reviewer_role: str
    current_decision: AutonomyDecisionType
    current_authority_state: RuntimeAuthorityState
    reason: str
    safety_gate_rationale: str
    expected_behavior_id: str
    triggered_rule_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _require_text(self.request_id, "request_id"))
        object.__setattr__(self, "scenario_id", _require_text(self.scenario_id, "scenario_id"))
        object.__setattr__(
            self,
            "required_reviewer_role",
            _require_text(self.required_reviewer_role, "required_reviewer_role"),
        )
        object.__setattr__(self, "reason", _require_text(self.reason, "reason"))
        object.__setattr__(
            self,
            "safety_gate_rationale",
            _require_text(self.safety_gate_rationale, "safety_gate_rationale"),
        )
        object.__setattr__(
            self,
            "expected_behavior_id",
            _require_text(self.expected_behavior_id, "expected_behavior_id"),
        )
        object.__setattr__(
            self,
            "triggered_rule_ids",
            _normalize_text_tuple(self.triggered_rule_ids, "triggered_rule_ids"),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _normalize_text_tuple(self.evidence_ids, "evidence_ids"),
        )

    @classmethod
    def from_safety_gate_result(
        cls,
        *,
        request_id: str,
        result: SafetyGateResult,
        requested_by: ReviewActor,
        required_reviewer_role: str,
    ) -> AuthorityReviewRequest:
        """Create a review request from a runtime safety-gate result."""

        if result.permits_nominal_execution():
            reason = "Runtime safety gate permits nominal autonomous execution."
        else:
            reason = "Runtime safety gate requires human authority review."

        return cls(
            request_id=request_id,
            scenario_id=result.scenario_id,
            requested_by=requested_by,
            required_reviewer_role=required_reviewer_role,
            current_decision=result.decision,
            current_authority_state=result.authority_state,
            reason=reason,
            safety_gate_rationale=result.rationale,
            expected_behavior_id=result.expected_behavior_id,
            triggered_rule_ids=result.triggered_rule_ids,
            evidence_ids=result.evidence_ids,
        )

    def requires_review(self) -> bool:
        """Return whether the current authority state requires human review."""

        return (
            self.current_decision.is_restrictive()
            or not self.current_authority_state.permits_autonomous_execution()
        )


@dataclass(frozen=True, slots=True)
class AuthorityReviewDecision:
    """Human review decision for a runtime authority request."""

    decision_id: str
    request_id: str
    reviewer: ReviewActor
    disposition: ReviewDisposition
    rationale: str
    approved_decision: AutonomyDecisionType | None = None
    approved_authority_state: RuntimeAuthorityState | None = None
    conditions: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", _require_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "request_id", _require_text(self.request_id, "request_id"))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        object.__setattr__(
            self,
            "conditions",
            _normalize_text_tuple(self.conditions, "conditions"),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _normalize_text_tuple(self.evidence_ids, "evidence_ids"),
        )

        if self.disposition.allows_acceptance():
            if self.approved_decision is None:
                raise AuthorityReviewError("approved_decision is required for accepting reviews.")
            if self.approved_authority_state is None:
                raise AuthorityReviewError(
                    "approved_authority_state is required for accepting reviews."
                )

        if self.disposition is ReviewDisposition.APPROVED_WITH_CONDITIONS and not self.conditions:
            raise AuthorityReviewError(
                "conditions are required for approved_with_conditions reviews."
            )

        if not self.disposition.allows_acceptance():
            if self.approved_decision is not None or self.approved_authority_state is not None:
                raise AuthorityReviewError(
                    "non-accepting reviews must not provide approved authority outcomes."
                )


@dataclass(frozen=True, slots=True)
class AuthorityDecisionResult:
    """Final authority outcome after applying a human review decision."""

    request_id: str
    decision_id: str
    final_decision: AutonomyDecisionType
    final_authority_state: RuntimeAuthorityState
    disposition: ReviewDisposition
    accepted: bool
    rationale: str
    reviewer: ReviewActor
    conditions: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _require_text(self.request_id, "request_id"))
        object.__setattr__(self, "decision_id", _require_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        object.__setattr__(
            self,
            "conditions",
            _normalize_text_tuple(self.conditions, "conditions"),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _normalize_text_tuple(self.evidence_ids, "evidence_ids"),
        )

    def permits_nominal_execution(self) -> bool:
        """Return whether the final authority outcome permits nominal autonomy."""

        return (
            self.final_decision.permits_nominal_execution()
            and self.final_authority_state.permits_autonomous_execution()
        )

    def blocks_or_restricts_execution(self) -> bool:
        """Return whether the final authority outcome blocks or restricts autonomy."""

        return not self.permits_nominal_execution()


@dataclass(frozen=True, slots=True)
class AuthorityController:
    """Applies human authority review decisions to safety-gate review requests."""

    def apply_review_decision(
        self,
        *,
        request: AuthorityReviewRequest,
        decision: AuthorityReviewDecision,
    ) -> AuthorityDecisionResult:
        """Apply a human review decision and return the final authority outcome."""

        if decision.request_id != request.request_id:
            raise AuthorityReviewError(
                f"Decision {decision.decision_id!r} references request "
                f"{decision.request_id!r}, expected {request.request_id!r}."
            )

        if decision.disposition.allows_acceptance():
            return self._apply_accepting_decision(request=request, decision=decision)

        if decision.disposition is ReviewDisposition.REJECTED:
            return AuthorityDecisionResult(
                request_id=request.request_id,
                decision_id=decision.decision_id,
                final_decision=AutonomyDecisionType.VETO,
                final_authority_state=RuntimeAuthorityState.DENIED,
                disposition=decision.disposition,
                accepted=False,
                rationale=decision.rationale,
                reviewer=decision.reviewer,
                conditions=decision.conditions,
                evidence_ids=decision.evidence_ids,
            )

        if decision.disposition in {
            ReviewDisposition.NEEDS_MORE_EVIDENCE,
            ReviewDisposition.ESCALATED,
        }:
            return AuthorityDecisionResult(
                request_id=request.request_id,
                decision_id=decision.decision_id,
                final_decision=_more_restrictive_decision(
                    request.current_decision,
                    AutonomyDecisionType.DEFER,
                ),
                final_authority_state=_more_restrictive_authority(
                    request.current_authority_state,
                    RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
                ),
                disposition=decision.disposition,
                accepted=False,
                rationale=decision.rationale,
                reviewer=decision.reviewer,
                conditions=decision.conditions,
                evidence_ids=decision.evidence_ids,
            )

        raise AuthorityReviewError(f"Unsupported review disposition {decision.disposition.value!r}.")

    def _apply_accepting_decision(
        self,
        *,
        request: AuthorityReviewRequest,
        decision: AuthorityReviewDecision,
    ) -> AuthorityDecisionResult:
        approved_decision = decision.approved_decision
        approved_authority_state = decision.approved_authority_state

        if approved_decision is None or approved_authority_state is None:
            raise AuthorityReviewError("Accepting review decisions must provide authority outcomes.")

        if self._would_relax_restricted_runtime_state(
            request=request,
            approved_decision=approved_decision,
            approved_authority_state=approved_authority_state,
        ):
            raise AuthorityReviewError(
                "Review decision would relax a restrictive runtime state without a "
                "defer-to-human approval path."
            )

        return AuthorityDecisionResult(
            request_id=request.request_id,
            decision_id=decision.decision_id,
            final_decision=approved_decision,
            final_authority_state=approved_authority_state,
            disposition=decision.disposition,
            accepted=True,
            rationale=decision.rationale,
            reviewer=decision.reviewer,
            conditions=decision.conditions,
            evidence_ids=decision.evidence_ids,
        )

    @staticmethod
    def _would_relax_restricted_runtime_state(
        *,
        request: AuthorityReviewRequest,
        approved_decision: AutonomyDecisionType,
        approved_authority_state: RuntimeAuthorityState,
    ) -> bool:
        relaxes_decision = _decision_rank(approved_decision) < _decision_rank(
            request.current_decision
        )
        relaxes_authority = _authority_rank(approved_authority_state) < _authority_rank(
            request.current_authority_state
        )

        if not relaxes_decision and not relaxes_authority:
            return False

        defer_to_human_release = (
            request.current_decision is AutonomyDecisionType.DEFER
            and request.current_authority_state is RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED
        )
        return not defer_to_human_release
