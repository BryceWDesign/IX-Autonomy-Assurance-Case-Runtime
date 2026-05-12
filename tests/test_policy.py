from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime import (
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
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError


def _review_rule() -> PolicyRule:
    return PolicyRule(
        rule_id="rule-human-review-high-risk-autonomy",
        name="Require human review for high-risk autonomy",
        description="High-risk autonomy execution needs an explicit reviewer.",
        decision=PolicyDecision.REQUIRE_REVIEW,
        action_categories=(PolicyActionCategory.AUTONOMY_EXECUTION,),
        subject_types=(PolicySubjectType.DEPLOYMENT,),
        minimum_risk_tier=PolicyRiskTier.HIGH,
        authority_requirement=PolicyAuthorityRequirement.HUMAN_REVIEWER,
        required_evidence_kinds=("safety-gate-result",),
    )


def test_policy_rule_preserves_action_subject_risk_and_authority_boundaries() -> None:
    rule = _review_rule()

    assert rule.applies_to_action(PolicyActionCategory.AUTONOMY_EXECUTION)
    assert rule.applies_to_subject(PolicySubjectType.DEPLOYMENT)
    assert rule.applies_to_risk_tier(PolicyRiskTier.CRITICAL)
    assert not rule.applies_to_risk_tier(PolicyRiskTier.MODERATE)
    assert rule.decision.needs_authority()
    assert PolicyAuthorityRequirement.SYSTEM_OWNER.satisfies(
        PolicyAuthorityRequirement.HUMAN_REVIEWER
    )


def test_block_policy_rule_can_describe_hard_denial_conditions() -> None:
    rule = PolicyRule(
        rule_id="rule-block-unsigned-evidence",
        name="Block unsigned evidence changes",
        description="Evidence updates missing provenance must be blocked.",
        decision=PolicyDecision.BLOCK,
        action_categories=(PolicyActionCategory.EVIDENCE_UPDATE,),
        subject_types=(PolicySubjectType.EVIDENCE_BUNDLE,),
        blocked_conditions=("signature_missing",),
    )

    assert rule.decision.blocks_action()
    assert rule.blocked_conditions == ("signature_missing",)


def test_policy_rule_rejects_review_or_waiver_without_required_authority() -> None:
    with pytest.raises(ContractValueError, match="requires authority"):
        PolicyRule(
            rule_id="bad-review-rule",
            name="Bad review rule",
            description="This rule is missing authority.",
            decision=PolicyDecision.REQUIRE_REVIEW,
            action_categories=(PolicyActionCategory.AUTONOMY_EXECUTION,),
            subject_types=(PolicySubjectType.DEPLOYMENT,),
        )

    with pytest.raises(ContractValueError, match="requires waiver evidence kinds"):
        PolicyRule(
            rule_id="bad-waiver-rule",
            name="Bad waiver rule",
            description="This rule is missing waiver evidence.",
            decision=PolicyDecision.REQUIRE_WAIVER,
            action_categories=(PolicyActionCategory.EXPORT_PACKAGE,),
            subject_types=(PolicySubjectType.EXPORT_PACKAGE,),
            authority_requirement=PolicyAuthorityRequirement.SYSTEM_OWNER,
        )


def test_policy_rule_rejects_high_risk_allow_without_authority() -> None:
    with pytest.raises(ContractValueError, match="cannot allow high-risk action"):
        PolicyRule(
            rule_id="bad-high-risk-allow",
            name="Bad high-risk allow",
            description="This rule allows too much without authority.",
            decision=PolicyDecision.ALLOW,
            action_categories=(PolicyActionCategory.AUTONOMY_EXECUTION,),
            subject_types=(PolicySubjectType.DEPLOYMENT,),
            minimum_risk_tier=PolicyRiskTier.HIGH,
        )


def test_policy_pack_preserves_versioned_rules_and_blocks_default_allow() -> None:
    pack = PolicyPack(
        policy_pack_id="pack-fed-001",
        name="Federal aligned local policy pack",
        version="2026.05",
        owner="Assurance Lab",
        lifecycle_state=PolicyLifecycleState.ACTIVE,
        rules=(_review_rule(),),
    )

    assert pack.is_evaluable()
    assert pack.rule_by_id("rule-human-review-high-risk-autonomy") == _review_rule()
    assert PolicyLifecycleState.SUSPENDED.blocks_policy_claims()

    with pytest.raises(ContractValueError, match="default decision must not be allow"):
        PolicyPack(
            policy_pack_id="bad-pack",
            name="Bad pack",
            version="1.0",
            owner="Assurance Lab",
            lifecycle_state=PolicyLifecycleState.DRAFT,
            rules=(),
            default_decision=PolicyDecision.ALLOW,
        )


def test_active_policy_pack_requires_rules_and_restrictive_governance() -> None:
    with pytest.raises(ContractValueError, match="active policy packs"):
        PolicyPack(
            policy_pack_id="empty-active-pack",
            name="Empty active pack",
            version="1.0",
            owner="Assurance Lab",
            lifecycle_state=PolicyLifecycleState.ACTIVE,
            rules=(),
        )

    allow_rule = PolicyRule(
        rule_id="allow-low-risk-decision-support",
        name="Allow low-risk decision support",
        description="Low-risk decision support can proceed.",
        decision=PolicyDecision.ALLOW,
        action_categories=(PolicyActionCategory.DECISION_SUPPORT,),
        subject_types=(PolicySubjectType.USE_CASE,),
    )
    with pytest.raises(ContractValueError, match="restrictive rule"):
        PolicyPack(
            policy_pack_id="allow-only-pack",
            name="Allow only pack",
            version="1.0",
            owner="Assurance Lab",
            lifecycle_state=PolicyLifecycleState.ACTIVE,
            rules=(allow_rule,),
        )


def test_policy_pack_rejects_duplicate_rule_ids() -> None:
    rule = _review_rule()

    with pytest.raises(ContractValueError, match="duplicate rule IDs"):
        PolicyPack(
            policy_pack_id="duplicate-rule-pack",
            name="Duplicate rule pack",
            version="1.0",
            owner="Assurance Lab",
            lifecycle_state=PolicyLifecycleState.ACTIVE,
            rules=(rule, rule),
        )


def test_policy_waiver_requires_authority_evidence_scope_and_expiration() -> None:
    waiver = PolicyWaiver(
        waiver_id="waiver-sim-001",
        policy_pack_id="pack-fed-001",
        covered_rule_ids=("rule-human-review-high-risk-autonomy",),
        granted_by="Chief AI Officer delegate",
        authority_requirement=PolicyAuthorityRequirement.GOVERNANCE_BOARD,
        justification="Bounded simulation-only exception for regression testing.",
        evidence_bundle_ids=("ev-waiver-sim-001",),
        scope_limitations=("simulation only", "expires before field testing"),
        expires_at_utc="2026-06-01T00:00:00Z",
    )

    assert waiver.covers_rule("rule-human-review-high-risk-autonomy")
    assert not waiver.covers_rule("uncovered-rule")

    with pytest.raises(ContractValueError, match="require explicit authority"):
        PolicyWaiver(
            waiver_id="bad-waiver",
            policy_pack_id="pack-fed-001",
            covered_rule_ids=("rule-human-review-high-risk-autonomy",),
            granted_by="Reviewer",
            authority_requirement=PolicyAuthorityRequirement.NONE,
            justification="Bad waiver.",
            evidence_bundle_ids=("ev-waiver-sim-001",),
            scope_limitations=("simulation only",),
            expires_at_utc="2026-06-01T00:00:00Z",
        )
