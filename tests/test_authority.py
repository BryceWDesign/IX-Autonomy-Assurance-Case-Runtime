from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.authority import (
    AuthorityController,
    AuthorityReviewDecision,
    AuthorityReviewError,
    AuthorityReviewRequest,
    ReviewActor,
)
from ix_autonomy_assurance_case_runtime.contracts import (
    AutonomyDecisionType,
    ReviewDisposition,
    RuntimeAuthorityState,
)
from ix_autonomy_assurance_case_runtime.safety_gate import SafetyGateResult


def build_actor(*, role: str = "test-director") -> ReviewActor:
    return ReviewActor(
        actor_id="USR-001",
        role=role,
        display_name="Test Director",
    )


def build_gate_result(
    *,
    decision: AutonomyDecisionType = AutonomyDecisionType.DEFER,
    authority_state: RuntimeAuthorityState = RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
) -> SafetyGateResult:
    return SafetyGateResult(
        scenario_id="SCN-001",
        decision=decision,
        authority_state=authority_state,
        operator_review_required=True,
        degraded_mode=True,
        triggered_rule_ids=("RULE-001",),
        expected_behavior_id="BEH-001",
        rule_evaluations=(),
        rationale="Navigation confidence is degraded and requires review.",
        telemetry_source="simulated-runtime",
        evidence_ids=("EV-001",),
    )


def build_request(
    *,
    decision: AutonomyDecisionType = AutonomyDecisionType.DEFER,
    authority_state: RuntimeAuthorityState = RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED,
) -> AuthorityReviewRequest:
    return AuthorityReviewRequest.from_safety_gate_result(
        request_id="REQ-REVIEW-001",
        result=build_gate_result(decision=decision, authority_state=authority_state),
        requested_by=build_actor(role="runtime-gate"),
        required_reviewer_role="test-director",
    )


def test_review_request_from_safety_gate_result_preserves_context() -> None:
    request = build_request()

    assert request.request_id == "REQ-REVIEW-001"
    assert request.scenario_id == "SCN-001"
    assert request.current_decision is AutonomyDecisionType.DEFER
    assert request.current_authority_state is RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED
    assert request.reason == "Runtime safety gate requires human authority review."
    assert request.triggered_rule_ids == ("RULE-001",)
    assert request.evidence_ids == ("EV-001",)
    assert request.requires_review() is True


def test_review_request_for_nominal_result_does_not_require_review() -> None:
    request = build_request(
        decision=AutonomyDecisionType.ALLOW,
        authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
    )

    assert request.reason == "Runtime safety gate permits nominal autonomous execution."
    assert request.requires_review() is False


def test_approved_review_can_release_defer_to_autonomous_allowed() -> None:
    request = build_request()
    decision = AuthorityReviewDecision(
        decision_id="DEC-001",
        request_id=request.request_id,
        reviewer=build_actor(),
        disposition=ReviewDisposition.APPROVED,
        rationale="Evidence supports release from human-approval defer.",
        approved_decision=AutonomyDecisionType.ALLOW,
        approved_authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
        evidence_ids=("EV-REVIEW-001",),
    )

    result = AuthorityController().apply_review_decision(
        request=request,
        decision=decision,
    )

    assert result.accepted is True
    assert result.final_decision is AutonomyDecisionType.ALLOW
    assert result.final_authority_state is RuntimeAuthorityState.AUTONOMOUS_ALLOWED
    assert result.permits_nominal_execution() is True
    assert result.evidence_ids == ("EV-REVIEW-001",)


def test_approved_with_conditions_requires_and_preserves_conditions() -> None:
    request = build_request()
    decision = AuthorityReviewDecision(
        decision_id="DEC-002",
        request_id=request.request_id,
        reviewer=build_actor(),
        disposition=ReviewDisposition.APPROVED_WITH_CONDITIONS,
        rationale="Release is allowed only while telemetry confidence remains stable.",
        approved_decision=AutonomyDecisionType.ALLOW,
        approved_authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
        conditions=("navigation confidence must remain >= 0.80",),
    )

    result = AuthorityController().apply_review_decision(
        request=request,
        decision=decision,
    )

    assert result.accepted is True
    assert result.disposition is ReviewDisposition.APPROVED_WITH_CONDITIONS
    assert result.conditions == ("navigation confidence must remain >= 0.80",)


def test_approved_with_conditions_without_conditions_is_rejected() -> None:
    request = build_request()

    with pytest.raises(AuthorityReviewError, match="conditions are required"):
        AuthorityReviewDecision(
            decision_id="DEC-BAD",
            request_id=request.request_id,
            reviewer=build_actor(),
            disposition=ReviewDisposition.APPROVED_WITH_CONDITIONS,
            rationale="This accepting decision is missing conditions.",
            approved_decision=AutonomyDecisionType.ALLOW,
            approved_authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
        )


def test_rejected_review_forces_veto_and_denied_authority() -> None:
    request = build_request()
    decision = AuthorityReviewDecision(
        decision_id="DEC-003",
        request_id=request.request_id,
        reviewer=build_actor(),
        disposition=ReviewDisposition.REJECTED,
        rationale="Evidence does not support safe autonomous release.",
    )

    result = AuthorityController().apply_review_decision(
        request=request,
        decision=decision,
    )

    assert result.accepted is False
    assert result.final_decision is AutonomyDecisionType.VETO
    assert result.final_authority_state is RuntimeAuthorityState.DENIED
    assert result.blocks_or_restricts_execution() is True


