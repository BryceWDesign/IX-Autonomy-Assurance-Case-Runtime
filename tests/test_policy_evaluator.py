from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError
from ix_autonomy_assurance_case_runtime.policy import (
    PolicyActionCategory,
    PolicyAuthorityRequirement,
    PolicyDecision,
    PolicyLifecycleState,
    PolicyPack,
    PolicyRiskTier,
    PolicyRule,
    PolicySubjectType,
    PolicyWaiver,
)
from ix_autonomy_assurance_case_runtime.policy_evaluator import (
    PolicyEvaluationFinding,
    PolicyEvaluationFindingSeverity,
    PolicyEvaluationRequest,
    PolicyEvaluator,
    rule_matches,
)


def _review_rule() -> PolicyRule:
    return PolicyRule(
        rule_id="rule-review-high-risk-autonomy",
        name="Review high-risk autonomy",
        description="High-risk autonomy requires explicit human review.",
        decision=PolicyDecision.REQUIRE_REVIEW,
        action_categories=(PolicyActionCategory.AUTONOMY_EXECUTION,),
        subject_types=(PolicySubjectType.DEPLOYMENT,),
        minimum_risk_tier=PolicyRiskTier.HIGH,
        authority_requirement=PolicyAuthorityRequirement.HUMAN_REVIEWER,
        required_evidence_kinds=("safety-gate-result",),
    )


def _waiver_rule() -> PolicyRule:
    return PolicyRule(
        rule_id="rule-waiver-export-sensitive-package",
        name="Require waiver for sensitive export",
        description="Sensitive governance exports need a bounded waiver.",
        decision=PolicyDecision.REQUIRE_WAIVER,
        action_categories=(PolicyActionCategory.EXPORT_PACKAGE,),
        subject_types=(PolicySubjectType.EXPORT_PACKAGE,),
        minimum_risk_tier=PolicyRiskTier.MODERATE,
        authority_requirement=PolicyAuthorityRequirement.SYSTEM_OWNER,
        required_evidence_kinds=("export-justification",),
    )


def _block_rule() -> PolicyRule:
    return PolicyRule(
        rule_id="rule-block-unsafe-condition",
        name="Block unsafe autonomy condition",
        description="Unsafe autonomy conditions must fail closed.",
        decision=PolicyDecision.ALLOW,
        action_categories=(PolicyActionCategory.AUTONOMY_EXECUTION,),
        subject_types=(PolicySubjectType.DEPLOYMENT,),
        blocked_conditions=("authority_denied",),
    )


def _policy_pack(*rules: PolicyRule) -> PolicyPack:
    return PolicyPack(
        policy_pack_id="pack-fed-001",
        name="Federal aligned local policy pack",
        version="2026.05",
        owner="Assurance Lab",
        lifecycle_state=PolicyLifecycleState.ACTIVE,
        rules=rules or (_review_rule(),),
    )


def _autonomy_request(
    *,
    authority: PolicyAuthorityRequirement = PolicyAuthorityRequirement.HUMAN_REVIEWER,
    evidence_kinds: tuple[str, ...] = ("safety-gate-result",),
    active_conditions: tuple[str, ...] = (),
) -> PolicyEvaluationRequest:
    return PolicyEvaluationRequest(
        request_id="policy-request-001",
        action_category=PolicyActionCategory.AUTONOMY_EXECUTION,
        subject_type=PolicySubjectType.DEPLOYMENT,
        subject_id="deploy-nav-001",
        risk_tier=PolicyRiskTier.HIGH,
        requested_by="runtime-gate",
        authority=authority,
        evidence_kinds=evidence_kinds,
        active_conditions=active_conditions,
        evaluated_at_utc="2026-05-12T12:00:00Z",
    )


def test_policy_evaluator_allows_review_rule_when_authority_and_evidence_are_satisfied() -> None:
    report = PolicyEvaluator(_policy_pack()).evaluate(_autonomy_request())

    assert report.decision is PolicyDecision.ALLOW
    assert report.permits_without_intervention()
    assert report.matched_rule_ids == ("rule-review-high-risk-autonomy",)
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "policy-evaluation: allow (1 matched rule(s), 0 blocker(s), 0 warning(s))"
    )


def test_policy_evaluator_requires_review_when_authority_is_insufficient() -> None:
    report = PolicyEvaluator(_policy_pack()).evaluate(
        _autonomy_request(authority=PolicyAuthorityRequirement.NONE)
    )

    assert report.decision is PolicyDecision.REQUIRE_REVIEW
    assert not report.permits_without_intervention()
    assert report.warning_count == 1
    assert report.findings[0].finding_id == (
        "rule-rule-review-high-risk-autonomy-authority-insufficient"
    )


