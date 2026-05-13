"""Claim guardrail domain records.

The serious prototype target needs explicit controls over what the project may
claim publicly or inside review packages. These records model evidence-backed
claim statements, audience/risk posture, prohibited phrase rules, review status,
and release packages so the repo can keep prototype language bounded.

This module is local prototype infrastructure only. It does not claim
certification, authority to operate, deployment approval, official endorsement,
or agency acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable claim-guardrail identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if normalized != value:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    """Validate and return nonblank claim-guardrail text."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    return normalized


def _normalize_identifier_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    """Validate identifier tuples and reject duplicates."""

    normalized = tuple(_require_identifier(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicate identifiers.")
    return normalized


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    """Validate text tuples and reject duplicates."""

    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")
    return normalized


def _parse_utc_timestamp(value: str, field_name: str) -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC."""

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractValueError(f"{field_name} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise ContractValueError(f"{field_name} must include a timezone.")
    return parsed.astimezone(UTC)


class ClaimAudience(RuntimeStrEnum):
    """Intended audience for a claim package."""

    LOCAL_DEVELOPMENT = "local_development"
    OPEN_SOURCE_README = "open_source_readme"
    TECHNICAL_REVIEW = "technical_review"
    FEDERAL_EVALUATION = "federal_evaluation"
    INTERNAL_ASSURANCE = "internal_assurance"

    def requires_strict_language_review(self) -> bool:
        """Return whether the audience requires strict public-claim review."""

        return self in {
            ClaimAudience.OPEN_SOURCE_README,
            ClaimAudience.TECHNICAL_REVIEW,
            ClaimAudience.FEDERAL_EVALUATION,
        }


class ClaimStatementType(RuntimeStrEnum):
    """Type of claim being made."""

    CAPABILITY = "capability"
    LIMITATION = "limitation"
    MATURITY = "maturity"
    EVIDENCE = "evidence"
    SAFETY_BOUNDARY = "safety_boundary"
    NON_ENDORSEMENT = "non_endorsement"

    def requires_evidence(self) -> bool:
        """Return whether this claim type requires evidence references."""

        return self is not ClaimStatementType.NON_ENDORSEMENT


class ClaimRiskLevel(RuntimeStrEnum):
    """Risk level for a claim statement."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    PROHIBITED = "prohibited"

    def blocks_release(self) -> bool:
        """Return whether this risk level blocks release."""

        return self is ClaimRiskLevel.PROHIBITED

    def requires_reviewer_signoff(self) -> bool:
        """Return whether this risk level requires explicit reviewer signoff."""

        return self in {ClaimRiskLevel.MODERATE, ClaimRiskLevel.HIGH}


class ClaimEvidenceStrength(RuntimeStrEnum):
    """Evidence strength attached to a claim statement."""

    NONE = "none"
    DESCRIBED = "described"
    TESTED = "tested"
    TRACE_CLOSED = "trace_closed"
    EXPORTED = "exported"

    @property
    def rank(self) -> int:
        """Return an ordinal strength rank."""

        ranks = {
            ClaimEvidenceStrength.NONE: 0,
            ClaimEvidenceStrength.DESCRIBED: 1,
            ClaimEvidenceStrength.TESTED: 2,
            ClaimEvidenceStrength.TRACE_CLOSED: 3,
            ClaimEvidenceStrength.EXPORTED: 4,
        }
        return ranks[self]

    def supports_public_claim(self) -> bool:
        """Return whether the evidence strength can support a public claim."""

        return self.rank >= ClaimEvidenceStrength.TESTED.rank


class ClaimReviewStatus(RuntimeStrEnum):
    """Review state for a claim statement or package."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    APPROVED_WITH_LIMITATIONS = "approved_with_limitations"
    REJECTED = "rejected"

    def supports_release(self) -> bool:
        """Return whether this review state can support release."""

        return self in {
            ClaimReviewStatus.APPROVED,
            ClaimReviewStatus.APPROVED_WITH_LIMITATIONS,
        }

    def requires_limitations(self) -> bool:
        """Return whether the status requires explicit limitation text."""

        return self is ClaimReviewStatus.APPROVED_WITH_LIMITATIONS


@dataclass(frozen=True, slots=True)
class ClaimEvidenceReference:
    """Evidence reference supporting a claim statement."""

    reference_id: str
    evidence_bundle_id: str
    artifact_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]
    rationale: str = "Evidence supports the bounded claim statement."

    def __post_init__(self) -> None:
        """Validate claim evidence reference fields."""

        object.__setattr__(
            self,
            "reference_id",
            _require_identifier(self.reference_id, "reference_id"),
        )
        object.__setattr__(
            self,
            "evidence_bundle_id",
            _require_identifier(self.evidence_bundle_id, "evidence_bundle_id"),
        )
        object.__setattr__(
            self,
            "artifact_ids",
            _normalize_identifier_tuple(self.artifact_ids, "artifact_ids"),
        )
        object.__setattr__(
            self,
            "capability_ids",
            _normalize_identifier_tuple(self.capability_ids, "capability_ids"),
        )
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        if not self.artifact_ids:
            raise ContractValueError("claim evidence references require artifact_ids.")
        if not self.capability_ids:
            raise ContractValueError("claim evidence references require capability_ids.")


@dataclass(frozen=True, slots=True)
class ClaimProhibitedPhraseRule:
    """Phrase rule used to block or warn about overclaim language."""

    rule_id: str
    phrase: str
    rationale: str
    blocks_release: bool = True
    replacement_guidance: str = "Replace with bounded prototype language."
    allowed_context_markers: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate prohibited phrase rule fields."""

        object.__setattr__(self, "rule_id", _require_identifier(self.rule_id, "rule_id"))
        object.__setattr__(self, "phrase", _require_text(self.phrase, "phrase"))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        object.__setattr__(
            self,
            "replacement_guidance",
            _require_text(self.replacement_guidance, "replacement_guidance"),
        )
        object.__setattr__(
            self,
            "allowed_context_markers",
            _normalize_text_tuple(self.allowed_context_markers, "allowed_context_markers"),
        )

    def matches(self, text: str) -> bool:
        """Return whether this rule phrase appears in text."""

        return self.phrase.lower() in text.lower()

    def is_allowed_context(self, text: str) -> bool:
        """Return whether text includes an allowed context marker."""

        lowered = text.lower()
        return any(marker.lower() in lowered for marker in self.allowed_context_markers)


@dataclass(frozen=True, slots=True)
class EvidenceBackedClaim:
    """One bounded claim statement with evidence and review posture."""

    claim_id: str
    statement_type: ClaimStatementType
    risk_level: ClaimRiskLevel
    evidence_strength: ClaimEvidenceStrength
    review_status: ClaimReviewStatus
    text: str
    evidence_reference_ids: tuple[str, ...]
    limitation_text: str | None = None
    reviewer_ids: tuple[str, ...] = field(default_factory=tuple)
    related_capability_ids: tuple[str, ...] = field(default_factory=tuple)
    related_artifact_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate evidence-backed claim fields."""

        object.__setattr__(self, "claim_id", _require_identifier(self.claim_id, "claim_id"))
        object.__setattr__(self, "text", _require_text(self.text, "text"))
        object.__setattr__(
            self,
            "evidence_reference_ids",
            _normalize_identifier_tuple(
                self.evidence_reference_ids,
                "evidence_reference_ids",
            ),
        )
        object.__setattr__(
            self,
            "reviewer_ids",
            _normalize_identifier_tuple(self.reviewer_ids, "reviewer_ids"),
        )
        object.__setattr__(
            self,
            "related_capability_ids",
            _normalize_identifier_tuple(
                self.related_capability_ids,
                "related_capability_ids",
            ),
        )
        object.__setattr__(
            self,
            "related_artifact_ids",
            _normalize_identifier_tuple(self.related_artifact_ids, "related_artifact_ids"),
        )
        if self.limitation_text is not None:
            object.__setattr__(
                self,
                "limitation_text",
                _require_text(self.limitation_text, "limitation_text"),
            )
        if self.statement_type.requires_evidence() and not self.evidence_reference_ids:
            raise ContractValueError("evidence-backed claims require evidence_reference_ids.")
        if self.risk_level.requires_reviewer_signoff() and not self.reviewer_ids:
            raise ContractValueError("moderate or high risk claims require reviewer_ids.")
        if self.review_status.requires_limitations() and self.limitation_text is None:
            raise ContractValueError(
                "approved_with_limitations claims require limitation_text."
            )
        if self.evidence_strength is ClaimEvidenceStrength.NONE and self.evidence_reference_ids:
            raise ContractValueError(
                "claims with evidence references cannot use evidence strength none."
            )

    def can_be_released(self) -> bool:
        """Return whether the claim is structurally releaseable."""

        return (
            self.review_status.supports_release()
            and not self.risk_level.blocks_release()
            and (
                not self.statement_type.requires_evidence()
                or self.evidence_strength.supports_public_claim()
            )
        )

    def is_limitation_claim(self) -> bool:
        """Return whether this claim is a limitation or non-endorsement statement."""

        return self.statement_type in {
            ClaimStatementType.LIMITATION,
            ClaimStatementType.NON_ENDORSEMENT,
        }


@dataclass(frozen=True, slots=True)
class ClaimReleasePackage:
    """Collection of claims prepared for a specific audience."""

    package_id: str
    audience: ClaimAudience
    review_status: ClaimReviewStatus
    created_at_utc: str
    claims: tuple[EvidenceBackedClaim, ...]
    evidence_references: tuple[ClaimEvidenceReference, ...]
    prohibited_phrase_rules: tuple[ClaimProhibitedPhraseRule, ...]
    release_notes: tuple[str, ...] = field(default_factory=tuple)
    disclaimer: str = (
        "Local prototype claim package only; not a certification, authority-to-operate "
        "decision, deployment approval, official endorsement, or agency acceptance."
    )

    def __post_init__(self) -> None:
        """Validate claim release package fields."""

        object.__setattr__(
            self,
            "package_id",
            _require_identifier(self.package_id, "package_id"),
        )
        _parse_utc_timestamp(self.created_at_utc, "created_at_utc")
        object.__setattr__(
            self,
            "release_notes",
            _normalize_text_tuple(self.release_notes, "release_notes"),
        )
        object.__setattr__(self, "disclaimer", _require_text(self.disclaimer, "disclaimer"))
        if not self.claims:
            raise ContractValueError("claim release packages require claims.")
        if not self.evidence_references:
            raise ContractValueError("claim release packages require evidence_references.")
        if not self.prohibited_phrase_rules:
            raise ContractValueError("claim release packages require prohibited_phrase_rules.")
        _reject_duplicate_ids(
            tuple(claim.claim_id for claim in self.claims),
            "claim IDs",
        )
        _reject_duplicate_ids(
            tuple(reference.reference_id for reference in self.evidence_references),
            "claim evidence reference IDs",
        )
        _reject_duplicate_ids(
            tuple(rule.rule_id for rule in self.prohibited_phrase_rules),
            "claim prohibited phrase rule IDs",
        )
        if self.review_status.requires_limitations() and not self.limitation_claim_ids():
            raise ContractValueError(
                "approved_with_limitations claim packages require limitation claims."
            )

    def claim_ids(self) -> tuple[str, ...]:
        """Return claim IDs in package order."""

        return tuple(claim.claim_id for claim in self.claims)

    def releasable_claim_ids(self) -> tuple[str, ...]:
        """Return claim IDs that are structurally releaseable."""

        return tuple(claim.claim_id for claim in self.claims if claim.can_be_released())

    def blocked_claim_ids(self) -> tuple[str, ...]:
        """Return claim IDs that are not structurally releaseable."""

        return tuple(claim.claim_id for claim in self.claims if not claim.can_be_released())

    def limitation_claim_ids(self) -> tuple[str, ...]:
        """Return claim IDs that state limitations or non-endorsement posture."""

        return tuple(claim.claim_id for claim in self.claims if claim.is_limitation_claim())

    def required_evidence_reference_ids(self) -> tuple[str, ...]:
        """Return unique claim evidence reference IDs required by claims."""

        reference_ids: list[str] = []
        for claim in self.claims:
            reference_ids.extend(claim.evidence_reference_ids)
        return tuple(dict.fromkeys(reference_ids))

    def required_evidence_bundle_ids(self) -> tuple[str, ...]:
        """Return unique evidence bundle IDs referenced by this package."""

        return tuple(
            dict.fromkeys(
                reference.evidence_bundle_id for reference in self.evidence_references
            )
        )

    def prohibited_rule_ids_for_text(self, text: str) -> tuple[str, ...]:
        """Return prohibited phrase rule IDs that match text outside allowed context."""

        return tuple(
            rule.rule_id
            for rule in self.prohibited_phrase_rules
            if rule.matches(text) and not rule.is_allowed_context(text)
        )

    def can_release(self) -> bool:
        """Return whether the claim package is structurally releaseable."""

        return (
            self.review_status.supports_release()
            and not self.blocked_claim_ids()
            and not any(self.prohibited_rule_ids_for_text(claim.text) for claim in self.claims)
            and (
                not self.audience.requires_strict_language_review()
                or bool(self.limitation_claim_ids())
            )
        )


def _reject_duplicate_ids(values: tuple[str, ...], field_name: str) -> None:
    """Reject duplicate identifier tuples."""

    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicates.")
