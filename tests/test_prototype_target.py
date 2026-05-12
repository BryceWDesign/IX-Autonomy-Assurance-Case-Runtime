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


def test_serious_prototype_targets_cover_required_capability_areas() -> None:
    targets = build_serious_prototype_targets()

    assert len(targets) == 10
    assert {target.area for target in targets} == set(PrototypeCapabilityArea)
    assert {target.capability_id for target in targets} == {
        "registry-layer",
        "policy-pack-engine",
        "framework-crosswalks",
        "signed-provenance",
        "telemetry-adapters",
        "scenario-campaign-runner",
        "monitoring-incidents",
        "review-workflow",
        "audit-export-packages",
        "security-hardening",
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


def test_serious_prototype_maturity_starts_at_current_baseline() -> None:
    assessment = assess_serious_prototype_maturity(())

    assert isinstance(assessment, PrototypeMaturityAssessment)
    assert assessment.baseline_percent == BASELINE_MATURITY_PERCENT
    assert assessment.target_percent == SERIOUS_PROTOTYPE_TARGET_PERCENT
    assert assessment.achieved_percent == 40
    assert assessment.remaining_percent == 40
    assert not assessment.meets_serious_prototype_target()
    assert assessment.completed_capability_ids == ()
    assert len(assessment.remaining_capability_ids) == 10


def test_serious_prototype_maturity_reaches_target_when_all_capabilities_are_complete() -> None:
    targets = build_serious_prototype_targets()
    completed_ids = tuple(target.capability_id for target in targets)

    assessment = assess_serious_prototype_maturity(completed_ids)

    assert assessment.achieved_percent == 80
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

    assert assessment.achieved_percent == 50
    assert assessment.completed_capability_ids == ("registry-layer", "policy-pack-engine")
    assert "registry-layer" not in assessment.remaining_capability_ids
    assert "policy-pack-engine" not in assessment.remaining_capability_ids


def test_serious_prototype_maturity_rejects_unknown_capability_ids() -> None:
    with pytest.raises(ContractValueError, match="Unknown prototype capability ID"):
        assess_serious_prototype_maturity(("made-up-capability",))


def test_serious_prototype_target_rejects_non_reviewable_records() -> None:
    with pytest.raises(ContractValueError, match="needs acceptance signals"):
        PrototypeCapabilityTarget(
            capability_id="bad-target",
            area=PrototypeCapabilityArea.REGISTRY,
            name="Bad target",
            purpose="This target is intentionally incomplete.",
            acceptance_signals=(),
            blocked_claims_until_met=("Cannot claim reviewability.",),
            maturity_lift_points=1,
        )

    with pytest.raises(ContractValueError, match="needs blocked-claim limits"):
        PrototypeCapabilityTarget(
            capability_id="bad-target",
            area=PrototypeCapabilityArea.REGISTRY,
            name="Bad target",
            purpose="This target is intentionally incomplete.",
            acceptance_signals=("One signal exists.",),
            blocked_claims_until_met=(),
            maturity_lift_points=1,
        )