def test_policy_evaluator_requires_review_when_required_evidence_is_missing() -> None:
    report = PolicyEvaluator(_policy_pack()).evaluate(_autonomy_request(evidence_kinds=()))

    assert report.decision is PolicyDecision.REQUIRE_REVIEW
    assert report.warning_count == 1
    assert report.findings[0].finding_id == (
        "rule-rule-review-high-risk-autonomy-missing-evidence-safety-gate-result"
    )


def test_policy_evaluator_blocks_active_blocked_conditions_fail_closed() -> None:
    report = PolicyEvaluator(_policy_pack(_review_rule(), _block_rule())).evaluate(
        _autonomy_request(active_conditions=("authority_denied",))
    )

    assert report.decision is PolicyDecision.BLOCK
    assert not report.permits_without_intervention()
    assert report.blocker_count == 1
    assert "authority_denied" in report.findings[-1].message


def test_policy_evaluator_requires_waiver_when_no_valid_waiver_is_present() -> None:
    request = PolicyEvaluationRequest(
        request_id="policy-request-export-001",
        action_category=PolicyActionCategory.EXPORT_PACKAGE,
        subject_type=PolicySubjectType.EXPORT_PACKAGE,
        subject_id="export-audit-001",
        risk_tier=PolicyRiskTier.MODERATE,
        requested_by="export-cli",
        evidence_kinds=("export-justification",),
        evaluated_at_utc="2026-05-12T12:00:00Z",
    )

    report = PolicyEvaluator(_policy_pack(_waiver_rule())).evaluate(request)

    assert report.decision is PolicyDecision.REQUIRE_WAIVER
    assert report.warning_count == 1
    assert report.findings[0].finding_id == (
        "rule-rule-waiver-export-sensitive-package-waiver-required"
    )


def test_policy_evaluator_accepts_active_bounded_waiver_for_waiver_rule() -> None:
    waiver = PolicyWaiver(
        waiver_id="waiver-export-001",
        policy_pack_id="pack-fed-001",
        covered_rule_ids=("rule-waiver-export-sensitive-package",),
        granted_by="System Owner",
        authority_requirement=PolicyAuthorityRequirement.SYSTEM_OWNER,
        justification="Bounded review export for audit package validation.",
        evidence_bundle_ids=("ev-waiver-export-001",),
        scope_limitations=("audit package only",),
        expires_at_utc="2026-06-01T00:00:00Z",
    )
    request = PolicyEvaluationRequest(
        request_id="policy-request-export-001",
        action_category=PolicyActionCategory.EXPORT_PACKAGE,
        subject_type=PolicySubjectType.EXPORT_PACKAGE,
        subject_id="export-audit-001",
        risk_tier=PolicyRiskTier.MODERATE,
        requested_by="export-cli",
        evidence_kinds=("export-justification",),
        waiver_ids=("waiver-export-001",),
        evaluated_at_utc="2026-05-12T12:00:00Z",
    )

    report = PolicyEvaluator(_policy_pack(_waiver_rule()), waivers=(waiver,)).evaluate(request)

    assert report.decision is PolicyDecision.ALLOW
    assert report.permits_without_intervention()
    assert report.rule_evaluations[0].satisfied_by_waiver_id == "waiver-export-001"
    assert report.findings[0].severity is PolicyEvaluationFindingSeverity.INFO


def test_policy_evaluator_rejects_expired_waiver_and_duplicate_waiver_ids() -> None:
    waiver = PolicyWaiver(
        waiver_id="waiver-export-001",
        policy_pack_id="pack-fed-001",
        covered_rule_ids=("rule-waiver-export-sensitive-package",),
        granted_by="System Owner",
        authority_requirement=PolicyAuthorityRequirement.SYSTEM_OWNER,
        justification="Expired waiver.",
        evidence_bundle_ids=("ev-waiver-export-001",),
        scope_limitations=("audit package only",),
        expires_at_utc="2026-05-01T00:00:00Z",
    )
    request = PolicyEvaluationRequest(
        request_id="policy-request-export-001",
        action_category=PolicyActionCategory.EXPORT_PACKAGE,
        subject_type=PolicySubjectType.EXPORT_PACKAGE,
        subject_id="export-audit-001",
        risk_tier=PolicyRiskTier.MODERATE,
        requested_by="export-cli",
        evidence_kinds=("export-justification",),
        waiver_ids=("waiver-export-001",),
        evaluated_at_utc="2026-05-12T12:00:00Z",
    )

    report = PolicyEvaluator(_policy_pack(_waiver_rule()), waivers=(waiver,)).evaluate(request)

    assert report.decision is PolicyDecision.REQUIRE_WAIVER
    assert any(finding.finding_id.endswith("-expired") for finding in report.findings)

    with pytest.raises(ContractValueError, match="Duplicate policy waiver ID"):
        PolicyEvaluator(_policy_pack(_waiver_rule()), waivers=(waiver, waiver))


