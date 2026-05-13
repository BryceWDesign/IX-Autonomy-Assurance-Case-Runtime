from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError
from ix_autonomy_assurance_case_runtime.federal_evaluation_profile import (
    EvaluationAlignmentStatus,
    EvaluationEvidenceExpectation,
    FederalEvaluationConcernMapping,
    FederalEvaluationProfile,
    FederalReviewConcern,
)


def _mapping(
    *,
    mapping_id: str = "mapping-traceability-001",
    concern: FederalReviewConcern = FederalReviewConcern.MISSION_TRACEABILITY,
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


def _profile(
    *,
    concern_mappings: tuple[FederalEvaluationConcernMapping, ...] | None = None,
    completed_capability_ids: tuple[str, ...] = ("assurance-dossier",),
    available_artifact_ids: tuple[str, ...] = ("artifact-readiness-rollup-001",),
    available_evidence_bundle_ids: tuple[str, ...] = ("ev-federal-profile-001",),
    disclaimer: str | None = None,
) -> FederalEvaluationProfile:
    return FederalEvaluationProfile(
        profile_id="federal-profile-runtime-001",
        case_id="case-runtime-001",
        title="Runtime assurance federal evaluation profile",
        created_at_utc="2026-05-12T17:00:00Z",
        concern_mappings=concern_mappings if concern_mappings is not None else (_mapping(),),
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


def test_federal_profile_tracks_satisfied_concerns_and_summary() -> None:
    profile = _profile(
        concern_mappings=(
            _mapping(),
            _mapping(
                mapping_id="mapping-runtime-bounds-001",
                concern=FederalReviewConcern.BOUNDED_RUNTIME_ACTION,
                capability_ids=("telemetry-adapters",),
                artifact_ids=("artifact-run-ledger-001",),
                evidence_bundle_ids=("ev-runtime-bounds-001",),
            ),
        ),
        completed_capability_ids=("assurance-dossier", "telemetry-adapters"),
        available_artifact_ids=(
            "artifact-readiness-rollup-001",
            "artifact-run-ledger-001",
        ),
        available_evidence_bundle_ids=(
            "ev-federal-profile-001",
            "ev-runtime-bounds-001",
        ),
    )

    assert profile.can_support_evaluation_package()
    assert profile.mapping_ids() == (
        "mapping-traceability-001",
        "mapping-runtime-bounds-001",
    )
    assert profile.satisfied_mapping_ids() == (
        "mapping-traceability-001",
        "mapping-runtime-bounds-001",
    )
    assert profile.blocked_mapping_ids() == ()
    assert profile.core_t_and_e_concern_values() == (
        "mission_traceability",
        "bounded_runtime_action",
    )
    assert profile.summary() == (
        "federal-evaluation-profile: federal-profile-runtime-001 "
        "(2 concern mapping(s), 2 satisfied, 0 blocked, 2 core T&E concern(s))"
    )


def test_federal_profile_blocks_missing_required_capability_artifact_and_evidence() -> None:
    profile = _profile(
        completed_capability_ids=(),
        available_artifact_ids=(),
        available_evidence_bundle_ids=(),
    )

    assert not profile.can_support_evaluation_package()
    assert profile.blocked_mapping_ids() == ("mapping-traceability-001",)
    assert profile.missing_required_capability_ids() == ("assurance-dossier",)
    assert profile.missing_required_artifact_ids() == ("artifact-readiness-rollup-001",)
    assert profile.missing_required_evidence_bundle_ids() == ("ev-federal-profile-001",)


def test_federal_profile_blocks_explicitly_blocked_or_not_assessed_mapping() -> None:
    blocked = _profile(
        concern_mappings=(
            _mapping(status=EvaluationAlignmentStatus.BLOCKED),
        )
    )
    not_assessed = _profile(
        concern_mappings=(
            _mapping(status=EvaluationAlignmentStatus.NOT_ASSESSED),
        )
    )

    assert blocked.blocked_mapping_ids() == ("mapping-traceability-001",)
    assert not_assessed.blocked_mapping_ids() == ("mapping-traceability-001",)


def test_federal_profile_allows_recommended_evidence_to_be_missing_without_blocking() -> None:
    profile = _profile(
        concern_mappings=(
            _mapping(
                evidence_expectation=EvaluationEvidenceExpectation.RECOMMENDED,
                evidence_bundle_ids=(),
            ),
        ),
        available_evidence_bundle_ids=(),
    )

    assert profile.can_support_evaluation_package()
    assert profile.missing_required_evidence_bundle_ids() == ()


def test_required_mapping_requires_evidence_bundle_ids() -> None:
    with pytest.raises(ContractValueError, match="required federal concern mappings"):
        _mapping(evidence_bundle_ids=())


def test_mapping_rejects_empty_capabilities_and_artifacts() -> None:
    with pytest.raises(ContractValueError, match="capability_ids"):
        _mapping(capability_ids=())

    with pytest.raises(ContractValueError, match="artifact_ids"):
        _mapping(artifact_ids=())


def test_federal_profile_rejects_duplicate_records_and_values() -> None:
    mapping = _mapping()

    with pytest.raises(ContractValueError, match="federal concern mapping IDs"):
        _profile(concern_mappings=(mapping, mapping))

    with pytest.raises(ContractValueError, match="completed_capability_ids"):
        _profile(completed_capability_ids=("assurance-dossier", "assurance-dossier"))


def test_federal_profile_detects_weak_disclaimer() -> None:
    profile = _profile(disclaimer="Ready for review.")

    assert not profile.disclaimer_is_bounded()
    assert not profile.can_support_evaluation_package()


def test_federal_profile_validates_identifiers_and_timestamps() -> None:
    with pytest.raises(ContractValueError, match="profile_id must not contain spaces"):
        FederalEvaluationProfile(
            profile_id="federal profile",
            case_id="case-runtime-001",
            title="Runtime assurance federal evaluation profile",
            created_at_utc="2026-05-12T17:00:00Z",
            concern_mappings=(_mapping(),),
            completed_capability_ids=("assurance-dossier",),
            available_artifact_ids=("artifact-readiness-rollup-001",),
            available_evidence_bundle_ids=("ev-federal-profile-001",),
        )

    with pytest.raises(ContractValueError, match="must include a timezone"):
        FederalEvaluationProfile(
            profile_id="federal-profile-runtime-001",
            case_id="case-runtime-001",
            title="Runtime assurance federal evaluation profile",
            created_at_utc="2026-05-12T17:00:00",
            concern_mappings=(_mapping(),),
            completed_capability_ids=("assurance-dossier",),
            available_artifact_ids=("artifact-readiness-rollup-001",),
            available_evidence_bundle_ids=("ev-federal-profile-001",),
        )