def test_needs_more_evidence_keeps_or_raises_to_defer_review_state() -> None:
    request = build_request(
        decision=AutonomyDecisionType.CLAMP,
        authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
    )
    decision = AuthorityReviewDecision(
        decision_id="DEC-004",
        request_id=request.request_id,
        reviewer=build_actor(),
        disposition=ReviewDisposition.NEEDS_MORE_EVIDENCE,
        rationale="The reviewer needs more scenario evidence before release.",
    )

    result = AuthorityController().apply_review_decision(
        request=request,
        decision=decision,
    )

    assert result.accepted is False
    assert result.final_decision is AutonomyDecisionType.DEFER
    assert result.final_authority_state is RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED
    assert result.blocks_or_restricts_execution() is True


def test_escalated_review_preserves_emergency_safe_hold() -> None:
    request = build_request(
        decision=AutonomyDecisionType.SAFE_HOLD,
        authority_state=RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
    )
    decision = AuthorityReviewDecision(
        decision_id="DEC-005",
        request_id=request.request_id,
        reviewer=build_actor(),
        disposition=ReviewDisposition.ESCALATED,
        rationale="Escalated to safety authority.",
    )

    result = AuthorityController().apply_review_decision(
        request=request,
        decision=decision,
    )

    assert result.accepted is False
    assert result.final_decision is AutonomyDecisionType.SAFE_HOLD
    assert result.final_authority_state is RuntimeAuthorityState.EMERGENCY_SAFE_HOLD


def test_controller_rejects_mismatched_request_id() -> None:
    request = build_request()
    decision = AuthorityReviewDecision(
        decision_id="DEC-MISMATCH",
        request_id="REQ-OTHER",
        reviewer=build_actor(),
        disposition=ReviewDisposition.REJECTED,
        rationale="Mismatched request should fail.",
    )

    with pytest.raises(AuthorityReviewError, match="expected 'REQ-REVIEW-001'"):
        AuthorityController().apply_review_decision(
            request=request,
            decision=decision,
        )


def test_controller_prevents_relaxing_emergency_safe_hold_to_allow() -> None:
    request = build_request(
        decision=AutonomyDecisionType.SAFE_HOLD,
        authority_state=RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
    )
    decision = AuthorityReviewDecision(
        decision_id="DEC-UNSAFE",
        request_id=request.request_id,
        reviewer=build_actor(),
        disposition=ReviewDisposition.APPROVED,
        rationale="Unsafe attempt to relax emergency safe-hold.",
        approved_decision=AutonomyDecisionType.ALLOW,
        approved_authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
    )

    with pytest.raises(AuthorityReviewError, match="would relax a restrictive runtime state"):
        AuthorityController().apply_review_decision(
            request=request,
            decision=decision,
        )


def test_accepting_review_requires_approved_outcomes() -> None:
    request = build_request()

    with pytest.raises(AuthorityReviewError, match="approved_decision is required"):
        AuthorityReviewDecision(
            decision_id="DEC-MISSING",
            request_id=request.request_id,
            reviewer=build_actor(),
            disposition=ReviewDisposition.APPROVED,
            rationale="Accepting decisions must include approved outcomes.",
        )


def test_non_accepting_review_must_not_provide_approved_outcomes() -> None:
    request = build_request()

    with pytest.raises(AuthorityReviewError, match="must not provide approved authority outcomes"):
        AuthorityReviewDecision(
            decision_id="DEC-BAD",
            request_id=request.request_id,
            reviewer=build_actor(),
            disposition=ReviewDisposition.REJECTED,
            rationale="Rejected decisions cannot include release outcomes.",
            approved_decision=AutonomyDecisionType.ALLOW,
            approved_authority_state=RuntimeAuthorityState.AUTONOMOUS_ALLOWED,
        )


def test_actor_rejects_blank_fields() -> None:
    with pytest.raises(AuthorityReviewError, match="actor_id must not be blank"):
        ReviewActor(
            actor_id=" ",
            role="test-director",
            display_name="Test Director",
        )


def test_review_request_rejects_duplicate_evidence_ids() -> None:
    result = build_gate_result()

    with pytest.raises(AuthorityReviewError, match="evidence_ids must not contain duplicate"):
        AuthorityReviewRequest.from_safety_gate_result(
            request_id="REQ-DUP",
            result=SafetyGateResult(
                scenario_id=result.scenario_id,
                decision=result.decision,
                authority_state=result.authority_state,
                operator_review_required=result.operator_review_required,
                degraded_mode=result.degraded_mode,
                triggered_rule_ids=result.triggered_rule_ids,
                expected_behavior_id=result.expected_behavior_id,
                rule_evaluations=result.rule_evaluations,
                rationale=result.rationale,
                telemetry_source=result.telemetry_source,
                evidence_ids=("EV-001", "EV-001"),
            ),
            requested_by=build_actor(role="runtime-gate"),
            required_reviewer_role="test-director",
        )
