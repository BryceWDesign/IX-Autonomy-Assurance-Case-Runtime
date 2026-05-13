from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime import (
    BASELINE_MATURITY_PERCENT,
    SERIOUS_PROTOTYPE_TARGET_PERCENT,
    PrototypeCapabilityArea,
    PrototypeCapabilityTarget,
    PrototypeMaturityAssessment,
    assess_serious_prototype_maturity,
    build_serious_prototype_targets,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError

ORIGINAL_SERIOUS_PROTOTYPE_CAPABILITIES = (
    "registry-layer",
    "policy-pack-engine",
    "framework-crosswalks",
    "signed-provenance",
    "telemetry-adapters",
    "scenario-campaign-runner",
    "monitoring-incidents",
    "review-workflow",
    "audit-report-export",
)

EXTENDED_HARDENING_CAPABILITIES = (
    "assurance-dossier",
    "claim-guardrails",
    "federal-evaluation-profile",
)


def test_serious_prototype_targets_cover_required_capability_areas() -> None:
    targets = build_serious_prototype_targets()

    assert len(targets) == 12
    assert tuple(target.capability_id for target in targets) == (
        ORIGINAL_SERIOUS_PROTOTYPE_CAPABILITIES + EXTENDED_HARDENING_CAPABILITIES
    )
    assert {target.area for target in targets} >= {
        PrototypeCapabilityArea.REGISTRY,
        PrototypeCapabilityArea.POLICY,
        PrototypeCapabilityArea.FRAMEWORK,
        PrototypeCapabilityArea.PROVENANCE,
        PrototypeCapabilityArea.TELEMETRY,
        PrototypeCapabilityArea.SCENARIO_CAMPAIGN,
        PrototypeCapabilityArea.MONITORING,
        PrototypeCapabilityArea.REVIEW_WORKFLOW,
        PrototypeCapabilityArea.AUDIT_EXPORT,
        PrototypeCapabilityArea.TRACE_CLOSURE,
        PrototypeCapabilityArea.CLAIM_GOVERNANCE,
        PrototypeCapabilityArea.FEDERAL_EVALUATION,
    }


def test_serious_prototype_targets_are_reviewable_and_claim_limited() -> None:
    targets = build_serious_prototype_targets()

    for target in targets:
        assert isinstance(target, PrototypeCapabilityTarget)
        assert target.capability_id == target.capability_id.strip()
        assert target.name.strip()
        assert target.purpose.strip()
        assert len(target.acceptance_signals) >= 3
        assert len(target.blocked_claims_until_met) >= 2
        assert target.maturity_lift_points > 0
        assert target.requires_audit_artifact()

    assert all(target.required_for_serious_prototype for target in targets[:9])
    assert not any(target.required_for_serious_prototype for target in targets[-3:])


def test_serious_prototype_maturity_starts_at_current_baseline() -> None:
    assessment = assess_serious_prototype_maturity(())

    assert isinstance(assessment, PrototypeMaturityAssessment)
    assert assessment.baseline_percent == BASELINE_MATURITY_PERCENT
    assert assessment.target_percent == SERIOUS_PROTOTYPE_TARGET_PERCENT
    assert assessment.achieved_percent == 40
    assert assessment.remaining_percent == 40
    assert not assessment.meets_serious_prototype_target()
    assert assessment.completed_capability_ids == ()
    assert len(assessment.remaining_capability_ids) == 12


def test_original_capability_path_reaches_serious_prototype_target() -> None:
    assessment = assess_serious_prototype_maturity(ORIGINAL_SERIOUS_PROTOTYPE_CAPABILITIES)

    assert assessment.achieved_percent == 80
    assert assessment.remaining_percent == 0
    assert assessment.meets_serious_prototype_target()
    assert assessment.completed_capability_ids == ORIGINAL_SERIOUS_PROTOTYPE_CAPABILITIES
    assert assessment.remaining_capability_ids == EXTENDED_HARDENING_CAPABILITIES


def test_extended_model_reaches_local_prototype_maximum() -> None:
    completed_ids = ORIGINAL_SERIOUS_PROTOTYPE_CAPABILITIES + EXTENDED_HARDENING_CAPABILITIES

    assessment = assess_serious_prototype_maturity(completed_ids)

    assert assessment.achieved_percent == 100
    assert assessment.remaining_percent == 0
    assert assessment.meets_serious_prototype_target()
    assert assessment.completed_capability_ids == completed_ids
    assert assessment.remaining_capability_ids == ()


def test_serious_prototype_maturity_counts_duplicate_completed_ids_once() -> None:
    assessment = assess_serious_prototype_maturity(
        (
            "registry-layer",
            "registry-layer",
            "policy-pack-engine",
        )
    )

    assert assessment.achieved_percent == 48
    assert assessment.completed_capability_ids == (
        "registry-layer",
        "registry-layer",
        "policy-pack-engine",
    )
    assert assessment.duplicate_capability_ids == ("registry-layer",)
    assert "registry-layer" not in assessment.remaining_capability_ids
    assert "policy-pack-engine" not in assessment.remaining_capability_ids


def test_serious_prototype_maturity_reports_unknown_capability_ids() -> None:
    assessment = assess_serious_prototype_maturity(("made-up-capability",))

    assert assessment.achieved_percent == BASELINE_MATURITY_PERCENT
    assert assessment.unexpected_capability_ids == ("made-up-capability",)
    assert "made-up-capability" in assessment.completed_capability_ids


def test_prototype_capability_target_rejects_invalid_records() -> None:
    with pytest.raises(ContractValueError, match="capability_id must not contain spaces"):
        PrototypeCapabilityTarget(
            capability_id="bad target",
            area=PrototypeCapabilityArea.REGISTRY,
            title="Bad target",
            description="This target has an invalid identifier.",
            maturity_increment_percent=1,
            evidence_expectations=("one signal",),
        )

    with pytest.raises(ContractValueError, match="title must not be blank"):
        PrototypeCapabilityTarget(
            capability_id="bad-target",
            area=PrototypeCapabilityArea.REGISTRY,
            title="",
            description="This target is intentionally incomplete.",
            maturity_increment_percent=1,
            evidence_expectations=("one signal",),
        )

    with pytest.raises(ContractValueError, match="maturity_increment_percent"):
        PrototypeCapabilityTarget(
            capability_id="bad-target",
            area=PrototypeCapabilityArea.REGISTRY,
            title="Bad target",
            description="This target is intentionally incomplete.",
            maturity_increment_percent=0,
            evidence_expectations=("one signal",),
        )
