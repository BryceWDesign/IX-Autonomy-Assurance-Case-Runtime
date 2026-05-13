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
from ix_autonomy_assurance_case_runtime.claim_guardrails_readiness import (
    CLAIM_GUARDRAIL_CAPABILITY_ID,
    ClaimGuardrailLayerReadinessEvaluator,
    ClaimGuardrailReadinessDecision,
    ClaimGuardrailReadinessFinding,
    ClaimGuardrailReadinessFindingSeverity,
    ClaimGuardrailReadinessFindingSource,
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


def _evaluator(
    *,
    evidence_bundles: tuple[EvidenceBundle, ...] | None = None,
    known_capability_ids: tuple[str, ...] = ("assurance-dossier",),
    known_artifact_ids: tuple[str, ...] = ("artifact-readiness-rollup-001",),
    reviewer_ids: tuple[str, ...] = ("reviewer-001",),
) -> ClaimGuardrailLayerReadinessEvaluator:
    return ClaimGuardrailLayerReadinessEvaluator(
        evidence_bundles=(_bundle(),) if evidence_bundles is None else evidence_bundles,
        known_capability_ids=known_capability_ids,
        known_artifact_ids=known_artifact_ids,
        reviewer_ids=reviewer_ids,
    )


def test_claim_guardrail_readiness_completes_clean_claim_package() -> None:
    report = _evaluator().evaluate(_package())

    assert report.decision is ClaimGuardrailReadinessDecision.COMPLETE
    assert report.is_complete()
    assert report.completed_capability_ids() == (CLAIM_GUARDRAIL_CAPABILITY_ID,)
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "claim-guardrail-readiness: complete "
        "(2 claim(s), 1 evidence reference(s), 1 prohibited rule(s), "
        "1 evidence bundle(s), 0 blocker(s), 0 warning(s), "
        "capability=claim-guardrails)"
    )


def test_claim_guardrail_readiness_blocks_unreleased_review_status() -> None:
    report = _evaluator().evaluate(
        _package(
            review_status=ClaimReviewStatus.IN_REVIEW,
            audience=ClaimAudience.LOCAL_DEVELOPMENT,
        )
    )

    assert report.decision is ClaimGuardrailReadinessDecision.BLOCKED
    assert not report.is_complete()
    assert any(
        finding.finding_id == "package-claim-package-runtime-001-review-not-releaseable"
        for finding in report.findings_for_package("claim-package-runtime-001")
    )


def test_claim_guardrail_readiness_blocks_strict_audience_without_limitation_claim() -> None:
    report = _evaluator().evaluate(
        _package(
            claims=(_claim(),),
            review_status=ClaimReviewStatus.APPROVED,
            audience=ClaimAudience.FEDERAL_EVALUATION,
        )
    )

    assert report.decision is ClaimGuardrailReadinessDecision.BLOCKED
    assert any(
        finding.finding_id == "package-claim-package-runtime-001-missing-limitation-claim"
        for finding in report.findings_for_package("claim-package-runtime-001")
    )


def test_claim_guardrail_readiness_blocks_weak_claim() -> None:
    report = _evaluator().evaluate(
        _package(
            claims=(
                _claim(
                    claim_id="claim-weak-evidence-001",
                    evidence_strength=ClaimEvidenceStrength.DESCRIBED,
                ),
                _limitation_claim(),
            )
        )
    )

    assert report.decision is ClaimGuardrailReadinessDecision.BLOCKED
    assert report.findings_for_claim("claim-weak-evidence-001")


def test_claim_guardrail_readiness_blocks_prohibited_language() -> None:
    report = _evaluator().evaluate(
        _package(
            claims=(
                _claim(text="This runtime is certified for use."),
                _limitation_claim(),
            )
        )
    )

    assert report.decision is ClaimGuardrailReadinessDecision.BLOCKED
    assert report.findings_for_rule("rule-no-certified")[0].source is (
        ClaimGuardrailReadinessFindingSource.LANGUAGE
    )


def test_claim_guardrail_readiness_blocks_missing_evidence_reference() -> None:
    report = _evaluator().evaluate(
        _package(
            claims=(
                _claim(evidence_reference_ids=("claim-evidence-ref-missing",)),
                _limitation_claim(),
            )
        )
    )

    assert report.decision is ClaimGuardrailReadinessDecision.BLOCKED
    assert report.findings_for_evidence_reference("claim-evidence-ref-missing")


def test_claim_guardrail_readiness_blocks_missing_evidence_bundle() -> None:
    report = _evaluator(evidence_bundles=()).evaluate(_package())

    assert report.decision is ClaimGuardrailReadinessDecision.BLOCKED
    assert report.findings_for_evidence_bundle("ev-claim-001")


def test_claim_guardrail_readiness_limited_for_evidence_warnings() -> None:
    report = _evaluator(evidence_bundles=(_bundle(hashed=False),)).evaluate(_package())

    assert report.decision is ClaimGuardrailReadinessDecision.LIMITED
    assert report.warning_count == 2
    assert report.findings_for_evidence_bundle("ev-claim-001")


def test_claim_guardrail_readiness_blocks_unknown_reviewer() -> None:
    report = _evaluator(reviewer_ids=("reviewer-other",)).evaluate(_package())

    assert report.decision is ClaimGuardrailReadinessDecision.BLOCKED
    assert report.findings_for_reviewer("reviewer-001")


def test_claim_guardrail_readiness_blocks_weak_disclaimer() -> None:
    report = _evaluator().evaluate(_package(disclaimer="Ready for review."))

    assert report.decision is ClaimGuardrailReadinessDecision.BLOCKED
    assert any(
        finding.source is ClaimGuardrailReadinessFindingSource.DISCLAIMER
        for finding in report.findings
    )


def test_claim_guardrail_readiness_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        ClaimGuardrailReadinessFinding(
            finding_id="finding-claim-readiness-001",
            severity=ClaimGuardrailReadinessFindingSeverity.BLOCKER,
            source=ClaimGuardrailReadinessFindingSource.READINESS,
            message="",
        )

    with pytest.raises(ContractValueError, match="claim_id must not be blank"):
        ClaimGuardrailReadinessFinding(
            finding_id="finding-claim-readiness-001",
            severity=ClaimGuardrailReadinessFindingSeverity.BLOCKER,
            source=ClaimGuardrailReadinessFindingSource.CLAIM,
            message="Bad claim.",
            claim_id="",
        )
