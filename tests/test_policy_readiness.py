from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, EvidenceStatus
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
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
from ix_autonomy_assurance_case_runtime.policy_evaluator import PolicyEvaluationRequest
from ix_autonomy_assurance_case_runtime.policy_readiness import (
    PolicyLayerReadinessDecision,
    PolicyLayerReadinessEvaluator,
    PolicyReadinessFinding,
    PolicyReadinessFindingSeverity,
    PolicyReadinessFindingSource,
)
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessDecision,
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
        rule_id="rule-block-authority-denied",
        name="Block denied authority state",
        description="Denied authority state must fail closed.",
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


def _waiver(expires_at_utc: str = "2026-06-01T00:00:00Z") -> PolicyWaiver:
    return PolicyWaiver(
        waiver_id="waiver-export-001",
        policy_pack_id="pack-fed-001",
        covered_rule_ids=("rule-waiver-export-sensitive-package",),
        granted_by="System Owner",
        authority_requirement=PolicyAuthorityRequirement.SYSTEM_OWNER,
        justification="Bounded review export for audit package validation.",
        evidence_bundle_ids=("ev-waiver-export-001",),
        scope_limitations=("audit package only",),
        expires_at_utc=expires_at_utc,
    )


def _bundle(status: EvidenceStatus = EvidenceStatus.ACCEPTED) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="ev-waiver-export-001",
        case_id="case-policy-waiver-001",
        records=(
            EvidenceRecord(
                evidence_id="record-ev-waiver-export-001",
                kind="waiver-justification",
                source="unit-test",
                payload={"supports": "ev-waiver-export-001"},
                status=status,
            ),
        ),
    ).with_computed_hashes()


def _autonomy_request(
    *,
    authority: PolicyAuthorityRequirement = PolicyAuthorityRequirement.HUMAN_REVIEWER,
    evidence_kinds: tuple[str, ...] = ("safety-gate-result",),
    active_conditions: tuple[str, ...] = (),
) -> PolicyEvaluationRequest:
    return PolicyEvaluationRequest(
        request_id="policy-request-autonomy-001",
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


def _export_request(
    waiver_ids: tuple[str, ...] = ("waiver-export-001",),
) -> PolicyEvaluationRequest:
    return PolicyEvaluationRequest(
        request_id="policy-request-export-001",
        action_category=PolicyActionCategory.EXPORT_PACKAGE,
        subject_type=PolicySubjectType.EXPORT_PACKAGE,
        subject_id="export-audit-001",
        risk_tier=PolicyRiskTier.MODERATE,
        requested_by="export-cli",
        evidence_kinds=("export-justification",),
        waiver_ids=waiver_ids,
        evaluated_at_utc="2026-05-12T12:00:00Z",
    )


def test_policy_readiness_completes_with_clean_policy_and_waiver_evidence() -> None:
    report = PolicyLayerReadinessEvaluator(
        _policy_pack(_review_rule(), _waiver_rule()),
        waivers=(_waiver(),),
        evidence_bundles=(_bundle(),),
    ).evaluate(
        requests=(_autonomy_request(), _export_request()),
        as_of_utc="2026-05-12T12:00:00Z",
    )

    assert report.decision is PolicyLayerReadinessDecision.COMPLETE
    assert report.is_complete()
    assert report.completed_capability_ids() == ("policy-pack-engine",)
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "policy-readiness: complete "
        "(0 blocker(s), 0 warning(s), capability=policy-pack-engine)"
    )


def test_policy_readiness_feeds_prototype_claim_gate_with_existing_registry_completion() -> None:
    report = PolicyLayerReadinessEvaluator(
        _policy_pack(_review_rule()),
    ).evaluate(requests=(_autonomy_request(),))

    prototype_report = report.prototype_readiness_report(
        PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE,
        existing_completed_capability_ids=("registry-layer",),
    )

    assert prototype_report.decision is PrototypeReadinessDecision.BLOCK
    assert prototype_report.achieved_percent == 48
    assert prototype_report.completed_capability_ids == (
        "registry-layer",
        "policy-pack-engine",
    )
    assert "framework-crosswalks" in prototype_report.remaining_capability_ids


