"""Federal-style evaluation profile domain records.

This module maps completed prototype capability IDs, artifacts, and evidence
bundles to review concerns that are recognizable in federal, IC, DoD, test and
evaluation, trusted-autonomy, and assurance-case contexts.

The profile is an alignment aid only. It does not claim certification, authority
to operate, deployment approval, official endorsement, procurement acceptance,
or agency acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable federal-evaluation identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if normalized != value:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    """Validate and return nonblank federal-evaluation text."""

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


class FederalReviewConcern(RuntimeStrEnum):
    """Review concerns a serious autonomy assurance prototype should address."""

    MISSION_TRACEABILITY = "mission_traceability"
    REQUIREMENT_TO_EVIDENCE = "requirement_to_evidence"
    HAZARD_CONTROL_CLOSURE = "hazard_control_closure"
    BOUNDED_RUNTIME_ACTION = "bounded_runtime_action"
    TELEMETRY_REPLAYABILITY = "telemetry_replayability"
    HUMAN_AUTHORITY = "human_authority"
    MONITORING_AND_REVALIDATION = "monitoring_and_revalidation"
    PROVENANCE_AND_INTEGRITY = "provenance_and_integrity"
    EXPORTABILITY = "exportability"
    PUBLIC_CLAIM_DISCIPLINE = "public_claim_discpline"

    def is_core_t_and_e_concern(self) -> bool:
        """Return whether this concern is central to test/evaluation review."""

        return self in {
            FederalReviewConcern.MISSION_TRACEABILITY,
            FederalReviewConcern.REQUIREMENT_TO_EVIDENCE,
            FederalReviewConcern.HAZARD_CONTROL_CLOSURE,
            FederalReviewConcern.BOUNDED_RUNTIME_ACTION,
            FederalReviewConcern.TELEMETRY_REPLAYABILITY,
        }


class EvaluationEvidenceExpectation(RuntimeStrEnum):
    """How strongly evidence is expected for a review concern."""

    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"

    def blocks_when_missing(self) -> bool:
        """Return whether missing evidence blocks the profile."""

        return self is EvaluationEvidenceExpectation.REQUIRED


class EvaluationAlignmentStatus(RuntimeStrEnum):
    """Alignment status for a mapped review concern."""

    SATISFIED = "satisfied"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    NOT_ASSESSED = "not_assessed"

    def supports_acceptance(self) -> bool:
        """Return whether the concern can support profile acceptance."""

        return self is EvaluationAlignmentStatus.SATISFIED

    def blocks_acceptance(self) -> bool:
        """Return whether the concern blocks profile acceptance."""

        return self in {
            EvaluationAlignmentStatus.BLOCKED,
            EvaluationAlignmentStatus.NOT_ASSESSED,
        }


@dataclass(frozen=True, slots=True)
class FederalEvaluationConcernMapping:
    """Mapping from one review concern to capabilities, artifacts, and evidence."""

    mapping_id: str
    concern: FederalReviewConcern
    status: EvaluationAlignmentStatus
    evidence_expectation: EvaluationEvidenceExpectation
    capability_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    evidence_bundle_ids: tuple[str, ...]
    reviewer_question: str
    rationale: str
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate federal evaluation concern mapping fields."""

        object.__setattr__(
            self,
            "mapping_id",
            _require_identifier(self.mapping_id, "mapping_id"),
        )
        object.__setattr__(
            self,
            "capability_ids",
            _normalize_identifier_tuple(self.capability_ids, "capability_ids"),
        )
        object.__setattr__(
            self,
            "artifact_ids",
            _normalize_identifier_tuple(self.artifact_ids, "artifact_ids"),
        )
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        object.__setattr__(
            self,
            "reviewer_question",
            _require_text(self.reviewer_question, "reviewer_question"),
        )
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        object.__setattr__(self, "notes", _normalize_text_tuple(self.notes, "notes"))
        if not self.capability_ids:
            raise ContractValueError("federal concern mappings require capability_ids.")
        if not self.artifact_ids:
            raise ContractValueError("federal concern mappings require artifact_ids.")
        if (
            self.evidence_expectation.blocks_when_missing()
            and not self.evidence_bundle_ids
        ):
            raise ContractValueError(
                "required federal concern mappings require evidence_bundle_ids."
            )

    def missing_capability_ids(
        self,
        completed_capability_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Return required capability IDs that are not completed."""

        completed = set(completed_capability_ids)
        return tuple(
            capability_id
            for capability_id in self.capability_ids
            if capability_id not in completed
        )

    def missing_artifact_ids(
        self,
        available_artifact_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Return required artifact IDs that are not available."""

        available = set(available_artifact_ids)
        return tuple(
            artifact_id for artifact_id in self.artifact_ids if artifact_id not in available
        )

    def missing_evidence_bundle_ids(
        self,
        available_evidence_bundle_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Return required evidence bundle IDs that are not available."""

        if not self.evidence_expectation.blocks_when_missing():
            return ()
        available = set(available_evidence_bundle_ids)
        return tuple(
            bundle_id for bundle_id in self.evidence_bundle_ids if bundle_id not in available
        )

    def is_satisfied_by(
        self,
        *,
        completed_capability_ids: tuple[str, ...],
        available_artifact_ids: tuple[str, ...],
        available_evidence_bundle_ids: tuple[str, ...],
    ) -> bool:
        """Return whether this concern is fully satisfied by available records."""

        return (
            self.status.supports_acceptance()
            and not self.missing_capability_ids(completed_capability_ids)
            and not self.missing_artifact_ids(available_artifact_ids)
            and not self.missing_evidence_bundle_ids(available_evidence_bundle_ids)
        )


@dataclass(frozen=True, slots=True)
class FederalEvaluationProfile:
    """Profile mapping prototype evidence to federal-style review concerns."""

    profile_id: str
    case_id: str
    title: str
    created_at_utc: str
    concern_mappings: tuple[FederalEvaluationConcernMapping, ...]
    completed_capability_ids: tuple[str, ...]
    available_artifact_ids: tuple[str, ...]
    available_evidence_bundle_ids: tuple[str, ...]
    audience_label: str = "federal-technical-evaluation"
    notes: tuple[str, ...] = field(default_factory=tuple)
    disclaimer: str = (
        "Local prototype evaluation profile only; not a certification, "
        "authority-to-operate decision, deployment approval, official endorsement, "
        "procurement acceptance, or agency acceptance."
    )

    def __post_init__(self) -> None:
        """Validate federal evaluation profile fields."""

        object.__setattr__(
            self,
            "profile_id",
            _require_identifier(self.profile_id, "profile_id"),
        )
        object.__setattr__(self, "case_id", _require_identifier(self.case_id, "case_id"))
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        _parse_utc_timestamp(self.created_at_utc, "created_at_utc")
        object.__setattr__(
            self,
            "completed_capability_ids",
            _normalize_identifier_tuple(
                self.completed_capability_ids,
                "completed_capability_ids",
            ),
        )
        object.__setattr__(
            self,
            "available_artifact_ids",
            _normalize_identifier_tuple(self.available_artifact_ids, "available_artifact_ids"),
        )
        object.__setattr__(
            self,
            "available_evidence_bundle_ids",
            _normalize_identifier_tuple(
                self.available_evidence_bundle_ids,
                "available_evidence_bundle_ids",
            ),
        )
        object.__setattr__(
            self,
            "audience_label",
            _require_identifier(self.audience_label, "audience_label"),
        )
        object.__setattr__(self, "notes", _normalize_text_tuple(self.notes, "notes"))
        object.__setattr__(self, "disclaimer", _require_text(self.disclaimer, "disclaimer"))
        if not self.concern_mappings:
            raise ContractValueError("federal evaluation profiles require concern_mappings.")
        _reject_duplicate_ids(
            tuple(mapping.mapping_id for mapping in self.concern_mappings),
            "federal concern mapping IDs",
        )

    def mapping_ids(self) -> tuple[str, ...]:
        """Return mapping IDs in profile order."""

        return tuple(mapping.mapping_id for mapping in self.concern_mappings)

    def concern_values(self) -> tuple[str, ...]:
        """Return unique concern values in first-seen order."""

        return tuple(
            dict.fromkeys(mapping.concern.value for mapping in self.concern_mappings)
        )

    def core_t_and_e_concern_values(self) -> tuple[str, ...]:
        """Return unique core test/evaluation concern values."""

        return tuple(
            dict.fromkeys(
                mapping.concern.value
                for mapping in self.concern_mappings
                if mapping.concern.is_core_t_and_e_concern()
            )
        )

    def satisfied_mapping_ids(self) -> tuple[str, ...]:
        """Return mapping IDs satisfied by available profile records."""

        return tuple(
            mapping.mapping_id
            for mapping in self.concern_mappings
            if mapping.is_satisfied_by(
                completed_capability_ids=self.completed_capability_ids,
                available_artifact_ids=self.available_artifact_ids,
                available_evidence_bundle_ids=self.available_evidence_bundle_ids,
            )
        )

    def blocked_mapping_ids(self) -> tuple[str, ...]:
        """Return mapping IDs that block profile acceptance."""

        return tuple(
            mapping.mapping_id
            for mapping in self.concern_mappings
            if mapping.status.blocks_acceptance()
            or mapping.missing_capability_ids(self.completed_capability_ids)
            or mapping.missing_artifact_ids(self.available_artifact_ids)
            or mapping.missing_evidence_bundle_ids(self.available_evidence_bundle_ids)
        )

    def missing_required_capability_ids(self) -> tuple[str, ...]:
        """Return unique capability IDs missing from required mappings."""

        missing: list[str] = []
        for mapping in self.concern_mappings:
            missing.extend(mapping.missing_capability_ids(self.completed_capability_ids))
        return tuple(dict.fromkeys(missing))

    def missing_required_artifact_ids(self) -> tuple[str, ...]:
        """Return unique artifact IDs missing from required mappings."""

        missing: list[str] = []
        for mapping in self.concern_mappings:
            missing.extend(mapping.missing_artifact_ids(self.available_artifact_ids))
        return tuple(dict.fromkeys(missing))

    def missing_required_evidence_bundle_ids(self) -> tuple[str, ...]:
        """Return unique evidence bundle IDs missing from required mappings."""

        missing: list[str] = []
        for mapping in self.concern_mappings:
            missing.extend(
                mapping.missing_evidence_bundle_ids(self.available_evidence_bundle_ids)
            )
        return tuple(dict.fromkeys(missing))

    def disclaimer_is_bounded(self) -> bool:
        """Return whether the disclaimer clearly avoids official-acceptance claims."""

        disclaimer_lower = self.disclaimer.lower()
        required_terms = (
            "prototype",
            "not",
            "certification",
            "authority-to-operate",
            "agency acceptance",
        )
        return all(term in disclaimer_lower for term in required_terms)

    def can_support_evaluation_package(self) -> bool:
        """Return whether this profile can support a bounded evaluation package."""

        return not self.blocked_mapping_ids() and self.disclaimer_is_bounded()

    def summary(self) -> str:
        """Return a deterministic federal evaluation profile summary."""

        return (
            f"federal-evaluation-profile: {self.profile_id} "
            f"({len(self.concern_mappings)} concern mapping(s), "
            f"{len(self.satisfied_mapping_ids())} satisfied, "
            f"{len(self.blocked_mapping_ids())} blocked, "
            f"{len(self.core_t_and_e_concern_values())} core T&E concern(s))"
        )


def _reject_duplicate_ids(values: tuple[str, ...], field_name: str) -> None:
    """Reject duplicate identifier tuples."""

    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicates.")
