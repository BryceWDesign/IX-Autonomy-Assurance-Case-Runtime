from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.authority import ReviewActor
from ix_autonomy_assurance_case_runtime.contracts import (
    ContractValueError,
    EvidenceStatus,
    ReviewDisposition,
)
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
from ix_autonomy_assurance_case_runtime.review_workflow import (
    ReviewAuthorityBinding,
    ReviewAuthorityScope,
    ReviewDissentRecord,
    ReviewDissentSeverity,
    ReviewFinding,
    ReviewFindingSeverity,
    ReviewFindingStatus,
    ReviewSignoffRecord,
    ReviewWorkflowRecord,
    ReviewWorkflowStatus,
)
from ix_autonomy_assurance_case_runtime.review_workflow_validation import (
    ReviewWorkflowValidationFinding,
    ReviewWorkflowValidationFindingSeverity,
    ReviewWorkflowValidationFindingSource,
    ReviewWorkflowValidator,
)


def _actor(actor_id: str = "reviewer-001") -> ReviewActor:
    return ReviewActor(
        actor_id=actor_id,
        role="assurance-reviewer",
        display_name="Assurance Reviewer",
    )


def _binding(
    *,
    actor_id: str = "reviewer-001",
    scopes: tuple[ReviewAuthorityScope, ...] = (
        ReviewAuthorityScope.ASSURANCE_CASE,
        ReviewAuthorityScope.SCENARIO_CAMPAIGN,
        ReviewAuthorityScope.MONITORING,
    ),
    can_sign: bool = True,
    can_waive: bool = True,
    can_record_dissent: bool = True,
) -> ReviewAuthorityBinding:
    return ReviewAuthorityBinding(
        binding_id=f"binding-{actor_id}",
        actor=_actor(actor_id),
        authority_scopes=scopes,
        can_sign=can_sign,
        can_waive=can_waive,
        can_record_dissent=can_record_dissent,
    )


def _finding(
    *,
    finding_id: str = "finding-runtime-evidence-001",
    status: ReviewFindingStatus = ReviewFindingStatus.CLOSED,
    severity: ReviewFindingSeverity = ReviewFindingSeverity.HIGH,
    opened_by_actor_id: str = "reviewer-001",
    scope: ReviewAuthorityScope = ReviewAuthorityScope.SCENARIO_CAMPAIGN,
    waiver_id: str | None = None,
) -> ReviewFinding:
    return ReviewFinding(
        finding_id=finding_id,
        scope=scope,
        severity=severity,
        status=status,
        title="Runtime evidence reviewed",
        rationale="Campaign evidence supports the bounded runtime behavior claim.",
        opened_by_actor_id=opened_by_actor_id,
        opened_at_utc="2026-05-12T12:00:00Z",
        requirement_ids=("req-runtime-boundary",),
        hazard_ids=("hazard-runtime-boundary",),
        evidence_bundle_ids=("ev-review-finding-001",),
        source_record_ids=("campaign-run-001",),
        waiver_id=waiver_id,
    )


def _signoff(
    *,
    signoff_id: str = "signoff-reviewer-001",
    actor_id: str = "reviewer-001",
    scope: ReviewAuthorityScope = ReviewAuthorityScope.ASSURANCE_CASE,
    disposition: ReviewDisposition = ReviewDisposition.APPROVED,
    condition_ids: tuple[str, ...] = (),
) -> ReviewSignoffRecord:
    return ReviewSignoffRecord(
        signoff_id=signoff_id,
        workflow_id="workflow-review-001",
        actor=_actor(actor_id),
        scope=scope,
        disposition=disposition,
        rationale="Evidence, campaign, monitoring, and provenance posture reviewed.",
        signed_at_utc="2026-05-12T13:00:00Z",
        evidence_bundle_ids=("ev-review-signoff-001",),
        condition_ids=condition_ids,
    )


def _dissent(
    *,
    actor_id: str = "reviewer-002",
    severity: ReviewDissentSeverity = ReviewDissentSeverity.CONCERN,
    related_finding_ids: tuple[str, ...] = ("finding-runtime-evidence-001",),
) -> ReviewDissentRecord:
    return ReviewDissentRecord(
        dissent_id="dissent-reviewer-001",
        workflow_id="workflow-review-001",
        actor=_actor(actor_id),
        scope=ReviewAuthorityScope.MONITORING,
        severity=severity,
        rationale="Monitoring confidence should be reviewed again before wider claims.",
        recorded_at_utc="2026-05-12T13:10:00Z",
        evidence_bundle_ids=("ev-review-dissent-001",),
        related_finding_ids=related_finding_ids,
    )


