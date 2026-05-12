from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime import (
    EvidenceBundle,
    EvidenceRecord,
    EvidenceStatus,
    PolicyActionCategory,
    PolicyAuthorityRequirement,
    PolicyDecision,
    PolicyLifecycleState,
    PolicyPack,
    PolicyRiskTier,
    PolicyRule,
    PolicySubjectType,
    PolicyWaiver,
    PolicyWaiverEvidenceFinding,
    PolicyWaiverEvidenceFindingSeverity,
    PolicyWaiverEvidenceValidator,
    PolicyWaiverReferenceType,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError


def _rule() -> PolicyRule:
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


def _pack() -> PolicyPack:
    return PolicyPack(
        policy_pack_id="pack-fed-001",
        name="Federal aligned local policy pack",
        version="2026.05",
        owner="Assurance Lab",
        lifecycle_state=PolicyLifecycleState.ACTIVE,
        rules=(_rule(),),
    )


def _waiver(
    *,
    waiver_id: str = "waiver-export-001",
    policy_pack_id: str = "pack-fed-001",
    covered_rule_ids: tuple[str, ...] = ("rule-waiver-export-sensitive-package",),
    evidence_bundle_ids: tuple[str, ...] = ("ev-waiver-export-001",),
    expires_at_utc: str = "2026-06-01T00:00:00Z",
) -> PolicyWaiver:
    return PolicyWaiver(
        waiver_id=waiver_id,
        policy_pack_id=policy_pack_id,
        covered_rule_ids=covered_rule_ids,
        granted_by="System Owner",
        authority_requirement=PolicyAuthorityRequirement.SYSTEM_OWNER,
        justification="Bounded review export for audit package validation.",
        evidence_bundle_ids=evidence_bundle_ids,
        scope_limitations=("audit package only",),
        expires_at_utc=expires_at_utc,
    )


def _bundle(
    bundle_id: str = "ev-waiver-export-001",
    *,
    status: EvidenceStatus = EvidenceStatus.ACCEPTED,
) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=bundle_id,
        case_id="case-policy-waiver-001",
        records=(
            EvidenceRecord(
                evidence_id=f"record-{bundle_id}",
                kind="waiver-justification",
                source="unit-test",
                payload={"supports": bundle_id},
                status=status,
            ),
        ),
    ).with_computed_hashes()


def test_policy_waiver_evidence_accepts_valid_coverage() -> None:
    report = PolicyWaiverEvidenceValidator(_pack(), bundles=(_bundle(),)).validate(
        waivers=(_waiver(),),
        as_of_utc="2026-05-12T12:00:00Z",
    )

    assert report.is_coverage_ready()
    assert report.policy_pack_id == "pack-fed-001"
    assert report.waiver_count == 1
    assert report.referenced_bundle_count == 1
    assert report.provided_bundle_count == 1
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "policy-waiver-evidence: 1 waiver(s), 1 referenced bundle(s), "
        "1 provided bundle(s), 0 blocker(s), 0 warning(s)"
    )


def test_policy_waiver_evidence_blocks_wrong_policy_pack_and_missing_rule() -> None:
    report = PolicyWaiverEvidenceValidator(_pack(), bundles=(_bundle(),)).validate(
        waivers=(
            _waiver(
                policy_pack_id="wrong-pack",
                covered_rule_ids=("missing-rule",),
            ),
        )
    )

    assert not report.is_coverage_ready()
    assert report.blocker_count == 2
    assert {finding.reference_type for finding in report.findings} == {
        PolicyWaiverReferenceType.POLICY_PACK,
        PolicyWaiverReferenceType.POLICY_RULE,
    }


def test_policy_waiver_evidence_blocks_missing_evidence_bundle() -> None:
    report = PolicyWaiverEvidenceValidator(_pack(), bundles=()).validate(waivers=(_waiver(),))

    assert report.blocker_count == 1
    assert report.findings[0].finding_id == (
        "waiver-waiver-export-001-missing-evidence-ev-waiver-export-001"
    )
    assert report.findings[0].reference_type is PolicyWaiverReferenceType.EVIDENCE_BUNDLE


def test_policy_waiver_evidence_blocks_invalid_evidence_bundle_status() -> None:
    report = PolicyWaiverEvidenceValidator(
        _pack(),
        bundles=(_bundle(status=EvidenceStatus.INVALID),),
    ).validate(waivers=(_waiver(),))

    assert report.blocker_count == 1
    assert "is marked invalid" in report.findings[0].message


def test_policy_waiver_evidence_warns_on_unhashed_evidence_bundle() -> None:
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

    report = PolicyWaiverEvidenceValidator(_pack(), bundles=(unhashed_bundle,)).validate(
        waivers=(_waiver(),)
    )

    assert report.is_coverage_ready()
    assert report.warning_count == 2
    assert {finding.severity for finding in report.findings} == {
        PolicyWaiverEvidenceFindingSeverity.WARNING
    }


def test_policy_waiver_evidence_blocks_expired_waiver_when_as_of_time_is_supplied() -> None:
    report = PolicyWaiverEvidenceValidator(_pack(), bundles=(_bundle(),)).validate(
        waivers=(_waiver(expires_at_utc="2026-05-01T00:00:00Z"),),
        as_of_utc="2026-05-12T12:00:00Z",
    )

    assert report.blocker_count == 1
    assert report.findings[0].finding_id == "waiver-waiver-export-001-expired"
    assert report.findings[0].reference_type is PolicyWaiverReferenceType.WAIVER


def test_policy_waiver_evidence_rejects_duplicate_waivers_and_bundles() -> None:
    with pytest.raises(ContractValueError, match="duplicate waiver IDs"):
        PolicyWaiverEvidenceValidator(_pack(), bundles=(_bundle(),)).validate(
            waivers=(_waiver(), _waiver())
        )

    with pytest.raises(ContractValueError, match="Duplicate evidence bundle ID"):
        PolicyWaiverEvidenceValidator(_pack(), bundles=(_bundle(), _bundle()))


def test_policy_waiver_evidence_finding_requires_reference_pairing() -> None:
    with pytest.raises(ContractValueError, match="must pair reference ID and reference type"):
        PolicyWaiverEvidenceFinding(
            finding_id="bad-finding",
            severity=PolicyWaiverEvidenceFindingSeverity.BLOCKER,
            message="Bad finding.",
            waiver_id="waiver-export-001",
            reference_id="ev-waiver-export-001",
        )

    with pytest.raises(ContractValueError, match="blank reference ID"):
        PolicyWaiverEvidenceFinding(
            finding_id="bad-finding",
            severity=PolicyWaiverEvidenceFindingSeverity.BLOCKER,
            message="Bad finding.",
            waiver_id="waiver-export-001",
            reference_id="",
            reference_type=PolicyWaiverReferenceType.EVIDENCE_BUNDLE,
        )
