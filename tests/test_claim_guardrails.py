from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.claim_guardrails import (
    ClaimAudience,
    ClaimEvidenceReference,
    ClaimEvidenceStrength,
    ClaimProhibitedPhraseRule,
    ClaimReleasePackage,
    ClaimReviewStatus,
    ClaimRiskLevel,
    ClaimStatementType,
    EvidenceBackedClaim,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError


def _evidence_reference(
    *,
    reference_id: str = "claim-evidence-ref-001",
    evidence_bundle_id: str = "ev-claim-001",
) -> ClaimEvidenceReference:
    return ClaimEvidenceReference(
        reference_id=reference_id,
        evidence_bundle_id=evidence_bundle_id,
        artifact_ids=("artifact-readiness-rollup-001",),
        capability_ids=("assurance-dossier",),
    )


def _rule(
    *,
    rule_id: str = "rule-no-certified",
    phrase: str = "certified",
    allowed_context_markers: tuple[str, ...] = ("not certified",),
) -> ClaimProhibitedPhraseRule:
    return ClaimProhibitedPhraseRule(
        rule_id=rule_id,
        phrase=phrase,
        rationale="Prototype language must not imply official certification.",
        allowed_context_markers=allowed_context_markers,
    )


def _claim(
    *,
    claim_id: str = "claim-serious-prototype-001",
    statement_type: ClaimStatementType = ClaimStatementType.MATURITY,
    risk_level: ClaimRiskLevel = ClaimRiskLevel.MODERATE,
    evidence_strength: ClaimEvidenceStrength = ClaimEvidenceStrength.TRACE_CLOSED,
    review_status: ClaimReviewStatus = ClaimReviewStatus.APPROVED_WITH_LIMITATIONS,
    text: str = "The project is a serious open-source prototype with trace-closed evidence.",
    evidence_reference_ids: tuple[str, ...] = ("claim-evidence-ref-001",),
    limitation_text: str | None = "Prototype maturity is not deployment approval.",
    reviewer_ids: tuple[str, ...] = ("reviewer-001",),
) -> EvidenceBackedClaim:
    return EvidenceBackedClaim(
        claim_id=claim_id,
        statement_type=statement_type,
        risk_level=risk_level,
        evidence_strength=evidence_strength,
        review_status=review_status,
        text=text,
        evidence_reference_ids=evidence_reference_ids,
        limitation_text=limitation_text,
        reviewer_ids=reviewer_ids,
        related_capability_ids=("assurance-dossier",),
        related_artifact_ids=("artifact-readiness-rollup-001",),
    )


def _limitation_claim() -> EvidenceBackedClaim:
    return EvidenceBackedClaim(
        claim_id="claim-non-endorsement-001",
        statement_type=ClaimStatementType.NON_ENDORSEMENT,
        risk_level=ClaimRiskLevel.LOW,
        evidence_strength=ClaimEvidenceStrength.NONE,
        review_status=ClaimReviewStatus.APPROVED,
        text=(
            "This package is not certified, not an authority-to-operate decision, "
            "and not agency acceptance."
        ),
        evidence_reference_ids=(),
    )


def _package(
    *,
    claims: tuple[EvidenceBackedClaim, ...] | None = None,
    review_status: ClaimReviewStatus = ClaimReviewStatus.APPROVED_WITH_LIMITATIONS,
    audience: ClaimAudience = ClaimAudience.FEDERAL_EVALUATION,
) -> ClaimReleasePackage:
    return ClaimReleasePackage(
        package_id="claim-package-runtime-001",
        audience=audience,
        review_status=review_status,
        created_at_utc="2026-05-12T16:00:00Z",
        claims=claims if claims is not None else (_claim(), _limitation_claim()),
        evidence_references=(_evidence_reference(),),
        prohibited_phrase_rules=(_rule(),),
        release_notes=("Bounded prototype language only.",),
    )


def test_claim_release_package_tracks_releasable_claims_and_evidence() -> None:
    package = _package()

    assert package.can_release()
    assert package.claim_ids() == (
        "claim-serious-prototype-001",
        "claim-non-endorsement-001",
    )
    assert package.releasable_claim_ids() == (
        "claim-serious-prototype-001",
        "claim-non-endorsement-001",
    )
    assert package.blocked_claim_ids() == ()
    assert package.limitation_claim_ids() == ("claim-non-endorsement-001",)
    assert package.required_evidence_reference_ids() == ("claim-evidence-ref-001",)
    assert package.required_evidence_bundle_ids() == ("ev-claim-001",)


def test_prohibited_phrase_rule_allows_explicit_non_claim_context() -> None:
    package = _package()

    assert package.prohibited_rule_ids_for_text("This repo is certified.") == (
        "rule-no-certified",
    )
    assert package.prohibited_rule_ids_for_text("This repo is not certified.") == ()


def test_claim_requires_evidence_for_capability_or_maturity_statements() -> None:
    with pytest.raises(ContractValueError, match="evidence_reference_ids"):
        _claim(evidence_reference_ids=())


def test_claim_requires_reviewer_for_moderate_or_high_risk() -> None:
    with pytest.raises(ContractValueError, match="reviewer_ids"):
        _claim(reviewer_ids=())


def test_claim_requires_limitation_text_when_approved_with_limitations() -> None:
    with pytest.raises(ContractValueError, match="limitation_text"):
        _claim(limitation_text=None)


def test_claim_blocks_release_for_weak_evidence_or_prohibited_risk() -> None:
    weak = _claim(
        claim_id="claim-weak-evidence-001",
        evidence_strength=ClaimEvidenceStrength.DESCRIBED,
    )
    prohibited = _claim(
        claim_id="claim-prohibited-001",
        risk_level=ClaimRiskLevel.PROHIBITED,
    )

    assert not weak.can_be_released()
    assert prohibited.risk_level.blocks_release()
    assert not prohibited.can_be_released()


def test_non_endorsement_claim_can_release_without_evidence_references() -> None:
    claim = _limitation_claim()

    assert claim.is_limitation_claim()
    assert claim.can_be_released()


def test_claim_release_package_requires_limitation_claims_for_strict_audiences() -> None:
    strict_package = _package(claims=(_claim(),))
    local_package = _package(
        claims=(_claim(),),
        review_status=ClaimReviewStatus.APPROVED_WITH_LIMITATIONS,
        audience=ClaimAudience.LOCAL_DEVELOPMENT,
    )

    assert not strict_package.can_release()
    assert local_package.can_release()


def test_claim_release_package_blocks_unreviewed_claims() -> None:
    package = _package(
        claims=(
            _claim(review_status=ClaimReviewStatus.DRAFT),
            _limitation_claim(),
        ),
        review_status=ClaimReviewStatus.APPROVED,
    )

    assert not package.can_release()
    assert package.blocked_claim_ids() == ("claim-serious-prototype-001",)


def test_claim_release_package_rejects_duplicate_record_ids() -> None:
    claim = _claim()
    reference = _evidence_reference()
    rule = _rule()

    with pytest.raises(ContractValueError, match="claim IDs"):
        _package(claims=(claim, claim))

    with pytest.raises(ContractValueError, match="claim evidence reference IDs"):
        ClaimReleasePackage(
            package_id="claim-package-runtime-001",
            audience=ClaimAudience.LOCAL_DEVELOPMENT,
            review_status=ClaimReviewStatus.APPROVED,
            created_at_utc="2026-05-12T16:00:00Z",
            claims=(_claim(), _limitation_claim()),
            evidence_references=(reference, reference),
            prohibited_phrase_rules=(rule,),
        )

    with pytest.raises(ContractValueError, match="prohibited phrase rule IDs"):
        ClaimReleasePackage(
            package_id="claim-package-runtime-001",
            audience=ClaimAudience.LOCAL_DEVELOPMENT,
            review_status=ClaimReviewStatus.APPROVED,
            created_at_utc="2026-05-12T16:00:00Z",
            claims=(_claim(), _limitation_claim()),
            evidence_references=(reference,),
            prohibited_phrase_rules=(rule, rule),
        )


def test_claim_release_package_validates_identifiers_and_timestamps() -> None:
    with pytest.raises(ContractValueError, match="package_id must not contain spaces"):
        ClaimReleasePackage(
            package_id="claim package",
            audience=ClaimAudience.LOCAL_DEVELOPMENT,
            review_status=ClaimReviewStatus.APPROVED,
            created_at_utc="2026-05-12T16:00:00Z",
            claims=(_claim(), _limitation_claim()),
            evidence_references=(_evidence_reference(),),
            prohibited_phrase_rules=(_rule(),),
        )

    with pytest.raises(ContractValueError, match="must include a timezone"):
        ClaimReleasePackage(
            package_id="claim-package-runtime-001",
            audience=ClaimAudience.LOCAL_DEVELOPMENT,
            review_status=ClaimReviewStatus.APPROVED,
            created_at_utc="2026-05-12T16:00:00",
            claims=(_claim(), _limitation_claim()),
            evidence_references=(_evidence_reference(),),
            prohibited_phrase_rules=(_rule(),),
        )
