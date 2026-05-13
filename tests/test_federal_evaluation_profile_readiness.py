from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, EvidenceStatus
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
from ix_autonomy_assurance_case_runtime.federal_evaluation_profile import (
    EvaluationAlignmentStatus,
    EvaluationEvidenceExpectation,
    FederalEvaluationConcernMapping,
    FederalEvaluationProfile,
    FederalReviewConcern,
)
from ix_autonomy_assurance_case_runtime.federal_evaluation_profile_readiness import (
    FEDERAL_EVALUATION_PROFILE_CAPABILITY_ID,
    FederalEvaluationLayerReadinessEvaluator,
    FederalEvaluationReadinessDecision,
    FederalEvaluationReadinessFinding,
    FederalEvaluationReadinessFindingSeverity,
    FederalEvaluationReadinessFindingSource,
)
from ix_autonomy_assurance_case_runtime.prototype_readiness import PrototypeClaimLevel


def _mapping(
    *,
    mapping_id: str,
    concern: FederalReviewConcern,
    status: EvaluationAlignmentStatus = EvaluationAlignmentStatus.SATISFIED,
    evidence_expectation: EvaluationEvidenceExpectation = (
        EvaluationEvidenceExpectation.REQUIRED
    ),
    capability_ids: tuple[str, ...] = ("assurance-dossier",),
    artifact_ids: tuple[str, ...] = ("artifact-readiness-rollup-001",),
    evidence_bundle_ids: tuple[str, ...] = ("ev-federal-profile-001",),
) -> FederalEvaluationConcernMapping:
    return FederalEvaluationConcernMapping(
        mapping_id=mapping_id,
        concern=concern,
        status=status,
        evidence_expectation=evidence_expectation,
        capability_ids=capability_ids,
        artifact_ids=artifact_ids,
        evidence_bundle_ids=evidence_bundle_ids,
        reviewer_question="Can the runtime claim be traced to evidence?",
        rationale="The dossier links mission need to evidence-backed review artifacts.",
        notes=("Local prototype alignment only.",),
    )


def _core_mappings() -> tuple[FederalEvaluationConcernMapping, ...]:
    return (
        _mapping(
            mapping_id="mapping-mission-traceability-001",
            concern=FederalReviewConcern.MISSION_TRACEABILITY,
        ),
        _mapping(
            mapping_id="mapping-requirement-evidence-001",
            concern=FederalReviewConcern.REQUIREMENT_TO_EVIDENCE,
        ),
        _mapping(
            mapping_id="mapping-hazard-control-001",
            concern=FederalReviewConcern.HAZARD_CONTROL_CLOSURE,
        ),
        _mapping(
            mapping_id="mapping-runtime-bounds-001",
            concern=FederalReviewConcern.BOUNDED_RUNTIME_ACTION,
            capability_ids=("telemetry-adapters",),
            artifact_ids=("artifact-run-ledger-001",),
        ),
        _mapping(
            mapping_id="mapping-telemetry-replay-001",
            concern=FederalReviewConcern.TELEMETRY_REPLAYABILITY,
            capability_ids=("telemetry-adapters",),
            artifact_ids=("artifact-telemetry-replay-001",),
        ),
    )


def _profile(
    *,
    concern_mappings: tuple[FederalEvaluationConcernMapping, ...] | None = None,
    completed_capability_ids: tuple[str, ...] = (
        "assurance-dossier",
        "telemetry-adapters",
    ),
    available_artifact_ids: tuple[str, ...] = (
        "artifact-readiness-rollup-001",
        "artifact-run-ledger-001",
        "artifact-telemetry-replay-001",
    ),
    available_evidence_bundle_ids: tuple[str, ...] = ("ev-federal-profile-001",),
    disclaimer: str | None = None,
) -> FederalEvaluationProfile:
    return FederalEvaluationProfile(
        profile_id="federal-profile-runtime-001",
        case_id="case-runtime-001",
        title="Runtime assurance federal evaluation profile",
        created_at_utc="2026-05-12T17:00:00Z",
        concern_mappings=concern_mappings if concern_mappings is not None else _core_mappings(),
        completed_capability_ids=completed_capability_ids,
        available_artifact_ids=available_artifact_ids,
        available_evidence_bundle_ids=available_evidence_bundle_ids,
        notes=("Maps local prototype evidence to reviewer concerns.",),
        disclaimer=disclaimer
        or (
            "Local prototype evaluation profile only; not a certification, "
            "authority-to-operate decision, deployment approval, official endorsement, "
            "procurement acceptance, or agency acceptance."
        ),
    )


def _bundle(bundle_id: str = "ev-federal-profile-001", *, hashed: bool = True) -> EvidenceBundle:
    bundle = EvidenceBundle(
        bundle_id=bundle_id,
        case_id="case-runtime-001",
        records=(
            EvidenceRecord(
                evidence_id=f"record-{bundle_id}",
                kind="federal-evaluation-profile",
                source="unit-test",
                payload={"bundle_id": bundle_id},
                status=EvidenceStatus.ACCEPTED,
            ),
        ),
    )
    if hashed:
        return bundle.with_computed_hashes()
    return bundle


def test_federal_evaluation_readiness_completes_clean_profile() -> None:
    report = FederalEvaluationLayerReadinessEvaluator(
        evidence_bundles=(_bundle(),),
    ).evaluate(_profile())

    assert report.decision is FederalEvaluationReadinessDecision.COMPLETE
    assert report.is_complete()
    assert report.completed_capability_ids() == (FEDERAL_EVALUATION_PROFILE_CAPABILITY_ID,)
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "federal-evaluation-readiness: complete "
        "(5 mapping(s), 5 concern(s), 5 core concern(s), "
        "2 completed capability(s), 3 artifact(s), 1 evidence bundle(s), "
        "0 blocker(s), 0 warning(s), capability=federal-evaluation-profile)"
    )


