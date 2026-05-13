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
from ix_autonomy_assurance_case_runtime.federal_evaluation_profile_validation import (
    FederalEvaluationProfileValidator,
    FederalEvaluationValidationFinding,
    FederalEvaluationValidationFindingSeverity,
    FederalEvaluationValidationFindingSource,
)


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


def test_federal_evaluation_validator_accepts_grounded_profile() -> None:
    report = FederalEvaluationProfileValidator(
        evidence_bundles=(_bundle(),),
    ).validate(_profile())

    assert report.is_evaluation_ready()
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "federal-evaluation-validation: federal-profile-runtime-001 "
        "(5 mapping(s), 5 concern(s), 5 core concern(s), "
        "2 completed capability(s), 3 artifact(s), 1 evidence bundle(s), "
        "0 blocker(s), 0 warning(s))"
    )


def test_federal_evaluation_validator_blocks_missing_required_core_concerns() -> None:
    report = FederalEvaluationProfileValidator(
        evidence_bundles=(_bundle(),),
    ).validate(
        _profile(
            concern_mappings=(
                _mapping(
                    mapping_id="mapping-mission-traceability-001",
                    concern=FederalReviewConcern.MISSION_TRACEABILITY,
                ),
            )
        )
    )

    assert not report.is_evaluation_ready()
    assert report.findings_for_concern(FederalReviewConcern.REQUIREMENT_TO_EVIDENCE)
    assert report.findings_for_concern(FederalReviewConcern.HAZARD_CONTROL_CLOSURE)
    assert report.findings_for_concern(FederalReviewConcern.BOUNDED_RUNTIME_ACTION)
    assert report.findings_for_concern(FederalReviewConcern.TELEMETRY_REPLAYABILITY)


def test_federal_evaluation_validator_blocks_status_and_missing_records() -> None:
    report = FederalEvaluationProfileValidator(
        evidence_bundles=(_bundle(),),
    ).validate(
        _profile(
            concern_mappings=(
                _mapping(
                    mapping_id="mapping-runtime-bounds-001",
                    concern=FederalReviewConcern.BOUNDED_RUNTIME_ACTION,
                    status=EvaluationAlignmentStatus.BLOCKED,
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

    assert not report.is_evaluation_ready()
    assert report.findings_for_mapping("mapping-runtime-bounds-001")
    assert report.findings_for_capability("missing-capability")
    assert report.findings_for_artifact("missing-artifact")
    assert report.findings_for_evidence_bundle("missing-evidence")


def test_federal_evaluation_validator_warns_for_partial_mapping() -> None:
    report = FederalEvaluationProfileValidator(
        evidence_bundles=(_bundle(),),
    ).validate(
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

    assert report.is_evaluation_ready()
    assert report.warning_count == 1
    assert report.findings_for_mapping("mapping-mission-traceability-001")[0].source is (
        FederalEvaluationValidationFindingSource.MAPPING
    )


def test_federal_evaluation_validator_blocks_missing_evidence_bundle() -> None:
    report = FederalEvaluationProfileValidator(evidence_bundles=()).validate(_profile())

    assert not report.is_evaluation_ready()
    assert report.findings_for_evidence_bundle("ev-federal-profile-001")[0].source is (
        FederalEvaluationValidationFindingSource.EVIDENCE
    )


def test_federal_evaluation_validator_warns_for_unhashed_evidence_bundle() -> None:
    report = FederalEvaluationProfileValidator(
        evidence_bundles=(_bundle(hashed=False),),
    ).validate(_profile())

    assert report.is_evaluation_ready()
    assert report.warning_count == 2
    assert report.findings_for_evidence_bundle("ev-federal-profile-001")


def test_federal_evaluation_validator_blocks_weak_disclaimer() -> None:
    report = FederalEvaluationProfileValidator(
        evidence_bundles=(_bundle(),),
    ).validate(_profile(disclaimer="Ready for review."))

    assert not report.is_evaluation_ready()
    assert any(
        finding.source is FederalEvaluationValidationFindingSource.DISCLAIMER
        for finding in report.findings
    )


def test_federal_evaluation_validator_rejects_duplicate_evidence_inputs() -> None:
    bundle = _bundle()

    with pytest.raises(ContractValueError, match="Duplicate federal evaluation evidence"):
        FederalEvaluationProfileValidator(evidence_bundles=(bundle, bundle))


def test_federal_evaluation_validation_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        FederalEvaluationValidationFinding(
            finding_id="finding-federal-validation-001",
            severity=FederalEvaluationValidationFindingSeverity.BLOCKER,
            source=FederalEvaluationValidationFindingSource.PROFILE,
            message="",
        )

    with pytest.raises(ContractValueError, match="capability_id must not be blank"):
        FederalEvaluationValidationFinding(
            finding_id="finding-federal-validation-001",
            severity=FederalEvaluationValidationFindingSeverity.BLOCKER,
            source=FederalEvaluationValidationFindingSource.CAPABILITY,
            message="Bad capability.",
            capability_id="",
        )
