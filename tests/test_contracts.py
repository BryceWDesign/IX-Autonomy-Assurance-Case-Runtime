from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import (
    AssuranceCaseStatus,
    AutonomyDecisionType,
    ContractDefinition,
    ContractValueError,
    EvidenceStatus,
    HazardSeverity,
    ReviewDisposition,
    RuntimeAuthorityState,
    VerificationResult,
    build_contract_catalog,
)


def test_contract_catalog_contains_all_core_contracts() -> None:
    catalog = build_contract_catalog()

    assert set(catalog) == {
        "assurance_case_status",
        "evidence_status",
        "hazard_severity",
        "autonomy_decision_type",
        "runtime_authority_state",
        "verification_result",
        "review_disposition",
    }

    for definition in catalog.values():
        assert isinstance(definition, ContractDefinition)
        assert definition.default_value in definition.allowed_values


def test_contract_values_are_stable_and_unique() -> None:
    enum_types = (
        AssuranceCaseStatus,
        EvidenceStatus,
        HazardSeverity,
        AutonomyDecisionType,
        RuntimeAuthorityState,
        VerificationResult,
        ReviewDisposition,
    )

    for enum_type in enum_types:
        values = enum_type.values()
        assert len(values) == len(set(values))
        assert all(value == value.lower() for value in values)
        assert all(" " not in value for value in values)


def test_contract_enum_from_value_accepts_known_values() -> None:
    assert AssuranceCaseStatus.from_value("draft") is AssuranceCaseStatus.DRAFT
    assert EvidenceStatus.from_value("accepted") is EvidenceStatus.ACCEPTED
    assert HazardSeverity.from_value("critical") is HazardSeverity.CRITICAL
    assert AutonomyDecisionType.from_value("safe_hold") is AutonomyDecisionType.SAFE_HOLD
    assert VerificationResult.from_value("not_run") is VerificationResult.NOT_RUN


def test_contract_enum_from_value_rejects_unknown_values() -> None:
    with pytest.raises(ContractValueError, match="Unsupported VerificationResult value"):
        VerificationResult.from_value("maybe")


def test_assurance_case_status_terminal_and_review_behavior() -> None:
    assert AssuranceCaseStatus.DRAFT.is_terminal() is False
    assert AssuranceCaseStatus.READY_FOR_REVIEW.requires_review() is True
    assert AssuranceCaseStatus.ACCEPTED.is_terminal() is True
    assert AssuranceCaseStatus.REJECTED.is_terminal() is True
    assert AssuranceCaseStatus.SUPERSEDED.is_terminal() is True


def test_evidence_status_identifies_usable_evidence() -> None:
    assert EvidenceStatus.PROVIDED.is_usable() is True
    assert EvidenceStatus.ACCEPTED.is_usable() is True
    assert EvidenceStatus.MISSING.is_usable() is False
    assert EvidenceStatus.STALE.is_usable() is False
    assert EvidenceStatus.INVALID.is_usable() is False


def test_hazard_severity_orders_risk_and_requires_mitigation() -> None:
    assert HazardSeverity.NEGLIGIBLE.rank < HazardSeverity.MINOR.rank
    assert HazardSeverity.MINOR.rank < HazardSeverity.MAJOR.rank
    assert HazardSeverity.MAJOR.rank < HazardSeverity.CRITICAL.rank
    assert HazardSeverity.CRITICAL.rank < HazardSeverity.CATASTROPHIC.rank

    assert HazardSeverity.NEGLIGIBLE.requires_mitigation() is False
    assert HazardSeverity.MINOR.requires_mitigation() is False
    assert HazardSeverity.MAJOR.requires_mitigation() is True
    assert HazardSeverity.CRITICAL.requires_mitigation() is True
    assert HazardSeverity.CATASTROPHIC.requires_mitigation() is True


def test_autonomy_decision_type_marks_restrictive_outcomes() -> None:
    assert AutonomyDecisionType.ALLOW.permits_nominal_execution() is True
    assert AutonomyDecisionType.ALLOW.is_restrictive() is False
    assert AutonomyDecisionType.CLAMP.is_restrictive() is True
    assert AutonomyDecisionType.DEFER.is_restrictive() is True
    assert AutonomyDecisionType.VETO.is_restrictive() is True
    assert AutonomyDecisionType.SAFE_HOLD.is_restrictive() is True


def test_runtime_authority_state_controls_autonomous_execution() -> None:
    assert RuntimeAuthorityState.AUTONOMOUS_ALLOWED.permits_autonomous_execution() is True
    assert RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED.permits_autonomous_execution() is False
    assert RuntimeAuthorityState.DENIED.blocks_autonomous_execution() is True
    assert RuntimeAuthorityState.EMERGENCY_SAFE_HOLD.blocks_autonomous_execution() is True


def test_verification_result_success_and_follow_up_behavior() -> None:
    assert VerificationResult.PASS.is_success() is True
    assert VerificationResult.PASS.requires_follow_up() is False
    assert VerificationResult.FAIL.requires_follow_up() is True
    assert VerificationResult.INCONCLUSIVE.requires_follow_up() is True
    assert VerificationResult.NOT_RUN.requires_follow_up() is True


def test_review_disposition_acceptance_behavior() -> None:
    assert ReviewDisposition.APPROVED.allows_acceptance() is True
    assert ReviewDisposition.APPROVED_WITH_CONDITIONS.allows_acceptance() is True
    assert ReviewDisposition.REJECTED.allows_acceptance() is False
    assert ReviewDisposition.NEEDS_MORE_EVIDENCE.allows_acceptance() is False
    assert ReviewDisposition.ESCALATED.allows_acceptance() is False


def test_contract_definition_rejects_blank_name() -> None:
    with pytest.raises(ContractValueError, match="must not be blank"):
        ContractDefinition(
            name=" ",
            description="A valid description.",
            allowed_values=("one",),
            default_value="one",
        )


def test_contract_definition_rejects_default_outside_allowed_values() -> None:
    with pytest.raises(ContractValueError, match="Default value"):
        ContractDefinition(
            name="example",
            description="A valid description.",
            allowed_values=("one", "two"),
            default_value="three",
        )
