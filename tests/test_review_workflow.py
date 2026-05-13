from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.authority import ReviewActor
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, ReviewDisposition
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


def _actor(actor_id: str = "reviewer-001") -> ReviewActor:
    return ReviewActor(
        actor_id=actor_id,
        role="assurance-reviewer",
        display_name="Assurance Reviewer",
    )


def _binding() -> ReviewAuthorityBinding:
    return ReviewAuthorityBinding(
        binding_id="binding-reviewer-001",
        actor=_actor(),
        authority_scopes=(
            ReviewAuthorityScope.ASSURANCE_CASE,
            ReviewAuthorityScope.SCENARIO_CAMPAIGN,
        ),
        can_sign=True,
        can_waive=True,
    )


def _finding(
    *,
    status: ReviewFindingStatus = ReviewFindingStatus.CLOSED,
    severity: ReviewFindingSeverity = ReviewFindingSeverity.HIGH,
    waiver_id: str | None = None,
) -> ReviewFinding:
    return ReviewFinding(
        finding_id="finding-runtime-evidence-001",
        scope=ReviewAuthorityScope.SCENARIO_CAMPAIGN,
        severity=severity,
        status=status,
        title="Runtime evidence reviewed",
        rationale="Campaign evidence supports the bounded runtime behavior claim.",
        opened_by_actor_id="reviewer-001",
        opened_at_utc="2026-05-12T12:00:00Z",
        requirement_ids=("req-runtime-boundary",),
        hazard_ids=("hazard-runtime-boundary",),
        evidence_bundle_ids=("ev-review-finding-001",),
        source_record_ids=("campaign-run-001",),
        waiver_id=waiver_id,
    )


def _signoff(
    *,
    disposition: ReviewDisposition = ReviewDisposition.APPROVED,
    condition_ids: tuple[str, ...] = (),
) -> ReviewSignoffRecord:
    return ReviewSignoffRecord(
        signoff_id="signoff-reviewer-001",
        workflow_id="workflow-review-001",
        actor=_actor(),
        scope=ReviewAuthorityScope.ASSURANCE_CASE,
        disposition=disposition,
        rationale="Evidence, campaign, monitoring, and provenance posture reviewed.",
        signed_at_utc="2026-05-12T13:00:00Z",
        evidence_bundle_ids=("ev-review-signoff-001",),
        condition_ids=condition_ids,
    )


def _dissent(
    *,
    severity: ReviewDissentSeverity = ReviewDissentSeverity.CONCERN,
) -> ReviewDissentRecord:
    return ReviewDissentRecord(
        dissent_id="dissent-reviewer-001",
        workflow_id="workflow-review-001",
        actor=_actor("reviewer-002"),
        scope=ReviewAuthorityScope.MONITORING,
        severity=severity,
        rationale="Monitoring confidence should be reviewed again before wider claims.",
        recorded_at_utc="2026-05-12T13:10:00Z",
        evidence_bundle_ids=("ev-review-dissent-001",),
        related_finding_ids=("finding-runtime-evidence-001",),
    )


def _workflow(
    *,
    status: ReviewWorkflowStatus = ReviewWorkflowStatus.COMPLETED,
    finding: ReviewFinding | None = None,
    signoff: ReviewSignoffRecord | None = None,
    dissents: tuple[ReviewDissentRecord, ...] = (),
) -> ReviewWorkflowRecord:
    return ReviewWorkflowRecord(
        workflow_id="workflow-review-001",
        case_id="case-runtime-001",
        title="Runtime assurance review",
        status=status,
        authority_bindings=(_binding(),),
        findings=(finding if finding is not None else _finding(),),
        signoffs=(signoff if signoff is not None else _signoff(),),
        dissents=dissents,
        evidence_bundle_ids=("ev-review-workflow-001",),
        system_id="system-runtime-001",
        deployment_id="deploy-runtime-001",
    )


def test_review_workflow_records_acceptance_ready_signoff_state() -> None:
    workflow = _workflow()

    assert workflow.can_support_acceptance()
    assert workflow.unresolved_finding_ids() == ()
    assert workflow.accepted_signoff_ids() == ("signoff-reviewer-001",)
    assert workflow.required_evidence_bundle_ids() == (
        "ev-review-workflow-001",
        "ev-review-finding-001",
        "ev-review-signoff-001",
    )


def test_review_workflow_blocks_unresolved_medium_or_higher_findings() -> None:
    workflow = _workflow(finding=_finding(status=ReviewFindingStatus.OPEN))

    assert not workflow.can_support_acceptance()
    assert workflow.unresolved_finding_ids() == ("finding-runtime-evidence-001",)


