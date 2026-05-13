from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError
from ix_autonomy_assurance_case_runtime.prototype_target import (
    BASELINE_MATURITY_PERCENT,
    MAXIMUM_LOCAL_PROTOTYPE_PERCENT,
    SERIOUS_PROTOTYPE_TARGET_PERCENT,
    PrototypeCapabilityArea,
    PrototypeCapabilityTarget,
    assess_serious_prototype_maturity,
    build_serious_prototype_targets,
    serious_prototype_capability_ids,
)

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


def test_serious_prototype_targets_include_extended_hardening_layers() -> None:
    capability_ids = serious_prototype_capability_ids()

    assert capability_ids[:9] == ORIGINAL_SERIOUS_PROTOTYPE_CAPABILITIES
    assert capability_ids[-3:] == EXTENDED_HARDENING_CAPABILITIES
    assert len(capability_ids) == len(set(capability_ids))


def test_original_capability_path_still_reaches_eighty_percent() -> None:
    assessment = assess_serious_prototype_maturity(
        ORIGINAL_SERIOUS_PROTOTYPE_CAPABILITIES,
    )

    assert BASELINE_MATURITY_PERCENT == 40
    assert SERIOUS_PROTOTYPE_TARGET_PERCENT == 80
    assert assessment.achieved_percent == 80
    assert assessment.target_percent_met()
    assert assessment.is_serious_prototype_target_met()
    assert assessment.completed_target_count == 9
    assert assessment.missing_capability_ids == EXTENDED_HARDENING_CAPABILITIES


def test_extended_hardening_layers_push_local_prototype_toward_full_model() -> None:
    assessment = assess_serious_prototype_maturity(
        ORIGINAL_SERIOUS_PROTOTYPE_CAPABILITIES + EXTENDED_HARDENING_CAPABILITIES,
    )

    assert assessment.achieved_percent == MAXIMUM_LOCAL_PROTOTYPE_PERCENT
    assert assessment.target_percent_met()
    assert assessment.missing_capability_ids == ()
    assert assessment.unexpected_capability_ids == ()
    assert assessment.duplicate_capability_ids == ()
    assert assessment.summary() == (
        "prototype-maturity: 100% "
        "(12/12 target capability(s), 0 missing, 0 unexpected, 0 duplicate)"
    )


def test_prototype_maturity_assessment_reports_unknown_and_duplicate_ids() -> None:
    assessment = assess_serious_prototype_maturity(
        (
            "registry-layer",
            "registry-layer",
            "experimental-capability",
        )
    )

    assert assessment.achieved_percent == 44
    assert assessment.duplicate_capability_ids == ("registry-layer",)
    assert assessment.unexpected_capability_ids == ("experimental-capability",)
    assert "registry-layer" in assessment.completed_capability_ids


def test_capability_target_helpers_are_deterministic() -> None:
    target = build_serious_prototype_targets()[0]

    assert target.is_completed_by(("registry-layer",))
    assert target.name == target.title
    assert target.percent_contribution == target.maturity_increment_percent
    assert target.maturity_percent == target.maturity_increment_percent
    assert target.summary() == "registry-layer: Registry layer (registry, +4%)"


def test_capability_area_helpers_classify_runtime_and_review_layers() -> None:
    assert PrototypeCapabilityArea.TELEMETRY.is_runtime_facing()
    assert PrototypeCapabilityArea.SCENARIO_CAMPAIGN.is_runtime_facing()
    assert not PrototypeCapabilityArea.POLICY.is_runtime_facing()

    assert PrototypeCapabilityArea.REVIEW_WORKFLOW.is_review_facing()
    assert PrototypeCapabilityArea.FEDERAL_EVALUATION.is_review_facing()
    assert not PrototypeCapabilityArea.REGISTRY.is_review_facing()


def test_prototype_capability_target_validates_required_fields() -> None:
    with pytest.raises(ContractValueError, match="capability_id must not contain spaces"):
        PrototypeCapabilityTarget(
            capability_id="bad capability",
            area=PrototypeCapabilityArea.REGISTRY,
            title="Bad capability",
            description="Invalid identifier.",
            maturity_increment_percent=1,
        )

    with pytest.raises(ContractValueError, match="maturity_increment_percent"):
        PrototypeCapabilityTarget(
            capability_id="bad-capability",
            area=PrototypeCapabilityArea.REGISTRY,
            title="Bad capability",
            description="Invalid maturity increment.",
            maturity_increment_percent=0,
        )

    with pytest.raises(ContractValueError, match="evidence_expectations"):
        PrototypeCapabilityTarget(
            capability_id="bad-capability",
            area=PrototypeCapabilityArea.REGISTRY,
            title="Bad capability",
            description="Duplicate evidence expectations.",
            maturity_increment_percent=1,
            evidence_expectations=("evidence", "evidence"),
        )
