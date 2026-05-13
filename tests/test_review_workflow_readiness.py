from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.authority import ReviewActor
from ix_autonomy_assurance_case_runtime.contracts import (
    ContractValueError,
    EvidenceStatus,
    ReviewDisposition,
)
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessDecision,
)
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
from ix_autonomy_assurance_case_runtime.review_workflow_readiness import (
    REVIEW_WORKFLOW_CAPABILITY_ID,
    ReviewWorkflowLayerReadinessEvaluator,
    ReviewWorkflowReadinessDecision,
    ReviewWorkflowReadinessFinding,
    ReviewWorkflowReadinessFindingSeverity,
    ReviewWorkflowReadinessFindingSource,
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
    )


def _signoff(
    *,
    actor_id: str = "reviewer-001",
    scope: ReviewAuthorityScope = ReviewAuthorityScope.ASSURANCE_CASE,
    disposition: ReviewDisposition = ReviewDisposition.APPROVED,
    evidence_bundle_ids: tuple[str, ...] = ("ev-review-signoff-001",),
) -> ReviewSignoffRecord:
    return ReviewSignoffRecord(
        signoff_id="signoff-reviewer-001",
        workflow_id="workflow-review-001",
        actor=_actor(actor_id),
        scope=scope,
        disposition=disposition,
        rationale="Evidence, campaign, monitoring, and provenance posture reviewed.",
        signed_at_utc="2026-05-12T13:00:00Z",
        evidence_bundle_ids=evidence_bundle_ids,
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
    findings: tuple[ReviewFinding, ...] | None = None,
    signoffs: tuple[ReviewSignoffRecord, ...] | None = None,
    dissents: tuple[ReviewDissentRecord, ...] = (),
    bindings: tuple[ReviewAuthorityBinding, ...] | None = None,
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


def test_review_workflow_readiness_completes_clean_workflow() -> None:
    report = ReviewWorkflowLayerReadinessEvaluator(
        evidence_bundles=_bundles(),
    ).evaluate(_workflow())

    assert report.decision is ReviewWorkflowReadinessDecision.COMPLETE
    assert report.is_complete()
    assert report.completed_capability_ids() == (REVIEW_WORKFLOW_CAPABILITY_ID,)
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "review-workflow-readiness: complete "
        "(1 finding(s), 1 signoff(s), 0 dissent(s), 3 evidence bundle(s), "
        "0 blocker(s), 0 warning(s), capability=review-workflow)"
    )


def test_review_workflow_readiness_feeds_prototype_claim_gate() -> None:
    report = ReviewWorkflowLayerReadinessEvaluator(
        evidence_bundles=_bundles(),
    ).evaluate(_workflow())

    prototype_report = report.prototype_readiness_report(
        PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE,
        existing_completed_capability_ids=(
            "registry-layer",
            "policy-pack-engine",
            "framework-crosswalks",
            "signed-provenance",
            "telemetry-adapters",
            "scenario-campaign-runner",
            "monitoring-incidents",
        ),
    )

    assert prototype_report.decision is PrototypeReadinessDecision.BLOCK
    assert REVIEW_WORKFLOW_CAPABILITY_ID in prototype_report.completed_capability_ids


def test_review_workflow_readiness_blocks_uncompleted_workflow() -> None:
    report = ReviewWorkflowLayerReadinessEvaluator(
        evidence_bundles=_bundles(),
    ).evaluate(_workflow(status=ReviewWorkflowStatus.IN_REVIEW))

    assert report.decision is ReviewWorkflowReadinessDecision.BLOCKED
    assert any(
        finding.finding_id == "workflow-workflow-review-001-not-acceptance-ready"
        for finding in report.findings_for_workflow("workflow-review-001")
    )


def test_review_workflow_readiness_blocks_missing_accepting_signoff() -> None:
    report = ReviewWorkflowLayerReadinessEvaluator(
        evidence_bundles=_bundles(),
    ).evaluate(_workflow(signoffs=()))

    assert report.decision is ReviewWorkflowReadinessDecision.BLOCKED
    assert any(
        finding.source is ReviewWorkflowReadinessFindingSource.SIGNOFF
        for finding in report.findings
    )


def test_review_workflow_readiness_blocks_unresolved_review_finding() -> None:
    report = ReviewWorkflowLayerReadinessEvaluator(
        evidence_bundles=_bundles(),
    ).evaluate(_workflow(findings=(_finding(status=ReviewFindingStatus.OPEN),)))

    assert report.decision is ReviewWorkflowReadinessDecision.BLOCKED
    assert any(
        finding.finding_id == "finding-finding-runtime-evidence-001-unresolved-blocker"
        for finding in report.findings_for_review_finding("finding-runtime-evidence-001")
    )


def test_review_workflow_readiness_blocks_blocking_dissent() -> None:
    report = ReviewWorkflowLayerReadinessEvaluator(
        evidence_bundles=_bundles(),
    ).evaluate(
        _workflow(
            dissents=(_dissent(severity=ReviewDissentSeverity.BLOCKING_OBJECTION),),
        )
    )

    assert report.decision is ReviewWorkflowReadinessDecision.BLOCKED
    assert any(
        finding.finding_id == "dissent-dissent-reviewer-001-blocking"
        for finding in report.findings_for_dissent("dissent-reviewer-001")
    )


def test_review_workflow_readiness_limited_for_evidence_warnings() -> None:
    report = ReviewWorkflowLayerReadinessEvaluator(
        evidence_bundles=_bundles(unhashed="ev-review-finding-001"),
    ).evaluate(_workflow())

    assert report.decision is ReviewWorkflowReadinessDecision.LIMITED
    assert report.warning_count == 2
    assert report.findings_for_evidence_bundle("ev-review-finding-001")


def test_review_workflow_readiness_blocks_validation_authority_findings() -> None:
    report = ReviewWorkflowLayerReadinessEvaluator(
        evidence_bundles=_bundles(),
    ).evaluate(
        _workflow(
            bindings=(_binding(scopes=(ReviewAuthorityScope.MONITORING,),),),
            signoffs=(_signoff(scope=ReviewAuthorityScope.ASSURANCE_CASE),),
        )
    )

    assert report.decision is ReviewWorkflowReadinessDecision.BLOCKED
    assert report.findings_for_actor("reviewer-001")


def test_review_workflow_readiness_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        ReviewWorkflowReadinessFinding(
            finding_id="finding-review-readiness-001",
            severity=ReviewWorkflowReadinessFindingSeverity.BLOCKER,
            source=ReviewWorkflowReadinessFindingSource.READINESS,
            message="",
        )

    with pytest.raises(ContractValueError, match="signoff_id must not be blank"):
        ReviewWorkflowReadinessFinding(
            finding_id="finding-review-readiness-001",
            severity=ReviewWorkflowReadinessFindingSeverity.BLOCKER,
            source=ReviewWorkflowReadinessFindingSource.SIGNOFF,
            message="Bad signoff.",
            signoff_id="",
        )