def test_review_workflow_records_blocking_dissent() -> None:
    workflow = _workflow(dissents=(_dissent(severity=ReviewDissentSeverity.BLOCKING_OBJECTION),))

    assert not workflow.can_support_acceptance()
    assert workflow.blocking_dissent_ids() == ("dissent-reviewer-001",)
    assert workflow.dissent_ids() == ("dissent-reviewer-001",)


def test_review_finding_requires_evidence_for_medium_or_higher_severity() -> None:
    with pytest.raises(ContractValueError, match="medium, high, or critical findings"):
        ReviewFinding(
            finding_id="finding-missing-evidence",
            scope=ReviewAuthorityScope.POLICY,
            severity=ReviewFindingSeverity.MEDIUM,
            status=ReviewFindingStatus.OPEN,
            title="Policy evidence missing",
            rationale="The reviewer needs policy evidence.",
            opened_by_actor_id="reviewer-001",
            opened_at_utc="2026-05-12T12:00:00Z",
        )


def test_critical_review_finding_requires_hazard_links() -> None:
    with pytest.raises(ContractValueError, match="critical review findings"):
        _finding(severity=ReviewFindingSeverity.CRITICAL).__class__(
            finding_id="finding-critical-no-hazard",
            scope=ReviewAuthorityScope.SAFETY_GATE,
            severity=ReviewFindingSeverity.CRITICAL,
            status=ReviewFindingStatus.OPEN,
            title="Critical finding without hazard",
            rationale="Critical review finding lacks hazard trace.",
            opened_by_actor_id="reviewer-001",
            opened_at_utc="2026-05-12T12:00:00Z",
            evidence_bundle_ids=("ev-review-finding-002",),
        )


def test_waived_finding_requires_explicit_waiver_id() -> None:
    with pytest.raises(ContractValueError, match="waived review findings require waiver_id"):
        _finding(status=ReviewFindingStatus.WAIVED, waiver_id=None)

    waived = _finding(status=ReviewFindingStatus.WAIVED, waiver_id="waiver-review-001")

    assert waived.status.requires_waiver_reference()
    assert waived.waiver_id == "waiver-review-001"


def test_signoff_enforces_acceptance_evidence_and_conditions() -> None:
    with pytest.raises(ContractValueError, match="accepting review signoffs"):
        ReviewSignoffRecord(
            signoff_id="signoff-no-evidence",
            workflow_id="workflow-review-001",
            actor=_actor(),
            scope=ReviewAuthorityScope.ASSURANCE_CASE,
            disposition=ReviewDisposition.APPROVED,
            rationale="No evidence attached.",
            signed_at_utc="2026-05-12T13:00:00Z",
        )

    with pytest.raises(ContractValueError, match="approved_with_conditions"):
        _signoff(disposition=ReviewDisposition.APPROVED_WITH_CONDITIONS)

    conditional = _signoff(
        disposition=ReviewDisposition.APPROVED_WITH_CONDITIONS,
        condition_ids=("condition-review-001",),
    )

    assert conditional.supports_acceptance()


def test_dissent_preserves_blocking_objection_traceability() -> None:
    with pytest.raises(ContractValueError, match="blocking dissent requires"):
        ReviewDissentRecord(
            dissent_id="dissent-blocking-no-finding",
            workflow_id="workflow-review-001",
            actor=_actor("reviewer-002"),
            scope=ReviewAuthorityScope.MONITORING,
            severity=ReviewDissentSeverity.BLOCKING_OBJECTION,
            rationale="Blocking objection without linked finding.",
            recorded_at_utc="2026-05-12T13:10:00Z",
        )


def test_review_workflow_rejects_duplicate_and_mismatched_records() -> None:
    finding = _finding()

    with pytest.raises(ContractValueError, match="review finding IDs"):
        _workflow(finding=finding).__class__(
            workflow_id="workflow-review-001",
            case_id="case-runtime-001",
            title="Runtime assurance review",
            status=ReviewWorkflowStatus.COMPLETED,
            authority_bindings=(_binding(),),
            findings=(finding, finding),
            signoffs=(_signoff(),),
        )

    bad_signoff = ReviewSignoffRecord(
        signoff_id="signoff-other-workflow",
        workflow_id="workflow-other",
        actor=_actor(),
        scope=ReviewAuthorityScope.ASSURANCE_CASE,
        disposition=ReviewDisposition.APPROVED,
        rationale="Wrong workflow.",
        signed_at_utc="2026-05-12T13:00:00Z",
        evidence_bundle_ids=("ev-review-signoff-002",),
    )

    with pytest.raises(ContractValueError, match="signoff workflow_id"):
        _workflow(signoff=bad_signoff)
