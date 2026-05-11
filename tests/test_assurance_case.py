from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.assurance_case import (
    AssuranceCase,
    AssuranceClaim,
    AssuranceModelError,
    Control,
    EvidenceLink,
    Hazard,
    Mitigation,
    VerificationCriterion,
)
from ix_autonomy_assurance_case_runtime.contracts import (
    AssuranceCaseStatus,
    EvidenceStatus,
    HazardSeverity,
    VerificationResult,
)


def build_valid_case() -> AssuranceCase:
    evidence = EvidenceLink(
        evidence_id="EV-001",
        description="Scenario run log with bounded autonomy behavior.",
        source="run-bundles/scenario-001.json",
        status=EvidenceStatus.ACCEPTED,
        supports=("CLM-001", "VC-001", "CTRL-001"),
        content_hash="sha256:0123456789abcdef",
    )
    criterion = VerificationCriterion(
        criterion_id="VC-001",
        statement="Autonomy enters safe-hold when navigation confidence is lost.",
        verification_method="fault-injection scenario",
        expected_result="safe_hold decision emitted before mission boundary violation",
        result=VerificationResult.PASS,
        evidence_ids=("EV-001",),
    )
    hazard = Hazard(
        hazard_id="HZ-001",
        title="Navigation confidence loss",
        description="The autonomy stack may continue nominal behavior after navigation degrades.",
        severity=HazardSeverity.CRITICAL,
        control_ids=("CTRL-001",),
        mitigation_ids=("MIT-001",),
        evidence_ids=("EV-001",),
    )
    control = Control(
        control_id="CTRL-001",
        name="Navigation degradation safe-hold gate",
        description="Blocks nominal autonomy when navigation confidence drops below threshold.",
        mitigates_hazard_ids=("HZ-001",),
        evidence_ids=("EV-001",),
    )
    mitigation = Mitigation(
        mitigation_id="MIT-001",
        hazard_id="HZ-001",
        control_id="CTRL-001",
        description="Force safe-hold and require operator review under degraded navigation.",
        evidence_ids=("EV-001",),
    )
    claim = AssuranceClaim(
        claim_id="CLM-001",
        statement="The autonomy function remains bounded during navigation degradation.",
        argument="A runtime safety gate prevents nominal operation without trusted navigation.",
        evidence_ids=("EV-001",),
        verification_criterion_ids=("VC-001",),
        verification_result=VerificationResult.PASS,
    )

    return AssuranceCase(
        case_id="CASE-001",
        title="Navigation Degradation Assurance Case",
        system_name="Reference Autonomy Stack",
        mission_context="Autonomous route execution under degraded navigation conditions.",
        status=AssuranceCaseStatus.READY_FOR_REVIEW,
        claims=(claim,),
        hazards=(hazard,),
        controls=(control,),
        mitigations=(mitigation,),
        evidence=(evidence,),
        verification_criteria=(criterion,),
    )


def test_valid_assurance_case_passes_reference_validation() -> None:
    case = build_valid_case()

    report = case.validate_references()

    assert report.is_valid is True
    assert report.errors == ()
    assert report.warnings == ()
    assert case.ready_for_human_review() is True


def test_assurance_case_builds_indexes_by_identifier() -> None:
    case = build_valid_case()

    assert set(case.claim_index()) == {"CLM-001"}
    assert set(case.hazard_index()) == {"HZ-001"}
    assert set(case.control_index()) == {"CTRL-001"}
    assert set(case.mitigation_index()) == {"MIT-001"}
    assert set(case.evidence_index()) == {"EV-001"}
    assert set(case.verification_criterion_index()) == {"VC-001"}


def test_assurance_case_reports_missing_references() -> None:
    case = AssuranceCase(
        case_id="CASE-002",
        title="Broken Case",
        system_name="Reference Autonomy Stack",
        mission_context="Mission context exists.",
        status=AssuranceCaseStatus.DRAFT,
        claims=(
            AssuranceClaim(
                claim_id="CLM-404",
                statement="A claim points to missing evidence.",
                argument="The reference validation should catch the missing object.",
                evidence_ids=("EV-MISSING",),
            ),
        ),
    )

    report = case.validate_references()

    assert report.is_valid is False
    assert report.errors == (
        "Artifact 'CLM-404' references missing evidence 'EV-MISSING'.",
    )


def test_ready_for_review_case_with_errors_is_blocked() -> None:
    case = AssuranceCase(
        case_id="CASE-003",
        title="Blocked Review Case",
        system_name="Reference Autonomy Stack",
        mission_context="Mission context exists.",
        status=AssuranceCaseStatus.READY_FOR_REVIEW,
        claims=(
            AssuranceClaim(
                claim_id="CLM-404",
                statement="A claim points to missing evidence.",
                argument="The reference validation should catch the missing object.",
                evidence_ids=("EV-MISSING",),
            ),
        ),
    )

    report = case.validate_references()

    assert report.is_valid is False
    assert "Artifact 'CLM-404' references missing evidence 'EV-MISSING'." in report.errors
    assert "Case cannot be ready for review while validation errors exist." in report.errors
    assert case.ready_for_human_review() is False