def test_policy_evaluator_blocks_inactive_policy_pack() -> None:
    inactive_pack = PolicyPack(
        policy_pack_id="pack-fed-001",
        name="Federal aligned local policy pack",
        version="2026.05",
        owner="Assurance Lab",
        lifecycle_state=PolicyLifecycleState.SUSPENDED,
        rules=(_review_rule(),),
    )

    report = PolicyEvaluator(inactive_pack).evaluate(_autonomy_request())

    assert report.decision is PolicyDecision.BLOCK
    assert report.blocker_count == 1
    assert report.findings[0].finding_id == "policy-pack-not-active"


def test_policy_evaluator_applies_fail_closed_default_when_no_rules_match() -> None:
    report = PolicyEvaluator(_policy_pack()).evaluate(
        PolicyEvaluationRequest(
            request_id="policy-request-export-001",
            action_category=PolicyActionCategory.EXPORT_PACKAGE,
            subject_type=PolicySubjectType.EXPORT_PACKAGE,
            subject_id="export-audit-001",
            risk_tier=PolicyRiskTier.LOW,
            requested_by="export-cli",
            evaluated_at_utc="2026-05-12T12:00:00Z",
        )
    )

    assert report.decision is PolicyDecision.REQUIRE_REVIEW
    assert report.matched_rule_ids == ()
    assert report.warning_count == 1
    assert report.findings[0].finding_id == "policy-default-decision-applied"


def test_policy_request_rejects_duplicate_and_naive_timestamp_inputs() -> None:
    with pytest.raises(ContractValueError, match="duplicate values"):
        PolicyEvaluationRequest(
            request_id="policy-request-001",
            action_category=PolicyActionCategory.AUTONOMY_EXECUTION,
            subject_type=PolicySubjectType.DEPLOYMENT,
            subject_id="deploy-nav-001",
            risk_tier=PolicyRiskTier.HIGH,
            requested_by="runtime-gate",
            evidence_kinds=("safety-gate-result", "safety-gate-result"),
        )

    with pytest.raises(ContractValueError, match="must include a timezone"):
        PolicyEvaluationRequest(
            request_id="policy-request-001",
            action_category=PolicyActionCategory.AUTONOMY_EXECUTION,
            subject_type=PolicySubjectType.DEPLOYMENT,
            subject_id="deploy-nav-001",
            risk_tier=PolicyRiskTier.HIGH,
            requested_by="runtime-gate",
            evaluated_at_utc="2026-05-12T12:00:00",
        )


def test_policy_evaluation_finding_rejects_blank_rule_and_waiver_ids() -> None:
    with pytest.raises(ContractValueError, match="blank rule ID"):
        PolicyEvaluationFinding(
            finding_id="bad-finding",
            severity=PolicyEvaluationFindingSeverity.WARNING,
            message="Bad finding.",
            rule_id="",
        )

    with pytest.raises(ContractValueError, match="blank waiver ID"):
        PolicyEvaluationFinding(
            finding_id="bad-finding",
            severity=PolicyEvaluationFindingSeverity.WARNING,
            message="Bad finding.",
            waiver_id="",
        )


def test_rule_matches_uses_action_subject_and_minimum_risk_tier() -> None:
    rule = _review_rule()

    assert rule_matches(rule, _autonomy_request())
    assert not rule_matches(
        rule,
        PolicyEvaluationRequest(
            request_id="policy-request-low-001",
            action_category=PolicyActionCategory.AUTONOMY_EXECUTION,
            subject_type=PolicySubjectType.DEPLOYMENT,
            subject_id="deploy-nav-001",
            risk_tier=PolicyRiskTier.LOW,
            requested_by="runtime-gate",
            evaluated_at_utc="2026-05-12T12:00:00Z",
        ),
    )
