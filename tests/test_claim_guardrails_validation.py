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
from ix_autonomy_assurance_case_runtime.claim_guardrails_validation import (
    ClaimGuardrailValidationFinding,
    ClaimGuardrailValidationFindingSeverity,
    ClaimGuardrailValidationFindingSource,
    ClaimGuardrailValidator,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, EvidenceStatus
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord


def _evidence_reference(
    *,
    reference_id: str = "claim-evidence-ref-001",
    evidence_bundle_id: str = "ev-claim-001",
    artifact_ids: tuple[str, ...] = ("artifact-readiness-rollup-001",),
    capability_ids: tuple[str, ...] = ("assurance-dossier",),
) -> ClaimEvidenceReference:
    return ClaimEvidenceReference(
        reference_id=reference_id,
        evidence_bundle_id=evidence_bundle_id,
        artifact_ids=artifact_ids,
        capability_ids=capability_ids,
    )


def _rule(
    *,
    rule_id: str = "rule-no-certified",
    phrase: str = "certified",
    blocks_release: bool = True,
    allowed_context_markers: tuple[str, ...] = ("not certified",),
) -> ClaimProhibitedPhraseRule:
    return ClaimProhibitedPhraseRule(
        rule_id=rule_id,
        phrase=phrase,
        rationale="Prototype language must not imply official certification.",
        blocks_release=blocks_release,
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
    related_capability_ids: tuple[str, ...] = ("assurance-dossier",),
    related_artifact_ids: tuple[str, ...] = ("artifact-readiness-rollup-001",),
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
        related_capability_ids=related_capability_ids,
        related_artifact_ids=related_artifact_ids,
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
    evidence_references: tuple[ClaimEvidenceReference, ...] | None = None,
    prohibited_phrase_rules: tuple[ClaimProhibitedPhraseRule, ...] | None = None,
    review_status: ClaimReviewStatus = ClaimReviewStatus.APPROVED_WITH_LIMITATIONS,
    audience: ClaimAudience = ClaimAudience.FEDERAL_EVALUATION,
    disclaimer: str | None = None,
) -> ClaimReleasePackage:
    return ClaimReleasePackage(
        package_id="claim-package-runtime-001",
        audience=audience,
        review_status=review_status,
        created_at_utc="2026-05-12T16:00:00Z",
        claims=claims if claims is not None else (_claim(), _limitation_claim()),
        evidence_references=(
            evidence_references if evidence_references is not None else (_evidence_reference(),)
        ),
        prohibited_phrase_rules=(
            prohibited_phrase_rules if prohibited_phrase_rules is not None else (_rule(),)
        ),
        release_notes=("Bounded prototype language only.",),
        disclaimer=disclaimer
        or (
            "Local prototype claim package only; not a certification, "
            "authority-to-operate decision, deployment approval, official endorsement, "
            "or agency acceptance."
        ),
    )


def _bundle(bundle_id: str = "ev-claim-001", *, hashed: bool = True) -> EvidenceBundle:
    bundle = EvidenceBundle(
        bundle_id=bundle_id,
        case_id="case-runtime-001",
        records=(
            EvidenceRecord(
                evidence_id=f"record-{bundle_id}",
                kind="claim-guardrail",
                source="unit-test",
                payload={"bundle_id": bundle_id},
                status=EvidenceStatus.ACCEPTED,
            ),
        ),
    )
    if hashed:
        return bundle.with_computed_hashes()
    return bundle


def _validator(
    *,
    evidence_bundles: tuple[EvidenceBundle, ...] | None = None,
    known_capability_ids: tuple[str, ...] = ("assurance-dossier",),
    known_artifact_ids: tuple[str, ...] = ("artifact-readiness-rollup-001",),
    reviewer_ids: tuple[str, ...] = ("reviewer-001",),
) -> ClaimGuardrailValidator:
    return ClaimGuardrailValidator(
        evidence_bundles=(_bundle(),) if evidence_bundles is None else evidence_bundles,
        known_capability_ids=known_capability_ids,
        known_artifact_ids=known_artifact_ids,
        reviewer_ids=reviewer_ids,
    )


def test_claim_guardrail_validator_accepts_grounded_claim_package() -> None:
    report = _validator().validate(_package())

    assert report.is_claim_release_ready()
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "claim-guardrail-validation: claim-package-runtime-001 "
        "(2 claim(s), 1 evidence reference(s), 1 prohibited rule(s), "
        "1 evidence bundle(s), 0 blocker(s), 0 warning(s))"
    )


def test_claim_guardrail_validator_blocks_unreleased_package_review_status() -> None:
    report = _validator().validate(
        _package(
            review_status=ClaimReviewStatus.IN_REVIEW,
            audience=ClaimAudience.LOCAL_DEVELOPMENT,
        )
    )

    assert not report.is_claim_release_ready()
    assert any(
        finding.finding_id == "package-claim-package-runtime-001-review-not-releaseable"
        for finding in report.findings
    )


def test_claim_guardrail_validator_blocks_strict_audience_without_limitation_claim() -> None:
    report = _validator().validate(
        _package(
            claims=(_claim(),),
            review_status=ClaimReviewStatus.APPROVED,
            audience=ClaimAudience.FEDERAL_EVALUATION,
        )
    )

    assert not report.is_claim_release_ready()
    assert any(
        finding.finding_id == "package-claim-package-runtime-001-missing-limitation-claim"
        for finding in report.findings
    )