def _workflow(
    *,
    status: ReviewWorkflowStatus = ReviewWorkflowStatus.COMPLETED,
    bindings: tuple[ReviewAuthorityBinding, ...] | None = None,
    findings: tuple[ReviewFinding, ...] | None = None,
    signoffs: tuple[ReviewSignoffRecord, ...] | None = None,
    dissents: tuple[ReviewDissentRecord, ...] = (),
) -> ReviewWorkflowRecord:
    return ReviewWorkflowRecord(
        workflow_id="workflow-review-001",
        case_id="case-runtime-001",
        title="Runtime assurance review",
        status=status,
        authority_bindings=(
            bindings
            if bindings is not None
            else (_binding(), _binding(actor_id="reviewer-002"))
        ),
        findings=findings if findings is not None else (_finding(),),
        signoffs=signoffs if signoffs is not None else (_signoff(),),
        dissents=dissents,
        evidence_bundle_ids=("ev-review-workflow-001",),
        system_id="system-runtime-001",
        deployment_id="deploy-runtime-001",
    )


def _bundle(bundle_id: str, *, hashed: bool = True) -> EvidenceBundle:
    bundle = EvidenceBundle(
        bundle_id=bundle_id,
        case_id="case-runtime-001",
        records=(
            EvidenceRecord(
                evidence_id=f"record-{bundle_id}",
                kind="review-workflow",
                source="unit-test",
                payload={"bundle_id": bundle_id},
                status=EvidenceStatus.ACCEPTED,
            ),
        ),
    )
    if hashed:
        return bundle.with_computed_hashes()
    return bundle


def _bundles(*, unhashed: str | None = None) -> tuple[EvidenceBundle, ...]:
    bundle_ids = (
        "ev-review-workflow-001",
        "ev-review-finding-001",
        "ev-review-signoff-001",
        "ev-review-dissent-001",
    )
    return tuple(_bundle(bundle_id, hashed=bundle_id != unhashed) for bundle_id in bundle_ids)


def test_review_workflow_validator_accepts_grounded_workflow() -> None:
    report = ReviewWorkflowValidator(evidence_bundles=_bundles()).validate(_workflow())

    assert report.is_review_ready()
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "review-workflow-validation: workflow-review-001 "
        "(1 finding(s), 1 signoff(s), 0 dissent(s), 3 evidence bundle(s), "
        "0 blocker(s), 0 warning(s))"
    )


def test_review_workflow_validator_blocks_uncompleted_workflow_and_missing_signoff() -> None:
    report = ReviewWorkflowValidator(evidence_bundles=_bundles()).validate(
        _workflow(status=ReviewWorkflowStatus.IN_REVIEW, signoffs=())
    )

    assert not report.is_review_ready()
    assert {finding.finding_id for finding in report.findings} >= {
        "workflow-workflow-review-001-not-completed",
        "workflow-workflow-review-001-no-accepting-signoff",
    }


def test_review_workflow_validator_blocks_unbound_finding_actor() -> None:
    report = ReviewWorkflowValidator(evidence_bundles=_bundles()).validate(
        _workflow(findings=(_finding(opened_by_actor_id="reviewer-missing"),))
    )

    assert not report.is_review_ready()
    actor_findings = report.findings_for_actor("reviewer-missing")
    assert {finding.finding_id for finding in actor_findings} == {
        "finding-finding-runtime-evidence-001-actor-not-bound",
        "finding-finding-runtime-evidence-001-actor-scope-missing",
    }


def test_review_workflow_validator_blocks_unresolved_review_finding() -> None:
    report = ReviewWorkflowValidator(evidence_bundles=_bundles()).validate(
        _workflow(findings=(_finding(status=ReviewFindingStatus.OPEN),))
    )

    assert not report.is_review_ready()
    assert report.findings_for_review_finding("finding-runtime-evidence-001")[0].source is (
        ReviewWorkflowValidationFindingSource.FINDING
    )


