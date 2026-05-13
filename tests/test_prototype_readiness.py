from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime import (
    PrototypeClaimLevel,
    PrototypeFindingSeverity,
    PrototypeReadinessDecision,
    PrototypeReadinessFinding,
    PrototypeReadinessGate,
    build_serious_prototype_targets,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError


def _all_capability_ids() -> tuple[str, ...]:
    return tuple(target.capability_id for target in build_serious_prototype_targets())


def _required_capability_ids() -> tuple[str, ...]:
    return tuple(
        target.capability_id
        for target in build_serious_prototype_targets()
        if target.required_for_serious_prototype
    )


def test_local_reference_claim_is_allowed_with_limits_before_target_completion() -> None:
    report = PrototypeReadinessGate().evaluate(
        completed_capability_ids=(),
        requested_claim_level=PrototypeClaimLevel.LOCAL_REFERENCE_RUNTIME,
    )

    assert report.decision is PrototypeReadinessDecision.LIMIT
    assert report.permits_requested_claim()
    assert report.achieved_percent == 40
    assert report.blocker_count == 0
    assert report.warning_count == 1
    assert report.blocked_claims == ("Cannot claim serious prototype completion yet.",)
    assert report.summary() == (
        "local_reference_runtime: limit (40/80 maturity, 0 blocker(s), 1 warning(s))"
    )


def test_serious_open_source_claim_is_blocked_until_required_capabilities_are_complete() -> None:
    report = PrototypeReadinessGate().evaluate(
        completed_capability_ids=("registry-layer", "policy-pack-engine"),
        requested_claim_level=PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE,
    )

    assert report.decision is PrototypeReadinessDecision.BLOCK
    assert not report.permits_requested_claim()
    assert report.achieved_percent == 48
    assert report.blocker_count == 7
    assert report.warning_count == 0
    assert "framework-crosswalks" in report.remaining_capability_ids
    assert "Cannot claim framework crosswalks capability completion yet." in report.blocked_claims


def test_serious_open_source_claim_is_allowed_when_original_target_path_is_complete() -> None:
    report = PrototypeReadinessGate().evaluate(
        completed_capability_ids=_required_capability_ids(),
        requested_claim_level=PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE,
    )

    assert report.decision is PrototypeReadinessDecision.ALLOW
    assert report.permits_requested_claim()
    assert report.achieved_percent == 80
    assert report.remaining_capability_ids == (
        "assurance-dossier",
        "claim-guardrails",
        "federal-evaluation-profile",
    )
    assert report.findings == ()


def test_full_local_model_reaches_one_hundred_percent_without_extra_claims() -> None:
    report = PrototypeReadinessGate().evaluate(
        completed_capability_ids=_all_capability_ids(),
        requested_claim_level=PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE,
    )

    assert report.decision is PrototypeReadinessDecision.ALLOW
    assert report.permits_requested_claim()
    assert report.achieved_percent == 100
    assert report.remaining_capability_ids == ()
    assert report.findings == ()


def test_federal_aligned_claim_remains_limited_even_when_target_capabilities_are_complete() -> None:
    report = PrototypeReadinessGate().evaluate(
        completed_capability_ids=_all_capability_ids(),
        requested_claim_level=PrototypeClaimLevel.FEDERAL_ALIGNED_PROTOTYPE,
    )

    assert report.decision is PrototypeReadinessDecision.LIMIT
    assert report.permits_requested_claim()
    assert report.blocker_count == 0
    assert report.warning_count == 1
    assert report.blocked_claims == (
        "Cannot claim official federal, IC, or DoD endorsement.",
    )


def test_operational_and_certified_claims_are_always_blocked_by_repo_only_evidence() -> None:
    gate = PrototypeReadinessGate()

    operational_report = gate.evaluate(
        completed_capability_ids=_all_capability_ids(),
        requested_claim_level=PrototypeClaimLevel.OPERATIONAL_DEPLOYMENT_READY,
    )
    certified_report = gate.evaluate(
        completed_capability_ids=_all_capability_ids(),
        requested_claim_level=PrototypeClaimLevel.CERTIFIED_OR_AUTHORIZED,
    )

    assert operational_report.decision is PrototypeReadinessDecision.BLOCK
    assert certified_report.decision is PrototypeReadinessDecision.BLOCK
    assert operational_report.blocked_claims == (
        "Cannot self-attest operational or certified readiness.",
    )
    assert certified_report.blocked_claims == (
        "Cannot self-attest operational or certified readiness.",
    )


def test_readiness_gate_warns_for_unknown_completed_capability_ids() -> None:
    report = PrototypeReadinessGate().evaluate(
        completed_capability_ids=("not-real",),
        requested_claim_level=PrototypeClaimLevel.LOCAL_REFERENCE_RUNTIME,
    )

    assert report.decision is PrototypeReadinessDecision.LIMIT
    assert report.warning_count == 2
    assert "not-real" in report.completed_capability_ids
    assert any(finding.finding_id == "unexpected-not-real" for finding in report.findings)


def test_readiness_gate_rejects_duplicate_target_ids() -> None:
    targets = build_serious_prototype_targets()

    with pytest.raises(ContractValueError, match="unique capability IDs"):
        PrototypeReadinessGate(targets=(targets[0], targets[0]))


def test_readiness_finding_rejects_blank_message_and_blank_capability() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        PrototypeReadinessFinding(
            finding_id="bad-finding",
            severity=PrototypeFindingSeverity.BLOCKER,
            message="",
        )

    with pytest.raises(ContractValueError, match="blank capability ID"):
        PrototypeReadinessFinding(
            finding_id="bad-finding",
            severity=PrototypeFindingSeverity.BLOCKER,
            message="Bad finding.",
            capability_id="",
        )
