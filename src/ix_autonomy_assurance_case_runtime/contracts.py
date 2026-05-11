"""Core domain contracts for the assurance-case runtime.

The rest of the runtime depends on these values being stable, explicit, and
machine-checkable. They define the shared vocabulary for assurance-case status,
evidence posture, hazard severity, autonomy decisions, authority state,
verification results, and human review disposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

EnumT = TypeVar("EnumT", bound="RuntimeStrEnum")


class ContractValueError(ValueError):
    """Raised when a domain contract receives an unsupported value."""


class RuntimeStrEnum(StrEnum):
    """Base class for strict string enums used by the runtime."""

    @classmethod
    def values(cls) -> tuple[str, ...]:
        """Return the allowed wire values for this contract enum."""

        return tuple(member.value for member in cls)

    @classmethod
    def from_value(cls: type[EnumT], value: str) -> EnumT:
        """Parse a wire value into a contract enum member."""

        try:
            return cls(value)
        except ValueError as exc:
            allowed = ", ".join(cls.values())
            message = f"Unsupported {cls.__name__} value {value!r}; allowed values: {allowed}"
            raise ContractValueError(message) from exc


class AssuranceCaseStatus(RuntimeStrEnum):
    """Lifecycle status for an assurance case."""

    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"

    def is_terminal(self) -> bool:
        """Return whether the status ends active review for this case version."""

        return self in {
            AssuranceCaseStatus.ACCEPTED,
            AssuranceCaseStatus.REJECTED,
            AssuranceCaseStatus.SUPERSEDED,
        }

    def requires_review(self) -> bool:
        """Return whether the case is ready for human review."""

        return self is AssuranceCaseStatus.READY_FOR_REVIEW


class EvidenceStatus(RuntimeStrEnum):
    """Status of evidence attached to a claim, hazard, scenario, or review."""

    MISSING = "missing"
    PROVIDED = "provided"
    ACCEPTED = "accepted"
    STALE = "stale"
    INVALID = "invalid"

    def is_usable(self) -> bool:
        """Return whether this evidence status can support a claim."""

        return self in {EvidenceStatus.PROVIDED, EvidenceStatus.ACCEPTED}


class HazardSeverity(RuntimeStrEnum):
    """Severity level for hazards in an autonomy assurance case."""

    NEGLIGIBLE = "negligible"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
    CATASTROPHIC = "catastrophic"

    @property
    def rank(self) -> int:
        """Return an ordinal severity rank where larger values are more severe."""

        ranks = {
            HazardSeverity.NEGLIGIBLE: 1,
            HazardSeverity.MINOR: 2,
            HazardSeverity.MAJOR: 3,
            HazardSeverity.CRITICAL: 4,
            HazardSeverity.CATASTROPHIC: 5,
        }
        return ranks[self]

    def requires_mitigation(self) -> bool:
        """Return whether this hazard severity must have an explicit mitigation."""

        return self.rank >= HazardSeverity.MAJOR.rank


class AutonomyDecisionType(RuntimeStrEnum):
    """Decision type emitted by the runtime assurance gate."""

    ALLOW = "allow"
    CLAMP = "clamp"
    DEFER = "defer"
    VETO = "veto"
    SAFE_HOLD = "safe_hold"

    def permits_nominal_execution(self) -> bool:
        """Return whether the autonomy function may proceed without restriction."""

        return self is AutonomyDecisionType.ALLOW

    def is_restrictive(self) -> bool:
        """Return whether the decision restricts or blocks autonomy behavior."""

        return self in {
            AutonomyDecisionType.CLAMP,
            AutonomyDecisionType.DEFER,
            AutonomyDecisionType.VETO,
            AutonomyDecisionType.SAFE_HOLD,
        }


class RuntimeAuthorityState(RuntimeStrEnum):
    """Authority state governing whether autonomy may act without intervention."""

    AUTONOMOUS_ALLOWED = "autonomous_allowed"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    HUMAN_OVERRIDE_ACTIVE = "human_override_active"
    DENIED = "denied"
    EMERGENCY_SAFE_HOLD = "emergency_safe_hold"

    def permits_autonomous_execution(self) -> bool:
        """Return whether autonomy can execute without additional approval."""

        return self is RuntimeAuthorityState.AUTONOMOUS_ALLOWED

    def blocks_autonomous_execution(self) -> bool:
        """Return whether autonomy must not continue nominal execution."""

        return self in {
            RuntimeAuthorityState.HUMAN_OVERRIDE_ACTIVE,
            RuntimeAuthorityState.DENIED,
            RuntimeAuthorityState.EMERGENCY_SAFE_HOLD,
        }


class VerificationResult(RuntimeStrEnum):
    """Result of checking a scenario, evidence bundle, trace, or assurance claim."""

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    NOT_RUN = "not_run"

    def is_success(self) -> bool:
        """Return whether the verification result supports acceptance."""

        return self is VerificationResult.PASS

    def requires_follow_up(self) -> bool:
        """Return whether the verification result requires more work."""

        return self in {
            VerificationResult.FAIL,
            VerificationResult.INCONCLUSIVE,
            VerificationResult.NOT_RUN,
        }


class ReviewDisposition(RuntimeStrEnum):
    """Human review disposition for an assurance case or runtime decision."""

    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    REJECTED = "rejected"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    ESCALATED = "escalated"

    def allows_acceptance(self) -> bool:
        """Return whether the review disposition allows conditional or full acceptance."""

        return self in {
            ReviewDisposition.APPROVED,
            ReviewDisposition.APPROVED_WITH_CONDITIONS,
        }


@dataclass(frozen=True, slots=True)
class ContractDefinition:
    """Machine-readable definition of a runtime domain contract."""

    name: str
    description: str
    allowed_values: tuple[str, ...]
    default_value: str

    def __post_init__(self) -> None:
        """Validate that each contract definition is internally consistent."""

        if not self.name.strip():
            raise ContractValueError("Contract name must not be blank.")
        if not self.description.strip():
            raise ContractValueError(f"Contract {self.name!r} must have a description.")
        if not self.allowed_values:
            raise ContractValueError(f"Contract {self.name!r} must define allowed values.")
        if self.default_value not in self.allowed_values:
            message = (
                f"Default value {self.default_value!r} is not allowed for contract {self.name!r}."
            )
            raise ContractValueError(message)


def build_contract_catalog() -> dict[str, ContractDefinition]:
    """Build the canonical catalog of domain contracts used by the runtime."""

    return {
        "assurance_case_status": ContractDefinition(
            name="assurance_case_status",
            description="Lifecycle state for a versioned assurance case.",
            allowed_values=AssuranceCaseStatus.values(),
            default_value=AssuranceCaseStatus.DRAFT.value,
        ),
        "evidence_status": ContractDefinition(
            name="evidence_status",
            description="Usability state for evidence attached to assurance artifacts.",
            allowed_values=EvidenceStatus.values(),
            default_value=EvidenceStatus.MISSING.value,
        ),
        "hazard_severity": ContractDefinition(
            name="hazard_severity",
            description="Ordinal severity level for autonomy hazards.",
            allowed_values=HazardSeverity.values(),
            default_value=HazardSeverity.NEGLIGIBLE.value,
        ),
        "autonomy_decision_type": ContractDefinition(
            name="autonomy_decision_type",
            description="Runtime assurance decision emitted for autonomous behavior.",
            allowed_values=AutonomyDecisionType.values(),
            default_value=AutonomyDecisionType.DEFER.value,
        ),
        "runtime_authority_state": ContractDefinition(
            name="runtime_authority_state",
            description="Authority state controlling whether autonomy may execute.",
            allowed_values=RuntimeAuthorityState.values(),
            default_value=RuntimeAuthorityState.HUMAN_APPROVAL_REQUIRED.value,
        ),
        "verification_result": ContractDefinition(
            name="verification_result",
            description="Outcome of a verification check against runtime evidence.",
            allowed_values=VerificationResult.values(),
            default_value=VerificationResult.NOT_RUN.value,
        ),
        "review_disposition": ContractDefinition(
            name="review_disposition",
            description="Human review disposition for an assurance artifact.",
            allowed_values=ReviewDisposition.values(),
            default_value=ReviewDisposition.NEEDS_MORE_EVIDENCE.value,
        ),
    }