def test_severe_hazard_without_control_is_unresolved() -> None:
    case = AssuranceCase(
        case_id="CASE-004",
        title="Unresolved Hazard Case",
        system_name="Reference Autonomy Stack",
        mission_context="Mission context exists.",
        claims=(
            AssuranceClaim(
                claim_id="CLM-001",
                statement="A top-level claim exists.",
                argument="The case has at least one claim.",
            ),
        ),
        hazards=(
            Hazard(
                hazard_id="HZ-CRIT",
                title="Critical autonomy hazard",
                description="Critical hazard lacks a control path.",
                severity=HazardSeverity.CRITICAL,
            ),
        ),
    )

    report = case.validate_references()

    assert case.unresolved_hazard_ids() == ("HZ-CRIT",)
    assert (
        "Hazard 'HZ-CRIT' is critical and requires at least one control or mitigation."
        in report.errors
    )


def test_minor_hazard_without_control_is_allowed_for_later_refinement() -> None:
    case = AssuranceCase(
        case_id="CASE-005",
        title="Minor Hazard Draft",
        system_name="Reference Autonomy Stack",
        mission_context="Mission context exists.",
        claims=(
            AssuranceClaim(
                claim_id="CLM-001",
                statement="A top-level claim exists.",
                argument="The case has at least one claim.",
            ),
        ),
        hazards=(
            Hazard(
                hazard_id="HZ-MINOR",
                title="Minor hazard",
                description="Minor hazard may be accepted without explicit mitigation in draft.",
                severity=HazardSeverity.MINOR,
            ),
        ),
    )

    report = case.validate_references()

    assert case.unresolved_hazard_ids() == ()
    assert all("HZ-MINOR" not in error for error in report.errors)


def test_unsupported_claims_are_reported_as_warnings_not_errors() -> None:
    case = AssuranceCase(
        case_id="CASE-006",
        title="Unsupported Claim Draft",
        system_name="Reference Autonomy Stack",
        mission_context="Mission context exists.",
        claims=(
            AssuranceClaim(
                claim_id="CLM-UNSUPPORTED",
                statement="A claim currently has no supporting path.",
                argument="The model should identify unsupported claims.",
            ),
        ),
    )

    report = case.validate_references()

    assert report.is_valid is True
    assert case.unsupported_claim_ids() == ("CLM-UNSUPPORTED",)
    assert report.warnings == ("Claim 'CLM-UNSUPPORTED' has no support path.",)


def test_stale_or_invalid_evidence_is_reported_as_warning() -> None:
    case = AssuranceCase(
        case_id="CASE-007",
        title="Stale Evidence Draft",
        system_name="Reference Autonomy Stack",
        mission_context="Mission context exists.",
        claims=(
            AssuranceClaim(
                claim_id="CLM-001",
                statement="A claim references stale evidence.",
                argument="Evidence status should remain visible.",
                evidence_ids=("EV-STALE",),
            ),
        ),
        evidence=(
            EvidenceLink(
                evidence_id="EV-STALE",
                description="Old scenario result.",
                source="run-bundles/old.json",
                status=EvidenceStatus.STALE,
            ),
        ),
    )

    report = case.validate_references()

    assert report.is_valid is True
    assert report.warnings == ("Evidence 'EV-STALE' is referenced with status 'stale'.",)


def test_assurance_case_rejects_blank_required_fields() -> None:
    with pytest.raises(AssuranceModelError, match="case_id must not be blank"):
        AssuranceCase(
            case_id=" ",
            title="Valid title",
            system_name="Valid system",
            mission_context="Valid context",
        )


def test_model_rejects_duplicate_identifier_lists() -> None:
    with pytest.raises(AssuranceModelError, match="evidence_ids must not contain duplicate"):
        AssuranceClaim(
            claim_id="CLM-DUP",
            statement="Claim with duplicate evidence identifiers.",
            argument="Duplicates should be rejected at construction time.",
            evidence_ids=("EV-001", "EV-001"),
        )


def test_case_reports_global_duplicate_artifact_identifiers() -> None:
    case = AssuranceCase(
        case_id="CASE-008",
        title="Duplicate Artifact Case",
        system_name="Reference Autonomy Stack",
        mission_context="Mission context exists.",
        claims=(
            AssuranceClaim(
                claim_id="DUP-001",
                statement="Claim with duplicate global identifier.",
                argument="Global identifiers should remain unique.",
            ),
        ),
        evidence=(
            EvidenceLink(
                evidence_id="DUP-001",
                description="Evidence with duplicate global identifier.",
                source="run-bundles/evidence.json",
            ),
        ),
    )

    report = case.validate_references()

    assert "Artifact identifier 'DUP-001' is duplicated." in report.errors