def test_policy_readiness_blocks_when_no_evaluation_requests_are_supplied() -> None:
    report = PolicyLayerReadinessEvaluator(_policy_pack()).evaluate(requests=())

    assert report.decision is PolicyLayerReadinessDecision.BLOCKED
    assert not report.is_complete()
    assert report.blocker_count == 1
    assert report.findings[0].finding_id == "policy-readiness-no-evaluation-requests"
    assert report.findings[0].source is PolicyReadinessFindingSource.READINESS


def test_policy_readiness_blocks_policy_denial_conditions() -> None:
    report = PolicyLayerReadinessEvaluator(
        _policy_pack(_review_rule(), _block_rule()),
    ).evaluate(requests=(_autonomy_request(active_conditions=("authority_denied",)),))

    assert report.decision is PolicyLayerReadinessDecision.BLOCKED
    assert report.blocker_count == 1
    assert report.findings[0].source is PolicyReadinessFindingSource.EVALUATION
    assert report.findings[0].rule_id == "rule-block-authority-denied"


def test_policy_readiness_blocks_missing_waiver_evidence() -> None:
    report = PolicyLayerReadinessEvaluator(
        _policy_pack(_review_rule(), _waiver_rule()),
        waivers=(_waiver(),),
        evidence_bundles=(),
    ).evaluate(
        requests=(_autonomy_request(), _export_request()),
        as_of_utc="2026-05-12T12:00:00Z",
    )

    assert report.decision is PolicyLayerReadinessDecision.BLOCKED
    assert report.blocker_count == 1
    assert any(
        finding.source is PolicyReadinessFindingSource.WAIVER_EVIDENCE
        for finding in report.findings_for_waiver("waiver-export-001")
    )


def test_policy_readiness_is_limited_when_policy_evaluation_has_warnings() -> None:
    report = PolicyLayerReadinessEvaluator(
        _policy_pack(_review_rule()),
    ).evaluate(
        requests=(
            _autonomy_request(
                authority=PolicyAuthorityRequirement.NONE,
                evidence_kinds=(),
            ),
        )
    )

    assert report.decision is PolicyLayerReadinessDecision.LIMITED
    assert not report.is_complete()
    assert report.warning_count == 2
    request_sources = {
        finding.source
        for finding in report.findings_for_request("policy-request-autonomy-001")
    }
    assert request_sources == {PolicyReadinessFindingSource.EVALUATION}


def test_policy_readiness_is_limited_when_waiver_evidence_has_hash_warnings() -> None:
    unhashed_bundle = EvidenceBundle(
        bundle_id="ev-waiver-export-001",
        case_id="case-policy-waiver-001",
        records=(
            EvidenceRecord(
                evidence_id="record-ev-waiver-export-001",
                kind="waiver-justification",
                source="unit-test",
                payload={"supports": "ev-waiver-export-001"},
                status=EvidenceStatus.ACCEPTED,
            ),
        ),
    )
    report = PolicyLayerReadinessEvaluator(
        _policy_pack(_review_rule(), _waiver_rule()),
        waivers=(_waiver(),),
        evidence_bundles=(unhashed_bundle,),
    ).evaluate(
        requests=(_autonomy_request(), _export_request()),
        as_of_utc="2026-05-12T12:00:00Z",
    )

    assert report.decision is PolicyLayerReadinessDecision.LIMITED
    assert report.warning_count == 2
    waiver_findings = report.findings_for_waiver("waiver-export-001")
    assert any(
        finding.source is PolicyReadinessFindingSource.WAIVER_EVIDENCE
        for finding in waiver_findings
    )


def test_policy_readiness_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        PolicyReadinessFinding(
            finding_id="bad-finding",
            severity=PolicyReadinessFindingSeverity.BLOCKER,
            source=PolicyReadinessFindingSource.READINESS,
            message="",
        )

    with pytest.raises(ContractValueError, match="blank request ID"):
        PolicyReadinessFinding(
            finding_id="bad-finding",
            severity=PolicyReadinessFindingSeverity.BLOCKER,
            source=PolicyReadinessFindingSource.READINESS,
            message="Bad finding.",
            request_id="",
        )