def test_claim_guardrail_validator_blocks_weak_or_prohibited_claims() -> None:
    weak_claim = _claim(
        claim_id="claim-weak-evidence-001",
        evidence_strength=ClaimEvidenceStrength.DESCRIBED,
    )
    prohibited_claim = _claim(
        claim_id="claim-prohibited-001",
        risk_level=ClaimRiskLevel.PROHIBITED,
    )
    report = _validator().validate(
        _package(claims=(weak_claim, prohibited_claim, _limitation_claim()))
    )

    assert not report.is_claim_release_ready()
    assert report.findings_for_claim("claim-weak-evidence-001")
    assert report.findings_for_claim("claim-prohibited-001")


def test_claim_guardrail_validator_blocks_prohibited_language_outside_allowed_context() -> None:
    report = _validator().validate(
        _package(
            claims=(
                _claim(text="This runtime is certified for use."),
                _limitation_claim(),
            )
        )
    )

    assert not report.is_claim_release_ready()
    assert report.findings_for_rule("rule-no-certified")[0].source is (
        ClaimGuardrailValidationFindingSource.LANGUAGE
    )


def test_claim_guardrail_validator_blocks_missing_claim_evidence_reference() -> None:
    report = _validator().validate(
        _package(
            claims=(
                _claim(evidence_reference_ids=("claim-evidence-ref-missing",)),
                _limitation_claim(),
            )
        )
    )

    assert not report.is_claim_release_ready()
    assert report.findings_for_evidence_reference("claim-evidence-ref-missing")


def test_claim_guardrail_validator_blocks_unsupported_capability_and_artifact_links() -> None:
    report = _validator().validate(
        _package(
            evidence_references=(
                _evidence_reference(
                    artifact_ids=("artifact-other",),
                    capability_ids=("capability-other",),
                ),
            )
        )
    )

    assert not report.is_claim_release_ready()
    assert any(
        finding.capability_id == "assurance-dossier"
        for finding in report.findings_for_claim("claim-serious-prototype-001")
    )
    assert any(
        finding.artifact_id == "artifact-readiness-rollup-001"
        for finding in report.findings_for_claim("claim-serious-prototype-001")
    )


def test_claim_guardrail_validator_blocks_unknown_reviewer_capability_and_artifact() -> None:
    report = _validator(
        known_capability_ids=("other-capability",),
        known_artifact_ids=("other-artifact",),
        reviewer_ids=("reviewer-other",),
    ).validate(_package())

    assert not report.is_claim_release_ready()
    assert report.findings_for_reviewer("reviewer-001")
    assert any(finding.capability_id == "assurance-dossier" for finding in report.findings)
    assert any(
        finding.artifact_id == "artifact-readiness-rollup-001"
        for finding in report.findings
    )


def test_claim_guardrail_validator_blocks_missing_evidence_bundle() -> None:
    report = _validator(evidence_bundles=()).validate(_package())

    assert not report.is_claim_release_ready()
    assert report.findings_for_evidence_bundle("ev-claim-001")[0].source is (
        ClaimGuardrailValidationFindingSource.EVIDENCE
    )


def test_claim_guardrail_validator_warns_for_unhashed_evidence_bundle() -> None:
    report = _validator(evidence_bundles=(_bundle(hashed=False),)).validate(_package())

    assert report.is_claim_release_ready()
    assert report.warning_count == 2
    assert report.findings_for_evidence_bundle("ev-claim-001")


def test_claim_guardrail_validator_warns_for_unused_evidence_reference() -> None:
    report = _validator(
        evidence_bundles=(_bundle(), _bundle("ev-unused-claim-001")),
    ).validate(
        _package(
            evidence_references=(
                _evidence_reference(),
                _evidence_reference(
                    reference_id="claim-evidence-ref-unused",
                    evidence_bundle_id="ev-unused-claim-001",
                ),
            )
        )
    )

    assert report.is_claim_release_ready()
    assert report.warning_count == 1
    assert report.findings_for_evidence_reference("claim-evidence-ref-unused")


def test_claim_guardrail_validator_blocks_weak_disclaimer() -> None:
    report = _validator().validate(_package(disclaimer="Ready for review."))

    assert not report.is_claim_release_ready()
    assert any(
        finding.source is ClaimGuardrailValidationFindingSource.DISCLAIMER
        for finding in report.findings
    )


def test_claim_guardrail_validator_rejects_duplicate_inputs() -> None:
    bundle = _bundle()

    with pytest.raises(ContractValueError, match="Duplicate claim guardrail evidence"):
        ClaimGuardrailValidator(evidence_bundles=(bundle, bundle))

    with pytest.raises(ContractValueError, match="known_capability_ids"):
        ClaimGuardrailValidator(known_capability_ids=("capability-001", "capability-001"))

    with pytest.raises(ContractValueError, match="reviewer_ids"):
        ClaimGuardrailValidator(reviewer_ids=("reviewer-001", "reviewer-001"))


def test_claim_guardrail_validation_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        ClaimGuardrailValidationFinding(
            finding_id="finding-claim-validation-001",
            severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
            source=ClaimGuardrailValidationFindingSource.CLAIM,
            message="",
        )

    with pytest.raises(ContractValueError, match="claim_id must not be blank"):
        ClaimGuardrailValidationFinding(
            finding_id="finding-claim-validation-001",
            severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
            source=ClaimGuardrailValidationFindingSource.CLAIM,
            message="Bad claim.",
            claim_id="",
        )