def test_review_workflow_validator_blocks_waiver_without_waiver_authority() -> None:
    report = ReviewWorkflowValidator(evidence_bundles=_bundles()).validate(
        _workflow(
            bindings=(_binding(can_waive=False),),
            findings=(
                _finding(status=ReviewFindingStatus.WAIVED, waiver_id="waiver-review-001"),
            ),
        )
    )

    assert not report.is_review_ready()
    assert any(
        finding.finding_id == "finding-finding-runtime-evidence-001-waiver-without-authority"
        for finding in report.findings_for_review_finding("finding-runtime-evidence-001")
    )


def test_review_workflow_validator_blocks_signoff_without_scope_or_signing_authority() -> None:
    report = ReviewWorkflowValidator(evidence_bundles=_bundles()).validate(
        _workflow(
            bindings=(_binding(scopes=(ReviewAuthorityScope.MONITORING,), can_sign=False),),
            signoffs=(_signoff(scope=ReviewAuthorityScope.ASSURANCE_CASE),),
        )
    )

    assert not report.is_review_ready()
    assert report.findings_for_signoff("signoff-reviewer-001")[0].finding_id == (
        "signoff-signoff-reviewer-001-actor-cannot-sign"
    )


def test_review_workflow_validator_blocks_missing_condition_finding_reference() -> None:
    report = ReviewWorkflowValidator(evidence_bundles=_bundles()).validate(
        _workflow(
            signoffs=(
                _signoff(
                    disposition=ReviewDisposition.APPROVED_WITH_CONDITIONS,
                    condition_ids=("finding-missing",),
                ),
            )
        )
    )

    assert not report.is_review_ready()
    assert any(
        finding.review_finding_id == "finding-missing"
        for finding in report.findings_for_signoff("signoff-reviewer-001")
    )


def test_review_workflow_validator_blocks_dissent_without_scope_or_finding_link() -> None:
    report = ReviewWorkflowValidator(evidence_bundles=_bundles()).validate(
        _workflow(
            bindings=(_binding(actor_id="reviewer-002", scopes=(ReviewAuthorityScope.POLICY,)),),
            dissents=(_dissent(related_finding_ids=("finding-missing",)),),
        )
    )

    assert not report.is_review_ready()
    dissent_findings = report.findings_for_dissent("dissent-reviewer-001")
    assert {finding.finding_id for finding in dissent_findings} == {
        "dissent-dissent-reviewer-001-actor-cannot-dissent",
        "dissent-dissent-reviewer-001-finding-finding-missing-missing",
    }


def test_review_workflow_validator_blocks_blocking_dissent() -> None:
    report = ReviewWorkflowValidator(evidence_bundles=_bundles()).validate(
        _workflow(dissents=(_dissent(severity=ReviewDissentSeverity.BLOCKING_OBJECTION),))
    )

    assert not report.is_review_ready()
    assert any(
        finding.finding_id == "dissent-dissent-reviewer-001-blocks-acceptance"
        for finding in report.findings_for_dissent("dissent-reviewer-001")
    )


def test_review_workflow_validator_blocks_missing_evidence_bundle() -> None:
    report = ReviewWorkflowValidator(evidence_bundles=()).validate(_workflow())

    assert not report.is_review_ready()
    assert report.findings_for_evidence_bundle("ev-review-workflow-001")[0].source is (
        ReviewWorkflowValidationFindingSource.EVIDENCE
    )


def test_review_workflow_validator_warns_for_unhashed_evidence() -> None:
    report = ReviewWorkflowValidator(
        evidence_bundles=_bundles(unhashed="ev-review-finding-001")
    ).validate(_workflow())

    assert report.is_review_ready()
    assert report.warning_count == 2
    assert report.findings_for_evidence_bundle("ev-review-finding-001")


def test_review_workflow_validator_rejects_duplicate_evidence_bundles() -> None:
    with pytest.raises(ContractValueError, match="Duplicate review workflow evidence"):
        ReviewWorkflowValidator(
            evidence_bundles=(
                _bundle("ev-review-workflow-001"),
                _bundle("ev-review-workflow-001"),
            )
        )


def test_review_workflow_validation_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        ReviewWorkflowValidationFinding(
            finding_id="finding-review-validation-001",
            severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
            source=ReviewWorkflowValidationFindingSource.WORKFLOW,
            message="",
        )

    with pytest.raises(ContractValueError, match="signoff_id must not be blank"):
        ReviewWorkflowValidationFinding(
            finding_id="finding-review-validation-001",
            severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
            source=ReviewWorkflowValidationFindingSource.SIGNOFF,
            message="Bad signoff.",
            signoff_id="",
        )