def test_federal_evaluation_readiness_feeds_prototype_claim_gate() -> None:
    report = FederalEvaluationLayerReadinessEvaluator(
        evidence_bundles=(_bundle(),),
    ).evaluate(_profile())

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
            "review-workflow",
            "audit-report-export",
            "assurance-dossier",
            "claim-guardrails",
        ),
    )

    assert FEDERAL_EVALUATION_PROFILE_CAPABILITY_ID in prototype_report.completed_capability_ids


def test_federal_evaluation_readiness_blocks_missing_required_core_concerns() -> None:
    report = FederalEvaluationLayerReadinessEvaluator(
        evidence_bundles=(_bundle(),),
    ).evaluate(
        _profile(
            concern_mappings=(
                _mapping(
                    mapping_id="mapping-mission-traceability-001",
                    concern=FederalReviewConcern.MISSION_TRACEABILITY,
                ),
            )
        )
    )

    assert report.decision is FederalEvaluationReadinessDecision.BLOCKED
    assert report.findings_for_concern(FederalReviewConcern.REQUIREMENT_TO_EVIDENCE)
    assert report.findings_for_concern(FederalReviewConcern.HAZARD_CONTROL_CLOSURE)
    assert report.findings_for_concern(FederalReviewConcern.BOUNDED_RUNTIME_ACTION)
    assert report.findings_for_concern(FederalReviewConcern.TELEMETRY_REPLAYABILITY)


def test_federal_evaluation_readiness_blocks_missing_capability_artifact_and_evidence() -> None:
    report = FederalEvaluationLayerReadinessEvaluator(
        evidence_bundles=(_bundle(),),
    ).evaluate(
        _profile(
            concern_mappings=(
                _mapping(
                    mapping_id="mapping-runtime-bounds-001",
                    concern=FederalReviewConcern.BOUNDED_RUNTIME_ACTION,
                    capability_ids=("missing-capability",),
                    artifact_ids=("missing-artifact",),
                    evidence_bundle_ids=("missing-evidence",),
                ),
                *_core_mappings()[:3],
                _core_mappings()[4],
            ),
            completed_capability_ids=("assurance-dossier",),
            available_artifact_ids=("artifact-readiness-rollup-001",),
            available_evidence_bundle_ids=("ev-federal-profile-001",),
        )
    )

    assert report.decision is FederalEvaluationReadinessDecision.BLOCKED
    assert report.findings_for_capability("missing-capability")
    assert report.findings_for_artifact("missing-artifact")
    assert report.findings_for_evidence_bundle("missing-evidence")


def test_federal_evaluation_readiness_limited_for_partial_mapping() -> None:
    report = FederalEvaluationLayerReadinessEvaluator(
        evidence_bundles=(_bundle(),),
    ).evaluate(
        _profile(
            concern_mappings=(
                _mapping(
                    mapping_id="mapping-mission-traceability-001",
                    concern=FederalReviewConcern.MISSION_TRACEABILITY,
                    status=EvaluationAlignmentStatus.PARTIAL,
                ),
                *_core_mappings()[1:],
            )
        )
    )

    assert report.decision is FederalEvaluationReadinessDecision.LIMITED
    assert report.warning_count == 1
    assert report.findings_for_mapping("mapping-mission-traceability-001")[0].source is (
        FederalEvaluationReadinessFindingSource.MAPPING
    )


def test_federal_evaluation_readiness_blocks_missing_evidence_bundle() -> None:
    report = FederalEvaluationLayerReadinessEvaluator(evidence_bundles=()).evaluate(
        _profile()
    )

    assert report.decision is FederalEvaluationReadinessDecision.BLOCKED
    assert report.findings_for_evidence_bundle("ev-federal-profile-001")


def test_federal_evaluation_readiness_limited_for_evidence_warnings() -> None:
    report = FederalEvaluationLayerReadinessEvaluator(
        evidence_bundles=(_bundle(hashed=False),),
    ).evaluate(_profile())

    assert report.decision is FederalEvaluationReadinessDecision.LIMITED
    assert report.warning_count == 2
    assert report.findings_for_evidence_bundle("ev-federal-profile-001")


def test_federal_evaluation_readiness_blocks_weak_disclaimer() -> None:
    report = FederalEvaluationLayerReadinessEvaluator(
        evidence_bundles=(_bundle(),),
    ).evaluate(_profile(disclaimer="Ready for review."))

    assert report.decision is FederalEvaluationReadinessDecision.BLOCKED
    assert any(
        finding.source is FederalEvaluationReadinessFindingSource.DISCLAIMER
        for finding in report.findings_for_profile("federal-profile-runtime-001")
    )


def test_federal_evaluation_readiness_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        FederalEvaluationReadinessFinding(
            finding_id="finding-federal-readiness-001",
            severity=FederalEvaluationReadinessFindingSeverity.BLOCKER,
            source=FederalEvaluationReadinessFindingSource.READINESS,
            message="",
        )

    with pytest.raises(ContractValueError, match="capability_id must not be blank"):
        FederalEvaluationReadinessFinding(
            finding_id="finding-federal-readiness-001",
            severity=FederalEvaluationReadinessFindingSeverity.BLOCKER,
            source=FederalEvaluationReadinessFindingSource.CAPABILITY,
            message="Bad capability.",
            capability_id="",
        )
